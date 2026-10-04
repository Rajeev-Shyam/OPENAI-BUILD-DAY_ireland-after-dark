# Shared decisions and assumptions

Updated 4 October 2026. Product/build decisions are proposals unless marked confirmed. Actual user names/roles are not recorded here.

| ID | Decision | Status / rationale |
|---|---|---|
| D1 | Four human contributors | Confirmed by user; role slots in implementation plan |
| D2 | After-dark route idea using public data | Confirmed team direction; detailed MVP remains proposed |
| D3 | First geography is small central Dublin | Proposed: source coverage and four-hour limit; broader repo name is not national coverage |
| D4 | Route preference comparison, not a crime/safety classifier | Proposed evidence-led scope: current sources cannot support street-level recent incidents or safety guarantees |
| D5 | Deterministic routing and geometry | Proposed: reproducibility, measurable cap, source-derived features |
| D6 | Plain browser UI plus one Python service | Proposed: less setup/integration work; dependency compatibility untested |
| D7 | Real walking graph and recorded lamps first | Proposed P0: simplest useful end-to-end flow; graph access must pass first gate |
| D8 | Nightlife avoidance is optional preference | Proposed P1 reflecting team interest; mapped venue presence is not risk/opening/crowding evidence |
| D9 | Bounded model explanation behind access gate | Proposed P1: no paid calls/key creation assumed; template fallback labelled |
| D10 | Footfall is historical point context | Proposed P2: sparse/missing counters and mislabeled resource prevent route-wide live activity scoring |
| D11 | Current GitHub name is ireland-after-dark; visibility public | Observed live during docs work; do not change settings; only reviewed project files pushed |
| D12 | Keep local personal context outside shared tree | Confirmed user privacy boundary; .git/info/exclude protects this workspace |

Proposed numeric defaults, candidate limits and buffers are in [design](DESIGN.md); they are not validated risk coefficients. Change them only with a reason recorded here and consistent PRD/acceptance updates.

Unresolved: people-to-role mapping, exact corridor/bounds, remaining time, model access/authority, source attribution details, relevant organiser rules and actual submission method. Do not infer resolution from repository existence or this plan.

Documentation review completed: checked scope/priorities against four human roles, detour cap against physical geometry, source-versus-application schema wording, incomplete-feature states and next-session independence from private files. Local relative-link/fence/privacy checks passed. Application tests remain NOT RUN; no implementation occurred.
