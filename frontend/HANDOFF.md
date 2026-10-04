# Person 3 handoff

4 October 2026. Sharing branch: `frontend`, created from the completed
`codex/frontend` implementation at `81c1db8`, based on fetched
`origin/docs/task-split` at `3f969b0`. The owner authorises pushing only `frontend`
from now on. The owner subsequently authorised merging `backend-routing` into
`frontend`; merge commit `796e590` incorporates routing commit `5987dfd` and its
data-pipeline ancestry. No merge into main is authorised.

## Routing integration — latest

The branch now includes Person 1's engine and Person 2's pipeline. Neither included
Person 4's HTTP API, so `frontend/dev_api.py` provides a local-only development
bridge matching the proposed frontend shape. Backend routing/scoring/pipeline code
is unchanged by this integration. The older backend-absent notes below describe
the pre-merge checkout.

The bridge accepts `POST /route`, validates coordinates/offset timestamps, reverses
coordinates for the engine, converts units and allows frontend-origin CORS. It
loads only the prebuilt Dublin cache and disables request-time network downloads.
Unsupported locations include the actual cached bounds in the error. It has no
journey logs, database, credentials or paid services.

Important contract behavior:
- Overall route score and its factors are not produced by the engine and stay unknown.
- No evidence for either lighting or activity yields Low confidence and explicitly
  labels the Night alternative unavailable. Partial evidence confidence stays unknown
  until Person 4 implements the agreed calculation.
- Activity is a normalized historical index over covered sections, not counts or safety.
- The bundle covers one weekday/hour. Other selected times disable the engine's
  activity preference and hide that metric. The UI explains this limitation.
- Missing source content dates remain unknown; graph retrieval date is separately labelled.

Verified so far: merged backend suite 95 tests and 5 subtests pass; bridge suite
13 tests pass; frontend core 5 tests and browser 7 tests pass; production build passes.
Real HTTP and browser integration passed against the cached OSM graph before a score
bundle was loaded: valid 965.5 m / 12.4 min baseline route, null evidence/score,
Low confidence, Night unavailable. Real unsupported-area and invalid-input responses
passed. HTTP no-route handling is tested using an explicit test double, not claimed
as a disconnected route observed in the downloaded graph.

After loading the actual Sunday 20:00 bundle, real HTTP and browser checks returned
distinct CHQ–Connolly routes: 965.5 m / 12.4 min / 64.5% recorded lighting coverage
and 1007.8 m / 12.9 min / 89.8% coverage. Activity was unknown on that journey.
A city-centre request returned identical valid routes with a historical normalized
activity index of 0.882. An alternate departure hour correctly excluded activity.
These are observed local snapshot results, not permanent route guarantees.

Local data built successfully: 101,875 graph nodes / 267,580 edges; lighting evidence
supports 39.073% of total graph length and footfall 0.324%. All downloads, graph,
bundle, screenshots and .env.local remain ignored. Actual graph bounds are
[-6.39, 53.29, -6.11, 53.41]; the bridge deliberately rejects outside-cache requests.

Run commands and the current development-bridge boundary are in frontend/README.md.
Next for Person 4: agree or replace this bridge with the application API, supplying
the overall score/factors and confidence calculation without changing unknowns to zero.

## Visual refresh — 4 October 2026

User-supplied reference: https://www.safewalkmaps.com/, visually inspected in a
browser. Adapted the dark palette, warm amber accents and route-led presentation
into an original Ireland After Dark interface. No reference assets, testimonials,
safety guarantees, live-data scores or unimplemented features were copied.

The desktop planner has controls beside a sticky map; phones use a stacked layout.
Added navigation/skip link, a clearly labelled illustrative route diagram, an empty
comparison state and a concise data-limitations section. Fastest is blue; Night is
amber and dashed. Existing API contract and adapter remain unchanged.

Verification for this refresh: production build passes; all 6 Edge browser tests
pass, including the original 5 flows and new navigation/empty-state/layout checks
at 320px, 768px and 1440px. Desktop hero/planner and mobile screenshots visually
reviewed. Public tiles were blocked in tests; live tiles and real API integration
remain unverified. Earlier 5 core tests are unchanged and were not rerun for this
presentation change. Test/build processes were launched hidden on Windows.

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
