import csv
import pytest
from shapely.geometry import LineString

from data.pipeline.footfall import PROJECT, build_profiles, match_footfall


def fixture_files(tmp_path, rows, series="Aston Quay/Fitzgeralds", location_name=None):
    counts, locations = tmp_path / "counts.csv", tmp_path / "locations.csv"
    with counts.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Time", series, series + " IN", series + " OUT"])
        writer.writerows(rows)
    with locations.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["_id", "Counter Locations", "Eco-Visio Oupput", "Latitude", "Longitude", "User Type"])
        writer.writerow(["5", "Aston Quay", location_name or series, 53.34662, -6.25982, "Pedestrians"])
    return counts, locations


def test_observed_means_not_sum_of_total_and_directions(tmp_path):
    p = build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 10, 4, 6],
                                                ["08/01/2026 00:00", 20, 8, 12],
                                                ["15/01/2026 00:00", "", "", ""]]))
    assert p["counters"][0]["bins"] == [{"weekday": 3, "hour": 0, "mean_count": 15, "sample_count": 2}]
    assert p["timezone_verified"] is False


def test_genuine_zero_and_missing_remain_distinct(tmp_path):
    p = build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 0, 0, 0],
                                                ["01/01/2026 01:00", "", 3, ""]]))
    assert p["counters"][0]["bins"] == [{"weekday": 3, "hour": 0, "mean_count": 0, "sample_count": 1}]


def test_zero_day_filter_is_conservative_and_configurable(tmp_path):
    rows = [[f"01/01/2026 {hour:02}:00", 0, 0, 0] for hour in range(24)]
    files = fixture_files(tmp_path, rows)
    p = build_profiles(*files)
    assert p["counters"][0]["bins"] == []
    assert p["counters"][0]["quality"]["excluded_full_zero_days"] == ["2026-01-01"]
    assert len(build_profiles(*files, exclude_full_zero_days=False)["counters"][0]["bins"]) == 24


def test_duplicate_and_dst_hours_quarantined(tmp_path):
    p = build_profiles(*fixture_files(tmp_path, [["29/03/2026 02:00", "", "", ""],
                                                ["29/03/2026 02:00", 10, 4, 6],
                                                ["29/03/2026 01:00", 12, 5, 7],
                                                ["25/10/2026 01:00", 12, 5, 7],
                                                ["29/03/2026 03:00", 10, 4, 6]]))
    assert p["diagnostics"]["excluded_timestamp_rows"] == 4
    assert p["counters"][0]["bins"] == [{"weekday": 6, "hour": 3, "mean_count": 10, "sample_count": 1}]


@pytest.mark.parametrize("count", ["-1", "nan", "1.5", "offline"])
def test_invalid_counts_rejected(tmp_path, count):
    with pytest.raises(ValueError, match="Invalid pedestrian count"):
        build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", count, 0, 0]]))


def test_cyclist_series_rejected_even_when_mapped(tmp_path):
    with pytest.raises(ValueError, match="cyclist"):
        build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 10, 4, 6]], series="Aston Quay Cyclists"))


def test_no_fuzzy_matching(tmp_path):
    with pytest.raises(ValueError, match="No pedestrian total"):
        build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 10, 4, 6]], location_name="Aston Quay"))


def test_total_direction_mismatch_is_not_trusted(tmp_path):
    p = build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 99, 4, 6]]))
    assert not p["counters"][0]["bins"]
    assert p["counters"][0]["quality"]["total_direction_mismatches"] == 1


def test_partial_edge_support_and_missing_time_slot(tmp_path):
    p = build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 10, 4, 6]]))
    x, y = PROJECT.transform(-6.25982, 53.34662)
    edge = LineString([(x, y), (x + 1000, y)])
    result = match_footfall(edge, p, 3, 0)
    assert result["has_footfall_data"]
    assert result["footfall_coverage_fraction"] == pytest.approx(0.1)
    assert result["expected_pedestrians_per_hour"] == 10
    assert 0 < result["footfall_score"] < 100
    missing = match_footfall(edge, p, 3, 1)
    assert not missing["has_footfall_data"]
    assert missing["footfall_score"] is None
    assert missing["expected_pedestrians_per_hour"] is None


def test_outside_counter_support_unknown(tmp_path):
    p = build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 10, 4, 6]]))
    x, y = PROJECT.transform(-8.47, 51.90)
    result = match_footfall(LineString([(x, y), (x + 100, y)]), p, 3, 0)
    assert not result["has_footfall_data"]
    assert result["footfall_coverage_fraction"] == 0


def test_invalid_query_and_geometry_rejected(tmp_path):
    p = build_profiles(*fixture_files(tmp_path, [["01/01/2026 00:00", 10, 4, 6]]))
    edge = LineString([(0, 0), (100, 0)])
    with pytest.raises(ValueError):
        match_footfall(edge, p, 7, 0)
    with pytest.raises(ValueError):
        match_footfall(edge, p, True, 0)
    with pytest.raises(ValueError):
        match_footfall(edge, p, 3, 0, radius_m=float("nan"))
    with pytest.raises(ValueError):
        match_footfall(LineString([(0, 0), (0, 0)]), p, 3, 0)
