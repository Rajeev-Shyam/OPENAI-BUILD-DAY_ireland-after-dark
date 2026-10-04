# Ireland After Dark

A Build for Ireland prototype exploring walking-route choices after dark. Routing works anywhere in Ireland via OpenStreetMap; lighting/footfall/SCATS coverage is Dublin-only today, so routes outside Dublin get an honest Low data-confidence badge.

**Status: FastAPI + MongoDB backend skeleton is running. Person 1's routing engine (`backend/routing/`) and Person 2's data pipeline (`data/pipeline/`) are merged in. Wiring them together behind `POST /route`, plus the frontend, is in progress.**

## Status by person (`phase1` branch, 4 Oct 2026)

Pulled from each branch's own handoff doc, not guessed — see the linked doc per
row for full evidence. ✅ done and verified · ⚠️ partially done / blocked · ❌ not started.

### Person 1 — Routing engine (`backend/routing/`)

| Task | Status |
|---|---|
| OSM walking network pull (Dublin cached, other areas on-demand) | ✅ |
| Graph build + disk cache | ✅ |
| Snap origin/destination to nearest node | ✅ |
| Fastest route (Dijkstra) | ✅ |
| NightCost edge weights + Night Route | ✅ |
| Return geometry, minutes, metres | ✅ |
| P1: preference weights (well-lit, busier, crossings, less walking) | ✅ |
| P1: crossing penalties | ⚠️ formula exists; no effect yet — data pipeline doesn't supply the `crossing` field |
| P1: performance pass | ❌ not verified |
| P2: route deviation check | ❌ |
| **Wired into `backend/api`'s `POST /route`** | ❌ **next integration step** |

Details: [`backend/routing/README.md`](backend/routing/README.md)

### Person 2 — Data pipeline (`data/pipeline/`)

| Task | Status |
|---|---|
| Download scripts (lighting, footfall, counter locations — pinned & hashed) | ✅ |
| Street-light cleaning, edge matching, lighting density | ✅ |
| Footfall cleaning, weekday/hour averaging, edge matching | ✅ code exists; thin coverage (34 counters, city-centre only) |
| Per-edge score export + per-source coverage flags (nullable, not zero) | ✅ |
| P1: SCATS signals + OSM crossings | ❌ |
| P1: Garda/fire/hospital points layer | ❌ |
| P1: RSA collisions | ❌ |
| P2: CSO crime context | ❌ |
| Integration against Person 1's real Dublin graph | ⚠️ tested only against a synthetic fixture graph so far |

Details: [`docs/data-validation.md`](docs/data-validation.md)

### Person 3 — Frontend (`frontend/`)

| Task | Status |
|---|---|
| Map of Ireland (Leaflet) | ✅ |
| Origin/destination input (local directory search + map click + coordinates) | ✅ no live geocoder — deliberate, per Nominatim policy |
| Time/day picker (Europe/Dublin, DST-aware) | ✅ |
| Fastest/Night routes in distinct colours + comparison card + explanation list + score/confidence UI | ✅ |
| Built against mock/demo fixtures, with a Real API switch | ✅ switch exists; real side unverified |
| Loading / error / no-route / unsupported-area states | ✅ |
| P1: preference sliders | ❌ |
| P1: mobile layout | ✅ |
| P1: nearby-help locations layer | ❌ |
| P1: accessibility pass | ✅ basics in (keyboard, focus, labels); no screen-reader pass yet |
| **Real backend integration end to end** | ❌ **not verified — the blocker** |

Details: [`frontend/HANDOFF.md`](frontend/HANDOFF.md)

### Person 4 — API, scoring, pitch (`backend/api/`, `backend/scoring/`, docs)

| Task | Status |
|---|---|
| FastAPI app skeleton + MongoDB connection + `/health` | ✅ |
| `POST /route` matching the contract | ❌ |
| Route Score / Data Confidence calculation | ❌ |
| Explanation generator | ❌ |
| Input validation + error responses | ❌ |
| Unit tests for score, confidence, explanations | ❌ |
| Demo script with a fixed Dublin route | ❌ |
| Pitch and limitations slide | ❌ |

Details: [`docs/ACCEPTANCE_CHECKLIST.md`](docs/ACCEPTANCE_CHECKLIST.md) (every check currently **NOT RUN**).

**Next piece of work:** wire Person 1's `get_route()` and Person 2's edge-score
bundle into `POST /route`, then point Person 3's frontend at it with the Real
API switch — that one path closes the loop for everyone.

## Proposed first demo

Compare the shortest walking route with an alternative favouring proximity to recorded public lighting assets, within a user's acceptable detour. Show both paths, calculated distance, estimated time, source dates and missing information.

This supports informed preferences. It does not predict crime, certify working lamps or guarantee a safe journey. Pub/nightclub avoidance can be an optional preference, not a danger classifier.

Start with one small area. CHQ to Connolly Station is a proposed corridor, subject to verifying valid pedestrian paths and meaningful alternatives.

## Start collaborating

Agree roles and scope using [the brief](docs/PROJECT_BRIEF.md) and [the task split](docs/TASKS.md). Read [the verified data notes](docs/data-sources.md) before coding ([earlier notes](docs/data-sources-legacy.md) for history). Use separate branches and review before merging into main.

Further planning docs from the data-pipeline/routing work: [data plan](docs/data-plan.md), [edge-data contract](docs/edge-data-contract.md), [data validation status](docs/data-validation.md), [design](docs/DESIGN.md), [PRD](docs/PRD.md), [implementation plan](docs/IMPLEMENTATION_PLAN.md).

### Run the backend API + MongoDB

```sh
cp .env.example .env   # fill in OPENAI_API_KEY and MONGODB_URI (local or Atlas)
docker compose up -d --build
```

- backend — `http://localhost:8000` (`/health`, `/docs`)
- frontend — `http://localhost:4173` (production build via `vite preview`)

`MONGODB_URI` in `.env` can point at a local Mongo (if you add one back to
`docker-compose.yml`) or an Atlas `mongodb+srv://` connection string — the
backend container just reads whatever is set there. Logs: `docker compose logs -f`.
Stop everything: `docker compose down`.

Manual, faster-iteration path:

```sh
uv sync
uv run uvicorn backend.api.main:app --reload --port 8000
```

```sh
cd frontend
cp .env.example .env.local   # set VITE_API_BASE_URL to the backend origin
npm install
npm run dev -- --port 5173 --strictPort
```

Frontend dev server: `http://127.0.0.1:5173`. See [`frontend/README.md`](frontend/README.md)
for demo-mode fixtures, search/geocoding policy and the [proposed API contract](frontend/API_CONTRACT_PROPOSED.md).

Tests: `uv run pytest` (backend), `cd frontend && npm test && npm run test:browser` (frontend)

### Run the routing engine and data pipeline

These currently use their own `pip`/`venv` environment (not yet folded into the
`uv` project above):

```sh
python3 -m venv .venv-routing
.venv-routing/bin/pip install -r requirements.txt -r requirements-data.txt
.venv-routing/bin/python -m data.pipeline.download --source all
.venv-routing/bin/python -m pytest -q
```

See [`backend/routing/README.md`](backend/routing/README.md) for routing engine usage and
[`docs/edge-data-contract.md`](docs/edge-data-contract.md) for the data pipeline's output contract.

## Structure

- `backend/api/`: FastAPI app and `POST /route` endpoint.
- `backend/routing/`: OSM graph build, caching, Fastest/Night route pathfinding (Person 1).
- `backend/scoring/`: Route Score, Data Confidence, explanation generation.
- `backend/db/`: shared MongoDB client.
- `frontend/`: map UI (Vite, vanilla JS, Leaflet) (Person 3).
- `data/raw/` and `data/processed/`: local data; payloads ignored pending review.
- `data/pipeline/`: dataset download, clean, match and export scripts (Person 2).
- `docs/`: team brief, task split, API contract, data-source evidence and planning docs.
- `tests/`: backend and routing checks (pytest).
- `.env.example` / `frontend/.env.example`: placeholders only — copy to `.env` / `.env.local`.

## Boundaries

Keep secrets in ignored local configuration and backend-only. Do not commit live locations, personal travel histories, private account/ticket information or API keys. Confirm model access and event credits before inference.

The first version excludes crime prediction and live transit rerouting. Historical readings are not live occupancy; missing counts are not zero. No invented safety scores or improvement percentages.

Confirm relevant event submission/code-reuse rules and third-party data/code licences. No project licence has been selected by the team.
