# Current shared API contract

Implemented in backend/api/main.py; the phase1 route API uses coordinate arrays.
The earlier named-coordinate draft is superseded.

## POST /route

Request: `origin` and `destination` are `[longitude, latitude]`. Optional
`departure_time` is an ISO timestamp with an explicit offset; omitted means now.
`timezone` defaults to `Europe/Dublin`. Unsupported fields are rejected.

Response: `mode: walking`, `coverage`, `comparison_status`, `route_options_note`,
`activity_enabled`, `departure_time`, `hospital_context`, and `routes`.
Routes contain one to three distinct candidates: `fastest`, optionally `night`,
and `alternative1` / `alternative2`. The search is bounded, not an exhaustive
ranking. Alternatives stay within five extra estimated walking minutes.

Each route supplies GeoJSON LineString geometry, `distance_m`, `duration_s`,
`lighting_coverage_pct`, `activity_coverage_pct`, `historical_activity`, `score`,
`score_breakdown`, `confidence`, `limitations`, `explanations`, `sources`, and
`nearby_hospitals`. Coverage is the measured fraction of route length with
recorded evidence; scores are separate prototype preference indices. Unknown
measurements stay null. `waiting` is null for walking.

Activity is excluded from both ranking and output when the requested local
weekday/hour does not match the prepared snapshot. The offline time-score
pipeline can prepare another time slot; no full graph rebuild runs per request.

Hospital entries identify mapped landmarks within 1 km straight-line of the
route (up to five, nearest first). Distances are not walking access distances.
Opening hours, entrances, emergency care and assistance are unverified. Null
means the dataset is unavailable; an empty list means no matching landmarks in
this incomplete snapshot. This is not medical advice or emergency navigation.

Errors have `error.code` and `error.message`: INVALID_INPUT (400),
UNSUPPORTED_AREA (422), NO_ROUTE (404), or INTERNAL_ERROR (500).
Identical endpoints that snap to one node are INVALID_INPUT. Duplicate route
geometries are omitted; fewer than three valid alternatives is a normal result.

## Other endpoints

- POST /geocode: `{ "query": "CHQ Dublin" }` -> `coordinates`, `label`, attribution.
  User-triggered searches only, cached in memory, shared workspace request gate
  at least 1.1 seconds apart. Use a single local API instance. No autocomplete.
  Provider can be changed with GEOCODING_URL. Coordinates and map clicks avoid
  external geocoding. [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/).
- GET /transport/stops: optional saved Luas stop/platform GeoJSON, NTA attribution
  and download date. 503 when missing. Stop location does not prove service now.
- GET /transport/status: freshness recomputed from a saved, checksum-verified
  NTA snapshot. Missing/stale/future/unavailable states remain explicit. Browser
  requests do not fetch NTA. Refresh separately under the shared 60-second gate.
- GET /health: application status and bounded Mongo connectivity check. Walking
  routing uses the cached graph and does not require Mongo or a model API key.

Responses use Cache-Control: no-store. The local development bridge remains an
explicit alternate implementation in frontend/dev_api.py, with its own older
two-route response and no geocoding/transport endpoints.
