# Team project brief

**Historical starter proposal.** The subsequent team task split targets Ireland
routing with Dublin-specific evidence. Person 2's current implementation scope
and acceptance gates are in [data-plan.md](data-plan.md). The narrower scope and
timing assumptions below predate that split.

## Direction

The team proposed an after-dark route tool using public data for Build for Ireland on 4 October 2026. Intended build window: four hours. Final feature scope and roles remain to be agreed.

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

30 minutes for data/paths; 60 for routing; 60 for map/comparisons; 45 for optional historical activity or AI; final 45 for checks and rehearsal. Drop optional features when time slips.

## Demo readiness

Valid pedestrian access; measured outputs with sources/dates; unknowns visible; secrets excluded from client/Git; normal and failure cases verified. This starter has not passed application checks yet.
