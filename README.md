# Ireland After Dark

Shows up to three distinct walking candidates in a scrollable left sidebar. The Night
route favours streets with recorded lighting and historical footfall. It is
not a safety score. It does not use crime data. Missing data shows as
unknown, never as zero.

Lighting and footfall data only cover Dublin right now. Outside Dublin the
app still routes (OpenStreetMap covers all of Ireland) but confidence is
always Low because there is no lighting or footfall evidence to use.

## Run it

```sh
cp .env.example .env   # set OPENAI_API_KEY and MONGODB_URI
docker compose up -d --build
```

Backend: http://localhost:8000 (`/health`, `/docs`). Frontend: http://localhost:4173.

First time only, the routing engine needs a local graph and score bundle
(gitignored, built once, a few minutes):

```sh
uv sync
uv run python -m backend.routing --area dublin
uv run python -m data.pipeline.download --source all
uv run python -m data.pipeline.build --edges data/raw/walking_edges.geojson --weekday 4 --hour 23 --output data/processed/edge_scores.json
```

Faster local loop without Docker:

```sh
uv run uvicorn backend.api.main:app --reload --port 8000
cd frontend && npm install && npm run dev -- --port 5173 --strictPort
```

Tests: `uv run pytest`; frontend: `npm test`, `npm run test:browser`, `npm run build`.

## Using it

Type a start and a destination and press Find route. This geocodes both
through the backend's rate-limited, cached OpenStreetMap Nominatim proxy (no autocomplete). You can also enter latitude, longitude or click map points. [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/) requires at most one request per second across the app; this prototype uses a shared workspace gate and should run as one local API instance. Change GEOCODING_URL to switch provider.

Two real limits to know about, not bugs:

- **Most Eircodes won't resolve.** OSM barely tags Eircodes, so Nominatim
  usually can't find one. Place names work (`"CHQ Dublin"`, `"Connolly
  Station Dublin"`).
- **Points more than 15 km apart outside the cached Dublin area return
  `UNSUPPORTED_AREA`.** The routing engine downloads a fresh OSM tile for
  any area outside Dublin on first request, but caps that to 15 km apart so
  one request can't trigger a huge download.

## What's done

- Routing engine (`backend/routing/`): OSM graph, cached Dublin network plus
  on-demand tiles elsewhere, Fastest and Night routes, NightCost weighting
  from lighting/activity/crossing data.
- Data pipeline (`data/pipeline/`): downloads and cleans DCC lighting and
  footfall data, matches it to graph edges, exports a per-edge score bundle.
  Lighting covers ~39% of Dublin edge length; footfall covers ~0.3% (34
  counters, city centre only).
- Backend API (`backend/api/`, `backend/scoring/`): `POST /route` wired to
  the routing engine, Route Score and Data Confidence computed from real
  edge coverage, deterministic (non-AI) explanation text. Verified against
  real Dublin routes; see the current checks below.
- Frontend (`frontend/`): one-page map UI. Type start/destination, see
  up to three distinct candidates with distance, estimated time, recorded-lighting evidence, confidence, nearby mapped hospitals and source limitations. Results extend below the input panel.

## Snapshot layers and limits

- Luas stops are an opt-in map layer. NTA realtime is shown as a dated saved
  snapshot, not continuous live tracking. Credentials stay backend-only.
- Nearby hospitals are OSM landmarks within 1 km straight-line of each route;
  opening hours, entrances, public access and emergency care are unverified.
- Lighting is a recorded asset inventory, **not working-lamp status**. Activity
  is historical and is excluded when its snapshot weekday/hour does not match.
- The context/crossing/time-score pipelines are integrated. Existing graph caches
  may lack crossing evidence; do not infer signal control from nearby SCATS sites.
- No transit journey planner, live wait estimates or supported preference sliders.

Prepare optional layers once (generated data stays ignored):

```sh
uv run python -m data.pipeline.nta_download --source nta_gtfs_luas
uv run python -m data.pipeline.transport build --source nta_gtfs_luas --output data/processed/luas.sqlite
uv run python -m data.pipeline.transport stops --database data/processed/luas.sqlite --output data/processed/luas-stops.geojson
uv run python -m data.pipeline.context_layers all
uv run python -m data.pipeline.gtfs_realtime fetch --output data/raw/nta-realtime --env-file .env
```

The NTA command makes one request. All requests using the key must share that
output directory and stay at least 60 seconds apart, including failed requests.
[Official usage policy](https://developer.nationaltransport.ie/usagepolicy).
Missing optional datasets do not stop walking routes. The full context command
also downloads non-hospital sources; these are not needed by the route cards.

## Not doing

- Crime prediction or any "safety" score. Recorded lighting and historical
  footfall are not safety measures.
- Calling emergency services automatically.
- Community reporting (needs moderation and abuse prevention this scope
  doesn't have time for).

## Structure

- `backend/api/`: FastAPI app, `POST /route`.
- `backend/routing/`: OSM graph, Fastest/Night pathfinding.
- `backend/scoring/`: Route Score, Data Confidence, explanations.
- `backend/db/`: MongoDB client.
- `data/pipeline/`: lighting/footfall/GTFS download and processing scripts.
- `data/raw/`, `data/processed/`: local build output, gitignored.
- `frontend/`: the map UI (Vite, vanilla JS, Leaflet).
- `tests/`: pytest checks for routing, data pipelines, snapshots and API behavior.

## Secrets

Never commit `.env`. `OPENAI_API_KEY` is used only for optional preference
interpretation and phrasing; routing and scoring are deterministic and don't
need it to work. `MONGODB_URI` can be local (`docker compose up -d mongo`
if you add that service back) or an Atlas connection string.

## Data sources

- DCC Public Lighting: Dublin City Council via Smart Dublin, CC BY 4.0.
  2021 asset inventory, not live lamp status.
- DCC Pedestrian Footfall Counters: Dublin City Council and NTA via Smart
  Dublin, CC BY 4.0. Historical hourly counts, not live occupancy.
- OpenStreetMap: © OpenStreetMap contributors, ODbL. Walking network and
  map tiles.

## Integration checks (4 October 2026)

328 Python tests plus 10 subtests, four Node tests, six Edge browser tests and a
production build passed during integration. Real local API/browser checks also
returned three distinct Dublin routes with hospital proximity, loaded Luas stops,
and exercised unsupported/identical-endpoint errors. Public tiles were blocked
in automated tests; Docker and physical-device checks were not run.

The API contract is in [docs/api-contract.md](docs/api-contract.md). Alternative
routes are bounded candidates, not a guarantee of the globally best three routes.
