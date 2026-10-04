# NTA static GTFS: research and validation

Research checked 4 October 2026. This covers Person 2's timetable ingestion handoff, not transit routing.

## Primary sources and decisions

The [NTA public transport data index](https://www.transportforireland.ie/transitData/PT_Data.html) publishes operator, all-operator and realtime-compatible static feeds. It attributes these downloads to the National Transport Authority under CC BY 4.0. It also distinguishes API registration from freely downloadable static data. Use the realtime-compatible static archive when matching realtime IDs; do not assume all-operator and individual-operator IDs are interchangeable.

The [GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/) defines identifiers, required tables, local agency timezone, service-day times and calendar exceptions. Accordingly, this pipeline preserves identifiers as strings, retains original times, and adds integer seconds that can exceed 86,400. Blank intermediate times stay unknown. Calendar exceptions override the weekday schedule. Agency timezones are validated rather than replaced with an assumed timezone. The official samples processed here declare `Europe/London`.

These design choices follow the saved gstack learning notes: reuse standard-library streaming and SQLite; test observable semantics and failure paths; record real-source evidence separately from fixture tests; replace artifacts atomically.

## Processed artifact

`python -m data.pipeline.gtfs --archive INPUT.zip --output OUTPUT.sqlite --source-id nta_gtfs_realtime --source-url URL`

Tables: `agency`, `stops`, `routes`, `trips`, `stop_times`, `calendar`, `calendar_dates`, `shapes`, `feed_info`, and `metadata`. Absent optional tables are empty. Core source columns are preserved; missing convenience columns are added with blank values. Source IDs remain TEXT. `stop_sequence` and `shape_pt_sequence` are INTEGER, as are derived `arrival_seconds` and `departure_seconds`.

`metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)` stores JSON values including schema version, source ID/URL, SHA-256 archive fingerprint, build timestamp, row counts, table columns, QA results, calendar range, uninterpreted files and limitations. Key `report` contains the complete report returned by `build_gtfs`.

`active_services(database, service_date)` accepts a local service date in YYYYMMDD format and applies calendar exceptions. It is not a departure board. A journey planner must also consider the preceding service day when interpreting times after midnight and correctly handle GTFS timezone/DST semantics; this ingestion module does not convert service seconds into UTC instants.

CSV rows stream in batches of 5,000 with a bounded SQLite cache and disk-backed temporary operations. ZIP members are read without extraction. Duplicate members, nested/traversal paths, malformed CSV, duplicate primary keys, invalid dates/times/coordinates, missing references, nonchronological trips and unknown terminal times fail the build. Existing outputs survive failed builds. Frequency-based services fail explicitly so template times cannot be mistaken for scheduled departures.

This is deliberately not a complete GTFS conformance validator. It retains source columns but does not interpret fares, transfers, pathways, accessibility routing or Flex extensions. Extra files are listed as uninterpreted. Geometry and scheduling availability must not be transformed into a personal-safety score.

## Real-source acceptance evidence

Both files below were acquired from the official index and processed locally on 4 October 2026; generated files remain outside version control.

| Feed | Archive SHA-256 | Accepted records |
| --- | --- | --- |
| [Luas](https://www.transportforireland.ie/transitData/Data/GTFS_LUAS.zip) | `5712cc24bf43958a0b08a1b055fb07dea9484b9bca021d14f59f2f41fad26761` | 1 agency, 128 stops, 2 routes, 2,935 trips, 63,488 stop times, 32,755 shape points |
| [Realtime-compatible static](https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip) | `3d103bfb5e2477691ddbb1eff7d03d4296598e58540c67f56eeb6d66e0c99a78` | 7 agencies, 10,262 stops, 402 routes, 248,284 trips, 8,153,396 stop times, 6,545,690 shape points |

The paired feed archive is 144,073,521 bytes. Its calendar range, including added dates, is 20261002–20270430. Luas's is 20261002–20261210. These are aggregate service-calendar bounds, not proof that each service runs every day in that interval, and not the same as `feed_info` publisher validity dates. Both feeds passed core reference, unique-key and chronological stop-time checks. `translations.txt` was reported as uninterpreted.

Focused tests exercise overnight times, string IDs, numeric stop ordering, calendar additions/removals and calendar-dates-only feeds, timezone validation, malformed input, unknown intermediate times, missing references, atomic rollback and frequency rejection. Real static acceptance does **not** establish realtime credentials, a successful live/static join or functioning public transport routing.

An independent review found three stop-hierarchy acceptance gaps: station centroids accepted as served platforms, invalid parent types/self-parenting, and entrances without parents. The parser now enforces served stop/platform types and GTFS parent rules across location types 0–4. Regression coverage includes valid platforms, station entrances, unlocated generic nodes and boarding areas. The strengthened complete QA routine was rerun read-only against both real processed databases; both passed. Their original archive fingerprints and processing evidence were preserved.

The production downloader and final parser also passed on the [all-operator archive](https://www.transportforireland.ie/transitData/Data/GTFS_All.zip), SHA-256 `e3915c7dd1ecce224a6cc177e7005698aa51785c358e5aa50249eb5446fe1430`: 104 agencies, 14,155 stops, 805 routes, 267,335 trips, 8,438,017 stop times, 8,700,198 shape points, 289 calendar rows and 1,927 date exceptions. Aggregate service bounds are 20261002–20271003. The archive is 179,594,769 compressed bytes, expanding to 871,521,603 bytes; the SQLite output is 1,662,906,368 bytes. All five recorded QA checks passed, including served stop types and parent hierarchy, and the source hash was rechecked before publication. Canonical local artifacts are `data/processed/nta/nta_gtfs_all.sqlite` and `nta_gtfs_all.report.json`; realtime-compatible counterparts use `nta_gtfs_realtime`. These are generated, ignored artifacts, not repository fixtures. Operator coverage and timetable presence do not establish live service availability everywhere in Ireland.
