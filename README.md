# Ireland After Dark

A Build for Ireland prototype exploring walking-route choices after dark in Dublin.

**Status: team starter repository. The application is not built yet.**

Four-person human team. First scope: a small Dublin walking corridor. For the next coding session start with [NEXT_SESSION.md](docs/NEXT_SESSION.md).

## Planning documents

- [PRD](docs/PRD.md): user needs, scope, priorities and acceptance criteria.
- [Design](docs/DESIGN.md): architecture, routing/data contracts, interface and AI boundaries.
- [Four-person implementation plan](docs/IMPLEMENTATION_PLAN.md): roles, file ownership, milestones and cut order.
- [Acceptance and demo checklist](docs/ACCEPTANCE_CHECKLIST.md): evidence required before claiming readiness.
- [Shared decisions](docs/DECISIONS_SHARED.md): confirmed choices, proposals and unresolved gaps.
- [Next-session handoff](docs/NEXT_SESSION.md): current state and a copy-ready implementation prompt.

## Proposed first demo

Compare the shortest walking route with an alternative favouring proximity to recorded public lighting assets, within a user's acceptable detour. Show both paths, calculated distance, estimated time, source dates and missing information.

This supports informed preferences. It does not predict crime, certify working lamps or guarantee a safe journey. Pub/nightclub avoidance can be an optional preference, not a danger classifier.

Start with one small area. CHQ to Connolly Station is a proposed corridor, subject to verifying valid pedestrian paths and meaningful alternatives.

## Start collaborating

```sh
git clone https://github.com/Rajeev-Shyam/ireland-after-dark.git
cd ireland-after-dark
git switch -c codex/your-task
```

Agree roles and scope using [the brief](docs/PROJECT_BRIEF.md). Read [the verified data notes](docs/DATA_SOURCES.md) before coding. Use separate branches and review before merging into main.

The design proposes FastAPI, OSMnx/NetworkX and a plain browser/Leaflet interface. These choices and dependency compatibility are untested; create your own local environment and pass the first data-and-path gate before expanding. No application run command or working route engine exists yet.

## Structure

- `src/`: application code.
- `tests/`: application checks.
- `data/raw/` and `data/processed/`: local data; payloads ignored pending review.
- `docs/`: team brief and source evidence.
- `.env.example`: empty placeholders only.

## Boundaries

Keep secrets in ignored local configuration and backend-only. Do not commit live locations, personal travel histories, private account/ticket information or API keys. Confirm model access and event credits before inference.

The first version excludes crime prediction and live transit rerouting. Historical readings are not live occupancy; missing counts are not zero. No invented safety scores or improvement percentages.

Confirm relevant event submission/code-reuse rules and third-party data/code licences. No project licence has been selected by the team.
