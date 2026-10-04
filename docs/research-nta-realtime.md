# NTA realtime research and implementation evidence

Research checked 2026-10-04. This is Person 2 data acquisition and normalization, not a journey planner. The saved gstack knowledge methods informed source verification, explicit failure states and regression testing; the gstack runtime was not executed.

## Authoritative sources

- [NTA developer portal](https://developer.nationaltransport.ie/): registration and an API subscription are required to acquire keys. No credentials are distributed with this project.
- [NTA migration notice](https://www.nationaltransport.ie/ga/news/attention-developers-upgrade-to-gtfs-realtime-api/): identifies the v2 TripUpdates URL and announces expanded rail/Luas support. An announcement is not proof of current observation coverage.
- [Current data.gov.ie realtime resource](https://data.gov.ie/dataset/nta-gtfs/resource/53190120-1aa2-4127-acff-e5645acff08b): publishes `https://api.nationaltransport.ie/gtfsr/v2/gtfsr?format=json` and states an API key is required.
- [Public developer portal configuration](https://developer.nationaltransport.ie/config.json) identifies the public Azure API metadata service.
- [Public API metadata](https://apim.nationaltransport.ie/subscriptions/000/resourceGroups/000/providers/Microsoft.ApiManagement/service/apimrtpiprodp1/apis/gtfsr?api-version=2022-04-01-preview): `subscriptionRequired: true`, subscription header `x-api-key`, API revision 2, HTTPS, and the companion [GTFS_Realtime.zip](https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip). The internal `serviceUrl` in this metadata is a backend configuration value, **not a client endpoint**.
- [Public operations metadata](https://apim.nationaltransport.ie/subscriptions/000/resourceGroups/000/providers/Microsoft.ApiManagement/service/apimrtpiprodp1/apis/gtfsr/operations?api-version=2022-04-01-preview): exactly three listed operations: `/v2/TripUpdates`, `/v2/Vehicles`, `/v2/gtfsr`. The last is explicitly described as an alternative name for TripUpdates. Thus the catalogue URL and migration URL do not describe different datasets. Each operation offers an optional JSON format parameter; this implementation consumes protobuf without that parameter.
- [NTA fair usage policy](https://developer.nationaltransport.ie/usagepolicy): one request per 60 seconds per token, provider attribution, CC BY 4.0 and data supplied as is. Do not poll each endpoint every 60 seconds independently using the same key; the limit applies across requests.
- [GTFS-Realtime reference](https://gtfs.org/documentation/realtime/reference/): protobuf entity structure, optional field presence, schedule relationships, timestamps and incrementality.
- [GTFS-Realtime best practices](https://gtfs.org/documentation/realtime/realtime-best-practices/): recommends observation age within 90 seconds for trip updates and vehicle positions; a recently refreshed feed header does not establish that each position is recent.

No official service-alert operation was listed. Alerts are normalized when present in an input feed, but no invented `/Alerts` URL is fetched. Operator descriptions in old API prose and the migration announcement differ; this pipeline makes no claim that every operator or scheduled trip supplies realtime information.

## Interface

```sh
python -m data.pipeline.gtfs_realtime fetch --output data/raw/nta-realtime --endpoint trip_updates --env-file .env
# Wait at least 60 seconds before another request using the same subscription.
python -m data.pipeline.gtfs_realtime fetch --output data/raw/nta-realtime --endpoint vehicles --env-file .env
python -m data.pipeline.gtfs_realtime normalize --input snapshot.pb --output data/processed/nta-realtime.json
```

`NTA_API_KEY` may be supplied through the process environment or an explicit ignored env file. The key is sent only in the header to the two fixed HTTPS endpoints. Redirects are rejected. No key, header or response error body is persisted or printed. There is no automatic retry or stale-cache fallback.

A durable request timestamp and file lock in the output directory coordinate both endpoints, including failed requests. All local processes using one key must share this output directory. This cannot coordinate external applications or other output directories; that remains an operational responsibility. A backwards clock prevents another request until the gate expires rather than bypassing it.

The manifest records the endpoint, receipt epoch, byte count, content type and SHA-256, with immutable raw and normalized snapshot paths. The manifest is published last and prior manifests survive failed refreshes. Downloads are bounded at 20 MiB and 30-second socket timeout. Content type, declared length and identity content encoding are checked. The timeout is a socket operation timeout, not a whole-download deadline. A downloaded stale snapshot can be archived, but its explicit state remains stale.

`normalize_feed(bytes, now=epoch, max_age_seconds=90)` emits:

- `schema_version`, `assessed_at_unix`, `freshness_policy_seconds`, raw `header` and `feed_freshness`.
- `trip_updates`, `vehicle_positions`, `alerts`: arrays of `{entity_id, data, observation_freshness, usable_as_current_observation}`.
- `data` uses protobuf snake_case field names; IDs are preserved exactly. Protobuf 64-bit integers such as timestamps are decimal strings, per protobuf JSON serialization. Optional values remain absent: absent delay is not zero delay, and explicit zero is preserved.
- `unsupported_entities` preserves parsed unhandled entities for inspection; it is not applied to routing.
- `coverage` explicitly states that missing entities mean unknown realtime information.

Trip start date/time and relationship are retained for subsequent trip-instance matching. CANCELED, SKIPPED and NO_DATA remain distinct; negative delay remains valid. No predictions are synthesized from delay-only records. Stop-sequence ordering, duplicate entity IDs and vehicle coordinate ranges are checked. This is focused ingest validation, **not full certification against every GTFS semantic rule**.

Only FULL_DATASET snapshots are supported; DIFFERENTIAL is rejected because a stateful merger would be required. A missing entity in the next FULL_DATASET must not retain an old prediction. The normalizer does not merge snapshots.

Freshness has four states: fresh, stale, future, unknown. Header and observation timestamps are assessed independently; missing observations never inherit a fresh header. `usable_as_current_observation` requires both timestamps to be fresh. It does not mean a trip operates, a stop is served, an arrival is available, or identifiers match static data. Alerts lack observation timestamps and therefore do not get that boolean; their text/selectors/active periods remain available for a future alert consumer. Future predicted arrival times are legitimate and are **not** confused with future observation timestamps. A later consumer must recompute freshness using its own current time; persisted booleans expire.

## Verification and limits

Synthetic protobuf fixtures test optional field absence versus zero, opaque IDs, independent feed/entity freshness, missing/future/stale timestamps, cancellation/skipped/no-data semantics, negative delays, alert preservation, malformed input, differential rejection, duplicate IDs, ordering, coordinates, authentication, redirect refusal, shared request gating, bounded responses, interrupted-length rejection, secret exclusion and failure preservation.

Authenticated NTA production fetches and real static/realtime identifier agreement require a provisioned key and separate recorded evidence. Passing synthetic tests does not establish live coverage, live response content type, service availability, or working multimodal routing. Review the project validation document for the latest executed evidence.

## Pinned protobuf schema boundary

`gtfs-realtime-bindings==1.0.0` does not implement every field and enum in the current GTFS-Realtime specification. In particular, the current reference includes TripDescriptor `DELETED=7` and `NEW=8`, while these pinned bindings do not. Proto2 can silently preserve an unknown wire enum but expose the default `SCHEDULED` when read, and omit the unsupported enum from JSON. That would misrepresent a deleted or newly introduced trip.

The normalizer therefore recursively inspects protobuf unknown fields and **rejects the entire snapshot** if it encounters unsupported wire fields or enum values, including newer extensions. It does not silently default them. Tests inject the actual wire values 7 and 8, first demonstrate the dangerous binding default, then verify rejection. An unsupported live feed requires a reviewed schema/dependency upgrade before it can be normalized. Supporting the protocol's version string `2.0` does not claim support for every subsequent field added under that version. Failed normalization does not publish a new accepted snapshot or replace the previous manifest.

Additional failure-path checks prevent the standalone normalization command from overwriting its raw protobuf input, and sanitize malformed HTTP status/chunked-transfer exceptions without exposing upstream text.
