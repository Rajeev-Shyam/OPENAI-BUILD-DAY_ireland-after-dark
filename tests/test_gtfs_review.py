"""Independent review regressions; synthetic GTFS only."""
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from data.pipeline.gtfs import build_gtfs


def sample(tmp_path, stops):
    files = {
        'agency.txt': 'agency_name,agency_url,agency_timezone\nSynthetic,https://example.org,Europe/Dublin\n',
        'stops.txt': stops,
        'routes.txt': 'route_id,route_short_name,route_type\nR,1,3\n',
        'trips.txt': 'route_id,service_id,trip_id\nR,S,T\n',
        'stop_times.txt': 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT,24:00:00,24:00:00,A,1\nT,24:10:00,24:10:00,B,2\n',
        'calendar_dates.txt': 'service_id,date,exception_type\nS,20261004,1\n',
    }
    path = tmp_path / 'synthetic.zip'
    with ZipFile(path, 'w', ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return path


def test_stop_times_cannot_serve_station_centroid(tmp_path):
    archive = sample(tmp_path, 'stop_id,stop_name,stop_lat,stop_lon,location_type\nA,Station,53,-6,1\nB,Platform,53,-6,0\n')
    with pytest.raises(ValueError):
        build_gtfs(archive, tmp_path / 'result.sqlite')


def test_parent_station_must_be_station_not_self_or_platform(tmp_path):
    archive = sample(tmp_path, 'stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\nA,Platform,53,-6,0,A\nB,Platform,53,-6,0,A\n')
    with pytest.raises(ValueError):
        build_gtfs(archive, tmp_path / 'result.sqlite')


def test_entrance_requires_parent_station(tmp_path):
    archive = sample(tmp_path, 'stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\nA,Platform,53,-6,0,\nB,Platform,53,-6,0,\nE,Entrance,53,-6,2,\n')
    with pytest.raises(ValueError):
        build_gtfs(archive, tmp_path / 'result.sqlite')
