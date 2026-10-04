# Task split

Scope: Ireland map. Routing works anywhere in Ireland using OpenStreetMap. Some datasets only cover Dublin (street lights, footfall, SCATS signals), so outside Dublin the Data Confidence score will be Low and the app says so. That keeps us honest and makes the confidence feature earn its place.

Priority: P0 = must ship, P1 = if time allows, P2 = future.

Names are placeholders. Swap in real ones.

## Shared first (everyone, first hour)

- [ ] P0 Create repo, folders, `.gitignore`, `.env.example`
- [ ] P0 Write `docs/api-contract.md` (request and response JSON for `POST /route`)
- [ ] P0 Agree wording rules (coverage not brightness, activity not safe)
- [ ] P0 Everyone clones and runs hello world

## Person 1: Routing engine (`backend/routing/`)

- [ ] P0 Pull Ireland walking network from OSM (start with Dublin tile, then widen)
- [ ] P0 Build graph and cache it to disk so startup is fast
- [ ] P0 Snap origin and destination to nearest nodes
- [ ] P0 Fastest route (distance based Dijkstra)
- [ ] P0 NightCost edge weights from the score fields
- [ ] P0 Night Route (Dijkstra or A* on NightCost)
- [ ] P0 Return geometry, minutes and metres for both routes
- [ ] P1 Apply user preference weights from the request
- [ ] P1 Crossing penalties (signal, minor road, major unsignalised)
- [ ] P1 Performance pass: keep response under a few seconds
- [ ] P2 Route deviation check against the chosen route

## Person 2: Data pipeline (`data/`)

- [ ] P0 Download scripts for every dataset, no manual steps
- [ ] P0 Street-light data: clean, match lights to edges, lighting density per km
- [ ] P0 Footfall counters: clean, average by weekday and hour, assign to nearby edges
- [ ] P0 Write per edge scores to a processed file that Person 1 loads
- [ ] P0 Coverage flag per edge per source (has lighting data, has footfall data)
- [ ] P1 SCATS signals and OSM crossings to crossing score
- [ ] P1 Garda stations, fire stations, hospitals as a points layer
- [ ] P1 RSA collisions as a pedestrian road-risk layer
- [ ] P2 CSO recorded crime as area context text only
- [ ] Doc: `docs/data-sources.md` with links, licences, known gaps

## Person 3: Frontend (`frontend/`)

- [ ] P0 Map of Ireland (Leaflet or MapLibre, OSM tiles)
- [ ] P0 Origin and destination input with place search
- [ ] P0 Time and day picker (default now)
- [ ] P0 Fastest and Night route drawn in different colours
- [ ] P0 Comparison card: minutes, distance, lighting, activity, waiting, score
- [ ] P0 "Why this route" explanation list
- [ ] P0 Night Route Score breakdown and Data Confidence badge with a clear Low warning
- [ ] P0 Build against mock JSON first, then switch to the real API
- [ ] P0 Loading, error and no route states
- [ ] P1 Preference sliders (well lit, busier, less walking, less waiting, crossings)
- [ ] P1 Mobile layout, since the real use is on a phone
- [ ] P1 Nearby help locations layer
- [ ] P1 Accessibility pass (contrast, keyboard, labels)
- [ ] P2 Share journey and arrival check-in screens

## Person 4: API, scoring, transport, pitch (`backend/api/`, `backend/scoring/`, `docs/`)

- [ ] P0 FastAPI app and `POST /route` matching the contract
- [ ] P0 Route Score out of 100 with per factor breakdown
- [ ] P0 Data Confidence calculation from per edge coverage flags
- [ ] P0 Explanation generator ("4 min longer, 29% more light coverage...")
- [ ] P0 Input validation and clean error responses
- [ ] P0 Unit tests for score, confidence and explanations
- [ ] P0 Demo script with a fixed Dublin route that always works
- [ ] P0 Pitch and limitations slide
- [ ] P1 NTA GTFS: load stops and timetables, walk then transit then walk
- [ ] P1 Minimise outdoor waiting
- [ ] P1 Wait or Walk (our signature feature)
- [ ] P1 GTFS-Realtime for delays and cancellations
- [ ] P1 Met Éireann weather as a secondary factor
- [ ] P2 Stay on the bus longer
- [ ] P2 Journey sharing and arrival check-in endpoints

## Not doing (say it in the pitch)

- Community reporting: needs moderation, abuse prevention, verification and expiry
- Street level crime scoring: recorded crime data is not reliable at that level
- Calling emergency services automatically

## Order of work

1. Contract and mock JSON (everyone)
2. Graph + mock UI + data download (Persons 1, 3, 2 in parallel)
3. Lighting and footfall scores land, Night Route works (1 and 2)
4. Frontend switches from mock to real API (3 and 4)
5. Score, confidence, explanations (4)
6. Feature freeze, demo, pitch
7. P1 items only after step 5 is demo ready

## Dependencies to watch

- Person 1 needs Person 2's processed edge file. Person 2 should ship a rough version early (even with fake values) so routing is not blocked.
- Person 3 needs the contract, not the backend.
- Person 4 needs Person 1's route output shape. Agree it in the contract.
