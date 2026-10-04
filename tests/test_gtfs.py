"""Observable ingestion, relational integrity and night-time service semantics."""
import json
import sqlite3
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from data.pipeline.gtfs import active_services, build_gtfs, gtfs_seconds


@pytest.fixture
def files():
    return {
        'agency.txt': 'agency_id,agency_name,agency_url,agency_timezone\nA,Test,https://example.org,Europe/Dublin\n',
        'stops.txt': 'stop_id,stop_name,stop_lat,stop_lon\n001,First,53.34,-6.26\n002,Last,53.35,-6.27\n',
        'routes.txt': 'route_id,agency_id,route_short_name,route_type\n01,A,1,3\n',
        'trips.txt': 'route_id,service_id,trip_id\n01,WK,0001\n',
        'stop_times.txt': 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n0001,24:50:00,24:51:00,001,2\n0001,25:10:00,25:10:00,002,10\n',
        'calendar.txt': 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,1,1,1,1,0,0,20260101,20261231\n',
        'calendar_dates.txt': 'service_id,date,exception_type\nWK,20261005,2\nWK,20261004,1\n',
    }


def archive(tmp_path, files):
    path = tmp_path / 'feed.zip'
    with ZipFile(path, 'w', ZIP_DEFLATED) as z:
        for name, contents in files.items():
            z.writestr(name, contents)
    return path


def test_service_day_times_ids_and_exceptions(tmp_path, files):
    db = tmp_path / 'out.sqlite'
    report = build_gtfs(archive(tmp_path, files), db, source_id='test')
    assert report['row_counts']['stop_times'] == 2
    assert len(report['archive_sha256']) == 64
    assert report['agency_timezones'] == ['Europe/Dublin']
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT trip_id,stop_id,stop_sequence,departure_seconds FROM stop_times ORDER BY stop_sequence').fetchall() == [('0001', '001', 2, 89460), ('0001', '002', 10, 90600)]
        assert json.loads(conn.execute("SELECT value FROM metadata WHERE key='report'").fetchone()[0]) == report
    assert active_services(db, '20261004') == {'WK'}  # Sunday explicitly added
    assert active_services(db, '20261005') == set()  # Monday explicitly removed
    assert active_services(db, '20261006') == {'WK'}
    assert active_services(db, '20271006') == set()


def test_calendar_dates_only(tmp_path, files):
    del files['calendar.txt']
    db = tmp_path / 'out.sqlite'
    build_gtfs(archive(tmp_path, files), db)
    assert active_services(db, '20261004') == {'WK'}
    assert active_services(db, '20261006') == set()


@pytest.mark.parametrize('time,seconds', [('0:00:00', 0), ('25:01:02', 90062), ('', None)])
def test_times(time, seconds):
    assert gtfs_seconds(time) == seconds


@pytest.mark.parametrize('time', ['-1:00:00', '24:60:00', '12:00:99', '1:2:00', '12:00'])
def test_bad_times(time):
    with pytest.raises(ValueError):
        gtfs_seconds(time)


@pytest.mark.parametrize('table,old,new,message', [
    ('stop_times.txt', '0001,24:50', 'missing,24:50', 'missing trip'),
    ('stop_times.txt', ',002,10', ',missing,10', 'missing stop'),
    ('trips.txt', '01,WK,0001', 'missing,WK,0001', 'missing route'),
    ('trips.txt', '01,WK,0001', '01,missing,0001', 'missing service'),
    ('routes.txt', '01,A,1,3', '01,missing,1,3', 'missing agency'),
    ('stop_times.txt', '25:10:00,25:10:00', '24:10:00,24:10:00', 'times decrease'),
    ('stop_times.txt', '24:50:00,24:51:00', '24:50:00,24:49:00', 'Departure precedes'),
    ('stop_times.txt', ',002,10', ',002,2', 'UNIQUE'),
    ('agency.txt', 'Europe/Dublin', 'Not/AZone', 'agency_timezone'),
    ('calendar.txt', '20261231', '20251301', 'calendar date'),
    ('stops.txt', '53.34', 'nan', 'coordinates'),
    ('calendar_dates.txt', '20261005,2', '20261005,3', 'exception_type'),
])
def test_rejects_bad_semantics_atomically(tmp_path, files, table, old, new, message):
    files[table] = files[table].replace(old, new)
    db = tmp_path / 'out.sqlite'
    db.write_bytes(b'previous validated version')
    with pytest.raises(ValueError, match=message):
        build_gtfs(archive(tmp_path, files), db)
    assert db.read_bytes() == b'previous validated version'
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('extra', ['../stops.txt', '/evil.txt', 'nested/stops.txt', 'nested\\stops.txt'])
def test_rejects_nonroot_archive_paths(tmp_path, files, extra):
    files[extra] = 'no extraction'
    with pytest.raises(ValueError, match='root-level'):
        build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite')


def test_frequency_feed_not_misrepresented_as_fixed_times(tmp_path, files):
    files['frequencies.txt'] = 'trip_id,start_time,end_time,headway_secs\n0001,24:00:00,26:00:00,600\n'
    with pytest.raises(ValueError, match='Frequency-based'):
        build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite')


def test_unknown_intermediate_time_retained(tmp_path, files):
    files['stop_times.txt'] = 'trip_id,arrival_time,departure_time,stop_id,stop_sequence,timepoint\n0001,24:50:00,24:51:00,001,2,1\n0001,,,001,5,0\n0001,25:10:00,25:10:00,002,10,1\n'
    db = tmp_path / 'out.sqlite'
    build_gtfs(archive(tmp_path, files), db)
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT arrival_seconds FROM stop_times WHERE stop_sequence=5').fetchone() == (None,)


def test_missing_terminal_time_rejected(tmp_path, files):
    files['stop_times.txt'] = 'trip_id,arrival_time,departure_time,stop_id,stop_sequence,timepoint\n0001,,,001,2,0\n0001,25:10:00,25:10:00,002,10,1\n'
    with pytest.raises(ValueError, match='first or last'):
        build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite')


def test_bad_zip_and_expansion_limit(tmp_path, files):
    with pytest.raises(ValueError, match='size limit'):
        build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite', max_uncompressed_bytes=10)
    path = tmp_path / 'bad.zip'
    path.write_text('not a zip')
    with pytest.raises(ValueError, match='Invalid GTFS'):
        build_gtfs(path, tmp_path / 'out.sqlite')


def test_duplicate_zip_members(tmp_path, files):
    path = archive(tmp_path, files)
    with pytest.warns(UserWarning), ZipFile(path, 'a') as z:
        z.writestr('stops.txt', files['stops.txt'])
    with pytest.raises(ValueError, match='duplicate members'):
        build_gtfs(path, tmp_path / 'out.sqlite')


def test_optional_single_agency_identifier(tmp_path, files):
    files['agency.txt'] = 'agency_name,agency_url,agency_timezone\nTest,https://example.org,Europe/London\n'
    files['routes.txt'] = 'route_id,route_short_name,route_type\n01,1,3\n'
    report = build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite')
    assert report['agency_timezones'] == ['Europe/London']


def test_duplicate_csv_header(tmp_path, files):
    files['stops.txt'] = 'stop_id,stop_id\n001,001\n'
    with pytest.raises(ValueError, match='duplicate'):
        build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite')


def test_changed_source_does_not_publish(tmp_path, files, monkeypatch):
    import data.pipeline.gtfs as module
    source = archive(tmp_path, files)
    output = tmp_path / 'out.sqlite'
    output.write_bytes(b'old artifact')
    original_qa = module._qa

    def change_source(conn, counts):
        original_qa(conn, counts)
        with source.open('ab') as handle:
            handle.write(b'changed after parsing')

    monkeypatch.setattr(module, '_qa', change_source)
    with pytest.raises(ValueError, match='changed during build'):
        module.build_gtfs(source, output)
    assert output.read_bytes() == b'old artifact'


def test_cli_reports_clean_failure(tmp_path, capsys):
    from data.pipeline.gtfs import main
    with pytest.raises(SystemExit) as error:
        main(['--archive', str(tmp_path / 'missing.zip'), '--output', str(tmp_path / 'out.sqlite')])
    assert error.value.code == 1
    assert 'GTFS processing failed:' in capsys.readouterr().err


def test_valid_station_hierarchy_including_unlocated_nodes(tmp_path, files):
    files['stops.txt'] = ('stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n'
                         '001,First,53.34,-6.26,0,ST\n002,Last,53.35,-6.27,,ST\n'
                         'ST,Station,53.34,-6.26,1,\n'
                         'E,Entrance,53.34,-6.26,2,ST\n'
                         'N,,,,3,ST\n'
                         'BA,,,,4,001\n')
    report = build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite')
    assert report['row_counts']['stops'] == 6


@pytest.mark.parametrize('extra', [
    'ST,Station,53.34,-6.26,1,001\n',
    'BA,Boarding,53.34,-6.26,4,\n',
    'N,Node,53.34,-6.26,3,001\n',
    'ST,Station,53.34,-6.26,1,\nBA,Boarding,53.34,-6.26,4,ST\n',
])
def test_invalid_station_hierarchy(tmp_path, files, extra):
    files['stops.txt'] = ('stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n'
                         '001,First,53.34,-6.26,0,\n002,Last,53.35,-6.27,0,\n' + extra)
    with pytest.raises(ValueError, match='parent hierarchy'):
        build_gtfs(archive(tmp_path, files), tmp_path / 'out.sqlite')
