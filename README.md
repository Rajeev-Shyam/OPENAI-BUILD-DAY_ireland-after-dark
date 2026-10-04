# Ireland After Dark

Compares a Fastest route and a Night route for walking in Ireland. The Night
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

Tests: `uv run pytest`.

## Using it

Type a start and a destination and press Find route. This geocodes both
through OpenStreetMap's Nominatim (one lookup per field, not autocomplete)
and draws both routes on the map.

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
  real Dublin routes with 221 passing tests.
- Frontend (`frontend/`): one-page map UI. Type start/destination, see
  Fastest vs Night compared with distance, time, lighting %, and a
  confidence badge.

## What's not done / not wired in

- **GTFS/NTA transit data** (`data/pipeline/gtfs*.py`, `nta_download.py`):
  downloads and parses NTA static and realtime transit feeds. This exists
  in the codebase but nothing in the API or frontend uses it yet.
- **Crossing penalties**: the formula exists in the routing engine but has
  no effect, because the data pipeline doesn't tag edges with crossing type
  yet.
- **SCATS signals, Garda/fire/hospital points, RSA collisions, CSO crime
  context**: researched, not implemented. Street-level crime data isn't
  reliable enough to use; see "Not doing" below.
- Preference sliders (prefer better lit / busier / less walking), a nearby-
  help layer, and a full accessibility pass are not built.

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
- `tests/`: pytest, 221 tests across routing, data pipeline and the API.

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
