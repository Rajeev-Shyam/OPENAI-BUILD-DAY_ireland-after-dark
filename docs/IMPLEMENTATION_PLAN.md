# Implementation plan — four people, four hours

4 October 2026. Four-person team size is confirmed by the user. Names and individual assignments are not supplied; P1–P4 are human role slots, not spawned agents. This is a proposed build schedule, not work already done. [PRD](PRD.md) defines scope and [design](DESIGN.md) defines interfaces.

## Outcome

One reproducible Dublin corridor comparison: real shortest pedestrian path plus a bounded preference alternative, measured recorded-lighting proximity, honest unknowns and a usable browser view. Nightlife preference is the first optional feature; model explanation follows when access is confirmed. Historical footfall is last priority.

Start the clock from actual available time. Four hours is a budget, not proof the event deadline still permits four hours. Confirm current submission instructions before planning the final handover.

## Four roles and file ownership

| Person | Responsibility | Owned files | Deliverable |
|---|---|---|---|
| P1 — data/geometry | Public downloads, pedestrian graph, lamps, optional venues, feature metrics and provenance | `src/data.py`, `src/features.py`, `scripts/prepare_data.py`, data manifest, `tests/test_data.py` | Verified graph/features with reproducible preparation and data gaps |
| P2 — routing/API, integration lead | Request contract, validation, routes, detour cap and application assembly | `src/app.py`, `src/config.py`, `src/routing.py`, requirements/lock, `tests/test_routing.py` | Local API with deterministic baseline/alternative and useful error states |
| P3 — interface | Map, preference controls, comparison cards, source/unknown states and accessibility | `src/static/`, UI manual-check evidence | Browser flow usable against the same-origin API |
| P4 — explanation/QA, demo lead | Template/model explanation, independent integration checks, release checklist and rehearsal | `src/explain.py`, `tests/test_api.py`, `tests/test_explain.py`, verification/demo evidence | Truthful explanation, tested integrated flow and demo backup |

Every person checks their own output; P4 does not inherit all testing at the end. P2 owns shared configuration and dependency pins. P1/P4 request additions rather than editing the lock simultaneously. P4 curates checklist/handoff updates; all contributors record their actual contribution.

Suggested branches: `codex/data-graph`, `codex/routing-api`, `codex/map-ui`, `codex/explanation-qa`. These are human collaboration suggestions; no branches/agents have been created by this plan. Repository write access remains to arrange; public read access is not collaborator write access.

## Parallel timeline

| Elapsed | P1: data | P2: API/routes | P3: UI | P4: explanation/QA | Checkpoint |
|---|---|---|---|---|---|
| 0–15 min | Confirm corridor/bounds and source URLs | Freeze minimal request/response contract | Sketch one screen against contract | Establish evidence checklist; check model access status | All agree schema, P0 and roles |
| 15–45 | Load lamps; retrieve/inspect walking graph; import smoke checks | Implement validation and synthetic graph route invariants | Build controls and two clearly labelled mock paths | Implement deterministic text; API fixtures and independent test cases | Real graph and dependency gate |
| 45–90 | Return graph/edge feature interface; source manifest | Wire genuine shortest path, edges and API | Replace mock with genuine baseline response | Verify units, source warnings and error states | Real baseline shown end-to-end |
| 90–135 | Validate buffers; add mapped venue layer if straightforward | Preference candidates + hard detour cap | Comparison cards; venue toggle only when available | Check cap/same-route/unknowns; prepare optional model adapter | Real two-route comparison or honest same-route state |
| 135–180 | Fix spatial/data issues; valid counter context only if core passes | Integrate bounded explanation; performance fixes | Accessibility and failure states; source details | Verify explanations against computed facts; integration regression | Feature freeze at 180 min |
| 180–210 | Check freshness/attribution and manifest | Resolve integration defects; confirm run commands | Browser smoke test and map failure fallback | Run acceptance checklist and save measured evidence | Release candidate; no new features |
| 210–240 | Record individual contribution | Confirm exact commit and reproducible startup | Capture permitted demo backup | Rehearse, prepare handoff, confirm submission instructions | Demo/submission only if evidence passes |

The final block includes event submission only if the organisers' method and actual deadline are confirmed. Repository upload is not event submission.

## Contracts that unblock parallel work

P2 publishes a small typed contract before UI work: request preferences and endpoint points/presets; response status, baseline/alternative geometry, distance/time, feature availability, sources, detour and explanation mode. P3 may use a clearly marked fixture until integration; fixtures cannot appear as live results in the demo.

P1 exports a validated graph plus per-edge physical length, geometry and feature fractions/status. All geometry and metres use the declared CRS. P2 preserves multigraph edge identity through routing and response assembly.

P4 receives server-computed facts, not arbitrary client metrics. Explanations cannot generate geometry or unverified safety claims. Core comparison continues if AI is disabled or fails.

Only merge changes whose local checks pass. P2 integrates in dependency order: data interface → baseline API → UI → preferences → explanation. P4 tests the integrated commit after each milestone. Avoid last-minute broad refactors.

## Gates, scope cuts and fallback

1. **By 45 minutes:** dependencies and a valid real pedestrian graph load. If not, shrink the area or use a permitted, source-documented snapshot. After about 20 minutes of repeated access failure, reassess. Never quietly substitute generated map lines.
2. **By 90 minutes:** one genuine baseline appears in the browser. If not, everyone prioritises that flow; stop optional features.
3. **By 135 minutes:** preferences obey the cap and a same-route result is honest. A showcase need not have a fabricated improvement.
4. **By 180 minutes:** freeze features. Fix bugs and rehearse only.

Cut order: footfall → live model adapter → venue avoidance if data is unavailable → unrestricted map-point input (keep verified presets). Preserve genuine graph routing, source disclosure, cap and missing-data behaviour. If lighting cannot load, a baseline-only view is partial, not a completed lighting recommender. If no real graph works, stop claiming routing readiness and show research/prototype status.

No AI API calls until existing access and authority are established. Do not create keys or buy credits. If only deterministic explanations work, label them correctly and leave AI/event readiness unresolved.

## Completion and handoff

Complete [acceptance](ACCEPTANCE_CHECKLIST.md), record commands actually run and source hashes, update README with the real run command, and save final commit plus known gaps in [NEXT_SESSION.md](NEXT_SESSION.md). Keep personal notes excluded from Git. Push reviewed changes only to the existing repo; no deployment, invitations or public data redistribution without the relevant authority/licence review.

Immediate next action: begin the first 15-minute contract/corridor checkpoint, then the data-and-path gate. Do not restart completed project-selection research.
