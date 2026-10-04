# Person 3 handoff

4 October 2026. Sharing branch: `frontend`, created from the completed
`codex/frontend` implementation at `81c1db8`, based on fetched
`origin/docs/task-split` at `3f969b0`. The owner authorises pushing only `frontend`
from now on. No merge into another branch is authorised.

## Implemented

- Vite/vanilla JavaScript/Leaflet Ireland map, OSM attribution, selected A/B markers.
- Explicit local place search (12 approximate town/city centres), map selection and
  labelled numeric-coordinate keyboard alternative. No unapproved geocoder calls.
- Europe/Dublin time default, absolute UTC payload, explicit autumn occurrence and
  spring gap validation independent of browser timezone.
- Fastest/Night polylines, colour/text/dash legend, comparison cards, explanations,
  Night Route Score factors, backend confidence, prominent Low warning, source dates.
- Unknown measurements preserved; walking waiting defaults to Not applicable;
  valid distance/time retained when evidence is missing; identical routes accepted.
- Persistent synthetic demo banner and explicit API switch. Validation, loading,
  invalid input, unsupported area, no route, network/timeout/malformed-response states.
- Pending requests cancelled on edits; stale cards/routes cleared. Viewport changes
  only through map controls or the explicit Show routes button.
- Responsive layout, native keyboard controls, visible focus, plain-text rendering.

## Contract and decisions

No backend, frontend stack or docs/api-contract.md existed in the fetched branch.
[API_CONTRACT_PROPOSED.md](API_CONTRACT_PROPOSED.md) is explicitly PROPOSED pending
Person 4 agreement. It is kept inside frontend/ rather than changing personal
docs exclusions. Fixtures are in src/fixtures.js; request/validation adapter in
src/api.js. No claim of backend compatibility is made.

Demo geometry and numbers are synthetic and fixed, independent of endpoint edits.
Place search is limited to a local directory; full street-address search is not
implemented. Public Nominatim policy was reviewed and the service is not used.
The directory centres are approximate, hand-entered and not independently verified.
No preferences, transport, weather, nearby-help layer, tracking or backend scoring.

## Verified

- `npm.cmd install`: succeeded, 18 packages added; npm audit reported zero vulnerabilities.
- `npm.cmd test`: 5 passing Node tests for timezone/DST, fixture invariants, adapter
  payload/errors, missing metrics and local search.
- `npm.cmd run build`: production build succeeded (Vite 7.3.6).
- `npm.cmd run test:browser`: 5 passing automated Edge/Playwright tests. Covers normal,
  identical, Low/missing, unsupported and no-route results; selected markers/route
  paths; API payload; escaped explanations; network failure; explicit mode switch;
  loading and cancelled stale requests; keyboard selection; 375px layout overflow.
- Browser timezone forced to America/Los_Angeles: the Dublin departure still posts
  the expected UTC instant. Both DST transitions separately covered by Node tests.
- Mobile screenshot visually inspected: readable stacked controls/cards, no overflow.
  External tiles were intentionally blocked during tests; tile-error text is visible.

An initial browser run failed because an exact label-text selector included select
options. It was corrected to the accessible combobox role/name; the full rerun passed.
Review also caught author CSS overriding the hidden demo control; explicit [hidden]
styling fixes it. The user reported visible terminal windows during testing; no
frontend process or listener remained after the run. Subsequent build/Git processes
are launched hidden. No user terminal was closed.

## Not verified / remaining

- **Real API integration NOT verified:** no backend implementation/run command exists
  on this branch. Browser API checks intercept synthetic responses, not real routes.
- Live map tile availability, real source coverage/graph bounds, real scoring, CORS
  against Person 4's server, physical-phone and screen-reader use remain untested.
- No full-address geocoder, P1 preferences or nearby help. Current local directory
  and map/coordinate fallback keep endpoint selection usable.
- No application secrets, private context, node_modules, generated build or test
  screenshots should be shared. Existing .git/info/exclude is unchanged.

## Next action for Person 4

Agree or revise API_CONTRACT_PROPOSED.md, then provide one runnable `POST /route`
response plus unsupported-area and missing-data cases. Set VITE_API_BASE_URL in
ignored .env.local, allow frontend-origin CORS, select Real API and verify those
three cases end to end. Update only the adapter if the backend shape differs.

Run from repository root: `cd frontend`, then
`npm.cmd run dev -- --port 5173 --strictPort`; open http://127.0.0.1:5173.
