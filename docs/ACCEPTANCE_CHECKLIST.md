# Acceptance, verification and demo

Initial state: every application check below is **NOT RUN**. No application exists. Prior successful public downloads do not count as route or UI tests. P4 curates this checklist; P1–P3 own checks for their modules.

## Required checks

| Check | Method / evidence needed | Pass condition |
|---|---|---|
| Reproducible startup | Fresh project environment or documented clean-environment run | Pinned installs and recorded commands work; no hidden private-file dependency |
| Source provenance | Preparation manifest | URLs, fetch/content dates, licence status, hashes, CRS, bounds, counts and errors saved |
| Coordinates and units | Known-distance synthetic geometry | Metres computed in metric CRS; WGS84 GeoJSON order correct |
| Pedestrian validity | Graph invariants plus manual map inspection | Connected edge sequence; no prohibited shortcut; crossings and endpoint entrances inspected |
| Baseline correctness | Independently sum selected edges and compare shortest distance | Output uses actual selected edges and physical distance, not preference cost |
| Lighting fraction | Synthetic geometry with overlapping/duplicate buffers | Fraction in [0,1]; no double counting; missing data remains unavailable |
| Venue preference | Synthetic venue/graph plus source state | Toggle can affect cost; absent data disables it; no venue-danger/open-now claim |
| Detour cap | Synthetic short/long alternatives, including zero allowance | Every offered alternative satisfies physical cap |
| Same-route case | Fixture with no distinct qualifying alternative | Honest explanation; no invented benefit |
| Normal request | Real corridor via API/browser | Valid routes, measured comparison and source dates display |
| Unsupported request | Outside area/invalid coordinate; crime-prediction request if AI input exists | Typed error or unsupported explanation; no hallucinated route/incident |
| Missing-data case | Remove snapshot or optional feature | Clear readiness/feature state; no silent zero or fabricated recommendation |
| Disconnected points | Known disconnected graph components | No-path response, no straight line substituted |
| AI failure/grounding | Timeout, malformed output and invented numeric claim | Valid routes preserved; rejected explanation uses labelled deterministic fallback |
| Browser/accessibility | Keyboard use, mobile-size layout, source/error states | Controls usable, lines labelled, contrast adequate, unknowns visible |
| Privacy/share audit | Diff and tracked-file inspection | No secrets, request histories, personal notes or executable data artifacts shared |

Use small synthetic fixtures to test algorithm invariants without changing real-world facts. Label fixtures and exclude them from production result paths. Add meaningful application tests as code exists, not tests that merely echo implementation.

## Release evidence record

Fill with actual results, never predicted results:

```text
Commit: pending
Runtime/package pins: pending
Preparation command and manifest hash: pending
Application run command: pending
Automated checks and result: NOT RUN
Real corridor / source dates: pending
Normal request: NOT RUN
Unsupported request: NOT RUN
Missing-data request: NOT RUN
Browser/manual route inspection: NOT RUN
Model mode/access: unverified
Known gaps / failed checks: pending
Submission instructions / confirmation: pending
```

## Suggested short demo

1. State the user's task: comparing walking choices after dark, not predicting crime.
2. Show one genuine baseline and chosen preferences.
3. Show the actual alternative or explain that none meets the cap; read measured trade-offs.
4. Open source dates/unknowns. Explain that recorded assets and historical counters are not live conditions.
5. Show one unsupported or missing-data case and describe the next bounded improvement.

Do not hard-code a more impressive result for the demo. Prepare a permitted screenshot/video or saved measured response at the tested commit, labelled as a recorded backup. No bulk tile cache. Deployment/submission are not complete until separately verified.
