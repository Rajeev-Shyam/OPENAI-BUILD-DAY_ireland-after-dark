# Routing engine

Fastest and Night walking routes on the OpenStreetMap walking network, scored with the data pipeline's edge bundle. Deterministic: no AI, no invented geometry. It reports recorded features and what is unknown; it does not say a route is safe.

## Setup

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 1. Walking graph and its edge export (about 1 minute, one-off)
.venv/bin/python -m backend.routing --area dublin

# 2. Lighting and footfall sources, then the score bundle (about 2.5 minutes)
.venv/bin/python -m data.pipeline.download --source all
.venv/bin/python -m data.pipeline.build \
  --edges data/raw/walking_edges.geojson \
  --weekday 4 --hour 23 \
  --output data/processed/edge_scores.json

.venv/bin/python -m pytest
```

`requirements.txt` also runs the data pipeline and its tests; its pins are newer than `requirements-data.txt`.

Step 1 writes `data/processed/graph_dublin.graphml` and `data/raw/walking_edges.geojson`. Step 2 writes `data/processed/edge_scores.json`. All three are git-ignored, so each developer builds them locally.

The bundle is tied to the exact bytes of the edge export. If you rerun step 1 with `--force`, rerun the build in step 2; the engine refuses a bundle built for a different export.

If the default Overpass server is down, the next one in `config.OVERPASS_URLS` is tried; set `OVERPASS_URL` to put your own first.

## Calling it (API)

```python
from backend.routing import get_route, get_store, Preferences, RoutingError

get_store()  # at startup: loads the bundle and the Dublin graph, about 12 s

result = get_route(
    origin=(53.3489, -6.2479),        # (lat, lon)
    destination=(53.3531, -6.2470),
    prefs=Preferences(well_lit=1.0, busier=0.5, crossings=1.0, less_walking=0.0),
    max_extra_minutes=5.0,            # None removes the detour cap
)
```

Result:

```text
status      ok | same_route | no_alternative | baseline_only
area        "dublin" or the on-demand tile name
time_slice  weekday and hour the activity scores are for, or null
fastest     route object (shortest by distance)
night       route object (lowest NightCost within the detour cap)
detour      extra_m, extra_min, max_extra_min, preference_scale
snap        origin / destination: node, lat, lon, distance_m
```

Route object:

```text
geometry      GeoJSON LineString, [lon, lat]
distance_m    sum of the edges walked
duration_min  distance at 1.3 m/s
night_cost    NightCost under the request's preferences
lighting      score, coverage
activity      score, coverage
crossings     counts by type: signal, minor, major_unsignalised
segments      per edge: u, v, key, length_m, lighting, lighting_coverage,
              activity, activity_coverage, crossing
```

- `lighting.score`: share of the route's length within 20 m of a recorded street light. Not brightness, and not whether the lamp works.
- `lighting.coverage`: share of the route's length with any lighting evidence. With the current source this equals the score, because the inventory only records where lights are.
- `activity.score`: mean historical counter activity (0 to 1) over the part of the route within 100 m of a counter.
- `activity.coverage`: share of the route's length within 100 m of a counter.

A score is `null` when the route has no evidence at all. It is never zero for that reason. For Data Confidence use the `coverage` values, which are already weighted by length as the edge-data contract asks.

Status meanings:

- `ok`: the Night route differs from the fastest. The difference can be small; check `detour` and the scores before claiming a benefit.
- `same_route`: the fastest route is already the best for these preferences.
- `no_alternative`: the preferred route broke the detour cap, so the fastest is returned.
- `baseline_only`: no edge scores apply to this graph. Do not present this as a Night route.

When the preferred route breaks the cap, preferences are halved (up to four times) until a route fits. `preference_scale` shows the strength actually used.

Errors are `RoutingError` subclasses with a `code`:

| Code | Meaning | Suggested HTTP |
|---|---|---|
| `outside_coverage` | off the island, or no walking path within 100 m | 400 |
| `same_point` | both points snap to the same node | 400 |
| `too_far` | outside the cached area and over 15 km apart | 400 |
| `no_route` | no connected walking route | 404 |
| `graph_unavailable` | OSM download for a new area failed | 503 |

## NightCost and unknown data

```text
length_m * (1 + well_lit * (1 - lit) + busier * (1 - active)) + crossings * penalty_m
```

Unknown-data policy: unsupported portions use neutral preference terms. Observed
activity below the neutral value can increase cost; missing observations remain unknown.

- `lit`: the part of the edge near a recorded light counts as 1; the part with no evidence counts as 0.5.
- `active`: the part of the edge near a counter takes that counter's score; the rest counts as 0.5.

So an edge with no data is never costed as dark or empty, and an edge with a few recorded lights is never worse than one with none.

Crossing penalties are 10 m (signal), 20 m (minor) and 80 m (major unsignalised), read from an optional `crossing` field on bundle edges. The pipeline does not supply that field yet, so crossings have no effect today. `less_walking` (0 to 1) scales the other three preferences down. These are preference strengths, not risk measurements; all of them are in `config.py`.

## Coverage and limits

- Dublin (`-6.39, 53.29` to `-6.11, 53.41`) is cached: 101,875 nodes, 267,580 edges, fetched 4 October 2026.
- In that graph 39% of edge length has lighting evidence and 0.3% has footfall evidence (34 counters, city centre only).
- Activity scores are for one weekday and hour: the slice the bundle was built for (Friday 23:00 above). A request for another time still gets that slice; `time_slice` in the result says which. Lighting does not vary by time.
- Elsewhere in Ireland a tile around the two points is downloaded on the first request and cached. That first request took about 80 s for Galway; later ones are instant. Outside Dublin there are no scores, so results are `baseline_only`.
- Routes run between the nearest graph nodes. The walk from the clicked point to that node is not included in distance or time.
- Distances use OSMnx's spherical edge lengths; the pipeline measures in EPSG:2157. Across the Dublin graph the pipeline's total is 0.2% longer.
- OSM walking access is not a guarantee of real-world access or closures. Lighting matches are by straight-line distance and can cross rivers or walls.

## Verified data handoff and time selection

The shared Python 3.12 `uv` environment includes routing and NTA dependencies.
`python -m data.pipeline.validate_handoff` verifies that the actual cached GraphML
reproduces the scored export and checks route segments against strict validated
observations. See [the phase1 receipt](../../docs/phase1-data-validation.md).

`load_edge_scores(..., departure_time=aware_datetime)` can prepare another
historical time slice offline. It validates the full bundle, preserves lighting
and re-evaluates activity; the default `get_route()` remains fixed to the loaded
slice. Cache or precompute before request-time integration. See
[the time contract](../../docs/time-score-contract.md). Crossing metadata in the
edge export remains evidence only; it does not activate crossing penalties.
