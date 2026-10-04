# PROPOSED POST /route contract

Awaiting Person 4 agreement. No backend compatibility has been established.
There is no docs/api-contract.md on the fetched task-split branch. This proposal
lives under frontend/ to preserve the existing personal docs exclusions.

Request (JSON):
```json
{
  "origin": [-6.2603, 53.3498],
  "destination": [-6.248, 53.348],
  "departure_time": "2026-10-04T19:00:00.000Z",
  "timezone": "Europe/Dublin"
}
```

Coordinates use GeoJSON [longitude, latitude]. Departure is an absolute ISO instant
with Z; timezone records the intended local calendar. The example means 20:00 Dublin.
No preferences are sent until agreed. Walking only.

HTTP 200 response: `src/fixtures.js` supplies executable, entirely synthetic examples.
Top-level fields:
- `mode`: `"walking"`.
- `coverage`: `{ "bounds": [west,south,east,north] | null, "description": string }`.
  Bounds describe the actual routing graph extent, not lighting coverage or a promise
  that every point connects. Null means unknown. Description must explain limitations.
- `routes`: exactly two entries, one `kind: "fastest"`, one `kind: "night"`.

Each route:
- `geometry`: GeoJSON LineString; at least two finite [longitude, latitude] points.
- `distance_m`, `duration_s`: required nonnegative finite numbers; estimated walking metrics.
- `lighting_coverage_pct`: number 0–100 or null; recorded coverage, not working lamps.
- `historical_activity`: `{ "value": number, "unit": string }` or null; historical units must be explicit.
- `waiting`: null for walking-only; optionally `{ "seconds": number, "meaning": string }`
  only when the backend has an agreed walking-related meaning (not transit waiting).
- `score`: number 0–100 or null; backend route preference score, never a safety probability.
- `score_breakdown`: array of `{ "label": string, "value": number | null, "max": positive number | null }`.
  Frontend displays factors as supplied and does not derive totals or weightings.
- `confidence`: `"Low"`, `"Medium"`, `"High"` or null, calculated by backend.
- `limitations`, `explanations`: arrays of plain text; low confidence should say which evidence is missing.
- `sources`: array of `{ "name": string, "date": string | null, "attribution": string }`.
  Date is source content date, not download date. Empty array means not supplied.

Missing measurements must be explicit null; absent required fields are malformed.
Identical routes are valid. Low confidence should preserve valid geometry/distance/time.
Source coverage is per route; map position never determines confidence in the frontend.

Errors: non-2xx response with `{ "error": { "code": string, "message": string } }`.
- 400 `INVALID_INPUT`: invalid coordinates, time or unsupported preferences.
- 422 `UNSUPPORTED_AREA`: outside graph; message should describe actual supported area.
- 404 `NO_ROUTE`: no connected walking route.
- 500 `INTERNAL_ERROR`: non-sensitive failure message.

All API access and validation are in src/api.js. Base URL is VITE_API_BASE_URL;
empty means same origin. Person 4 must provide CORS for the frontend origin when
running on a separate port. No credentials are included. Timeout is 15 seconds;
errors never activate fixtures. API must not include secrets or internal stack traces.
