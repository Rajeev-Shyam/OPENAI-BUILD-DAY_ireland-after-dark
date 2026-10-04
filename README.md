# Dublin After Dark

A Build for Ireland prototype exploring walking-route choices after dark in Dublin.

**Status: Person 2's core data pipeline is implemented and tested. The routing
application and real-graph integration are not built or verified here yet.**

The latest task split targets routing across Ireland, with Dublin-specific
lighting and footfall evidence. The earlier demo proposal below remains historical
context; it does not override the latest scope.

## Data pipeline handoff

Start with the [edge-data contract and run commands](docs/edge-data-contract.md),
[source audit](docs/data-sources.md), and [work allocation](docs/data-plan.md).
The pipeline downloads pinned public snapshots, cleans lighting and historical
footfall, and enriches the routing team's supplied edge GeoJSON. It preserves
unknowns outside evidence coverage and records source/graph fingerprints.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-data.txt
.venv/bin/python -m data.pipeline.download --source all
.venv/bin/python -m pytest -q
```

The contract explains how to build the processed edge file. A graph from Person 1
is required for actual routing; the included synthetic geometry is only a test
fixture. Review [validation status](docs/data-validation.md) before declaring a
deliverable complete.

## NTA public transport data

The [NTA handoff guide](docs/transport-data-contract.md) covers static GTFS downloads,
SQLite timetable processing, stop GeoJSON, authenticated realtime snapshots and
static/realtime identifier audits. [Validation status](docs/nta-validation.md)
records real static-feed checks and successful authenticated realtime fetches,
including stale observations and unresolved timetable references. This addition prepares data for the transport team; it does not provide
multimodal routing or waiting-time recommendations.

## Proposed first demo

Compare the shortest walking route with an alternative favouring proximity to recorded public lighting assets, within a user's acceptable detour. Show both paths, calculated distance, estimated time, source dates and missing information.

This supports informed preferences. It does not predict crime, certify working lamps or guarantee a safe journey. Pub/nightclub avoidance can be an optional preference, not a danger classifier.

Start with one small area. CHQ to Connolly Station is a proposed corridor, subject to verifying valid pedestrian paths and meaningful alternatives.

## Start collaborating

```sh
git clone https://github.com/Rajeev-Shyam/dublin-after-dark.git
cd dublin-after-dark
git switch -c codex/your-task
```

The [original brief](docs/PROJECT_BRIEF.md) records the starter proposal. Use the
latest task split and [data plan](docs/data-plan.md) for current Person 2 scope.
Read [the verified data notes](docs/data-sources.md) before coding. Use separate
branches and review before merging into main.

Python backend and a simple browser interface are proposed. Application frameworks
remain unselected; data-pipeline dependencies are in `requirements-data.txt`.
No application run command or working route engine exists yet.

## Structure

- `src/`: application code.
- `tests/`: application checks.
- `data/raw/` and `data/processed/`: local data; payloads ignored pending review.
- `data/pipeline/`: download, clean, match and export commands.
- `docs/`: team brief and source evidence.
- `.env.example`: empty placeholders only.

## Boundaries

Keep secrets in ignored local configuration and backend-only. Do not commit live locations, personal travel histories, private account/ticket information or API keys. Confirm model access and event credits before inference.

The first version excludes crime prediction and live transit rerouting. Historical readings are not live occupancy; missing counts are not zero. No invented safety scores or improvement percentages.

Confirm relevant event submission/code-reuse rules and third-party data/code licences. No project licence has been selected by the team.
