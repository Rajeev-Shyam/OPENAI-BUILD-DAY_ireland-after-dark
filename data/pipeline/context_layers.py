"""Download and clean public-service landmarks and SCATS sites, never safety scores."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

from pyproj import Transformer
from shapely import wkt

from .download import atomic_write, download_source, validate_csv

REGISTRY = Path(__file__).resolve().parents[1] / 'context-sources.json'
ITM_TO_WGS84 = Transformer.from_crs(2157, 4326, always_xy=True)


def registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))['sources']


def _text(value):
    return ' '.join(value.split()) if value and value.strip() else None


def _point(row, source):
    if source == 'garda_dlr':
        east, north = float(row['itm_east']), float(row['itm_north'])
        if not (400000 <= east <= 800000 and 500000 <= north <= 1000000):
            raise ValueError('invalid ITM coordinates')
        lon, lat = ITM_TO_WGS84.transform(east, north)
    elif source == 'scats_dcc':
        lon, lat = float(row['Long']), float(row['Lat'])
        try:
            point = wkt.loads(row['WKT'])
        except Exception as error:
            raise ValueError('invalid WKT') from error
        if point.geom_type != 'Point' or point.is_empty or point.has_z:
            raise ValueError('WKT must be a two-dimensional point')
        if not (math.isfinite(point.x) and math.isfinite(point.y)):
            raise ValueError('non-finite WKT coordinates')
        if abs(point.x - lon) > 1e-6 or abs(point.y - lat) > 1e-6:
            raise ValueError('WKT and latitude/longitude disagree')
    else:
        lon, lat = float(row['Longitude']), float(row['Latitude'])
    if not (math.isfinite(lon) and math.isfinite(lat) and -11 <= lon <= -5 and 51 <= lat <= 56):
        raise ValueError('coordinates outside Ireland plausibility bounds')
    return [lon, lat]


def clean_source(body, source, spec):
    """Quarantine invalid observations and every row with a conflicting identity."""
    if source == 'hospitals_osm':
        return clean_hospitals(body, spec)
    if source not in {'garda_dlr', 'fire_dublin', 'scats_dcc'}:
        raise ValueError('Unknown context source')
    validate_csv(body, spec, 'text/csv')
    features, rejected, seen = [], [], {}
    duplicate_rows = 0
    input_rows = 0
    rows = list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))))
    identities = {}
    conflicts = set()
    for row in rows:
        identity = _text(row[spec['id_column']])
        if identity in identities and identities[identity] != row:
            conflicts.add(identity)
        identities[identity] = row
    for row in rows:
        if not row or not any(value and value.strip() for value in row.values()):
            continue
        input_rows += 1
        source_id = _text(row[spec['id_column']])
        if source_id in conflicts:
            rejected.append({'record': input_rows, 'source_id': source_id,
                             'reason': 'conflicting duplicate source identifier'})
            continue
        try:
            if not source_id:
                raise ValueError('missing source identifier')
            coordinates = _point(row, source)
        except (ValueError, TypeError, OverflowError) as error:
            rejected.append({'record': input_rows, 'source_id': source_id, 'reason': str(error)})
            continue
        properties = {
            'source': source, 'source_id': source_id, 'kind': spec['kind'],
            'name': _text(row[spec['name_column']]), 'catalogue_url': spec['catalogue_url'],
            'license': spec['license'], 'attribution': spec['attribution'],
            'coverage': spec['coverage'], 'opening_hours': None,
            'public_access_verified': False, 'assistance_available_now': None,
        }
        if source == 'scats_dcc':
            properties['pedestrian_crossing_control'] = None
        else:
            properties['eircode'] = _text(row.get('eircode', row.get('Eircode')))
            properties['address'] = (_text(row.get('Address')) if source == 'fire_dublin' else
                                     ', '.join(filter(None, (_text(row.get(key)) for key in
                                      ['addr_line_', 'addr_line1', 'addr_lin_1', 'addr_lin_2', 'addr_lin_3']))) or None)
            # Preserve source formatting. Do not guess missing telephone prefixes.
            properties['phone_as_published'] = _text(row.get('PhoneNo'))
        feature = {'type': 'Feature', 'id': source + ':' + source_id,
                   'geometry': {'type': 'Point', 'coordinates': coordinates}, 'properties': properties}
        if source_id in seen:
            if seen[source_id] != feature:
                raise ValueError('Conflicting duplicate source identifier: ' + source_id)
            duplicate_rows += 1
            continue
        seen[source_id] = feature
        features.append(feature)
    if not features:
        raise ValueError('No usable points remain for ' + source)
    return features, {'input_rows': input_rows, 'accepted_features': len(features),
                      'duplicate_rows': duplicate_rows, 'rejected_rows': rejected}



def clean_hospitals(body, spec):
    """Validate Overpass completion sentinels and retain hospital-tagged map landmarks."""
    validate_csv(body, spec, 'text/csv')
    rows = list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))))
    if (not rows or rows[-1]['@type'] != 'count' or
            rows[-1]['@count'] != str(len(rows) - 1)):
        raise ValueError('Overpass completion count missing/mismatched')
    identities = [(row['@type'], row['@id']) for row in rows[:-1]]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate OSM element identity')
    features, rejected = [], []
    for number, row in enumerate(rows[:-1], 1):
        source_id = row['@type'] + '/' + row['@id']
        try:
            if row['@type'] not in {'node', 'way', 'relation'} or not row['@id'].isascii() or not row['@id'].isdigit() or int(row['@id']) <= 0:
                raise ValueError('Invalid OSM element identity')
            if row['amenity'] != 'hospital':
                raise ValueError('Element is not tagged amenity=hospital')
            lon, lat = float(row['@lon']), float(row['@lat'])
            if not (math.isfinite(lon) and math.isfinite(lat) and -11 <= lon <= -5 and 51 <= lat <= 56):
                raise ValueError('Coordinates outside Ireland plausibility bounds')
        except (ValueError, TypeError, OverflowError) as error:
            rejected.append({'record': number, 'source_id': source_id, 'reason': str(error)})
            continue
        features.append({
            'type': 'Feature', 'id': 'hospitals_osm:' + source_id,
            'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
            'properties': {
                'source': 'hospitals_osm', 'source_id': source_id, 'kind': 'hospital',
                'name': _text(row['name']), 'catalogue_url': spec['catalogue_url'],
                'osm_url': 'https://www.openstreetmap.org/' + source_id,
                'license': spec['license'], 'attribution': spec['attribution'],
                'coverage': spec['coverage'], 'opening_hours': None,
                'public_access_verified': False, 'assistance_available_now': None,
                'emergency_as_mapped': _text(row['emergency']),
                'opening_hours_as_mapped': _text(row['opening_hours']),
                'access_as_mapped': _text(row['access']),
                'position_kind': ('mapped_node' if row['@type'] == 'node' else 'bounding_box_centre'),
                'entrance_verified': False,
            },
        })
    if not features:
        raise ValueError('No usable hospital landmarks remain')
    return features, {'input_rows': len(rows) - 1, 'accepted_features': len(features),
                      'duplicate_rows': 0, 'rejected_rows': rejected,
                      'query_bbox_south_west_north_east': spec['query_bbox_south_west_north_east'],
                      'completion_count_verified': True,
                      'query': spec['query']}


def _verified_snapshot(raw_dir, source, spec):
    manifest = json.loads((raw_dir / (source + '.manifest.json')).read_text(encoding='utf-8'))
    if (manifest.get('source') != source or manifest.get('source_url') != spec['url'] or
            manifest.get('license') != spec['license']):
        raise ValueError('Manifest source or licence differs from registry')
    snapshot = (raw_dir / manifest['snapshot']).resolve()
    if not snapshot.is_relative_to(raw_dir.resolve() / 'snapshots'):
        raise ValueError('Snapshot path escapes raw snapshots directory')
    body = snapshot.read_bytes()
    if len(body) != manifest['bytes'] or hashlib.sha256(body).hexdigest() != manifest['sha256']:
        raise ValueError('Snapshot hash or size mismatch')
    validate_csv(body, spec, manifest['content_type'])
    return body, manifest


def build(raw_dir, output_dir, sources=None):
    raw_dir, output_dir = Path(raw_dir), Path(output_dir)
    sources = registry() if sources is None else sources
    layers = {'public_services': [], 'scats_sites': [], 'hospitals': []}
    report = {'schema_version': 1, 'sources': {}, 'limitations': [
        'Landmarks do not establish current opening hours, public access, or available assistance.',
        'SCATS sites do not establish pedestrian crossing control or street-level safety.',
        'Hospital landmarks are OSM features, not a complete or clinically verified inventory.',
        'Hospital way/relation centres are not verified entrances or pedestrian destinations.',
        'National public-service completeness is not supplied.',
    ]}
    # Validate every source before replacing any processed layer.
    for source, spec in sources.items():
        body, manifest = _verified_snapshot(raw_dir, source, spec)
        features, qa = clean_source(body, source, spec)
        layer = ('scats_sites' if source == 'scats_dcc' else
                 'hospitals' if source == 'hospitals_osm' else 'public_services')
        layers[layer].extend(features)
        report['sources'][source] = {**qa, 'sha256': manifest['sha256'],
                                     'source_url': spec['url'], 'fetched_at_utc': manifest['fetched_at_utc'],
                                     'coverage': spec['coverage'], 'license': spec['license'],
                                     'attribution': spec['attribution']}
    for name, features in layers.items():
        payload = {'type': 'FeatureCollection', 'schema_version': 1,
                   'metadata': report, 'features': features}
        atomic_write(output_dir / (name + '.geojson'),
                     (json.dumps(payload, indent=2, allow_nan=False) + '\n').encode())
    atomic_write(output_dir / 'context-report.json',
                 (json.dumps(report, indent=2, allow_nan=False) + '\n').encode())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['download', 'build', 'all'])
    parser.add_argument('--raw-dir', type=Path, default=REGISTRY.parent / 'raw' / 'context')
    parser.add_argument('--output-dir', type=Path, default=REGISTRY.parent / 'processed' / 'context')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    try:
        if args.command in {'download', 'all'}:
            for source, spec in registry().items():
                result = download_source(source, spec, args.raw_dir, refresh=args.refresh,
                                         timeout=45,
                                         attempts=1 if source == 'hospitals_osm' else 3)
                print(f"{source}: {result['rows']} downloaded rows; sha256={result['sha256']}")
        if args.command in {'build', 'all'}:
            report = build(args.raw_dir, args.output_dir)
            for source, qa in report['sources'].items():
                print(f"{source}: {qa['accepted_features']} points; {len(qa['rejected_rows'])} quarantined rows")
    except (OSError, ValueError, KeyError, csv.Error) as error:
        parser.exit(1, f'Context pipeline failed: {error}\n')


if __name__ == '__main__':
    main()
