# Ireland After Dark

A Build for Ireland prototype exploring walking-route choices after dark. Routing works anywhere in Ireland via OpenStreetMap; lighting/footfall/SCATS coverage is Dublin-only today, so routes outside Dublin get an honest Low data-confidence badge.

**Status: FastAPI + MongoDB backend skeleton is running. Person 1's routing engine (`backend/routing/`) and Person 2's data pipeline (`data/pipeline/`) are merged in. Wiring them together behind `POST /route`, plus the frontend, is in progress.**

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
- frontend — `http://localhost:3000`

`MONGODB_URI` in `.env` can point at a local Mongo (if you add one back to
`docker-compose.yml`) or an Atlas `mongodb+srv://` connection string — the
backend container just reads whatever is set there. Logs: `docker compose logs -f`.
Stop everything: `docker compose down`.

Manual, faster-iteration path:

```sh
uv sync
uv run uvicorn backend.api.main:app --reload --port 8000
```

Tests: `uv run pytest`

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
- `frontend/`: map UI.
- `data/raw/` and `data/processed/`: local data; payloads ignored pending review.
- `data/pipeline/`: dataset download, clean, match and export scripts (Person 2).
- `docs/`: team brief, task split, API contract, data-source evidence and planning docs.
- `tests/`: backend and routing checks (pytest).
- `.env.example` / `frontend/.env.example`: placeholders only — copy to `.env` / `.env.local`.

## Boundaries

Keep secrets in ignored local configuration and backend-only. Do not commit live locations, personal travel histories, private account/ticket information or API keys. Confirm model access and event credits before inference.

The first version excludes crime prediction and live transit rerouting. Historical readings are not live occupancy; missing counts are not zero. No invented safety scores or improvement percentages.

Confirm relevant event submission/code-reuse rules and third-party data/code licences. No project licence has been selected by the team.
