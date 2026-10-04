# Person 2 → Persons 1 and 4: edge-data contract v1

This is the data handoff, not the still-unagreed `POST /route` API contract.
The pipeline accepts a supplied Ireland walking graph and adds evidence. It does
not generate a walking graph, validate access restrictions or calculate routes.

## Input graph

Supply an RFC 7946 WGS84 GeoJSON FeatureCollection. Each feature must be a
two-dimensional LineString with `u`, `v`, `key` properties from the routing graph.
Integers and nonempty strings are accepted and canonicalised to strings. The
full tuple identifies a directed edge: reverse edges and parallel keys are kept.
Duplicate canonical tuples, floating-point IDs, zero-length lines, nonfinite or
out-of-Ireland coordinates, and projected GeoJSON `crs` members are rejected.
The supported input envelope includes the island of Ireland, including NI;
this envelope is a validation bound, never a data-coverage polygon.

Export from the routing team's existing OSMnx graph, without creating another:

```python
import osmnx as ox

edge_frame = ox.graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)
edge_frame = edge_frame.to_crs("EPSG:4326").reset_index()
for field in ("u", "v", "key"):
    edge_frame[field] = edge_frame[field].map(str)
edge_frame[["u", "v", "key", "geometry"]].to_file(
    "data/raw/walking_edges.geojson", driver="GeoJSON", RFC7946="YES"
)
```

This is an integration recipe based on [OSMnx's graph conversion API](https://osmnx.readthedocs.io/en/stable/user-reference.html#osmnx.convert.graph_to_gdfs),
not an executed test against the team's absent graph or environment. Preserve OSM
source attribution and [ODbL obligations](https://www.openstreetmap.org/copyright).
The pipeline itself does not need OSMnx or GeoPandas.

## Run

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-data.txt
.venv/bin/python -m data.pipeline.download --source all
.venv/bin/python -m data.pipeline.build \
  --edges data/raw/walking_edges.geojson \
  --weekday 4 --hour 23 \
  --output data/processed/edge_scores.json
.venv/bin/python -m pytest -q
```

Weekday is Monday=0 through Sunday=6. Hours are 0–23, under the explicitly
unverified Europe/Dublin interpretation of the source's clock labels. Optional
`--lighting-buffer-m` (20 default) and `--footfall-radius-m` (100 default) are
prototype spatial assumptions. `--raw-dir` changes the input snapshot directory.
Inputs need the downloader's matching per-source manifest; changed bytes fail.
Output is published as one atomic JSON bundle after all processing succeeds.

For a repeatable **processing smoke test only**, substitute
`tests/fixtures/edges.example.geojson` and output to
`data/processed/synthetic_geometry_real_sources.json`. These are invented test
segments, not an OSM graph, pedestrian paths or a demo route. The source
observations remain real; the graph metadata carries an explicit test description.

## Bundle

`schema_version: 1` accompanies these top-level fields:

| Field | Meaning |
| --- | --- |
| `graph` | SHA-256 of the exact input file, edge count, input/measurement CRS and identity fields |
| `time_slice` | Weekday/hour/timezone applicable to exported scores |
| `parameters` | Distance thresholds, quality heuristic and prototype score formulas |
| `sources` | Original/resolved URLs, retrieval time, content hashes, dates, licence and attribution |
| `edges` | One record per input graph edge, preserving order and identity |
| `footfall_profiles` | All observed weekday/hour bins, counter positions, sample counts and diagnostics |
| `quality` | Lighting input audit and length-weighted graph evidence summary |
| `limitations` | Required caveats for consumers |

Hashes refer to exact bytes. Reformatting the graph file changes its fingerprint
and requires a rebuild. Lengths are recalculated from EPSG:2157 geometry; do not
silently substitute another graph's distance convention when aggregating metrics.

## Edge fields

| Field | Type / semantics |
| --- | --- |
| `u`, `v`, `key` | String tuple matching the input graph |
| `length_m` | Positive geometric length in EPSG:2157 metres |
| `lighting_asset_count` | Nonnegative count of distinct recorded asset IDs within the configured buffer; zero alone is not a surveyed absence |
| `lighting_density_per_km` | Asset count / edge length in km, or null without evidence |
| `lighting_proximity_fraction` | Fraction of edge within the union of recorded asset buffers, or null without evidence |
| `lighting_score` | 100 × proximity fraction; null if unknown; not a brightness/safety score |
| `has_lighting_data` | Boolean: some positive-length support (or separately verified declared inventory coverage) exists |
| `lighting_data_coverage_fraction` | Supported edge-length fraction, 0–1; do not turn a true flag into 100% coverage |
| `lighting_coverage_basis` | `recorded_asset_proximity`, `unknown`, or `declared_inventory_coverage` for the explicit library-only polygon override |
| `lighting_buffer_m` | Matching distance used |
| `has_footfall_data` | Boolean: selected counter has observations for the requested hour/day and supports positive edge length |
| `footfall_coverage_fraction` | Fraction of edge in that counter's assumed radius; not surveyed street coverage |
| `footfall_score` | Capped log-normalised historical counter activity, 0–100; null if unknown |
| `expected_pedestrians_per_hour` | Historical **counter mean**, not a forecast of pedestrians on the edge; null if unknown |
| `footfall_counter_id` | Source location identifier, or null |
| `footfall_sample_count` | Number of valid historical observations supporting the selected bin; 0 if unknown |
| `footfall_counter_distance_m` | Nearest distance from selected counter to edge; null if unknown |

The lighting CLI does not declare complete administrative coverage. It uses
positive recorded-asset evidence only. The library's optional coverage polygon
must be independently justified; an administrative boundary alone is not proof of
a complete inventory. No source includes current lamp operating status.

Footfall's prototype score is
`min(100, 100 * log1p(mean_count) / log1p(1000))`. It refers to the supported
portion only. Lighting's score already contains whole-edge proximity fraction;
multiplying it by that fraction again would square its contribution. Neither
formula supplies the routing team's NightCost weights or a calibrated safety scale.
Unsupported portions remain uncertain; do not penalise them as known unlit or
empty streets. Person 1 must document the neutral/default policy for unknowns.

For confidence, aggregate supported lengths rather than count true edge flags:
`sum(edge_length * support_fraction) / sum(edge_length)` along the actual route.
Keep source freshness, sample counts, positional relevance and timezone uncertainty
visible alongside these fractions. These checks do not justify a High confidence
label by themselves. Route confidence and explanations belong to Person 4.

## Loading and time changes

```python
from data.pipeline.build import load_scores

scores = load_scores("data/processed/edge_scores.json",
                     "data/raw/walking_edges.geojson", weekday=4, hour=23)
for u, v, key, attrs in G.edges(keys=True, data=True):
    attrs.update(scores[(str(u), str(v), str(key))])
```

The loader verifies schema, graph fingerprint, exact edge identities, geometric
lengths, time slice, bounded scores/fractions and evidence consistency. It rejects
mismatches instead of silently joining the wrong graph. Rebuild for another time
slice, or use the bundled profiles with `match_footfall(projected_edge, profiles,
weekday, hour)` at request time. Do not reuse Friday 23:00 scores for Sunday noon.
Precompute/cache other time slices if required; all-island build performance has
not been measured. The complete bundle is offline enrichment, not a live feed.

## Acceptance status

Real-source ingestion and synthetic-geometry end-to-end checks passed. Integration
with Person 1's real graph, manual inspection of river/parallel-street matches,
agreed unknown-data policy and Person 4's confidence display remain open. Those
are required before calling the routed product complete.
