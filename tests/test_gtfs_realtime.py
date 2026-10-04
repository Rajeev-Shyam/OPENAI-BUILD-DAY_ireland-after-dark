"""Synthetic protocol fixtures: these are not observed NTA predictions."""
import json
import urllib.error

import pytest
from google.transit import gtfs_realtime_pb2 as pb
from data.pipeline import gtfs_realtime as rt


def feed():
    result = pb.FeedMessage()
    result.header.gtfs_realtime_version = '2.0'
    result.header.timestamp = 1000
    return result


def trip(f, identifier='synthetic-entity'):
    e = f.entity.add(id=identifier)
    e.trip_update.trip.trip_id = '001-synthetic-trip'
    e.trip_update.trip.start_date = '20261004'
    e.trip_update.timestamp = 990
    return e.trip_update


def test_zero_delay_missing_delay_and_identifiers():
    f = feed()
    t = trip(f)
    a = t.stop_time_update.add(stop_id='001', stop_sequence=1)
    a.arrival.delay = 0
    b = t.stop_time_update.add(stop_id='002', stop_sequence=2)
    b.departure.time = 1100
    result = rt.normalize_feed(f.SerializeToString(), now=1000)
    item = result['trip_updates'][0]
    assert item['usable_as_current_observation'] is True
    assert item['data']['trip']['trip_id'] == '001-synthetic-trip'
    assert item['data']['stop_time_update'][0]['arrival']['delay'] == 0
    assert 'delay' not in item['data']['stop_time_update'][1]['departure']
    assert item['data']['stop_time_update'][1]['departure']['time'] == '1100'


@pytest.mark.parametrize('header_stamp,entity_stamp,status,current', [
    (1000, 990, 'fresh', True), (1000, 800, 'stale', False),
    (800, 990, 'fresh', False), (1001, 990, 'fresh', False),
    (1000, 1001, 'future', False), (1000, None, 'unknown', False)])
def test_independent_freshness(header_stamp, entity_stamp, status, current):
    f = feed()
    f.header.timestamp = header_stamp
    t = trip(f)
    if entity_stamp is None:
        t.ClearField('timestamp')
    else:
        t.timestamp = entity_stamp
    item = rt.normalize_feed(f.SerializeToString(), now=1000)['trip_updates'][0]
    assert item['observation_freshness']['status'] == status
    assert item['usable_as_current_observation'] is current


def test_missing_header_timestamp_unknown():
    f = feed()
    f.header.ClearField('timestamp')
    trip(f)
    result = rt.normalize_feed(f.SerializeToString(), now=1000)
    assert result['feed_freshness']['status'] == 'unknown'
    assert not result['trip_updates'][0]['usable_as_current_observation']


def test_cancel_skip_no_data_negative_delay_and_alert():
    f = feed()
    t = trip(f)
    t.trip.schedule_relationship = pb.TripDescriptor.CANCELED
    other = trip(f, 'second')
    other.stop_time_update.add(stop_id='A', schedule_relationship=pb.TripUpdate.StopTimeUpdate.SKIPPED)
    other.stop_time_update.add(stop_id='B', schedule_relationship=pb.TripUpdate.StopTimeUpdate.NO_DATA)
    other.stop_time_update.add(stop_id='C').arrival.delay = -40
    f.entity.add(id='alert').alert.header_text.translation.add(text='Synthetic disruption', language='en')
    result = rt.normalize_feed(f.SerializeToString(), now=1000)
    assert result['trip_updates'][0]['data']['trip']['schedule_relationship'] == 'CANCELED'
    stops = result['trip_updates'][1]['data']['stop_time_update']
    assert [s.get('schedule_relationship') for s in stops[:2]] == ['SKIPPED', 'NO_DATA']
    assert stops[2]['arrival']['delay'] == -40
    assert result['alerts'][0]['data']['header_text']['translation'][0]['text'] == 'Synthetic disruption'
    assert not result['alerts'][0]['usable_as_current_observation']


def test_differential_and_deleted_rejected():
    f = feed()
    f.header.incrementality = pb.FeedHeader.DIFFERENTIAL
    with pytest.raises(ValueError, match='DIFFERENTIAL'):
        rt.normalize_feed(f.SerializeToString())
    f.header.incrementality = pb.FeedHeader.FULL_DATASET
    f.entity.add(id='deleted', is_deleted=True)
    with pytest.raises(ValueError, match='is_deleted'):
        rt.normalize_feed(f.SerializeToString())


@pytest.mark.parametrize('body', [b'', b'<html>Error</html>', b'\x00'])
def test_bad_payload(body):
    with pytest.raises(ValueError):
        rt.normalize_feed(body)


def test_duplicate_id_ordering_and_position():
    f = feed()
    trip(f)
    trip(f)
    with pytest.raises(ValueError, match='duplicate'):
        rt.normalize_feed(f.SerializeToString())
    f = feed()
    t = trip(f)
    t.stop_time_update.add(stop_sequence=2)
    t.stop_time_update.add(stop_sequence=1)
    with pytest.raises(ValueError, match='increasing'):
        rt.normalize_feed(f.SerializeToString())
    f = feed()
    p = f.entity.add(id='v').vehicle.position
    p.latitude = 91
    p.longitude = -6
    with pytest.raises(ValueError, match='coordinates'):
        rt.normalize_feed(f.SerializeToString())


class Response:
    def __init__(self, body, endpoint='trip_updates', content_type='application/x-protobuf'):
        self.body = body
        self.endpoint = endpoint
        self.headers = {'Content-Type': content_type}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def geturl(self):
        return rt.ENDPOINTS[self.endpoint]
    def read(self, limit):
        return self.body[:limit]


def test_fetch_provenance_secret_exclusion_and_cross_endpoint_rate_limit(tmp_path, monkeypatch):
    f = feed()
    trip(f)
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert request.get_header('X-api-key') == 'secret-test-key'
            return Response(f.SerializeToString())
    monkeypatch.setattr(rt.urllib.request, 'build_opener', lambda *a: Opener())
    monkeypatch.setattr(rt.time, 'time', lambda: 1000)
    manifest = rt.fetch_snapshot(tmp_path, api_key='secret-test-key')
    assert manifest['feed_freshness']['status'] == 'fresh'
    assert (tmp_path / manifest['snapshot']).read_bytes() == f.SerializeToString()
    for p in tmp_path.rglob('*'):
        if p.is_file():
            assert b'secret-test-key' not in p.read_bytes()
    with pytest.raises(ValueError, match='60 seconds'):
        rt.fetch_snapshot(tmp_path, endpoint='vehicles', api_key='secret-test-key')
    assert len(calls) == 1


def test_failed_refresh_preserves_manifest_and_redacts_error(tmp_path, monkeypatch):
    path = tmp_path / 'trip_updates.manifest.json'
    path.write_text('{"old":true}')
    class Opener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(request.full_url, 401, 'secret-test-key', {}, None)
    monkeypatch.setattr(rt.urllib.request, 'build_opener', lambda *a: Opener())
    with pytest.raises(ValueError, match='HTTP error 401') as exc:
        rt.fetch_snapshot(tmp_path, api_key='secret-test-key')
    assert 'secret-test-key' not in str(exc.value)
    assert json.loads(path.read_text()) == {'old': True}
    assert (tmp_path / '.last-request.json').exists()


def test_redirect_rejected_before_credentials_forwarded():
    request = rt.urllib.request.Request(rt.ENDPOINTS['trip_updates'], headers={'x-api-key': 'secret'})
    with pytest.raises(ValueError, match='redirect refused'):
        rt._NoRedirect().redirect_request(request, None, 302, '', {}, 'https://evil.example')


def test_fetch_missing_key_and_unknown_endpoint(tmp_path, monkeypatch):
    monkeypatch.delenv('NTA_API_KEY', raising=False)
    with pytest.raises(ValueError, match='NTA_API_KEY'):
        rt.fetch_snapshot(tmp_path)
    with pytest.raises(ValueError, match='Unknown NTA endpoint'):
        rt.fetch_snapshot(tmp_path, endpoint='https://evil.example', api_key='secret')


def test_wrong_content_type_and_size(tmp_path, monkeypatch):
    class Opener:
        def open(self, request, timeout):
            return Response(b'{"header":{}}', content_type='application/json')
    monkeypatch.setattr(rt.urllib.request, 'build_opener', lambda *a: Opener())
    with pytest.raises(ValueError, match='content type'):
        rt.fetch_snapshot(tmp_path, api_key='synthetic')
    monkeypatch.setattr(rt, 'MAX_BYTES', 5)
    with pytest.raises(ValueError, match='oversized'):
        rt.normalize_feed(feed().SerializeToString())


@pytest.mark.parametrize('key', ['line\nbreak', 'white space', 'é', 42])
def test_reject_malformed_key_without_leaking_it(tmp_path, key):
    with pytest.raises(ValueError, match='Invalid API key header'):
        rt.fetch_snapshot(tmp_path, api_key=key)


@pytest.mark.parametrize('headers,expected', [({'Content-Length': '10000'}, 'Content-Length'),
                                             ({'Content-Encoding': 'gzip'}, 'encoding')])
def test_incomplete_or_encoded_response_rejected(tmp_path, monkeypatch, headers, expected):
    class Opener:
        def open(self, request, timeout):
            response = Response(feed().SerializeToString())
            response.headers.update(headers)
            return response
    monkeypatch.setattr(rt.urllib.request, 'build_opener', lambda *a: Opener())
    with pytest.raises(ValueError, match=expected):
        rt.fetch_snapshot(tmp_path, api_key='synthetic')
    assert not (tmp_path / 'trip_updates.manifest.json').exists()


def test_vehicle_position_and_reassessing_saved_snapshot():
    f = feed()
    v = f.entity.add(id='synthetic-vehicle').vehicle
    v.timestamp = 995
    v.trip.trip_id = '0001'
    v.position.latitude = 53.35
    v.position.longitude = -6.26
    v.stop_id = '008'
    body = f.SerializeToString()
    now = rt.normalize_feed(body, now=1000)['vehicle_positions'][0]
    later = rt.normalize_feed(body, now=1100)['vehicle_positions'][0]
    assert now['usable_as_current_observation']
    assert not later['usable_as_current_observation']
    assert later['observation_freshness']['status'] == 'stale'
    assert now['data']['stop_id'] == '008'
    assert now['data']['trip']['trip_id'] == '0001'


def test_empty_full_snapshot_does_not_imply_on_time_or_coverage():
    snapshot = rt.normalize_feed(feed().SerializeToString(), now=1000)
    assert snapshot['trip_updates'] == []
    assert snapshot['coverage'] == 'observed_entities_only; absence_is_unknown'


def test_bad_http_status_redacted(tmp_path, monkeypatch):
    import http.client
    class Opener:
        def open(self, request, timeout):
            raise http.client.BadStatusLine('sensitive-upstream-text')
    monkeypatch.setattr(rt.urllib.request, 'build_opener', lambda *a: Opener())
    with pytest.raises(ValueError, match='NTA network request failed') as exc:
        rt.fetch_snapshot(tmp_path, api_key='synthetic')
    assert 'sensitive-upstream-text' not in str(exc.value)
    assert not (tmp_path / 'trip_updates.manifest.json').exists()


def test_normalize_cli_preserves_raw_input(tmp_path, monkeypatch):
    import sys
    source = tmp_path / 'snapshot.pb'
    original = feed().SerializeToString()
    source.write_bytes(original)
    monkeypatch.setattr(sys, 'argv', ['gtfs_realtime', 'normalize', '--input', str(source), '--output', str(source)])
    with pytest.raises(SystemExit) as exc:
        rt.main()
    assert exc.value.code == 1
    assert source.read_bytes() == original


@pytest.mark.parametrize('relationship', [7, 8])
def test_unknown_new_deleted_relationships_fail_closed(relationship):
    # Official current spec: DELETED=7, NEW=8. Pinned bindings1.0.0 lack them.
    # Field4 (wire varint) is TripDescriptor.schedule_relationship.
    f = feed()
    t = trip(f)
    descriptor = t.trip.SerializeToString() + bytes([4 << 3, relationship])
    t.trip.ParseFromString(descriptor)
    assert t.trip.schedule_relationship == pb.TripDescriptor.SCHEDULED  # dangerous proto2 default
    with pytest.raises(ValueError, match='Unsupported GTFS-RT wire'):
        rt.normalize_feed(f.SerializeToString(), now=1000)


def test_unknown_top_level_and_nested_wire_fields_rejected():
    f = feed()
    t = trip(f)
    # Unknown field127, varint1, nested in an otherwise valid timestamped update.
    t.ParseFromString(t.SerializeToString() + b'\xf8\x07\x01')
    with pytest.raises(ValueError, match='Unsupported GTFS-RT wire'):
        rt.normalize_feed(f.SerializeToString(), now=1000)
    with pytest.raises(ValueError, match='Unsupported GTFS-RT wire'):
        rt.normalize_feed(feed().SerializeToString() + b'\xf8\x07\x01', now=1000)
