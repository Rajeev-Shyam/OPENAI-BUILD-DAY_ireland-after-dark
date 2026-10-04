from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from backend.api import main, transport, geocoding
from backend.routing.engine import NoRoute
from test_scoring import _engine_result


@pytest.fixture
def client(monkeypatch):
    return TestClient(main.app)


@pytest.mark.parametrize('departure,enabled', [('2026-10-02T22:30:00Z', True), ('2026-10-04T22:30:00Z', False)])
def test_departure_controls_ranking_and_presentation(client, monkeypatch, departure, enabled):
    monkeypatch.setattr(main,'add_alternatives',lambda engine,result,prefs:result)
    result = _engine_result()
    for kind in ('fastest','night'):
        result[kind]['activity'] = {'score':0.7, 'coverage':0.2}
    engine = Mock()
    engine.route.side_effect = lambda *args: deepcopy(result)
    store = SimpleNamespace(bundle=SimpleNamespace(time_slice={'weekday':4,'hour':23}),
        _engines={'dublin':((-6.39,53.29,-6.11,53.41),engine)},
        engine_for=lambda *args: ('dublin',engine))
    monkeypatch.setattr(main,'get_store',lambda:store)
    response = client.post('/route',json={'origin':[-6.26,53.34],'destination':[-6.25,53.35],
        'departure_time':departure,'timezone':'Europe/Dublin'})
    assert response.status_code == 200
    body = response.json()
    assert body['activity_enabled'] is enabled
    assert [call.args[2].busier for call in engine.route.call_args_list] == ([0.2, 0.6] if enabled else [0, 0])
    assert (body['routes'][0]['historical_activity'] is not None) is enabled
    assert body['routes'][0]['lighting_coverage_pct'] == 90
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('extra', [{'departure_time':'2026-10-04T22:00:00'}, {'timezone':'UTC'}, {'preferences':{}}])
def test_invalid_time_or_unsupported_preferences(client, extra):
    r=client.post('/route',json={'origin':[-6.26,53.34],'destination':[-6.25,53.35],**extra})
    assert r.status_code == 400
    assert r.json()['error']['code']=='INVALID_INPUT'


def test_no_route_maps_without_fallback(client,monkeypatch):
    store=Mock()
    store.engine_for.side_effect=NoRoute('No connected walking route.')
    monkeypatch.setattr(main,'get_store',lambda:store)
    r=client.post('/route',json={'origin':[-6.26,53.34],'destination':[-6.25,53.35]})
    assert r.status_code==404 and r.json()['error']['code']=='NO_ROUTE'


def test_missing_and_invalid_transport_are_explicit(client,monkeypatch,tmp_path):
    monkeypatch.setattr(transport,'DATA',tmp_path)
    assert client.get('/transport/stops').status_code==503
    assert client.get('/transport/status').json()['status']=='missing'
    root=tmp_path/'raw/nta-realtime';root.mkdir(parents=True)
    (root/'trip_updates.manifest.json').write_text('{}')
    assert client.get('/transport/status').json()['status']=='unavailable'


def test_snapshot_freshness_recomputed(monkeypatch,tmp_path):
    from test_gtfs_realtime import feed
    from hashlib import sha256
    root=tmp_path/'raw/nta-realtime';root.mkdir(parents=True)
    body=feed().SerializeToString();(root/'test.pb').write_bytes(body)
    (root/'trip_updates.manifest.json').write_text(json.dumps({'snapshot':'test.pb','bytes':len(body),
        'sha256':sha256(body).hexdigest(),'received_at_unix':1000}))
    monkeypatch.setattr(transport,'DATA',tmp_path)
    monkeypatch.setattr(transport.time,'time',lambda:1005)
    assert transport.realtime_status()['status']=='fresh'
    monkeypatch.setattr(transport.time,'time',lambda:1100)
    assert transport.realtime_status()['status']=='stale'


def test_geocoding_cache_and_gate(monkeypatch,tmp_path):
    monkeypatch.setattr(geocoding,'GATE_DIR',tmp_path)
    monkeypatch.setattr(geocoding,'_cache',geocoding.OrderedDict())
    now=[1000.0]; sleeps=[]; calls=[]
    monkeypatch.setattr(geocoding.time,'time',lambda:now[0])
    def sleep(delay):
        sleeps.append(delay);now[0]+=delay
    monkeypatch.setattr(geocoding.time,'sleep',sleep)
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'[{"lon":"-6.25","lat":"53.35","display_name":"Synthetic place"}]'
    def fetch(request,**kwargs):calls.append(request);return Response()
    monkeypatch.setattr(geocoding,'urlopen',fetch)
    assert geocoding.search('Place One')==geocoding.search(' place one ')
    geocoding.search('Place Two')
    assert len(calls)==2
    assert sum(sleeps)>=1.1
    assert calls[0].get_header('User-agent').startswith('IrelandAfterDark/')
