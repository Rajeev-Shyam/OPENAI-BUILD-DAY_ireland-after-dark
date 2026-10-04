# Start here — next session

Status on 4 October 2026: **planning and team starter exist; application implementation is unstarted.** Four-person human team confirmed; names/roles pending. This handoff is shared and self-contained; it does not depend on the original owner's private context files.

## Read in order

1. [PRD](PRD.md): user, scope, priorities and what is confirmed.
2. [Design](DESIGN.md): architecture, routing behaviour, data/API contracts and unknowns.
3. [Four-person implementation plan](IMPLEMENTATION_PLAN.md): ownership, schedule, gates and cut order.
4. [Data sources](data-sources.md): actual prior download evidence and dataset defects.
5. [Acceptance](ACCEPTANCE_CHECKLIST.md) and [decisions](DECISIONS_SHARED.md).

## Current repository and evidence

- Canonical repo: https://github.com/Rajeev-Shyam/ireland-after-dark; branch main; currently public. It was originally created under a different name/private setting. Preserve current settings.
- Starter commit: `45b1cbe`. The planning commit comes after it; inspect `git log -1` for the actual latest SHA rather than treating this starter SHA as current forever.
- Original local environment: Python 3.14 with no application dependencies. A fresh clone has no environment; framework/library compatibility is untested.
- Lighting CSV downloaded successfully earlier: 45,017 records, source resource dated 2021; no live operating status.
- Genuine pedestrian counts were inspected through 2 June 2026. September-labelled resource contains cyclist series; some counters are empty. Do not use those as live pedestrians.
- Pedestrian graph, venues, API, browser application and application model access are unverified. No model call, code reuse, deployment or event submission has occurred.
- Personal local notes/instructions remain excluded in the original workspace. Do not upload them or change ignore rules to expose them. Shared planning docs contain no credentials or personal travel history.

## First bounded milestone

Confirm actual remaining time, role mapping and one small corridor. CHQ to Connolly is suggested, not validated. Set a supported area with margin; test dependency imports, load the lighting CSV, retrieve a real pedestrian graph and prove one shortest path exists. Record source hashes and manually inspect access/crossings/endpoints.

P1 works on data, P2 on contract/routing, P3 on a labelled UI fixture, P4 on template explanation/verification. See the first two rows of the implementation timeline. If a graph/source blocks for about 20 minutes, reassess rather than pretending the data exists.

Do not start with nationwide search, recent crime prediction, live transport or a learned safety model. Templates and mocked UI may support development but cannot be passed off as genuine/AI-generated demo results.

## Copy-ready prompt for implementation

> Continue Ireland After Dark from the saved repository. Read docs/NEXT_SESSION.md, docs/PRD.md, docs/DESIGN.md, docs/IMPLEMENTATION_PLAN.md, docs/data-sources.md and docs/ACCEPTANCE_CHECKLIST.md first; read any applicable local AGENTS.md without sharing personal notes. Do not restart idea selection or prior research. Work on the first bounded data-and-path milestone for a four-person human team: establish one small Dublin corridor, validate the local dependency setup, load recorded lighting, retrieve a real pedestrian graph and verify a genuine shortest path with source provenance. Use the proposed defaults where non-blocking; record changes and missing facts. Preserve existing files and credentials. No account/key creation, paid inference, deployment, visibility changes, invitations or contact. Do not spawn agents unless explicitly asked. Verify the milestone, update the shared plan/handoff with actual commands/results and known gaps, and leave one concrete next action. Coordinate role ownership before parallel human changes; do not claim other people's tasks are complete.

This prompt authorises milestone work only when the user sends it to the implementation session. Writing it here does not mean the application has been built or paid access authorised.

## End-of-session update

Record latest commit, actual source manifest, tested setup/run commands, completed role tasks, acceptance results, remaining blockers and next milestone here. Keep successful, failed, mocked and untested behaviour distinct. Push only reviewed team files when authorised; do not change repository visibility or rely on private local state for a teammate's run.
