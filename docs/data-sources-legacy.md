# Public data notes

**Historical starter notes.** The current audited source documentation, verified
licence versions, download commands and quality findings are in
[data-sources.md](data-sources.md). These earlier notes are preserved as context;
their unresolved questions may have been answered in the current audit.

Access checks: 4 October 2026, anonymous requests. Inspected in memory; no snapshots included. Data access is not application verification.

## Public Lighting DCC

- Catalogue: https://data.smartdublin.ie/dataset/street-lighting-dublin-city
- CSV: https://data.smartdublin.ie/dataset/064a3764-84aa-48d0-ac43-f5b45f229584/resource/41e3bf5e-74a3-4d98-9de7-fdf7c57f7c6b/download/dcc-pl-assert-list_open-data_260321.csv
- HTTP 200; 45,017 rows. Fields: ID, site_name, unit_no, unit_type, latitude, longitude.
- Resource metadata: December 2021. Exact latest survey date unknown.
- Catalogue licence: cc-by; confirm exact version/attribution before redistribution.
- No lamp operating status or measured brightness. Proximity buffers are assumptions; manually check mismatches across rivers/parallel roads.

## Pedestrian Footfall DCC

- Catalogue: https://data.smartdublin.ie/dataset/dublin-city-centre-footfall-counters
- Genuine pedestrian CSV inspected: https://data.smartdublin.ie/dataset/cc421859-1f4f-43f6-b349-f4ca0e1c60fa/resource/71d3bd5b-3f7a-40fa-94b4-022a97f804e2/download/pedestrain-counts-1-jan-2-jun-2026.csv
- Locations: https://data.smartdublin.ie/dataset/cc421859-1f4f-43f6-b349-f4ca0e1c60fa/resource/215d83bd-003d-4c1a-ac0d-b1132661746c/download/dublin-city-centre-footfall-counter-locations-18072023.csv
- HTTP 200 for both. Counts: 3,672 hourly rows, 1 January through 2 June 2026. Locations: 34 pedestrian counters.
- The September-labelled pedestrian resource contains cyclist series. Reject it for pedestrian estimates.
- Grafton st/Monsoon is entirely empty in the inspected 2026 CSV. Check series quality/coordinate matches; missing readings are unknown, not zero.
- Totals and IN/OUT overlap: do not double count. Time zone/DST remains to check.
- Catalogue licence: cc-by; verify exact version/attribution before redistribution.
- Historical point measurements do not establish live activity across an entire route.

## Other proposed sources

- OpenStreetMap: pedestrian graph/venues not yet retrieved or verified for the chosen area. Respect walking access, service usage policies and attribution/licence.
- CSO methodology: https://www.cso.ie/en/media/csoie/methods/recordedcrime/Recorded_Crime_SIMS_2023.pdf - area statistics do not provide yesterday's street-level incident locations. No recent incident feed verified.
- NTA: https://developer.nationaltransport.ie/ - realtime requires signup/keys; no credential or response checked. Outside the first version.

No source proves that a route is safe. Show recorded features, coverage and uncertainty independently.
