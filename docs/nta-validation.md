# NTA validation record

Date: 4 October 2026. Scope: public-transport dataset acquisition, processing and
handoff, not a journey planner. Static source checks and realtime protocol tests
are different evidence classes and are not interchangeable.

## Executed real-source checks

All three archives were fetched through the production downloader from the
official publisher, checked for bounded/safe ZIP structure and member CRCs,
fingerprinted, and processed into SQLite. Luas additionally exercised the
manifest-driven `transport build` command. The larger all-operator and paired
archives exercised the same static parser directly with exact source IDs/URLs.

| Snapshot | Agency records | Stops | Routes | Trips | Stop times |
| --- | ---: | ---: | ---: | ---: | ---: |
| All-operator | 104 | 14,155 | 805 | 267,335 | 8,438,017 |
| Realtime-compatible static | 7 | 10,262 | 402 | 248,284 | 8,153,396 |
| Luas | 1 | 128 | 2 | 2,935 | 63,488 |

These are records observed in the inspected archives, not a count of distinct
companies or a guarantee every published service is currently running. All
timezones observed are `Europe/London`, retained without substitution. No
Translink agency was observed; neither Ireland-wide completeness nor blanket
Northern Ireland coverage is claimed.

Source hashes:

- All: `e3915c7dd1ecce224a6cc177e7005698aa51785c358e5aa50249eb5446fe1430`
- Paired static: `3d103bfb5e2477691ddbb1eff7d03d4296598e58540c67f56eeb6d66e0c99a78`
- Luas: `5712cc24bf43958a0b08a1b055fb07dea9484b9bca021d14f59f2f41fad26761`

All-operator archive: 179,594,769 compressed / 871,521,603 expanded bytes.
Paired archive: 144,073,521 compressed / 756,618,259 expanded bytes.
Source manifests and snapshots are in `data/raw/nta/`; generated SQLite files,
reports and stop layers are in `data/processed/nta/`. These payloads are Git-ignored.
The full and paired stop GeoJSON exports produced 14,155 and 10,262 points
respectively, with no missing-coordinate records in those inspected feeds.

The paired import preceded strengthened hierarchy checks; the complete amended QA
was run against that unchanged database and passed, with evidence in its sidecar
report. The all-operator and manifest-driven Luas builds ran all checks directly.
Actual service-calendar ranges differ from publisher `feed_info` dates; the
reports preserve both distinctions. These datasets are versioned snapshots, not
permanent facts about future services.

## Test and review evidence

Run the complete suite with:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

**185 tests passed**, with no pytest warnings. `pip check` reported no broken
requirements. Tested on macOS arm64 with Python 3.9.6, the existing pinned
geospatial dependencies, `gtfs-realtime-bindings==1.0.0` and `protobuf==6.33.6`.
Tests include the original lighting/footfall checks and the NTA additions:

- Download retry/limits, corrupt ZIP/path handling, CRC/hash integrity, cached
  alias repair and preservation of prior good snapshots after failures.
- Opaque IDs, overnight times, service exceptions, missing intermediate readings,
  chronological order, referential integrity, station/platform hierarchy,
  atomic SQLite output and source changes during processing.
- Realtime missing/zero/negative delays, cancellations, skipped/no-data stops,
  observation-versus-header age, future/missing timestamps, full/differential
  semantics, credentials, response limits/redaction, rate gating and redirects.
- Static/realtime route/stop/sequence mismatch reporting, dynamic/unknown trip
  identities, manifest-based handoff, map-point coordinates, output protection,
  and recomputing freshness from raw protobuf rather than trusting saved flags.

Independent reviews found and reproduced defects before they were fixed:

1. Static ingestion accepted station centroids as served stop-time locations and
   invalid parent-station relationships. The required hierarchy is now enforced;
   positive and negative regression cases cover the supported location types.
2. Realtime malformed Content-Length could leak upstream text through an exception.
   It now produces a sanitized error. Declared-length mismatch and content encoding
   are also checked before publishing a snapshot.
3. The identifier audit did not report an empty stop reference in a pre-normalized
   trip update. It now reports that unresolved reference, while keeping a vehicle's
   current-stop information optional.

4. Final review protected standalone normalization from overwriting its raw input
   and sanitized malformed HTTP status/chunked-read exceptions as network errors.
5. The pinned official protobuf bindings silently omitted newer unknown enum values,
   which could make a deleted/new trip appear to use default `SCHEDULED` semantics.
   Wire-level tests demonstrated it. Unknown fields/enums are now rejected
   recursively before normalization; newer schema features require a dependency
   upgrade and remain unsupported, rather than being misrepresented.

Synthetic protobuf records are explicitly test fixtures, not observed NTA predictions.

## Authenticated live verification — 4 October 2026

The user supplied a regenerated subscription key through the ignored local `.env`.
Both production endpoints authenticated, returned `application/protobuf`, parsed
with the pinned schema and passed checksum-backed identifier audits against the
realtime-compatible static database. Requests were spaced more than 60 seconds
apart. No credential is included in snapshots, documentation or output.

| Endpoint | Received (UTC) | Entities | Fresh observations at receipt | Stale observations | Identifier matches | Unresolved |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TripUpdates | 2026-10-04 13:14:04 | 2,304 | 2,304 | 0 | 2,227 | 77 |
| Vehicles | 2026-10-04 13:15:26 | 880 | 807 | 73 | 875 | 5 |

Feed headers were 4.59 and 5.70 seconds old at receipt, respectively. A fresh
header did not conceal stale vehicle observations. These figures describe the
recorded snapshots, not the current network or guaranteed future coverage.

TripUpdates contained 2,253 SCHEDULED, 26 ADDED and 25 CANCELED entities.
The unresolved trip updates consist of 26 ADDED entities without trip IDs and
51 scheduled Irish Rail records whose realtime route IDs conflict with their
static trip route and are absent from the paired routes table. For example,
trip `5936_8346` supplied `DUB-GALWAY-I` while its static route is `DUB-GALWAY-O`.
This is observed source disagreement, not evidence permitting a guessed direction
correction. Those references remain unresolved. All five unresolved vehicle
records are ADDED trips absent from the static timetable.

Raw snapshot SHA-256 values:

- TripUpdates: `ac97a37551a43f7bedaa2793a65d02d8f9e63787f586a3765d803c5f57dbbb7e`
- Vehicles: `7362d9120a3cb86d00149587e2af6a177f62195e32110cab26d659eb6256d8a7`

Paired static archive SHA-256:
`3d103bfb5e2477691ddbb1eff7d03d4296598e58540c67f56eeb6d66e0c99a78`.
Acquisition manifests are under `data/raw/nta/realtime/`. Audits are
`data/processed/nta/trip_update_audit.json` and `vehicle_audit.json`; their
freshness assessments are recomputed at audit time and therefore differ from
receipt ages. Local payloads remain ignored by Git.

Authentication, observed protobuf compatibility, fresh-data handling and actual
identifier auditing are now demonstrated. **Full identifier alignment is not
established:** the unmatched/dynamic records above remain explicit. Neither audit
resolves service-date/trip instances, infers live arrivals, nor demonstrates every
operator provides realtime data. Future schema additions remain subject to the
normalizer's explicit unsupported-field rejection.

## Remaining product work

The transport/API team still needs service-date and trip-instance resolution,
UTC conversion under GTFS/DST rules, delay propagation, pickup/drop-off eligibility,
connections, walking transfers and the routing/UI integration. No outdoor waiting
time, Wait-or-Walk recommendation or weather factor is calculated here. Unknown
realtime coverage must not become an “on time” or available-service claim.

Static ingestion is implemented and verified for the inspected fixed-schedule
archives. Realtime acquisition is implemented, locally tested and demonstrated against both
production endpoints. Partial identifier disagreement and downstream journey
semantics remain open. The full transport product is not marked complete.
