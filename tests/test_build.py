"""Cross-module tests protect the actual routing-team handoff and failure paths."""
import csv
import json
from pathlib import Path

import pytest

from data.pipeline.build import atomic_json, build_bundle, load_scores, main
from data.pipeline.edges import file_sha256

EXAMPLE = Path(__file__).parent / "fixtures" / "edges.example.geojson"


@pytest.fixture
def raw_sources(tmp_path):
    sources = {
        "lighting": [["ID", "unit_type", "latitude", "longitude"],
                     ["fixture-light", "fixture", 53.34662, -6.25982]],
        "footfall_counts": [["Time", "Fixture Pedestrians", "Fixture Pedestrians IN", "Fixture Pedestrians OUT"],
                            ["01/01/2026 00:00", 10, 4, 6], ["08/01/2026 00:00", 20, 8, 12]],
        "footfall_locations": [["_id", "Counter Locations", "Eco-Visio Oupput", "Latitude", "Longitude", "User Type"],
                               ["fixture-counter", "TEST ONLY", "Fixture Pedestrians", 53.34662, -6.25982, "Pedestrians"]],
    }
    for name, rows in sources.items():
        path = tmp_path / f"{name}.csv"
        with path.open("w", newline="") as handle:
            csv.writer(handle).writerows(rows)
        (tmp_path / f"{name}.manifest.json").write_text(json.dumps({
            "source": name, "sha256": file_sha256(path), "source_url": "test fixture, not public data"}))
    return tmp_path


def test_real_pipeline_contract_missing_data_and_reverse_edges(raw_sources, tmp_path):
    bundle = build_bundle(EXAMPLE, raw_sources, weekday=3, hour=0)
    output = tmp_path / "scores.json"
    atomic_json(output, bundle)
    scores = load_scores(output, EXAMPLE, weekday=3, hour=0)
    assert len(scores) == 4
    dublin, reverse, cork, belfast = bundle["edges"]
    assert dublin["lighting_score"] == pytest.approx(reverse["lighting_score"])
    assert 0 < dublin["lighting_data_coverage_fraction"] < 0.3
    assert 0.8 < dublin["footfall_coverage_fraction"] < 1
    assert dublin["expected_pedestrians_per_hour"] == 15
    for row in (cork, belfast):
        assert row["has_lighting_data"] is False
        assert row["has_footfall_data"] is False
        assert row["lighting_score"] is None and row["footfall_score"] is None
    assert bundle["time_slice"]["timezone_verified"] is False
    assert bundle["footfall_profiles"]["counters"][0]["bins"][0]["sample_count"] == 2
    assert bundle["sources"]["lighting"]["sha256"] == file_sha256(raw_sources / "lighting.csv")


def test_consumer_rejects_wrong_graph_and_wrong_time(raw_sources, tmp_path):
    output = tmp_path / "scores.json"
    atomic_json(output, build_bundle(EXAMPLE, raw_sources, weekday=3, hour=0))
    with pytest.raises(ValueError, match="Time slice"):
        load_scores(output, EXAMPLE, weekday=4, hour=0)
    other_graph = tmp_path / "graph.geojson"
    other_graph.write_text(EXAMPLE.read_text() + "\n")
    with pytest.raises(ValueError, match="fingerprint"):
        load_scores(output, other_graph, weekday=3, hour=0)


def test_changed_source_rejected_before_scores_are_produced(raw_sources):
    with (raw_sources / "lighting.csv").open("a") as handle:
        handle.write("changed")
    with pytest.raises(ValueError, match="checksum"):
        build_bundle(EXAMPLE, raw_sources, weekday=3, hour=0)


def test_cli_failure_preserves_previous_good_output(raw_sources, tmp_path, capsys):
    output = tmp_path / "scores.json"
    output.write_text("previous-good-output")
    with pytest.raises(SystemExit) as result:
        main(["--edges", str(EXAMPLE), "--raw-dir", str(raw_sources), "--output", str(output),
              "--weekday", "7", "--hour", "0"])
    assert result.value.code == 2
    assert "weekday" in capsys.readouterr().err
    assert output.read_text() == "previous-good-output"


def test_cli_success_and_cannot_overwrite_input(raw_sources, tmp_path, capsys):
    output = tmp_path / "scores.json"
    command = ["--edges", str(EXAMPLE), "--raw-dir", str(raw_sources), "--weekday", "3", "--hour", "0"]
    assert main(command + ["--output", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["edge_count"] == 4
    assert load_scores(output, EXAMPLE, weekday=3, hour=0)
    with pytest.raises(SystemExit):
        main(command + ["--output", str(raw_sources / "lighting.csv")])


def test_atomic_writer_refuses_nonfinite_values_without_replacing_file(tmp_path):
    output = tmp_path / "scores.json"
    output.write_text("old")
    with pytest.raises(ValueError):
        atomic_json(output, {"score": float("nan")})
    assert output.read_text() == "old"


def test_missing_time_profile_remains_unknown(raw_sources):
    bundle = build_bundle(EXAMPLE, raw_sources, weekday=3, hour=1)
    assert bundle["edges"][0]["lighting_score"] is not None
    assert bundle["edges"][0]["footfall_score"] is None
    assert not bundle["edges"][0]["has_footfall_data"]


@pytest.mark.parametrize("field,value", [
    ("lighting_data_coverage_fraction", 12), ("footfall_coverage_fraction", -5),
    ("length_m", -10), ("length_m", 500), ("has_lighting_data", False),
    ("lighting_score", None), ("footfall_sample_count", 0),
    ("expected_pedestrians_per_hour", float("nan")), ("footfall_counter_id", None),
    ("lighting_proximity_fraction", 12), ("lighting_proximity_fraction", 0.6),
    ("lighting_density_per_km", -1), ("lighting_asset_count", 1.5),
    ("lighting_buffer_m", 0), ("lighting_coverage_basis", "assumed"),
    ("footfall_counter_distance_m", -1), ("footfall_score", 98),
])
def test_consumer_rejects_corrupt_confidence_and_observations(raw_sources, tmp_path, field, value):
    bundle = build_bundle(EXAMPLE, raw_sources, weekday=3, hour=0)
    bundle["edges"][0][field] = value
    output = tmp_path / "corrupt.json"
    output.write_text(json.dumps(bundle))
    with pytest.raises(ValueError):
        load_scores(output, EXAMPLE, weekday=3, hour=0)
