# PRD — Ireland After Dark

Version 0.1, 4 October 2026. Documentation complete; implementation unstarted. First geography: a small Dublin city-centre area, not national coverage.

## Decision summary

Help a person walking after dark compare the shortest path with alternatives matching their preferences for recorded lighting and avoiding nightlife venues. Show the trade-off, evidence age and unknowns. Do not predict crime or claim to identify the safest path.

Confidence: high in the already-inspected lighting download; medium in a bounded four-hour build; unverified pedestrian graph, venue coverage, dependency compatibility and application model access.

## Confirmed, proposed and unresolved

| Status | Item |
|---|---|
| Confirmed by user | Four-person human team exploring after-dark routes; public data; quick four-hour scope; shared repository and planning docs requested |
| Proposed product default | Dublin walking only; one corridor first; recorded-lighting preference plus optional nightlife avoidance |
| Proposed implementation | Python service, deterministic graph routing, simple browser map, bounded AI explanation when authorised access exists |
| Unresolved | Team roles, corridor, available time, final feature priorities, credits/model access, submission/code-reuse rules and source licence details |

The repo is currently public and named `Rajeev-Shyam/ireland-after-dark`, observed on GitHub during this documentation session. Earlier private/name status is historical. Visibility must not be changed without instruction.

## User and problem

Primary proposed user: a person walking home after dark who is willing to take a modest detour for their preferred surroundings. Students, night workers and visitors are examples; no demographic exclusivity is agreed.

Job: “Show my walking options and why I might prefer one, without pretending you know current conditions.”

Relevant concerns: visibility and isolation; nightlife/crowd discomfort; harassment or theft; crossings and path access; being stranded. The initial data measures only some environmental features. It cannot reliably quantify individual threats or live crowding. Avoiding pubs is a user preference, not a conclusion that pubs cause danger.

## First user flow

1. Select two verified presets, or map points inside the supported area. No external geocoding or automatic location permission required.
2. Choose a maximum extra walking time; toggle recorded-lighting preference and, if venue data exists, nightlife avoidance.
3. Compare shortest and preference-matching routes on one map.
4. Read calculated distance/estimated time, recorded-lighting proximity, mapped venues encountered and visible data limitations.
5. Adjust preferences or select the shortest route. If no distinct qualifying alternative exists, say so.

Time-of-day input is for optional historical counter summaries only. It must not imply that the lighting inventory is live or that venues are open.

## Requirements and priorities

| ID | Priority | Requirement | Acceptance |
|---|---|---|---|
| R1 | P0 | Genuine pedestrian paths for one area | Valid connectivity and sampled access/crossings manually checked; no straight-line substitutes |
| R2 | P0 | Shortest-path comparison and bounded detour | Independent shortest-distance check passes; alternative stays within the user's cap |
| R3 | P0 | Recorded-lighting feature | Calculation comes from real coordinates; source age and unknown operating status displayed |
| R4 | P0 | Honest route presentation | Same-route/no-alternative/unsupported/missing-data states work; no guaranteed safety language |
| R5 | P0 | Reproducible local demo | Documented commands, pinned working dependencies, source manifest and acceptance evidence |
| R6 | P1 | Nightlife preference | Uses verified mapped pubs/nightclubs; no assumed opening/crowding or danger labels; missing coverage disables the control |
| R7 | P1 | AI explanation/preferences | Structured, validated output based on calculated facts; no invented incidents or route geometry; deterministic fallback |
| R8 | P2 | Historical pedestrian context | Valid nearby counters only, matched coordinates, dates/sample counts, unknowns kept explicit |

P0 is the minimum software demo. AI/tool requirements for the event still need confirming; a deterministic demo alone must not be described as satisfying an AI requirement. R6 is the first optional feature because it directly reflects the team's proposal. R7 follows when model access and authority are established. Cut R8 first if time slips.

## Non-goals for this build

Recent street-level crime alerts, crime probability, universal safety scores, realtime crowds/lamp operation, bus cancellations or multimodal routing, weather integration, nationwide coverage, accounts, background tracking, SOS dispatch, live navigation and crowdsourced incident reporting. Future investigation is allowed; these are not promised features.

No dangerous-area or person profiling. No inference of demographic traits. No police-station proximity presented as proof of safety. A mapped road, venue or lamp is context, not a validated risk measurement.

## Product wording

Use: “Matches your lighting preference,” “near recorded lighting assets,” “mapped nightlife venues,” “historical activity at this counter,” and “current conditions unknown.”

Avoid: “safest,” “crime-free,” “82% safer,” “well lit now,” “this street is empty,” or “pubs are dangerous.” Display lighting-proximity percentage only with its definition, source date and threshold. An estimated walking time is not a service guarantee.

## Success and release criteria

Success is a reproducible comparison for a real corridor plus honest error states. Record actual route metrics and test evidence; do not promise crime reduction or invent user-study outcomes. Desired cached response time under three seconds is a proposed engineering target, to measure before claiming.

Demo-ready requires the [acceptance checklist](ACCEPTANCE_CHECKLIST.md), actual run instructions and a saved backup. Public deployment and event submission are separate actions, not authorised or completed by writing this PRD.

## Open decisions

- Confirm corridor and remaining build time. CHQ to Connolly is a suggestion, not a validated showcase.
- Confirm roles and whether R6 or R7 is the first optional milestone.
- Verify licences/attribution and graph/venue access.
- Confirm model access, allowed costs and submission instructions as needed.

Next: complete the data-and-path gate in [the implementation plan](IMPLEMENTATION_PLAN.md). For detailed behaviour see [design](DESIGN.md); for continuation see [next session](NEXT_SESSION.md).
