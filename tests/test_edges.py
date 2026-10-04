"""Protect graph identity and metre geometry at Person 1/2 boundary."""
import json

import pytest

from data.pipeline.edges import load_edges, metric_geometry


def write_edges(tmp_path, features):
    path = tmp_path / "edges.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def feature(u=1, v=2, key=0, coordinates=None):
    return {"type": "Feature", "properties": {"u": u, "v": v, "key": key},
            "geometry": {"type": "LineString", "coordinates": coordinates or
                         [[-6.26, 53.35], [-6.26, 53.351]]}}


def test_preserves_parallel_directed_edges_and_projects_metres(tmp_path):
    edges = load_edges(write_edges(tmp_path, [feature(), feature(2, 1), feature(key=1)]))
    assert [(e["u"], e["v"], e["key"]) for e in edges] == [
        ("1", "2", "0"), ("2", "1", "0"), ("1", "2", "1")]
    assert 110 < metric_geometry(edges[0]["geometry"]).length < 112


def test_normalized_identity_collision_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_edges(write_edges(tmp_path, [feature(), feature("1", "2", "0")]))


@pytest.mark.parametrize("coordinates", [
    [[53.35, -6.26], [53.351, -6.26]],
    [[-6.26, 53.35], [-6.26, 53.35]],
    [[-6.26, 53.35], [float("nan"), 53.35]],
    [[-6.26, 53.35, 2], [-6.26, 53.351, 2]],
    [[-73, 40], [-73, 41]],
])
def test_rejects_bad_geometry(tmp_path, coordinates):
    with pytest.raises(ValueError):
        load_edges(write_edges(tmp_path, [feature(coordinates=coordinates)]))


@pytest.mark.parametrize("identity", [1.5, True, "", " 1"])
def test_rejects_lossy_or_ambiguous_ids(tmp_path, identity):
    with pytest.raises(ValueError):
        load_edges(write_edges(tmp_path, [feature(u=identity)]))


def test_rejects_projected_geojson_crs(tmp_path):
    path = write_edges(tmp_path, [feature()])
    obj = json.loads(path.read_text())
    obj["crs"] = {"type": "name", "properties": {"name": "EPSG:2157"}}
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="crs"):
        load_edges(path)
