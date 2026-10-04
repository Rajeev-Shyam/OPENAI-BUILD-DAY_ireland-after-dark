"""Cross-module transport handoff, using visibly synthetic GTFS/protobuf inputs."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from google.transit import gtfs_realtime_pb2 as pb

from data.pipeline.gtfs import build_gtfs
from data.pipeline.gtfs_realtime import ENDPOINTS, normalize_feed
from data.pipeline.nta_download import registry
from data.pipeline.transport import audit_links, audit_snapshot, build_from_manifest, export_stops, main


@pytest.fixture
def static(tmp_path):
    files = {
        "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nA,Synthetic,https://example.org,Europe/Dublin\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n001,First,53.34,-6.26,0,\n002,Last,53.35,-6.27,0,\n003,Other,53.36,-6.28,0,\nstation,Station,53.34,-6.26,1,\nnode,,,,3,station\n",
        "routes.txt": "route_id,agency_id,route_short_name,route_type\n01,A,1,3\n02,A,2,3\n",
        "trips.txt": "route_id,service_id,trip_id\n01,WK,0001\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n0001,24:50:00,24:51:00,001,2\n0001,25:10:00,25:10:00,002,10\n",
        "calendar_dates.txt": "service_id,date,exception_type\nWK,20261004,1\n",
    }
    archive = tmp_path / "synthetic.zip"
    with ZipFile(archive, "w") as z:
        for name, body in files.items():
            z.writestr(name, body)
    db = tmp_path / "synthetic.sqlite"
    build_gtfs(archive, db, source_id="synthetic_test_fixture")
    return db, archive


def wire_feed():
    feed = pb.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1000
    update = feed.entity.add(id="synthetic-entity").trip_update
    update.trip.trip_id = "0001"
    update.trip.route_id = "01"
    update.timestamp = 995
    update.stop_time_update.add(stop_sequence=2, stop_id="001").arrival.delay = 0
    return feed


def test_static_points_keep_ids_axes_and_explicit_coverage_limits(static, tmp_path):
    db, _ = static
    output = tmp_path / "points.geojson"
    metadata = export_stops(db, output)
    document = json.loads(output.read_text())
    assert metadata["feature_count"] == 4
    assert metadata["records_without_coordinates"] == 1
    assert document["features"][0]["id"] == "001"
    assert document["features"][0]["geometry"]["coordinates"] == [-6.26, 53.34]
    assert "not evidence" in metadata["limitations"]


def test_static_manifest_build_uses_verified_snapshot_and_refuses_changed_bytes(static, tmp_path):
    _, archive = static
    source = "nta_gtfs_luas"
    manifest = {"schema_version": 1, "source": source, "source_url": registry()[source]["url"],
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "snapshot": archive.name}
    (tmp_path / (source + ".manifest.json")).write_text(json.dumps(manifest))
    output = tmp_path / "from-manifest.sqlite"
    assert build_from_manifest(source, tmp_path, output)["source_id"] == source
    archive.write_bytes(b"tampered")
    previous = output.read_bytes()
    with pytest.raises(ValueError, match="checksum"):
        build_from_manifest(source, tmp_path, output)
    assert output.read_bytes() == previous


def test_exact_pairing_and_freshness_reassessed_when_report_is_read(static):
    normalized = normalize_feed(wire_feed().SerializeToString(), now=1000)
    report = audit_links(static[0], normalized, now=1000)
    assert report["counts"]["matched_identifiers"] == 1
    assert report["entities"][0]["fresh_observation"] is True
    later = audit_links(static[0], normalized, now=1200)
    assert later["feed_freshness"]["status"] == "stale"
    assert later["entities"][0]["fresh_observation"] is False


@pytest.mark.parametrize("kind,expected", [
    ("trip", "trip_id_not_in_static"), ("route", "trip_route_mismatch"),
    ("stop", "stop_id_sequence_mismatch"), ("sequence", "stop_sequence_not_on_trip"),
    ("id-only", "stop_id_not_on_trip"), ("dynamic", "dynamic_trip_not_in_static"),
])
def test_unmatched_or_inconsistent_ids_never_silently_join(static, kind, expected):
    feed = wire_feed()
    update = feed.entity[0].trip_update
    if kind in {"trip", "dynamic"}:
        update.trip.trip_id = "absent"
        if kind == "dynamic":
            update.trip.schedule_relationship = pb.TripDescriptor.ADDED
    elif kind == "route":
        update.trip.route_id = "02"
    elif kind == "sequence":
        update.stop_time_update[0].stop_sequence = 9
    else:
        update.stop_time_update[0].stop_id = "003"
        if kind == "id-only":
            update.stop_time_update[0].ClearField("stop_sequence")
    report = audit_links(static[0], normalize_feed(feed.SerializeToString(), now=1000), now=1000)
    assert report["counts"]["unresolved_identifiers"] == 1
    assert expected in report["entities"][0]["issues"]


def test_cancellation_is_preserved_without_claiming_boardability(static):
    feed = wire_feed()
    feed.entity[0].trip_update.trip.schedule_relationship = pb.TripDescriptor.CANCELED
    report = audit_links(static[0], normalize_feed(feed.SerializeToString(), now=1000), now=1000)
    assert report["entities"][0]["schedule_relationship"] == "CANCELED"
    assert any("boardable" in message for message in report["limitations"])


def test_alert_selector_unknown_and_vehicle_stop_optional(static):
    feed = wire_feed()
    feed.entity.add(id="alert").alert.informed_entity.add(route_id="missing")
    vehicle = feed.entity.add(id="vehicle").vehicle
    vehicle.trip.trip_id = "0001"
    report = audit_links(static[0], normalize_feed(feed.SerializeToString(), now=1000), now=1000)
    by_id = {row["entity_id"]: row for row in report["entities"]}
    assert by_id["vehicle"]["identifier_status"] == "matched"
    assert by_id["vehicle"]["fresh_observation"] is False
    assert by_id["alert"]["issues"] == ["route_id_not_in_static"]
    assert by_id["alert"]["active_period_evaluated"] is False


def test_audit_manifest_revalidates_raw_hash_and_does_not_trust_saved_normalization(static, tmp_path):
    raw = tmp_path / "snapshot.pb"
    raw.write_bytes(wire_feed().SerializeToString())
    manifest = {"schema_version": 1, "source_url": ENDPOINTS["trip_updates"], "snapshot": raw.name,
                "bytes": raw.stat().st_size, "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "feed_freshness": {"status": "fresh"}}
    manifest_path = tmp_path / "trip_updates.manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    output = tmp_path / "audit.json"
    report = audit_snapshot(static[0], manifest_path, output, now=1200)
    assert report["feed_freshness"]["status"] == "stale"
    previous = output.read_bytes()
    raw.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        audit_snapshot(static[0], manifest_path, output, now=1200)
    assert output.read_bytes() == previous


def test_cli_stop_export_and_protect_input(static, tmp_path, capsys):
    output = tmp_path / "stops.json"
    main(["stops", "--database", str(static[0]), "--output", str(output)])
    assert json.loads(capsys.readouterr().out)["feature_count"] == 4
    with pytest.raises(SystemExit):
        main(["stops", "--database", str(static[0]), "--output", str(static[0])])


def test_audit_reports_missing_stop_reference_even_in_pre_normalized_document(static):
    document = normalize_feed(wire_feed().SerializeToString(), now=1000)
    document["trip_updates"][0]["data"]["stop_time_update"] = [{}]
    report = audit_links(static[0], document, now=1000)
    assert "stop_reference_absent" in report["entities"][0]["issues"]
