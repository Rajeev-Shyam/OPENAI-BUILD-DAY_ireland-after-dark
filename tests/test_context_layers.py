import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from data.pipeline.context_layers import build, clean_source, registry


def csv_body(source, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=registry()[source]['required_columns'])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode('utf-8')


def scats(**updates):
    return {'Site_ID': '001', 'Location': 'Example junction',
            'WKT': 'POINT (-6.25 53.35)', 'Lat': '53.35', 'Long': '-6.25', **updates}


def test_scats_is_not_classified_as_pedestrian_crossing():
    features, qa = clean_source(csv_body('scats_dcc', [scats()]), 'scats_dcc', registry()['scats_dcc'])
    assert features[0]['id'] == 'scats_dcc:001'
    assert features[0]['geometry']['coordinates'] == [-6.25, 53.35]
    assert features[0]['properties']['pedestrian_crossing_control'] is None
    assert features[0]['properties']['assistance_available_now'] is None
    assert qa['rejected_rows'] == []


def test_garda_transforms_itm_without_inventing_phone_prefix():
    row = {'Station_ID': '1971B', 'name': 'Dundrum Garda Station', 'itm_east': '717171.677',
           'itm_north': '728022.557', 'eircode': 'D14NA09', 'PhoneNo': '16665600'}
    features, _ = clean_source(csv_body('garda_dlr', [row]), 'garda_dlr', registry()['garda_dlr'])
    lon, lat = features[0]['geometry']['coordinates']
    assert -6.244 < lon < -6.241
    assert 53.288 < lat < 53.291
    assert features[0]['properties']['phone_as_published'] == '16665600'
    assert features[0]['properties']['public_access_verified'] is False
    assert features[0]['properties']['opening_hours'] is None


def test_fire_preserves_2025_schema_typo_and_address():
    row = {'StationID': '1', 'StaionName': 'Donnybrook', 'Latitude': '53.321919',
           'Longitude': '-6.237478', 'Address': 'Donnybrook Fire Station', 'Eircode': 'D04W6R9'}
    features, _ = clean_source(csv_body('fire_dublin', [row]), 'fire_dublin', registry()['fire_dublin'])
    assert features[0]['properties']['kind'] == 'fire_station'
    assert features[0]['properties']['address'] == 'Donnybrook Fire Station'


@pytest.mark.parametrize('updates', [
    {'Long': 'NaN'}, {'Lat': 'inf'}, {'Lat': '0'}, {'Site_ID': ''},
    {'WKT': 'POINT (-6.26 53.35)'}, {'WKT': 'garbage'}, {'WKT': 'POINT EMPTY'},
    {'WKT': 'POINT Z (-6.25 53.35 0)'}, {'WKT': 'POINT (NaN 53.35)'}, {'Lat': '-6.25', 'Long': '53.35'},
])
def test_bad_coordinates_or_ids_are_quarantined(updates):
    rows = [scats(), scats(Site_ID='002', **{k: v for k, v in updates.items() if k != 'Site_ID'})]
    if 'Site_ID' in updates:
        rows[1]['Site_ID'] = updates['Site_ID']
    features, qa = clean_source(csv_body('scats_dcc', rows), 'scats_dcc', registry()['scats_dcc'])
    assert len(features) == 1
    assert len(qa['rejected_rows']) == 1
    assert qa['input_rows'] == 2


def test_empty_output_fails_and_conflicting_duplicates_are_all_quarantined():
    spec = registry()['scats_dcc']
    with pytest.raises(ValueError, match='No usable'):
        clean_source(csv_body('scats_dcc', [scats(Lat='0')]), 'scats_dcc', spec)
    features, qa = clean_source(csv_body('scats_dcc', [scats(), scats(Location='Different'),
                                                scats(Site_ID='002')]), 'scats_dcc', spec)
    assert [f['id'] for f in features] == ['scats_dcc:002']
    assert len(qa['rejected_rows']) == 2
    assert all('conflicting duplicate' in row['reason'] for row in qa['rejected_rows'])
    features, qa = clean_source(csv_body('scats_dcc', [scats(), scats()]), 'scats_dcc', spec)
    assert len(features) == 1
    assert qa['duplicate_rows'] == 1


def snapshot(tmp_path):
    spec = registry()['scats_dcc']
    body = csv_body('scats_dcc', [scats()])
    digest = hashlib.sha256(body).hexdigest()
    path = tmp_path / 'snapshots' / (digest + '.csv')
    path.parent.mkdir()
    path.write_bytes(body)
    manifest = {'source': 'scats_dcc', 'source_url': spec['url'], 'license': spec['license'],
                'snapshot': str(path.relative_to(tmp_path)), 'sha256': digest, 'bytes': len(body),
                'content_type': 'text/csv', 'fetched_at_utc': '2026-10-04T00:00:00+00:00'}
    manifest_path = tmp_path / 'scats_dcc.manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    return path, manifest_path, manifest


def test_build_uses_verified_snapshot_not_mutable_alias(tmp_path):
    snapshot(tmp_path)
    (tmp_path / 'scats-dcc-2026.csv').write_text('tampered alias')
    out = tmp_path / 'out'
    report = build(tmp_path, out, {'scats_dcc': registry()['scats_dcc']})
    layer = json.loads((out / 'scats_sites.geojson').read_text())
    assert len(layer['features']) == 1
    assert layer['metadata'] == report
    assert report['sources']['scats_dcc']['accepted_features'] == 1
    assert json.loads((out / 'public_services.geojson').read_text())['features'] == []


@pytest.mark.parametrize('mutation', ['bytes', 'source_url', 'license', 'escape'])
def test_build_rejects_tampered_provenance(tmp_path, mutation):
    path, manifest_path, manifest = snapshot(tmp_path)
    if mutation == 'bytes':
        path.write_bytes(path.read_bytes() + b'\n')
    elif mutation == 'escape':
        manifest['snapshot'] = '../outside.csv'
    else:
        manifest[mutation] = 'untrusted'
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        build(tmp_path, tmp_path / 'out', {'scats_dcc': registry()['scats_dcc']})
    assert not (tmp_path / 'out').exists()


def hospital(**updates):
    return {'@type': 'way', '@id': '123', '@lat': '53.35', '@lon': '-6.25',
            'name': 'Hospital', 'amenity': 'hospital', 'emergency': 'yes',
            'opening_hours': '24/7', 'access': 'private', '@count': '', **updates}


def hospital_rows(rows):
    return [*rows, {'@type': 'count', '@count': str(len(rows))}]


def test_hospital_centres_and_mapped_tags_do_not_imply_access_or_emergency_help():
    spec = registry()['hospitals_osm']
    rows = hospital_rows([hospital(), hospital(**{'@type': 'node'})])
    features, qa = clean_source(csv_body('hospitals_osm', rows), 'hospitals_osm', spec)
    assert len(features) == 2  # node and way IDs occupy separate namespaces
    props = features[0]['properties']
    assert props['position_kind'] == 'bounding_box_centre'
    assert props['entrance_verified'] is False
    assert props['emergency_as_mapped'] == 'yes'
    assert props['assistance_available_now'] is None
    assert props['opening_hours'] is None
    assert props['opening_hours_as_mapped'] == '24/7'
    assert props['public_access_verified'] is False
    assert props['license'] == 'ODbL-1.0'
    assert features[1]['properties']['position_kind'] == 'mapped_node'
    assert qa['input_rows'] == 2
    assert qa['completion_count_verified'] is True


@pytest.mark.parametrize('change', ['missing_end', 'wrong_total', 'empty_result', 'duplicate'])
def test_overpass_incomplete_or_inconsistent_result_is_not_accepted(change):
    rows = hospital_rows([hospital()])
    if change == 'missing_end':
        rows.pop()
    elif change == 'wrong_total':
        rows[-1]['@count'] = '2'
    elif change == 'empty_result':
        rows = hospital_rows([])
    else:
        rows = hospital_rows([hospital(), hospital()])
    with pytest.raises(ValueError):
        clean_source(csv_body('hospitals_osm', rows), 'hospitals_osm', registry()['hospitals_osm'])


@pytest.mark.parametrize('bad', [
    {'amenity': 'clinic'}, {'@lon': 'NaN'}, {'@lat': '0'}, {'@type': 'area'}, {'@id': '-1'},
])
def test_hospital_invalid_or_non_hospital_rows_are_quarantined(bad):
    rows = hospital_rows([hospital(), hospital(**{'@id': '456', **bad})])
    features, qa = clean_source(csv_body('hospitals_osm', rows), 'hospitals_osm', registry()['hospitals_osm'])
    assert len(features) == 1
    assert len(qa['rejected_rows']) == 1
