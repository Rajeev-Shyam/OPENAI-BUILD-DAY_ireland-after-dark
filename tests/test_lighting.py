import csv

import pytest
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform

from data.pipeline.lighting import Light, clean_lights, enrich_lighting


TO_METRES = Transformer.from_crs(4326, 2157, always_xy=True).transform
TO_WGS84 = Transformer.from_crs(2157, 4326, always_xy=True).transform
X, Y = TO_METRES(-6.26, 53.35)


def edge(start=0, end=100, key="0"):
    return {"u": "123", "v": "456", "key": key,
            "geometry": transform(TO_WGS84, LineString([(X + start, Y), (X + end, Y)]))}


def light(position=50, offset=0, asset_id="1"):
    longitude, latitude = TO_WGS84(X + position, Y + offset)
    return Light(asset_id, longitude, latitude, "PL: Column")


def csv_file(tmp_path, rows):
    path = tmp_path / "lights.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ID", "site_name", "unit_no", "unit_type", "latitude", "longitude"])
        writer.writerows(rows)
    return path


def test_cleaning_reports_invalid_rows_and_deduplicates_asset_ids(tmp_path):
    row = ["1", "Street", "001", "PL: Column", "53.35", "-6.26"]
    path = csv_file(tmp_path, [row, row, ["2", "", "", "PL: Column", "nan", "-6.26"],
                              ["3", "", "", "PL: Column", "-6.26", "53.35"],
                              ["", "", "", "PL: Column", "53.35", "-6.26"]])
    lights, report = clean_lights(path)
    assert len(lights) == 1
    assert report["input_rows"] == 5
    assert report["duplicate_rows"] == 1
    assert report["rejected_rows"] == 3
    assert report["rejection_reasons"] == {"invalid_coordinates": 2, "missing_asset_id": 1}


def test_conflicting_ids_fail_without_silently_choosing_a_location(tmp_path):
    path = csv_file(tmp_path, [["1", "", "", "PL: Column", 53.35, -6.26],
                              ["1", "", "", "PL: Column", 53.36, -6.26]])
    with pytest.raises(ValueError, match="Conflicting"):
        clean_lights(path)


def test_wrong_schema_or_empty_valid_inventory_fails(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("ID,latitude,longitude\n1,53.35,-6.26\n")
    with pytest.raises(ValueError, match="missing columns"):
        clean_lights(path)
    with pytest.raises(ValueError, match="no valid assets"):
        clean_lights(csv_file(tmp_path, []))


def test_metric_distance_and_fraction_are_not_based_on_degrees():
    result = enrich_lighting([edge()], [light(), light(offset=30, asset_id="2")])[0]
    assert (result["u"], result["v"], result["key"]) == ("123", "456", "0")
    assert result["lighting_asset_count"] == 1
    assert result["lighting_density_per_km"] == pytest.approx(10, abs=1e-5)
    assert result["lighting_proximity_fraction"] == pytest.approx(0.4, abs=1e-5)
    assert result["lighting_score"] == pytest.approx(40, abs=1e-3)
    assert result["lighting_data_coverage_fraction"] == pytest.approx(0.4, abs=1e-5)
    assert result["lighting_coverage_basis"] == "recorded_asset_proximity"


def test_overlapping_or_colocated_assets_do_not_double_count_supported_length():
    results = enrich_lighting([edge()], [light(40), light(60, asset_id="2"), light(60, asset_id="3")])
    assert results[0]["lighting_asset_count"] == 3
    assert results[0]["lighting_proximity_fraction"] == pytest.approx(0.6, abs=1e-5)


def test_unknown_inventory_is_not_scored_as_unlit():
    result = enrich_lighting([edge()], [light(offset=100)])[0]
    assert result["lighting_asset_count"] == 0
    assert result["lighting_score"] is None
    assert result["lighting_density_per_km"] is None
    assert result["lighting_proximity_fraction"] is None
    assert result["has_lighting_data"] is False
    assert result["lighting_data_coverage_fraction"] == 0
    assert result["lighting_coverage_basis"] == "unknown"


def test_explicit_inventory_coverage_can_distinguish_zero_observations():
    coverage = transform(TO_WGS84, Point(X + 50, Y).buffer(500))
    result = enrich_lighting([edge()], [], coverage_geometry=coverage)[0]
    assert result["has_lighting_data"] is True
    assert result["lighting_score"] == 0
    assert result["lighting_density_per_km"] == 0
    assert result["lighting_data_coverage_fraction"] == 1
    assert result["lighting_coverage_basis"] == "declared_inventory_coverage"


def test_partial_inventory_boundary_does_not_declare_whole_edge_coverage():
    coverage = transform(TO_WGS84, Point(X, Y).buffer(30))
    result = enrich_lighting([edge()], [], coverage_geometry=coverage)[0]
    assert result["has_lighting_data"] is False
    assert result["lighting_score"] is None


def test_projected_inventory_boundary_is_rejected_instead_of_mislabelled_wgs84():
    with pytest.raises(ValueError, match="WGS84"):
        enrich_lighting([edge()], [], coverage_geometry=Point(X, Y).buffer(100))


def test_reverse_edges_and_splitting_preserve_length_weighted_proximity():
    lamps = [light(40), light(60, asset_id="2")]
    complete = enrich_lighting([edge()], lamps)[0]
    reverse = enrich_lighting([edge(100, 0)], lamps)[0]
    segments = enrich_lighting([edge(0, 50, "a"), edge(50, 100, "b")], lamps)
    assert reverse["lighting_score"] == pytest.approx(complete["lighting_score"], abs=1e-5)
    assert sum(r["lighting_score"] for r in segments) / 2 == pytest.approx(complete["lighting_score"], abs=1e-4)


@pytest.mark.parametrize("radius", [0, -1, float("nan"), float("inf")])
def test_invalid_distance_parameters_fail(radius):
    with pytest.raises(ValueError, match="buffer_m"):
        enrich_lighting([edge()], [light()], buffer_m=radius)


def test_duplicate_edges_and_projected_coordinates_fail():
    with pytest.raises(ValueError, match="Duplicate edge"):
        enrich_lighting([edge(), edge()], [light()])
    invalid = {**edge(), "geometry": LineString([(X, Y), (X + 100, Y)])}
    with pytest.raises(ValueError, match="Ireland envelope"):
        enrich_lighting([invalid], [])
    with pytest.raises(ValueError, match="LineString"):
        enrich_lighting([{**edge(), "geometry": LineString([(-6.26, 53.35)] * 2)}], [])
