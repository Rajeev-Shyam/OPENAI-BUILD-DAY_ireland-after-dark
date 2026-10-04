# Person 2 validation record

Validated locally on 4 October 2026. This record separates executed checks from
unverified product integration. No claim of scientific validation or universal
route safety is made.

## Work completed and evidence

| Deliverable | Executed evidence | Status |
| --- | --- | --- |
| P0 acquisition | All three pinned CSVs fetched anonymously; schema checks and SHA-256 manifests; subsequent verified offline cache reuse | Implemented and tested for core sources |
| Lighting cleaning/matching | 45,017 valid, distinct asset IDs; audit by unit type; projected metre matching, union coverage, density | Implemented and tested; topology remains a prototype assumption |
| Footfall profiles/matching | 3,672 input rows, 30 exact location joins, 17 counters with usable profiles; mean/sample count bins; duplicate-time and quality diagnostics | Implemented and tested; timezone and spatial representativeness remain assumptions |
| Per-edge export | CLI builds atomic JSON; guarded loader joins exact IDs and checks graph/time fingerprints and metric consistency | Implemented; actual Person 1 graph integration pending |
| Per-source evidence flags | Null unknown scores and partial supported lengths; Cork/Belfast test geometries remain unsupported | Implemented and tested |
| Source links/licences/gaps | Primary catalogue/payload inspection; core CC BY 4.0 confirmed in national catalogue | Documented in source audit |
| Download every proposed dataset | Only core lighting/counts/locations implemented; optional sources researched separately | **Not complete across P1/P2** |
| P1 SCATS/crossings/help locations/collisions | Source feasibility and access limitations researched | Not implemented; observe team's P0-first feature gate |
| P2 CSO context | Methodological constraints documented; no crime weight | Deferred |

## Test execution

Environment: macOS arm64, Python 3.9.6; Shapely 2.0.7, pyproj 3.6.1,
pytest 8.4.2. `pip check` found no broken requirements.

```sh
.venv/bin/python -m pytest -q
```

**77 passed.** The suite checks public behaviour rather than test counts as an
acceptance proxy: HTTP failure/cache integrity, schema rejection, stable graph
identities, unit correctness, invalid coordinates, lighting overlaps, unknowns,
footfall double-counting/missing/zero/DST handling, partial support, incorrect time
slices, corrupted confidence fields and output preservation after failures.

Independent agent review reproduced and corrected these defects:

1. Acquisition accepted duplicate/blank column headers. Explicit rejection and
   failing-then-passing regression cases were added. Strict CSV quoting validation
   was also added to prevent malformed rows being treated as valid observations.
2. The consumer loader initially accepted negative lengths and invalid coverage
   fields. It now validates geometry-derived length, bounded numeric values,
   nullable unknowns, evidence flags and observation/score consistency. Follow-up
   review caught the remaining unchecked lighting proximity fraction; validation
   now also covers proximity, density, asset count, radius, basis and counter distance.

These are local gstack-informed review practices, using its saved engineering
review/checklist and test-value guidance. No gstack runtime, remote reviewer,
deployment or publishing workflow was run.

## Real-source processing smoke test

Executed:

```sh
.venv/bin/python -m data.pipeline.download --source all
.venv/bin/python -m data.pipeline.build \
  --edges tests/fixtures/edges.example.geojson --weekday 3 --hour 0 \
  --output data/processed/synthetic_geometry_real_sources.json
```

The output holds four **synthetic test geometries**, not an actual OSM walking
graph. Its metadata explicitly marks `graph.is_test_fixture=true`. Real downloaded
lighting and footfall observations are used. Two reverse Dublin test segments have
evidence; Cork and Belfast test segments have null scores/false evidence flags.
The exported bundle loads successfully through the guarded consumer function.
This verifies data flow and outside-Dublin unknown handling, not pedestrian access,
route quality, meaningful alternatives or correctness of matches across barriers.

All source and processed payloads remain ignored local files. Exact source hashes
are in [research-sources.md](research-sources.md); per-run manifests are in
`data/raw/`. There is no generated production route file yet.

## Open acceptance requirements

- **Actual graph:** Person 1 must supply the graph-edge export described in
  [edge-data-contract.md](edge-data-contract.md). Run the pipeline and join every
  edge back into that same graph; review spatial samples along the demo route,
  especially rivers, parallel roads and pedestrian-only paths.
- **Unknown-data policy:** Persons 1 and 4 must agree how unsupported segments enter
  route cost and confidence. They must not become known dark/empty streets. True
  edge flags must not be treated as complete route coverage.
- **Unverified measurement assumptions:** 2021 lamp inventory freshness, lamp
  operating status, footfall timezone/hour interpretation and counter location
  validity are not established. Twenty/100-metre buffers and score scaling are
  prototype choices. Complete-zero-day exclusion may bias activity means upward;
  it is exposed in diagnostics and documented as a heuristic.
- **Nationwide scale:** tests validate geographic unknowns and edge contracts, not
  all-Ireland graph performance. Footfall matching is offline, with no claim that
  it meets request-time latency requirements on a nationwide graph.
- **Optional data:** RSA ingestion needs a permitted machine-readable source; no
  dashboard scraping was performed. Other optional layers require actual payload
  inspection and implementation before they may be marked done.

Until these applicable gates are met, the data-processing implementation can be
reviewed and integrated, but the full Person 2/product deliverables must not be
reported as functionally complete.
