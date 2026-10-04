"""Distance to mapped hospital landmarks, not verified entrances or care access."""
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform

PATH = Path(__file__).resolve().parents[2] / 'data/processed/context/hospitals.geojson'
PROJECT = Transformer.from_crs(4326,2157,always_xy=True).transform


def attach_hospitals(response, radius_m=1000):
    try:
        document=json.loads(PATH.read_text(encoding='utf-8'))
        if document['type']!='FeatureCollection':
            raise ValueError()
        source=document['metadata']['sources']['hospitals_osm']
        points=[(feature,transform(PROJECT,Point(feature['geometry']['coordinates'])))
                for feature in document['features']]
    except (OSError,ValueError,KeyError,TypeError):
        for route in response['routes']:
            route['nearby_hospitals']=None
        response['hospital_context']={'status':'unavailable','radius_m':radius_m,
            'message':'Hospital landmark data is unavailable; this does not mean no hospitals are nearby.'}
        return response
    for route in response['routes']:
        line=transform(PROJECT,LineString(route['geometry']['coordinates']))
        nearby=[]
        for feature,point in points:
            distance=line.distance(point)
            if distance>radius_m:
                continue
            p=feature['properties']
            nearby.append({'name':p.get('name') or 'Unnamed mapped hospital',
                'distance_from_route_m':round(distance), 'coordinates':feature['geometry']['coordinates'],
                'source_id':p['source_id'], 'opening_hours_verified':False,
                'assistance_available_now':None})
        route['nearby_hospitals']=sorted(nearby,key=lambda h:(h['distance_from_route_m'],h['name']))[:5]
    response['hospital_context']={'status':'available','radius_m':radius_m,
        'fetched_at_utc':source['fetched_at_utc'], 'attribution':'OpenStreetMap contributors, ODbL',
        'message':'Mapped hospital landmarks within 1 km straight-line distance of the route; not walking distance to an entrance. Hours, emergency care and public access are unverified. Coverage is incomplete.'}
    return response
