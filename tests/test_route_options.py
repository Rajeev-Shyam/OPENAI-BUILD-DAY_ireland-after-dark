import json
from copy import deepcopy

from backend.routing.alternatives import add_alternatives
from backend.routing.engine import Preferences, RoutingEngine
from backend.scoring.contract import build_route_response
from backend.api import hospitals
from test_routing import make_graph, ORIGIN, DESTINATION


def test_three_distinct_candidates_without_mutating_graph():
    graph=make_graph()
    graph.add_node(7,y=53.352,x=-6.259)
    for u,v in [(1,7),(7,4)]:
        graph.add_edge(u,v,0,length=300.)
        graph.add_edge(v,u,0,length=300.)
    engine=RoutingEngine(graph)
    before=deepcopy(dict(graph.edges.items()))
    result=engine.route(ORIGIN,DESTINATION)
    add_alternatives(engine,result,Preferences())
    response=build_route_response('synthetic',None,result)
    assert len(response['routes'])==3
    assert len({str(r['geometry']) for r in response['routes']})==3
    assert all(r['duration_s'] <= response['routes'][0]['duration_s']+300 for r in response['routes'])
    assert dict(graph.edges.items())==before


def test_no_fabricated_duplicate_when_only_one_path_exists():
    graph=make_graph();graph.remove_node(3)
    engine=RoutingEngine(graph)
    result=add_alternatives(engine,engine.route(ORIGIN,DESTINATION),Preferences())
    assert len(build_route_response('synthetic',None,result)['routes'])==1


def test_hospital_distance_is_to_route_and_absence_is_not_missing(tmp_path,monkeypatch):
    path=tmp_path/'hospitals.geojson';monkeypatch.setattr(hospitals,'PATH',path)
    def response():return {'routes':[{'geometry':{'type':'LineString','coordinates':[[-6.26,53.35],[-6.25,53.35]]}}]}
    assert hospitals.attach_hospitals(response())['routes'][0]['nearby_hospitals'] is None
    path.write_text(json.dumps({'type':'FeatureCollection','metadata':{'sources':{'hospitals_osm':{'fetched_at_utc':'2026-10-04'}}},
        'features':[{'geometry':{'type':'Point','coordinates':[-6.255,53.3505]},'properties':{'name':'Synthetic Hospital','source_id':'node/1'}}]}))
    result=hospitals.attach_hospitals(response())
    hospital=result['routes'][0]['nearby_hospitals'][0]
    assert 40 < hospital['distance_from_route_m'] < 70
    assert hospital['assistance_available_now'] is None
    assert 'not walking distance' in result['hospital_context']['message']
