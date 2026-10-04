# API contract: `POST /route`

Status: draft, agreed by the team before backend/frontend work starts. Change here first, then in code.

## Request

```json
{
  "origin": { "lat": 53.3478, "lng": -6.2597 },
  "destination": { "lat": 53.3524, "lng": -6.2498 },
  "departure_time": "2026-10-04T21:30:00+01:00",
  "preferences": {
    "max_detour_minutes": 10,
    "well_lit": 0.5,
    "busier": 0.5,
    "less_walking": 0.5,
    "less_waiting": 0.5,
    "avoid_nightlife": false
  }
}
```

- `origin` / `destination`: WGS84 lat/lng in decimal degrees. Required.
- `departure_time`: ISO 8601 with timezone offset. Optional; server defaults to "now" when omitted.
- `preferences`: optional. Each weight is `0.0`–`1.0`, default `0.5`. `max_detour_minutes` bounds how much longer the Night Route may take versus the Fastest Route. `avoid_nightlife` is a comfort preference, not a danger classifier.

## Response (success)

```json
{
  "routes": {
    "fastest": {
      "geometry": { "type": "LineString", "coordinates": [[-6.2597, 53.3478], [-6.2588, 53.3481]] },
      "distance_metres": 950,
      "duration_minutes": 12.3,
      "route_score": null
    },
    "night": {
      "geometry": { "type": "LineString", "coordinates": [[-6.2597, 53.3478], [-6.2601, 53.3490]] },
      "distance_metres": 1080,
      "duration_minutes": 14.1,
      "route_score": 78
    }
  },
  "score_breakdown": {
    "lighting": 82,
    "activity": 65,
    "crossings": 70,
    "waiting": null
  },
  "data_confidence": {
    "level": "high",
    "reasons": ["lighting data covers this area", "footfall data covers this area"]
  },
  "explanation": [
    "Night Route is 2 min longer and 29 percentage points more recorded street-light coverage than the fastest path.",
    "Both routes stay inside the area with recorded footfall data."
  ],
  "warnings": []
}
```

- `routes.fastest` / `routes.night`: GeoJSON `LineString` geometry in `[lng, lat]` order (GeoJSON convention), plus distance and duration. `route_score` is `null` on the fastest route (it is not optimised for score).
- `score_breakdown`: per-factor contribution to `route_score`, out of 100 each. A factor is `null` when its underlying data does not cover the route (e.g. no crossing data for an edge) rather than silently scored `0`.
- `data_confidence.level`: one of `"high"`, `"medium"`, `"low"`. Outside Dublin this is `"low"` by default because lighting/footfall/SCATS datasets do not cover the area yet — see [data-sources.md](data-sources.md).
- `explanation`: plain-language, deterministic-fact strings. See wording rules below; never invented numbers.
- `warnings`: non-fatal notices, e.g. `"destination is outside the area with lighting data"`.

## Response (no route found)

```json
{
  "routes": null,
  "error": {
    "code": "NO_ROUTE",
    "message": "No pedestrian path connects these points."
  }
}
```

## Response (invalid input)

```json
{
  "routes": null,
  "error": {
    "code": "INVALID_INPUT",
    "message": "destination.lat must be between -90 and 90."
  }
}
```

### Error codes

| Code | Meaning |
|---|---|
| `INVALID_INPUT` | Request failed validation (missing field, out-of-range value). |
| `OUT_OF_AREA` | Origin or destination is outside the routable network. |
| `NO_ROUTE` | Both points are in the network but no path connects them. |
| `INTERNAL_ERROR` | Unexpected server-side failure. |

## Wording rules (apply everywhere: API text, UI, pitch)

- Say **"lighting coverage"**, not "brightness" or "safety lighting" — we only know a light asset is recorded nearby, not that it works or how bright it is.
- Say **"activity"** or **"recorded footfall"**, not "safe" or "busy right now" — footfall data is historical, not live occupancy.
- Never say a route **"is safe"** or give a **"safety score"**. The product name for the computed value is **Route Score** / **Night Route Score**, not "Safety Score".
- Missing data is **"unknown"**, never **"zero"** or **"none"** — a gap in coverage must read as a gap, not as a negative signal.
- Never invent or round-dress numbers in `explanation` text. Every number in an explanation string must trace back to a field in this response.
