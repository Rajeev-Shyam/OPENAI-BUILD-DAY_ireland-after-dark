# Ireland After Dark

A Build for Ireland prototype exploring walking-route choices after dark. Routing works anywhere in Ireland via OpenStreetMap; lighting/footfall/SCATS coverage is Dublin-only today, so routes outside Dublin get an honest Low data-confidence badge.

**Status: hello-world skeleton is running (FastAPI + MongoDB + map frontend). Routing, scoring and real data are not built yet.**

## Proposed first demo

Compare the shortest walking route with an alternative favouring proximity to recorded public lighting assets, within a user's acceptable detour. Show both paths, calculated distance, estimated time, source dates and missing information.

This supports informed preferences. It does not predict crime, certify working lamps or guarantee a safe journey. Pub/nightclub avoidance can be an optional preference, not a danger classifier.

Start with one small area. CHQ to Connolly Station is a proposed corridor, subject to verifying valid pedestrian paths and meaningful alternatives.

## Start collaborating

Agree roles and scope using [the brief](docs/PROJECT_BRIEF.md) and [the task split](docs/TASKS.md). Read [the verified data notes](docs/DATA_SOURCES.md) before coding. Use separate branches and review before merging into main.

### Run it with one command

```sh
cp .env.example .env   # fill in OPENAI_API_KEY and MONGODB_URI (local or Atlas)
docker compose up -d --build
```

This builds and starts both containers:

- backend — `http://localhost:8000` (`/health`, `/docs`)
- frontend — `http://localhost:3000`

`MONGODB_URI` in `.env` can point at a local Mongo (if you add one back to
`docker-compose.yml`) or an Atlas `mongodb+srv://` connection string — the
backend container just reads whatever is set there. Logs: `docker compose logs -f`.
Stop everything: `docker compose down`.

### Run it manually (faster iteration, hot reload)

Backend:

```sh
uv sync
uv run uvicorn backend.api.main:app --reload --port 8000
```

Frontend:

```sh
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Tests: `uv run pytest`

## Structure

- `backend/api/`: FastAPI app and `POST /route` endpoint.
- `backend/routing/`: OSM graph build, caching, Fastest/Night route pathfinding.
- `backend/scoring/`: Route Score, Data Confidence, explanation generation.
- `backend/db/`: shared MongoDB client.
- `frontend/`: Next.js map UI (App Router, MapLibre, Tailwind).
- `data/raw/` and `data/processed/`: local data; payloads ignored pending review.
- `data/pipeline/`: dataset download/clean scripts.
- `docs/`: team brief, task split, API contract and source evidence.
- `tests/`: backend checks (pytest).
- `.env.example` / `frontend/.env.example`: placeholders only — copy to `.env` / `.env.local`.

## Boundaries

Keep secrets in ignored local configuration and backend-only. Do not commit live locations, personal travel histories, private account/ticket information or API keys. Confirm model access and event credits before inference.

The first version excludes crime prediction and live transit rerouting. Historical readings are not live occupancy; missing counts are not zero. No invented safety scores or improvement percentages.

Confirm relevant event submission/code-reuse rules and third-party data/code licences. No project licence has been selected by the team.
