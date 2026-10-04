# Ireland After Dark — frontend

Person 3 contribution. Vite, vanilla JavaScript and Leaflet. Starts in explicit
synthetic demo mode. The backend and agreed API contract are absent on the fetched
`origin/docs/task-split` (3f969b0); real integration is not verified.

The interface takes visual direction from the user-supplied
[SafeWalkMaps reference](https://www.safewalkmaps.com/): dark surfaces, amber accents
and route-focused presentation. Original copy and illustration retain this project's
evidence limitations. Desktop uses a side-by-side planner/map; mobile stacks them.
Use the Plan your walk link to jump directly to the functional planner.

## Local commands (PowerShell)

Requires Node 20.19+ or 22.12+; developed with Node 24.16.0 / npm 11.13.0.
From the repository root:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev -- --port 5173 --strictPort
```

Open http://127.0.0.1:5173. Choose origin and destination through directory results,
map clicks, or the keyboard coordinate controls; choose Compare routes, then Show
routes to fit the map. Editing does not move the viewport. Demo fixtures always use
the fixed illustrative Dublin journey, not the requested points. They are not paths
from a street graph and cannot be used for navigation.

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run test:browser
```

Browser checks use installed Microsoft Edge through Playwright. On another machine,
install an appropriate Playwright browser and adjust `launchOptions.channel` in
playwright.config.js. Tests block external tile requests: they exercise local UI,
route layers and API interception without scraping map tiles.

## Demo and API configuration

Use the Data mode selector to switch explicitly. Switching clears old results.
Demo scenarios include two routes, identical routes, missing data/Low confidence,
unsupported area and no route. All fixture measurements and scores are synthetic.
There is no automatic fallback after a real API failure.

Copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL` to the local backend
origin (e.g. http://127.0.0.1:8000). Restart Vite after changing configuration.
Without configuration the adapter calls same-origin `POST /route`.
`VITE_TILE_URL` may replace the default tile template; a replacement provider must
allow the usage and its required attribution must be added in src/main.js.
All VITE variables are public browser values: never put credentials in them.

Read [the proposed contract](API_CONTRACT_PROPOSED.md). Person 4 must agree or replace
it and configure CORS for http://127.0.0.1:5173 (JSON POST preflight included).
Only src/api.js handles API transport/validation; src/main.js uses its normalized
route shape. No transit preferences or scoring formulas are implemented.

## Search and provider policy

Search is a deliberately small local directory (12 approximate town/city-centre
points, hand-entered for endpoint selection). These are not verified street
addresses, POIs or evidence of routing support. Search submits only when requested;
unknown places use map clicks or explicit coordinates. No external geocoding
provider receives a query and there is no geocoding API/key requirement.

Reviewed on 4 October 2026: the [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/)
prohibits client autocomplete, limits aggregate application traffic to one request
per second, requires attribution/identification, and requires a deliberate informed
developer choice for generated integrations. Consequently the public geocoder is
not built into this implementation. A full address service requires a separately
agreed provider and its policy, with configuration and aggregate rate controls.

The [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/) permits
normal interactive browser viewing with attribution, Referer and browser caching.
The app uses its required HTTPS template and normal browser cache; no prefetch,
offline downloads or cache bypass. Tile availability is best effort. No automated
test accesses public tiles. Map requests reveal the viewed area/IP to the provider.

## Honest interpretation and privacy

- The map covers Ireland visually; real graph bounds stay unknown until the API returns them.
- Returned rectangular bounds show graph extent, not guaranteed connectivity or data completeness.
- Backend confidence/scores/factors are displayed unchanged. Unknown metrics stay unknown.
- Waiting is Not applicable for walking unless an explicit supported meaning is returned.
- Source content dates and attributions appear verbatim as text; absent dates are unknown.
- Departure is converted from Europe/Dublin to an absolute ISO instant regardless of
  browser timezone. DST gaps reject input; autumn duplicates have an explicit occurrence selector.
- No storage, analytics, accounts or coordinate logging. Requests send coordinates only
  to the configured API; the backend operator must also avoid unnecessary journey logging.
- Map/search/API errors remain visible; input edits abort pending work and clear stale routes.

## Verification

See [HANDOFF.md](HANDOFF.md) for actual checks and remaining integration work.
The intercepted browser responses are fixtures, not proof of a running backend.
