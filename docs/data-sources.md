# Data sources and acquisition

Audit date: 4 October 2026. Person 2 scope is lighting and pedestrian activity first; optional sources below are research findings, not implemented layers. Catalogue access is not proof of usable observations. Source snapshots were downloaded and parsed, and the acquisition tests passed; routing integration must be verified separately.

## Reproduce the P0 downloads

From the repository root, with Python 3.9 or newer:

```sh
python3 -m data.pipeline.download --source all
python3 -m data.pipeline.download --source lighting --refresh
python3 -m unittest discover -s tests -p test_download.py -v
```

`--source` also accepts `footfall_counts` and `footfall_locations`. `--output-dir`, `--timeout` (seconds), and `--attempts` are configurable. No account or manual browser download is required for these three sources. `all` means all registered P0 sources, not every proposed future dataset.

The [source registry](../data/sources.json) pins the exact CSV resources, required columns and licence metadata. Downloaded files are `data/raw/lighting.csv`, `footfall_counts.csv`, and `footfall_locations.csv`. Each has `<source>.manifest.json` containing retrieval time, original/resolved URL, SHA-256, byte size, row count, columns, attribution, licence, and HTTP metadata. Immutable copies live in `data/raw/snapshots/`. The manifest plus its referenced snapshot is authoritative; named CSVs are convenience aliases. A verified cache works offline; `--refresh` explicitly requests new upstream bytes. Refresh is not guaranteed to reproduce old data: retain immutable snapshots and hashes for exact replay.

Responses must have an accepted CSV-like content type, UTF-8 text, expected columns, consistent row widths and at least one observation. HTML/error payloads, cyclist series, truncation and oversized responses are rejected. Transient network/HTTP errors get bounded retries. A bad refresh preserves the prior valid manifest/snapshot. Cache corruption fails visibly; it is not silently accepted. These checks establish acquisition integrity, while the cleaning stages validate measurement quality.

## Lighting — P0

[Dublin City Council catalogue](https://data.smartdublin.ie/dataset/street-lighting-dublin-city). [Pinned CSV](https://data.smartdublin.ie/dataset/064a3764-84aa-48d0-ac43-f5b45f229584/resource/41e3bf5e-74a3-4d98-9de7-fdf7c57f7c6b/download/dcc-pl-assert-list_open-data_260321.csv).

The source records public lighting assets in the DCC administrative area, including some ESBN/Luas assets. The resource describes 2021 data; a newer catalogue modification date does not establish a fresh asset survey. Local inspection: 45,017 rows, columns `ID,site_name,unit_no,unit_type,latitude,longitude`, 2,768,433 bytes. Asset types were audited: this snapshot contains lighting-related columns, poles, brackets, housings and catenary. The pipeline counts recorded assets, not individual lamp heads; a management-system asset is not automatically a working lamp.

Coordinates represent recorded infrastructure, not brightness, working status or a verified illumination radius. Geometric proximity is a prototype assumption and can cross barriers or match parallel roads. Do not label missing assets as an unlit street. Do not infer administrative coverage from a bounding rectangle around points. Report evidence coverage independently of lighting density. No all-Ireland lighting coverage is supplied by this source.

## Pedestrian activity — P0

[DCC footfall catalogue](https://data.smartdublin.ie/dataset/dublin-city-centre-footfall-counters). [Pinned counts CSV](https://data.smartdublin.ie/dataset/cc421859-1f4f-43f6-b349-f4ca0e1c60fa/resource/71d3bd5b-3f7a-40fa-94b4-022a97f804e2/download/pedestrain-counts-1-jan-2-jun-2026.csv). [Counter locations](https://data.smartdublin.ie/dataset/cc421859-1f4f-43f6-b349-f4ca0e1c60fa/resource/215d83bd-003d-4c1a-ac0d-b1132661746c/download/dublin-city-centre-footfall-counter-locations-18072023.csv).

These are hourly historical point counts. Local inspection: 3,672 hourly records, 1 January–2 June 2026, plus 34 location rows. The CSV catalogue label says May while its filename and observed dates extend into June. September-labelled resources point to cycling files; automatic “newest resource” selection would be incorrect. The pinned pedestrian schema is checked explicitly.

Totals and directional IN/OUT series overlap and must not be added together. Missing readings are unknown. Grafton st/Monsoon is entirely empty in this snapshot. Location names require explicit verified aliases; unmatched series stay unlocated. Coordinates from a 2023 location file do not prove that a counter has never moved. Dublin local wall-clock interpretation is a stated assumption: the CSV has no explicit timezone/offset and DST treatment needs publisher confirmation. Short-range edge assignment is an estimate, not a measurement across a neighbourhood. Historical means cannot establish current activity.

## Licences and attribution

The dataset-specific data.gov.ie CKAN API confirms **CC BY 4.0** for both lighting and footfall, linked to https://creativecommons.org/licenses/by/4.0/. Smart Dublin CKAN instead returned the generic `cc-by` identifier without a version; the registry preserves that original metadata alongside the explicit national-catalogue licence. Ireland's [open-data licence guidance](https://data.gov.ie/pages/opendatalicence) specifies attribution. The verification endpoints are recorded in [research notes](research-sources.md).

Credit Dublin City Council via Smart Dublin; footfall is provided by Dublin City Council and NTA. Link to original sources and the applicable licence, and state that cleaning, spatial matching and prototype scores are our transformations. Suggested generic wording from the national guidance: “Contains Irish Public Sector Data licensed under a Creative Commons Attribution 4.0 International (CC BY 4.0) licence”. This does not imply provider endorsement. OpenStreetMap has a separate licence below. Do not apply a repository code licence to third-party data.

## Optional-source audit

| Source | Verified access and licence | What remains before an implemented layer |
| --- | --- | --- |
| [SCATS/signals DCC](https://data.gov.ie/dataset/traffic-signals-and-scats-sites-locations-dcc) | Official catalogue lists downloadable CSV/GeoJSON; national catalogue explicitly CC BY 4.0. DCC jurisdiction only. | Fetch and inspect chosen snapshot. Locations include junction signals/detectors; proximity alone does not prove a signal-controlled pedestrian crossing on the traversed edge. |
| [OSM crossing tags](https://wiki.openstreetmap.org/wiki/Key:crossing) | OSM supports crossing metadata. [ODbL](https://www.openstreetmap.org/copyright), attribution to OpenStreetMap contributors. | Use Person 1's exact graph/extract and retain tags; missing tags mean unknown. Resolve actual crossing topology before assigning penalties. Do not infer pedestrian signal control from any nearby traffic light. |
| [Garda stations DLR](https://data.gov.ie/dataset/garda-stations-dlr) | CSV/GeoJSON links verified in catalogue; CC BY 4.0 explicit on national catalogue. Dún Laoghaire–Rathdown only. | Inspect snapshot and merge wider-area sources without duplicate stations. This is not a national station list and does not establish public opening hours. |
| [Dublin Fire Brigade stations](https://data.smartdublin.ie/dataset/dublin-fire-brigade-stations-dublin-region) | Official catalogue offers 2021 and 2025 CSVs; CKAN licence `cc-by`, no explicit version. | Inspect coordinates and source-specific attribution/version. Station presence does not establish public access or available assistance. |
| [OSM hospitals](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dhospital) | Community-mapped hospitals are a feasible ODbL source. | A vetted Irish hospital point feed was not verified. Use reviewed OSM data if adopted; verify entrances, emergency-service tags and opening/access information. A hospital is not automatically an emergency department. |
| [RSA collisions](https://www.rsa.ie/road-safety/statistics/collisions) | Official map describes source-data export and permits use with RSA/date attribution, but explicitly prohibits web scraping and altering data values. | **Automated ingestion blocked:** no sanctioned machine-readable endpoint/licence for this pipeline verified. Do not scrape embedded dashboards. Source notes provisional recent data and some missing coordinates; this would describe road collisions, never personal security. |
| [CSO recorded crime](https://www.cso.ie/en/releasesandpublications/ep/p-rc/recordedcrimeq12026/backgroundnotes/) | Official methodology checked; records concern reported/known crimes and Garda administrative areas. | P2 context text only. No table/export or table-specific licence verified for ingestion, and no crime weight implemented. |

The user subsequently requested NTA schedule and realtime ingestion. That addition
now has a separate [source audit](research-nta-sources.md), [realtime research](research-nta-realtime.md)
and [data handoff contract](transport-data-contract.md). Static NTA acquisition and
processing are implemented; both realtime endpoints have passed authenticated
fetches, with stale observations and identifier mismatches documented in the
[validation record](nta-validation.md). Transport routing and weather remain outside this
data-pipeline implementation; Met Éireann ingestion is not implemented.

## Honest completion boundary

P0 source acquisition is implemented and tested. “Download every dataset” cannot truthfully be marked complete across all proposed P1/P2 sources: the table explicitly distinguishes discovered URLs from tested downloads and unresolved access/licensing. Further sources should be added to the registry only after actual payload and schema checks. Missing geographic coverage remains unknown, including outside Dublin. None of these sources establishes that a route is safe.
