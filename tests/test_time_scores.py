"""Departure slots, evidence preservation and corrupt-input handoff checks."""
import copy
import json
from datetime import datetime

import pytest

from data.pipeline.build import atomic_json, build_bundle
from data.pipeline.time_scores import departure_slot, load_time_scores
from test_build import EXAMPLE, raw_sources


@pytest.fixture
def snapshot(raw_sources, tmp_path):
    document = build_bundle(EXAMPLE, raw_sources, weekday=3, hour=0)
    path = tmp_path / "scores.json"
    atomic_json(path, document)
    return path, document


def test_evaluate_new_slot_keeps_lighting_and_original_file(snapshot):
    path, document = snapshot
    before = path.read_bytes()
    original, _ = load_time_scores(path, EXAMPLE)
    rows, slot = load_time_scores(path, EXAMPLE, departure_time=datetime.fromisoformat("2026-01-01T01:00:00+00:00"))
    assert slot == {"weekday": 3, "hour": 1, "timezone": "Europe/Dublin", "timezone_verified": False}
    assert path.read_bytes() == before
    for identity, row in rows.items():
        assert row["lighting_score"] == original[identity]["lighting_score"]
        assert row["footfall_score"] is None
        assert not row["has_footfall_data"]
        assert row["footfall_sample_count"] == 0


def test_selects_new_counter_when_original_has_no_bin(snapshot):
    path, document = snapshot
    other = copy.deepcopy(document["footfall_profiles"]["counters"][0])
    other["counter_id"] = "second"
    other["bins"] = [{"weekday": 3, "hour": 1, "mean_count": 1000, "sample_count": 4}]
    document["footfall_profiles"]["counters"].append(other)
    atomic_json(path, document)
    rows, _ = load_time_scores(path, EXAMPLE, departure_time=datetime.fromisoformat("2026-01-01T01:00:00+00:00"))
    row = next(iter(rows.values()))
    assert row["footfall_counter_id"] == "second"
    assert row["footfall_score"] == 100
    assert row["footfall_sample_count"] == 4


@pytest.mark.parametrize("stamp,slot", [
    ("2026-06-07T23:30:00+00:00", (0, 0)),  # Monday after Dublin summer offset
    ("2026-01-01T00:30:00+01:00", (2, 23)),
    ("2026-10-25T00:30:00+00:00", (6, 1)),
    ("2026-10-25T01:30:00+00:00", (6, 1)),
    ("2026-03-29T01:30:00+00:00", (6, 2)),
])
def test_offset_and_dst_conversion(stamp, slot):
    assert departure_slot(datetime.fromisoformat(stamp)) == slot


@pytest.mark.parametrize("value", [datetime(2026, 1, 1), "2026-01-01", 0])
def test_rejects_naive_or_non_datetime(value):
    with pytest.raises(ValueError, match="timezone-aware"):
        departure_slot(value)


@pytest.mark.parametrize("mutation", [
    lambda d: d["footfall_profiles"]["counters"].append(d["footfall_profiles"]["counters"][0]),
    lambda d: d["footfall_profiles"]["counters"][0]["bins"].append(d["footfall_profiles"]["counters"][0]["bins"][0]),
    lambda d: d["footfall_profiles"]["counters"][0]["bins"][0].update(mean_count=-1),
    lambda d: d["footfall_profiles"]["counters"][0]["bins"][0].update(sample_count=True),
    lambda d: d["footfall_profiles"]["counters"][0].update(latitude=100),
    lambda d: d["footfall_profiles"]["source_sha256"].update(counts="0" * 64),
    lambda d: d["parameters"].update(footfall_radius_m=True),
    lambda d: d["footfall_profiles"].update(timezone_verified=True),
    lambda d: d["footfall_profiles"].update(schema_version=True),
    lambda d: d["footfall_profiles"].update(source_sha256=None),
    lambda d: d.update(sources=None),
    lambda d: d.update(parameters=None),
    lambda d: d.update(graph=None),
    lambda d: d.update(schema_version=True),
    lambda d: d["edges"][0].update(lighting_score=999),
    lambda d: d["edges"].pop(),
    lambda d: d["graph"].update(sha256="0" * 64),
])
def test_rejects_invalid_profiles_or_snapshot(snapshot, mutation):
    path, document = snapshot
    mutation(document)
    atomic_json(path, document)
    with pytest.raises(ValueError):
        load_time_scores(path, EXAMPLE, departure_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"))


def test_routing_loader_enforces_full_edge_contract(snapshot):
    from backend.routing.scores import load_edge_scores
    path, document = snapshot
    document["edges"][0]["has_lighting_data"] = False
    atomic_json(path, document)
    with pytest.raises(ValueError, match="Inconsistent"):
        load_edge_scores(path, EXAMPLE)


def test_routing_loader_uses_requested_slot(snapshot):
    from backend.routing.scores import load_edge_scores
    from data.pipeline.edges import file_sha256
    path, document = snapshot
    graph = json.loads(EXAMPLE.read_text())
    edge_path = path.parent / "integer-edges.geojson"
    names = {}
    for feature, row in zip(graph["features"], document["edges"]):
        for field in ("u", "v"):
            name = row[field]
            names.setdefault(name, str(len(names) + 1))
            row[field] = feature["properties"][field] = names[name]
    edge_path.write_text(json.dumps(graph))
    document["graph"]["sha256"] = file_sha256(edge_path)
    atomic_json(path, document)
    original = load_edge_scores(path, edge_path)
    adjusted = load_edge_scores(path, edge_path, departure_time=datetime.fromisoformat("2026-01-01T01:00:00+00:00"))
    assert any(score.activity is not None for score in original.scores.values())
    assert all(score.activity is None for score in adjusted.scores.values())
    assert adjusted.time_slice["hour"] == 1


def test_routing_loader_rejects_naive_departure_without_bundle(tmp_path):
    from backend.routing.scores import load_edge_scores
    with pytest.raises(ValueError, match="timezone-aware"):
        load_edge_scores(tmp_path / "absent.json", departure_time=datetime(2026, 1, 1))


def test_re_evaluation_of_original_slot_matches_snapshot(snapshot):
    path, _ = snapshot
    original, original_slot = load_time_scores(path, EXAMPLE)
    evaluated, slot = load_time_scores(path, EXAMPLE, departure_time=datetime.fromisoformat("2026-01-01T00:30:00+00:00"))
    assert evaluated == original
    assert slot == original_slot
