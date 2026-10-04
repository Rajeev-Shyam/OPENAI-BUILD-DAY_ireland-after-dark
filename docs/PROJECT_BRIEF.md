# Team project brief

The complete specification is now in [PRD](PRD.md), [design](DESIGN.md) and the [four-person implementation plan](IMPLEMENTATION_PLAN.md). This brief is a summary; where scope differs, follow the PRD. Continue from [NEXT_SESSION.md](NEXT_SESSION.md).

## Direction

The four-person team proposed an after-dark route tool using public data for Build for Ireland on 4 October 2026. Intended build window: four hours. Role names and final optional-feature priorities remain to be agreed. Current repo name is Ireland After Dark; first geography is Dublin.

## Proposed MVP

For someone walking home in central Dublin, compare the shortest pedestrian path with an alternative favouring recorded lighting proximity, within a maximum detour preference. Show computed differences and data limitations.

Use one small area first. Historical footfall is optional where valid coverage exists. Identical routes are an honest result; never fabricate improvement.

AI may interpret supported preferences and explain computed facts once model access is confirmed. Routing/calculations stay deterministic. AI must not invent incidents or navigation geometry.

## First tasks

- [ ] Agree corridor, roles and detour rule.
- [ ] Retrieve a pedestrian graph; inspect access, crossings and connectivity.
- [ ] Match recorded lighting to paths; manually check samples.
- [ ] Implement shortest and preference-based routes with visible unknowns.
- [ ] Show both routes on a map with distance, estimated time and source dates.
- [ ] Confirm model access; add a bounded explanation if time permits.
- [ ] Verify normal, unsupported/out-of-area and missing-data cases.
- [ ] Rehearse, save a backup and confirm submission requirements.

## Scope cuts

No live crime prediction, safety guarantees, realtime transit, live crowd monitoring, nationwide coverage, accounts or user tracking. Nightlife avoidance is a comfort preference.

## Proposed four-hour budget

Use the parallel role timeline in [the implementation plan](IMPLEMENTATION_PLAN.md): contract/corridor first, real baseline by 90 minutes, preferences by 135, freeze at 180, then verification and rehearsal. Nightlife is the first optional preference; historical footfall is last priority. Drop optional work when time slips.

## Demo readiness

Valid pedestrian access; measured outputs with sources/dates; unknowns visible; secrets excluded from client/Git; normal and failure cases verified. This starter has not passed application checks yet.
