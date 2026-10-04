# Person 2 phase1 integration — 4 October 2026

Base: `origin/phase1` at `aa70f46`. Working branch: `feat/phase1-data-integration`.
The NTA implementation from `ac16edf` is integrated without replacing the shared
phase1 application. This document distinguishes executed data/routing checks
from application features that still belong to the other workstreams.

## Environment and reproducible acceptance

Python 3.12.15, OSMnx 2.1.1, NetworkX 3.7, Shapely 2.1.2, PyProj 3.8.0,
GTFS realtime bindings 1.0.0 and protobuf 6.33.6. `pyproject.toml` and `uv.lock`
include the NTA dependencies; the pip requirements no longer conflict.
`uv pip check` confirms all 50 installed packages are compatible.

Final shared-environment suite: **281 tests passed, plus 10 subtests** in
31.43 seconds. This includes routing, core data, NTA, time selection, context
layers, crossing evidence and the real-handoff validator's failure paths.
`git diff --check` passes. The private `.env` and generated score files remain
Git-ignored; no credentials or large downloaded payloads are included.

```sh
uv sync --frozen
uv run python -m data.pipeline.download --source all
uv run python -m backend.routing --area dublin --force
uv run python -m data.pipeline.build --edges data/raw/walking_edges.geojson --weekday 4 --hour 23
uv run python -m data.pipeline.validate_handoff
uv run python -m data.pipeline.validate_handoff --departure-time 2026-10-02T23:30:00+00:00 --output data/processed/handoff-saturday-validation.json
uv run python -m data.pipeline.context_layers all
uv run pytest -q
```

The validation command reloads the cached GraphML, reproduces its edge export,
compares the exact export fingerprint, loads the bundle through the strict
consumer guard, and checks actual route segments against their validated scores.
It rejects a different GraphML even if the original score/export pair still
matches. No network is needed for this acceptance step once inputs exist.
Generated payloads and detailed receipts remain ignored local files.

## Real Dublin handoff

The OSM graph contains **101,875 nodes and 267,580 directed keyed edges**. Every
exported edge has exactly one validated score record. Original and final graph
node IDs, keyed edge IDs and OSM routing lengths match exactly after the crossing
metadata change. The source measurements use EPSG:2157 metres; route lengths
retain Person 1's OSMnx measurements.

Friday 23:00 Europe/Dublin snapshot:

| Measurement | Observed value |
| --- | ---: |
| Edges with some recorded lighting evidence | 105,490 |
| Lighting-supported share of total edge length | 39.0731% |
| Edges with some historical activity evidence | 1,124 |
| Footfall-supported share of total edge length | 0.3238% |

The low footfall coverage is real and must remain visible in route confidence.
Unsupported observations are null, not zero; presence flags are not complete
route coverage. Source freshness, operating lamps, brightness, barriers and
footfall timestamp conventions remain limitations from the original contract.

Actual routing check from `(53.3339, -6.2632)` to `(53.3440, -6.2577)`:

| Result | Fastest | Night |
| --- | ---: | ---: |
| Distance | 1,380.3 m | 1,384.7 m |
| Estimated duration | 17.7 min | 17.8 min |
| Recorded lighting proximity/coverage | 84.6% | 87.8% |
| Historical activity evidence coverage | 5.0% | 17.3% |

Both activity scores saturate the prototype scale at 1.0 on their supported
portions; these results establish different evidence coverage, not a measured
increase in pedestrians along the route. The Night route differs by only 4.4 m;
there is no invented dramatic benefit. Status is `ok`.

Measured preparation was 17.779 seconds (graph loading/export verification,
strict score validation and routing index); the route computation then took
0.007 seconds. This single local run is not a service latency benchmark.

The explicit instant `2026-10-02T23:30:00+00:00` correctly selected Saturday
00:00 in Dublin. Full-graph activity recomputation and preparation took 44.533
seconds, followed by a 0.007-second route. The selected routes were unchanged;
time selection does not guarantee a different route. This cost reinforces the
need for batch preparation or bounded caching before HTTP integration.

- Edge export SHA-256: `cb5dfc05e08fa7694001169782b7688515eb74aaf669b4dca9fdad2b09b41c47`
- Score bundle SHA-256: `77021150d228c7de7bcf9147c755fe954e13e551628fbd7d0c1e634aa39c5365`

Bundle hashes include generated timestamps; rebuilding legitimately changes
them. These identify this run, not permanent expected fixtures.

## Review and remaining boundaries

Applied the saved gstack engineering-review and pre-landing checklist methods:
trace producer/consumer contracts, prove findings, test error paths, and preserve
failed evidence. The executable gstack runtime was not installed or invoked.

- Review caught a proposed simplify-after-truncation change that altered real
  boundary intersections. It was corrected before acceptance: the original
  OSMnx simplify-before-truncation flow is preserved. A regression test guards
  the call order; actual graph identity/length comparison confirms restoration.
- The stricter routing loader rejects corrupt scores, incomplete identities,
  incoherent coverage and graph mismatches instead of accepting plausible JSON.
- [Departure-time evaluation](time-score-contract.md) is available for batch/cache
  preparation. The HTTP API and `backend.routing.store.get_route` path still use the original
  slice. Do not tell users their time picker is connected yet.
- [Context layers](context-data.md) document verified downloads, licences,
  coverage, quarantines and current availability limitations. Verified offline
  rebuild produces 6 DLR Garda landmarks, 14 Dublin fire facilities, 1,203 SCATS
  sites (two conflicting records quarantined), and 47 Dublin hospital-tagged
  OSM features. Hospital features are not a count of unique facilities, and
  their display centres are not verified entrances. Wider Ireland hospital
  queries timed out; only the successfully downloaded Dublin bbox is shipped.
- [Crossing evidence](crossing-data.md) recognizes 1,444 directed original-way
  edges with explicit signal tags. This is not 1,444 distinct physical crossings.
  Simplified edges remain unknown. Crossing event identity and traversal-aware
  deduplication are still needed before enabling routing costs or confidence.
- NTA acquisition/parsing/QA remains as documented in [the NTA receipt](nta-validation.md).
  The prior authenticated receipt is historical; it does not mean cached feeds
  remain fresh. Timetable routing, service-instance matching and live journey
  adaptation are Person 4 work, not completed by importing these modules.
- API and protobuf imports succeed in the shared environment. `/health` is the
  only application endpoint currently registered; `POST /route` remains absent.
- Docker source copies and raw/processed bind mounts are corrected. Docker is
  unavailable on this machine, so image build/container execution is **not run**.
- RSA needs a verified suitable machine-readable source. CSO area context is P2.
  No street-level crime score or automatic emergency messaging is added.

These checks verify the data-side routing handoff, not the full product, a
geographical survey, a security guarantee or Ireland-wide performance.
