"""Stream a fixed-schedule GTFS ZIP into an atomic, versioned SQLite handoff.

This is ingestion, not a journey planner or a complete GTFS conformance validator.
IDs remain source strings. Times are service-day seconds, never Unix timestamps.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from zipfile import ZipFile, BadZipFile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = 1
WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
REQUIRED = {
    'agency': ('agency_name', 'agency_url', 'agency_timezone'),
    'stops': ('stop_id',),
    'routes': ('route_id', 'route_type'),
    'trips': ('route_id', 'service_id', 'trip_id'),
    'stop_times': ('trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'),
    'calendar': ('service_id', *WEEKDAYS, 'start_date', 'end_date'),
    'calendar_dates': ('service_id', 'date', 'exception_type'),
    'shapes': ('shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence'),
    'feed_info': ('feed_publisher_name', 'feed_publisher_url', 'feed_lang'),
}
DEFAULTS = {
    'agency': {'agency_id': ''},
    'stops': {'stop_name': '', 'stop_lat': '', 'stop_lon': '', 'location_type': '', 'parent_station': ''},
    'routes': {'agency_id': '', 'route_short_name': '', 'route_long_name': ''},
    'trips': {'shape_id': ''},
    'stop_times': {'pickup_type': '', 'drop_off_type': '', 'timepoint': ''},
}
KEYS = {'agency': ('agency_id',), 'stops': ('stop_id',), 'routes': ('route_id',),
        'trips': ('trip_id',), 'stop_times': ('trip_id', 'stop_sequence'),
        'calendar': ('service_id',), 'calendar_dates': ('service_id', 'date'),
        'shapes': ('shape_id', 'shape_pt_sequence')}


def gtfs_seconds(value: str):
    """Parse GTFS time (including 25:10:00); blanks remain unknown."""
    if value == '':
        return None
    if not re.fullmatch(r'\d{1,3}:[0-5]\d:[0-5]\d', value):
        raise ValueError(f'Invalid GTFS time: {value!r}')
    hour, minute, second = map(int, value.split(':'))
    return hour * 3600 + minute * 60 + second


def _date(value):
    if not re.fullmatch(r'\d{8}', value):
        raise ValueError('GTFS dates must be YYYYMMDD')
    try:
        datetime.strptime(value, '%Y%m%d')
    except ValueError:
        raise ValueError('Invalid GTFS calendar date') from None


def _integer(value):
    if not re.fullmatch(r'\d+', value):
        raise ValueError(f'Expected nonnegative integer: {value!r}')
    return int(value)


def _validate_row(table, row):
    for key in KEYS.get(table, ()):
        if not row[key] and not (table == 'agency' and key == 'agency_id'):
            raise ValueError(f'{table}: empty {key}')
    if table == 'agency':
        for key in REQUIRED[table]:
            if not row[key]:
                raise ValueError(f'agency: empty {key}')
        try:
            ZoneInfo(row['agency_timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Invalid agency_timezone') from None
    elif table == 'stops':
        kind = row['location_type'] or '0'
        if kind not in ('0', '1', '2', '3', '4'):
            raise ValueError('Invalid location_type')
        if kind in ('0', '1', '2') and (not row['stop_name'] or not row['stop_lat'] or not row['stop_lon']):
            raise ValueError('Stop/station/entrance missing name or coordinates')
        for key, bound in (('stop_lat', 90), ('stop_lon', 180)):
            if row[key] and (not math.isfinite(float(row[key])) or abs(float(row[key])) > bound):
                raise ValueError('Invalid stop coordinates')
    elif table == 'routes':
        _integer(row['route_type'])
        if not row['route_short_name'] and not row['route_long_name']:
            raise ValueError('Route missing both names')
    elif table == 'trips':
        if not row['route_id'] or not row['service_id']:
            raise ValueError('Trip missing route or service')
    elif table == 'stop_times':
        row['stop_sequence'] = _integer(row['stop_sequence'])
        if not row['stop_id']:
            raise ValueError('Fixed-schedule stop_times require stop_id; GTFS Flex is unsupported')
        row['arrival_seconds'] = gtfs_seconds(row['arrival_time'])
        row['departure_seconds'] = gtfs_seconds(row['departure_time'])
        arrival, departure = row['arrival_seconds'], row['departure_seconds']
        if (arrival is None) != (departure is None):
            raise ValueError('Arrival and departure must both be present or both absent')
        if arrival is not None and departure < arrival:
            raise ValueError('Departure precedes arrival')
        if row['timepoint'] not in ('', '0', '1'):
            raise ValueError('Invalid timepoint')
        if arrival is None and row['timepoint'] != '0':
            raise ValueError('Missing exact timepoint time')
        for key in ('pickup_type', 'drop_off_type'):
            if row[key] not in ('', '0', '1', '2', '3'):
                raise ValueError(f'Invalid {key}')
    elif table == 'calendar':
        for key in WEEKDAYS:
            if row[key] not in ('0', '1'):
                raise ValueError('Invalid calendar weekday')
        _date(row['start_date'])
        _date(row['end_date'])
        if row['end_date'] < row['start_date']:
            raise ValueError('Calendar end precedes start')
    elif table == 'calendar_dates':
        _date(row['date'])
        if row['exception_type'] not in ('1', '2'):
            raise ValueError('Invalid calendar exception_type')
    elif table == 'shapes':
        row['shape_pt_sequence'] = _integer(row['shape_pt_sequence'])
        for key, bound in (('shape_pt_lat', 90), ('shape_pt_lon', 180)):
            if not math.isfinite(float(row[key])) or abs(float(row[key])) > bound:
                raise ValueError('Invalid shape coordinates')


def _load(conn, archive, table, names):
    filename = table + '.txt'
    if filename not in names:
        headers = list(REQUIRED[table])
        reader = ()
        handle = None
    else:
        handle = io.TextIOWrapper(archive.open(filename), encoding='utf-8-sig', newline='')
        reader = csv.DictReader(handle, strict=True)
        headers = reader.fieldnames or []
        if not set(REQUIRED[table]).issubset(headers):
            handle.close()
            raise ValueError(f'{filename}: missing required columns')
    if len(set(headers)) != len(headers) or any(not re.fullmatch(r'[a-z][a-z0-9_]*', h) for h in headers):
        if handle:
            handle.close()
        raise ValueError(f'{filename}: duplicate or invalid header')
    if table == 'stop_times' and {'arrival_seconds', 'departure_seconds'} & set(headers):
        if handle:
            handle.close()
        raise ValueError('Source conflicts with reserved derived time columns')
    columns = headers + [k for k in DEFAULTS.get(table, {}) if k not in headers]
    if table == 'stop_times':
        columns += ['arrival_seconds', 'departure_seconds']
    integer_columns = {'stop_sequence', 'shape_pt_sequence', 'arrival_seconds', 'departure_seconds'}
    definitions = [f'"{c}" {"INTEGER" if c in integer_columns else "TEXT"}' for c in columns]
    keys = KEYS.get(table)
    if keys:
        definitions.append('PRIMARY KEY (' + ','.join(f'"{k}"' for k in keys) + ')')
    conn.execute(f'CREATE TABLE "{table}" ({",".join(definitions)})')
    sql = f'INSERT INTO "{table}" VALUES ({",".join("?" for _ in columns)})'
    count = 0
    batch = []
    try:
        for count, row in enumerate(reader, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'{filename}: malformed row {count + 1}')
            row = {k: v.strip() for k, v in row.items()}
            for k, default in DEFAULTS.get(table, {}).items():
                row.setdefault(k, default)
            try:
                _validate_row(table, row)
            except (ValueError, OverflowError) as error:
                raise ValueError(f'{filename}: row {count + 1}: {error}') from error
            batch.append(tuple(row[c] for c in columns))
            if len(batch) == 5000:
                conn.executemany(sql, batch)
                batch.clear()
        conn.executemany(sql, batch)
    finally:
        if handle:
            handle.close()
    return count


def _qa(conn, counts):
    checks = {
        'trip references missing route': 'SELECT 1 FROM trips t LEFT JOIN routes r USING(route_id) WHERE r.route_id IS NULL LIMIT 1',
        'stop time references missing trip': 'SELECT 1 FROM stop_times s LEFT JOIN trips t USING(trip_id) WHERE t.trip_id IS NULL LIMIT 1',
        'stop time references missing stop': 'SELECT 1 FROM stop_times s LEFT JOIN stops t USING(stop_id) WHERE t.stop_id IS NULL LIMIT 1',
        'missing parent station': "SELECT 1 FROM stops s LEFT JOIN stops p ON s.parent_station=p.stop_id WHERE s.parent_station<>'' AND p.stop_id IS NULL LIMIT 1",
        'stop time must reference a stop/platform': "SELECT 1 FROM stop_times t JOIN stops s USING(stop_id) WHERE s.location_type NOT IN ('', '0') LIMIT 1",
        'invalid stop parent hierarchy': """SELECT 1 FROM stops s LEFT JOIN stops p ON s.parent_station=p.stop_id
            WHERE (s.location_type='1' AND s.parent_station<>'')
               OR (s.location_type IN ('2','3','4') AND s.parent_station='')
               OR (s.parent_station<>'' AND (
                   s.parent_station=s.stop_id
                   OR (s.location_type IN ('','0','2','3') AND p.location_type<>'1')
                   OR (s.location_type='4' AND p.location_type NOT IN ('','0')))) LIMIT 1""",
        'trip references missing service': 'SELECT 1 FROM trips WHERE service_id NOT IN (SELECT service_id FROM calendar UNION SELECT service_id FROM calendar_dates WHERE exception_type=\'1\') LIMIT 1',
        'trip has fewer than two stop times': 'SELECT 1 FROM trips t LEFT JOIN stop_times s USING(trip_id) GROUP BY t.trip_id HAVING count(s.stop_id)<2 LIMIT 1',
        'first or last stop has unknown time': 'SELECT 1 FROM stop_times s WHERE arrival_seconds IS NULL AND (stop_sequence=(SELECT min(stop_sequence) FROM stop_times WHERE trip_id=s.trip_id) OR stop_sequence=(SELECT max(stop_sequence) FROM stop_times WHERE trip_id=s.trip_id)) LIMIT 1',
        'times decrease along trip': 'SELECT 1 FROM (SELECT arrival_seconds, max(departure_seconds) OVER (PARTITION BY trip_id ORDER BY stop_sequence ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) prior FROM stop_times) WHERE arrival_seconds < prior LIMIT 1',
    }
    if counts['agency'] > 1:
        checks['multiple agencies require explicit identifiers'] = "SELECT 1 FROM agency WHERE agency_id='' UNION ALL SELECT 1 FROM routes WHERE agency_id='' LIMIT 1"
    checks['route references missing agency'] = "SELECT 1 FROM routes r LEFT JOIN agency a USING(agency_id) WHERE r.agency_id<>'' AND a.agency_id IS NULL LIMIT 1"
    checks['trip references missing shape'] = "SELECT 1 FROM trips WHERE shape_id<>'' AND shape_id NOT IN (SELECT shape_id FROM shapes) LIMIT 1"
    for message, sql in checks.items():
        if conn.execute(sql).fetchone():
            raise ValueError('GTFS integrity: ' + message)
    if conn.execute('SELECT count(DISTINCT agency_timezone) FROM agency').fetchone()[0] != 1:
        raise ValueError('Agencies in one feed must share agency_timezone')


def build_gtfs(archive, output, *, source_id='nta_gtfs', source_url=None, max_uncompressed_bytes=4 * 1024 ** 3):
    """Build atomically; old output survives any download/CSV/QA failure.

    Archive extraction is never performed. All core source columns are retained.
    Unknown extension files are listed in metadata, not silently interpreted.
    """
    archive, output = Path(archive), Path(output)
    if archive.resolve() == output.resolve():
        raise ValueError('Output must differ from source archive')
    digest = hashlib.sha256()
    with archive.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=output.name + '.', suffix='.tmp', dir=output.parent)
    os.close(fd)
    temp = Path(name)
    conn = None
    try:
        with ZipFile(archive) as bundle:
            entries = bundle.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)):
                raise ValueError('ZIP contains duplicate members')
            if any('/' in n or '\\' in n or n in ('.', '..') for n in names):
                raise ValueError('GTFS ZIP must contain root-level files only')
            if sum(e.file_size for e in entries) > max_uncompressed_bytes:
                raise ValueError('GTFS ZIP exceeds uncompressed size limit')
            for table in ('agency', 'stops', 'routes', 'trips', 'stop_times'):
                if table + '.txt' not in names:
                    raise ValueError(f'GTFS missing {table}.txt')
            if not {'calendar.txt', 'calendar_dates.txt'} & set(names):
                raise ValueError('GTFS requires calendar.txt or calendar_dates.txt')
            if 'frequencies.txt' in names:
                with io.TextIOWrapper(bundle.open('frequencies.txt'), encoding='utf-8-sig', newline='') as handle:
                    if next(csv.DictReader(handle), None) is not None:
                        raise ValueError('Frequency-based service is unsupported; do not treat template times as departures')
            conn = sqlite3.connect(temp)
            conn.execute('PRAGMA temp_store=FILE')
            conn.execute('PRAGMA cache_size=-32768')
            counts = {table: _load(conn, bundle, table, names) for table in REQUIRED}
            for table in ('agency', 'stops', 'routes', 'trips', 'stop_times'):
                if not counts[table]:
                    raise ValueError(f'GTFS {table}.txt is empty')
            _qa(conn, counts)
            conn.execute('CREATE INDEX stop_departures ON stop_times(stop_id, departure_seconds)')
            conn.execute('CREATE INDEX trips_service ON trips(service_id)')
            report = {'schema_version': SCHEMA_VERSION, 'source_id': source_id,
                      'source_url': source_url, 'archive_sha256': digest.hexdigest(),
                      'processed_at_utc': datetime.now(timezone.utc).isoformat(),
                      'row_counts': counts, 'qa': {'core_references_valid': True, 'chronological_stop_times': True, 'unique_primary_keys': True, 'stop_hierarchy_valid': True, 'served_stop_types_valid': True},
                      'table_columns': {table: [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')] for table in REQUIRED},
                      'agency_timezones': [r[0] for r in conn.execute('SELECT DISTINCT agency_timezone FROM agency')],
                      'calendar_start': conn.execute('SELECT min(d) FROM (SELECT start_date d FROM calendar UNION ALL SELECT date d FROM calendar_dates WHERE exception_type=\'1\')').fetchone()[0],
                      'calendar_end': conn.execute('SELECT max(d) FROM (SELECT end_date d FROM calendar UNION ALL SELECT date d FROM calendar_dates WHERE exception_type=\'1\')').fetchone()[0],
                      'uninterpreted_files': sorted(set(names) - {t + '.txt' for t in REQUIRED}),
                      'limitations': ['Fixed-schedule ingestion only; no multimodal routing or departure predictions.', 'Blank intermediate times remain unknown; no interpolation.', 'Service coverage does not imply service runs now; evaluate calendar and exceptions.', 'Transfers, fares, pathways and Flex extensions are not interpreted.']}
            conn.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            conn.executemany('INSERT INTO metadata VALUES (?,?)', ((k, json.dumps(v)) for k, v in report.items()))
            conn.execute('INSERT INTO metadata VALUES (?,?)', ('report', json.dumps(report)))
            conn.commit()
            conn.close()
            conn = None
        final_digest = hashlib.sha256()
        with archive.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                final_digest.update(chunk)
        if final_digest.hexdigest() != report['archive_sha256']:
            raise ValueError('Source archive changed during build; output not published')
        os.replace(temp, output)
        return report
    except (BadZipFile, sqlite3.IntegrityError, csv.Error, UnicodeError) as error:
        raise ValueError(f'Invalid GTFS archive: {error}') from error
    finally:
        if conn is not None:
            conn.close()
        temp.unlink(missing_ok=True)


def active_services(database, service_date):
    """Return source service IDs for a local service date (YYYYMMDD).

    Callers must check the preceding service day for after-midnight trips. This
    helper deliberately does not convert GTFS service-day times to UTC.
    """
    _date(service_date)
    weekday = WEEKDAYS[datetime.strptime(service_date, '%Y%m%d').weekday()]
    with closing(sqlite3.connect(f'{Path(database).resolve().as_uri()}?mode=ro', uri=True)) as conn:
        active = {row[0] for row in conn.execute(f'SELECT service_id FROM calendar WHERE start_date<=? AND end_date>=? AND {weekday}=\'1\'', (service_date, service_date))}
        for service, kind in conn.execute('SELECT service_id, exception_type FROM calendar_dates WHERE date=?', (service_date,)):
            if kind == '1':
                active.add(service)
            else:
                active.discard(service)
        return active


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-id', default='nta_gtfs')
    parser.add_argument('--source-url')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build_gtfs(args.archive, args.output, source_id=args.source_id, source_url=args.source_url), indent=2))
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f'GTFS processing failed: {error}\n')


if __name__ == '__main__':
    main()
