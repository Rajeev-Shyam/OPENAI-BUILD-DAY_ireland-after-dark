# Public-service landmarks and SCATS source layer

These are contextual map layers, not route scores or evidence that a street is safe. The implementation downloads three pinned official CSV resources and a pinned OpenStreetMap hospital query, preserves their raw snapshots and provenance, and produces WGS84 GeoJSON. It does not infer pedestrian crossing control from a signal site's proximity.

## Run

From the repository root with the shared data dependencies installed:

```sh
python -m data.pipeline.context_layers all
# Rebuild offline from hash-verified snapshots:
python -m data.pipeline.context_layers build
# Explicitly fetch updated resources:
python -m data.pipeline.context_layers all --refresh
python -m pytest tests/test_context_layers.py -q
```

`--raw-dir` and `--output-dir` override the default `data/raw/context` and `data/processed/context`. Raw downloads and generated layers are ignored by Git. No API key or manual download is needed. Cached downloads are reused only with matching provenance, CSV schema and SHA-256. Existing CSV downloading code supplies size limits, retry handling and atomic snapshot/manifest writes.

## Sources and licence

| Source | Published coverage and interpretation | Cleaning |
| --- | --- | --- |
| [Garda Stations DLR](https://data.gov.ie/dataset/garda-stations-dlr) — Dún Laoghaire-Rathdown County Council | DLR station inventory; not all Dublin or Ireland. CC BY 4.0. | EPSG:2157 ITM coordinates converted to WGS84 with `always_xy=True`; station IDs retained as strings. Telephone values retained exactly as published, without guessing missing prefixes. |
| [Dublin Fire Brigade Stations](https://data.smartdublin.ie/dataset/dublin-fire-brigade-stations-dublin-region) — Dublin City Council | Dublin region, selected 2025 CSV. [National catalogue licence: CC BY 4.0](https://data.gov.ie/dataset/dublin-fire-brigade-stations-dublin-region/resource/d628b6be-eab0-4717-ad74-91b6efb67ec0). | Published latitude/longitude used; `StaionName` is the source's actual column spelling. Headquarters remains the published HQ landmark. |
| [Traffic signals and SCATS sites](https://data.gov.ie/dataset/traffic-signals-and-scats-sites-locations-dcc) — Dublin City Council | Catalogue describes DCC junctions and pedestrian crossings with signals and/or SCATS detectors. CC BY 4.0. Administrative membership is not independently verified; actual point extent reaches beyond central Dublin. | Latitude/longitude must agree with the supplied WKT point within 0.000001 degrees. Site IDs retained as strings. No site is automatically treated as a controlled pedestrian crossing. |

Contains Irish Government Data licensed under a [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/). Publisher attribution, catalogue URL and source identity are present on each output feature. `data/context-sources.json` records the exact selected resource URLs and required schemas. Catalogue update dates are not assertions of when individual facilities were surveyed.

## Output contract

- `public_services.geojson`: Point FeatureCollection for recorded Garda and fire facilities.
- `scats_sites.geojson`: separate Point FeatureCollection of traffic-signal/SCATS sites.
- `hospitals.geojson`: separate ODbL Point FeatureCollection of OSM hospital-tagged landmarks. Centres of ways/relations are display positions, not verified entrances.
- `context-report.json`: per-source counts, quarantine reasons, raw SHA-256, download timestamp, licence and coverage. The same metadata is embedded in each layer so it remains interpretable when copied separately. Attribution and licence apply per feature/source, not as a blanket CC BY licence for OSM data.

Feature IDs are `<source>:<source_id>`. Every feature contains `source`, `source_id`, `kind`, `name`, `catalogue_url`, `license`, `attribution`, and `coverage`. Public-service features also include address, Eircode and telephone as available. Unknown fields are JSON `null`.

`opening_hours` and `assistance_available_now` are always `null`; `public_access_verified` is always `false` (unverified, not a claim that access is prohibited). The interface must present landmarks, not promise an open building, a staffed desk, or emergency assistance. SCATS `pedestrian_crossing_control` is always `null`. No route costs, edge flags or confidence scores are changed by this module.

For all layers, finite coordinates must pass broad Ireland plausibility bounds (longitude -11 to -5, latitude 51 to 56). These bounds catch gross coordinate mistakes, not wrong street addresses. Garda ITM values are checked before conversion. Invalid observations are quarantined. For council sources, all rows sharing a conflicting source identifier are quarantined together; exact repeats are deduplicated. OSM duplicate element identities fail the build because the query should return each element once; distinct OSM elements may still describe one physical facility. Empty usable output or source/schema/hash failures stop the build before processed layers are replaced. Each output file is atomically replaced, not the entire directory as one transaction.

## Real-source validation receipt — 2026-10-04

Fresh council-source downloads at 13:28 UTC and the OSM hospital extract at 13:38 UTC produced:

| Source | Input rows | Accepted points | Quarantined rows | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| Garda DLR | 6 | 6 | 0 | `f639645e539bdba6ea0ae3adaec069deda185cba3c975c69c1c61b241f825c75` |
| Fire Dublin 2025 | 14 | 14 | 0 | `629a589477464589f3ecfc236a3972a3e8797d448b6e21e399f80eb91c396a4b` |
| SCATS | 1,205 | 1,203 | 2 | `8f263baf332ea6bd7807a3648e028e7d212cb972d8cd56f0ebd53d05523ce48a` |
| OSM hospitals, Dublin bbox | 47 features + 1 count sentinel | 47 | 0 | `29ad28dcfb7f4e50f61a10f84f9d02157d1a256fc73a8db45cea335a3528900b` |

The SCATS source assigns ID `6368` to two different locations and coordinates. Both records are excluded, with explicit quarantine entries; neither is arbitrarily selected. The initial validation failed on this real conflict, motivating the conservative quarantine rule and regression test. No location was corrected from a name or guessed.

Offline rebuild reproduces 20 council-source public-service landmarks, 1,203 SCATS points, and 47 hospital-tagged OSM features (2 nodes, 40 ways, 5 relations). These 47 features are not a count of unique physical hospitals. The complete `all` command passes using cached validated snapshots under the shared Python 3.12 runtime, and all 29 context tests pass. Tests exercise actual schema quirks, ITM conversion, null access/availability, coordinate agreement, invalid geometry, conflicting identifiers, unchanged raw telephone values and tampered snapshot/provenance rejection. Passing these checks establishes the cleaning contract, not an independent on-the-ground audit of each facility.

## Remaining work

Ireland-wide public-service completeness is not provided. Hospital landmarks use community mapping rather than an authoritative HSE inventory; absence from these files does not mean absence of a nearby service. Person 3 still needs to render the layers. Crossing scoring needs explicit OSM pedestrian-crossing evidence and topology, plus edge attribution tests; SCATS proximity alone is insufficient. RSA collisions and CSO context are outside this module.

## Hospital source decision and OSM contract

The current [HSE hospital directory](https://www.hse.ie/services/hospitals/) is a useful authoritative reference, but this implementation does not scrape its pages or claim an HSE-verified coordinate inventory. Research could not verify a working coordinate resource behind older national-catalogue hospital-list links, and the current Department of Health [hospitals-by-sector dataset](https://data.gov.ie/en_GB/dataset/jq14-hospitals-by-sector/resource/5ac0d952-1d9d-40f4-b635-7747d96c3b55) contains aggregate counts rather than facility coordinates.

The hospital layer therefore uses [OpenStreetMap's `amenity=hospital` definition](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dhospital), which describes inpatient facilities, distinct from `amenity=clinic` and `amenity=doctors`. It does not include clinics or infer emergency departments from the hospital classification. Public/private ownership and completeness are not independently verified. OSM tagging can be inaccurate, stale or duplicate a physical facility across different elements; identifiers are retained rather than merging facilities by name/proximity.

The exact Overpass query and URL are pinned in the source registry. It selects hospital nodes, ways and relations intersecting the Dublin bounding box south=53.29, west=-6.39, north=53.41, east=-6.11, matching the initial routing graph extent. Broader Ireland/Northern Ireland area queries failed live validation (overpass-api.de HTTP 504 and Private.coffee read timeout); the smaller Dublin query succeeded on the [documented overpass-api.de instance](https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances). The registry therefore pins that working bounded query, not unverified all-Ireland coverage. It runs only on explicit acquisition/refresh; normal builds use cached snapshots, not per-user live queries.

The [Overpass CSV protocol](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL#CSV_output_mode) supports a final object-count sentinel to detect partial responses. We require the final feature count to equal the received observations; a missing or mismatched count fails the build. The downloader's manifest row count includes the one sentinel record; the cleaner's `input_rows` excludes it. Duplicate element identities fail closed. Empty usable output also fails rather than claiming there are no hospitals.

Node coordinates retain their mapped location. For ways and relations, `position_kind=bounding_box_centre` explicitly signals an approximate display point that need not lie inside the hospital outline. `entrance_verified=false` is always supplied. These positions must not be used as pedestrian routing endpoints without entrance/topology work.

`emergency_as_mapped`, `opening_hours_as_mapped`, and `access_as_mapped` retain unverified OSM tags separately. They never populate the current availability fields. `opening_hours` and `assistance_available_now` remain null and public access remains unverified, even when an OSM tag says `24/7` or `emergency=yes`.

Hospital features retain `osm_url`, source identity, and attribution. **© OpenStreetMap contributors**, licensed under [ODbL 1.0](https://www.openstreetmap.org/copyright). Keep this attribution visible when displaying the hospital layer and preserve the ODbL terms when redistributing its database; it is not licensed as CC BY with the council layers. Raw hashes and retrieval timestamps establish the downloaded snapshot, not the date individual hospital details were last checked.


The validated hospital snapshot contains names such as “Lucena Clinic & St Peter's School” despite `amenity=hospital`, illustrating why this is a tagged-feature layer rather than an authoritative clinical classification. The source also includes specialty-specific `emergency` values, not only yes/no. We preserve the original tag values and do not reinterpret them as available emergency care. An eventual patient-facing service finder would require HSE verification and entrance/access data beyond this contextual map layer.
