# NTA public transport and realtime: data handoff v1

This extends Person 2's data pipeline at the user's request. It supplies timetable
tables, static map points and observed realtime entities for the transport/API
team. It does not implement multimodal routing, estimated outdoor waiting,
Wait-or-Walk, delay propagation or emergency features.

## Responsibilities and files

| Workstream | Implementation | Verification |
| --- | --- | --- |
| Official sources and acquisition | `nta-sources.json`, `nta_download.py` | Publisher links, licences, bounded streamed downloads, archive CRCs/hashes, atomic cache |
| Static timetable processing | `gtfs.py` | Real NTA archives, identity/reference checks, stop hierarchy, service calendars and overnight times |
| Realtime acquisition/normalization | `gtfs_realtime.py` | Official metadata, protocol/HTTP tests and successful authenticated snapshots; partial identifier mismatches documented |
| Integration and review | `credentials.py`, `transport.py` | Manifest-checked build, stop GeoJSON, exact static/realtime identifier audit, cross-agent regressions |

Research evidence is in [sources](research-nta-sources.md),
[static processing](research-nta-static.md) and
[realtime](research-nta-realtime.md). See [validation status](nta-validation.md)
for actual executed evidence and open gates. The local gstack knowledge library's
review and test-value methods were used; its executable runtime was not run.

## Static acquisition and processing

From the repository root, using the existing virtual environment:

```sh
.venv/bin/python -m pip install -r requirements-data.txt
.venv/bin/python -m data.pipeline.nta_download --source nta_gtfs_realtime --refresh
.venv/bin/python -m data.pipeline.transport build \
  --source nta_gtfs_realtime \
  --output data/processed/nta/nta_gtfs_realtime.sqlite
.venv/bin/python -m data.pipeline.transport stops \
  --database data/processed/nta/nta_gtfs_realtime.sqlite \
  --output data/processed/nta/nta_gtfs_realtime_stops.geojson
```

The default download directory is `data/raw/nta`. Registry choices:

| Source ID | Publisher archive | Purpose |
| --- | --- | --- |
| `nta_gtfs_realtime` | `GTFS_Realtime.zip` | **Static** timetable companion identified by NTA for realtime joins |
| `nta_gtfs_all` | `GTFS_All.zip` | Broader published operator timetable coverage |
| `nta_gtfs_luas` | `GTFS_LUAS.zip` | Luas-only timetable; small reproducible source check |

Use the same source ID for download and build. All three are static ZIP feeds;
the word “Realtime” in the companion archive name does not make its contents live.
The all-operator database is useful for broader schedules, but do not assume that
its IDs are compatible with a realtime snapshot merely because names match.

Each download records original/resolved URLs, SHA-256, byte count, HTTP metadata,
retrieval time, CC BY 4.0 attribution and archive members in `<source>.manifest.json`.
The referenced `snapshots/<source>-<sha>.zip` is immutable by content identity;
the named ZIP is a convenience alias. `transport build` verifies that manifest
against the registry and archive hash before using the immutable snapshot.

Without `--refresh`, verified cached snapshots are reused offline. **Refresh
before pairing with current realtime:** NTA says schedule IDs may change between
generations. No automatic refresh daemon is installed. HTTP modification times,
publisher `feed_info` dates and actual service calendars are different facts.
An intact old archive is suitable for reproducible historical testing, not proof
of current service. Refresh failures preserve the previous valid snapshot.

Defaults bound downloads to 512 MiB compressed and 4 GiB expanded. ZIP members
are read in place, never extracted. Static import uses batches and a disk-backed
SQLite database. Large feeds need disk space for the archive, immutable copy,
database, and temporary replacement during rebuilds. Atomic publication retains
the old database until the new one passes validation.

## SQLite contract

`metadata(key TEXT PRIMARY KEY, value TEXT)` stores JSON-encoded values, including
`schema_version=1`, `source_id`, `source_url`, `archive_sha256`, `row_counts`,
`table_columns`, `agency_timezones`, calendar bounds, QA results and a complete
`report`. These are processed datasets, not SQL migrations for an application DB.

| Table | Preserved data / keys |
| --- | --- |
| `agency` | Names, source timezones and opaque agency IDs |
| `stops` | Source IDs, coordinates, names, location types and parent relationships |
| `routes` | Route IDs, agency references, mode/type and source display fields |
| `trips` | Trip IDs, route/service IDs, directions, headsigns and shape references |
| `stop_times` | `(trip_id, stop_sequence)`, stop IDs, pickup/drop-off fields and source times |
| `calendar` | Weekday service flags and date range |
| `calendar_dates` | Explicit service additions/removals on dates |
| `shapes` | `(shape_id, shape_pt_sequence)` and shape coordinates when supplied |
| `feed_info` | Publisher metadata, version and feed date fields when supplied |

Original supported-table columns are retained, with missing optional columns
needed by consumers supplied as empty strings. IDs remain strings, including
leading zeroes. Stop and shape sequences are integers. Derived
`arrival_seconds`/`departure_seconds` are service-day seconds; source time strings
also remain available. `25:10:00` means 90,600 service-day seconds, not 01:10 on
the same service date and not a Unix timestamp. Unknown intermediate times remain
SQL NULL and are not interpolated.

Use `active_services(database, "YYYYMMDD")` for calendar flags plus exceptions.
It does not select a next departure. Journey queries must consider the previous
service day for after-midnight trips and apply the [GTFS service-day time
definition](https://gtfs.org/documentation/schedule/reference/#stop_timestxt),
including DST, before converting to UTC. Preserve the published agency timezone:
the inspected NTA archives specify `Europe/London`; this pipeline does not replace
it with a guessed value.

Nonempty frequency-based service is rejected rather than presenting template
times as departures. Transfers, fares, pathways, translations and GTFS Flex are
not interpreted; unprocessed files are listed in metadata. Core integrity checks
are not certification against the entire GTFS standard.

## Static stop GeoJSON

`transport stops` exports geolocated source records as WGS84 `[longitude, latitude]`
Points with exact `stop_id`, `stop_name`, `location_type`, `parent_station`.
`location_type` distinguishes a boarding location from a station, entrance or
other record; consumers must not treat every point as a boardable bus stop.
The FeatureCollection metadata includes source ID/hash, attribution, point count
and the count skipped for missing coordinates. It says nothing about service now,
public shelter, lighting, accessibility or realtime coverage. Other source stop
attributes remain available in SQLite.

## Realtime access

Obtain your own subscription through the [NTA developer portal](https://developer.nationaltransport.ie/).
Set `NTA_API_KEY` in the process environment, or put a literal assignment in the
project's ignored `.env` file and pass `--env-file .env`. `.env.example` contains
an empty placeholder. The loader reads only that key, never executes the file,
and prefers an existing environment variable. Keep a key out of command arguments,
commits and client-side code.

```sh
.venv/bin/python -m data.pipeline.gtfs_realtime fetch \
  --endpoint trip_updates --output data/raw/nta/realtime --env-file .env
```

After at least 60 seconds, the same client may fetch vehicle positions:

```sh
.venv/bin/python -m data.pipeline.gtfs_realtime fetch \
  --endpoint vehicles --output data/raw/nta/realtime --env-file .env
```

The confirmed public URLs are
`https://api.nationaltransport.ie/gtfsr/v2/TripUpdates` and
`https://api.nationaltransport.ie/gtfsr/v2/Vehicles`, using the `x-api-key` header.
The catalogue's `/v2/gtfsr` URL is an alternate name for TripUpdates according to
the official operations metadata. This client requests protobuf, without the
optional `format=json` parameter. No separate alerts endpoint was verified.

NTA's published [fair-usage policy](https://developer.nationaltransport.ie/usagepolicy)
limits requests to one per 60 seconds per token. Both endpoints and failures share
a durable gate in the output directory. All local callers using a key must use the
same directory; external clients need separate operational coordination. There
are no automatic retries, polling daemon or stale-cache fallback. The gate uses
`fcntl` file locking: this client targets macOS/Linux (Windows users need WSL or
an equivalent supported environment). Authentication redirects are rejected.

Each successful fetch publishes an endpoint manifest pointing to raw `.pb` and
normalized `.json` snapshots, with source URL, receive time, hash, byte count and
freshness assessment. A failed fetch does not replace the last successful
manifest. Old files remain historical records, not automatically current data.

## Normalized realtime contract

Schema v1 includes `header`, `assessed_at_unix`, `freshness_policy_seconds`,
`feed_freshness`, `trip_updates`, `vehicle_positions`, `alerts`,
`unsupported_entities` and an explicit absence-is-unknown coverage statement.
Each entity wrapper has `entity_id`, `data`, `observation_freshness` and
`usable_as_current_observation`. `data` preserves GTFS protobuf snake_case fields;
64-bit integers serialize as decimal strings. Optional absence stays absent:
missing delay is not zero, while an explicitly observed zero delay remains zero.

`CANCELED`, stop `SKIPPED`, stop `NO_DATA`, delays (including negative ones),
absolute event times, trip start date/time and alert text/selectors/active periods
remain distinct. No new predictions are calculated from them. Only FULL_DATASET
snapshots are accepted; DIFFERENTIAL needs an unimplemented stateful merger.
Do not carry absent entities forward as if they were present in the next snapshot.

The pinned official `gtfs-realtime-bindings==1.0.0` schema does not include every
later GTFS addition. Unknown protobuf wire fields/enums are rejected recursively
before normalization. This includes newer `DELETED`/`NEW` trip relationships:
otherwise protobuf could silently omit the unrecognized value and a consumer
could default it to `SCHEDULED`. A feed using newer fields needs an updated,
reviewed schema dependency before it can be ingested. This fail-closed boundary
may reject valid newer feeds; it is not a claim of supporting all current GTFS-RT.

The default freshness policy is 90 seconds, based on [GTFS realtime best-practice
guidance](https://gtfs.org/documentation/realtime/realtime-best-practices/).
Feed and observation timestamps are assessed separately as fresh/stale/future/
unknown. A fresh header cannot make an old or missing observation fresh. Future
predicted arrival times are valid; future **observation timestamps** are flagged.
Recompute freshness whenever consuming a saved artifact. `usable_as_current_observation`
means only both timestamps passed; it does not mean a trip is operating or boardable.
Alerts have no observation timestamp and retain false for this boolean; an alert
consumer still needs to evaluate their active periods.

## Static/realtime identifier audit

```sh
.venv/bin/python -m data.pipeline.transport audit \
  --database data/processed/nta/nta_gtfs_realtime.sqlite \
  --realtime-manifest data/raw/nta/realtime/trip_updates.manifest.json \
  --output data/processed/nta/trip_update_audit.json
```

The audit rechecks the raw protobuf hash and byte count, normalizes it again at
the current time, and checks exact trip, route, stop and sequence references.
Unknown/dynamic trips and mismatches are reported instead of fuzzy-joined.
Vehicle current-stop references are optional. Alert selector IDs are checked,
but active periods are not evaluated. A match does not establish the correct
service-date/trip instance or prove static generation alignment; downstream
transport routing must implement those checks. Reports include both archive and
realtime fingerprints. Scheduled-but-unobserved trips remain unknown in realtime.

## Acceptance boundary

Static acquisition and processing have real-source evidence. Both realtime
endpoints have now passed authenticated fetches and actual identifier audits.
The [validation record](nta-validation.md) reports stale vehicle observations,
added trips and Irish Rail route-reference conflicts that remain unresolved.
These checks establish acquisition and partial identifier agreement, not complete
journey semantics. Waiting-time calculations and routing remain separate work
for the transport/API owner.
