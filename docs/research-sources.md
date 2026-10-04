# Source audit evidence — 4 October 2026

Methods: inspect primary publisher pages and CKAN `package_show` responses, download the three pinned public CSVs, check payload schemas/rows and preserve SHA-256 manifests. Catalogue labels were treated as claims to test. gstack's local learning notes informed failure-path testing, evidence preservation and explicit completion boundaries; the gstack runtime was not installed or executed.

## Reproducible P0 fingerprints

| Source | Rows | SHA-256 |
| --- | ---: | --- |
| lighting | 45017 | `809e359b273f0684191cc3d97ac7d8c0853465b52f9ff405e2219412ed0574ea` |
| footfall_counts | 3672 | `eefa18a400c9730fbce3f96d26f3bab8cfd42ebf2079612cfa600bd7680b8633` |
| footfall_locations | 34 | `4bdf7a848070896b0a2dc00d8216e00de7e7a3b3e5ccb260942162c401acbe08` |

Checks passed: download all three real sources, offline cache reuse; tests cover corrupted snapshot rejection, alias repair, invalid refresh preserving prior good data, HTTP 404 without retry, transient 503/network retry, schema/content-type/truncation rejection and cyclist rejection. Network retrieval required sandbox approval; no credentials were used. Python unit tests mock HTTP responses, while the real-source run checks actual server compatibility.

## Catalogue metadata endpoints

The following official CKAN endpoints were inspected directly (the web reader could not read the API responses; Python HTTPS requests succeeded):

- https://data.smartdublin.ie/api/3/action/package_show?id=street-lighting-dublin-city
- https://data.smartdublin.ie/api/3/action/package_show?id=dublin-city-centre-footfall-counters
- https://data.smartdublin.ie/api/3/action/package_show?id=traffic-signals-and-scats-sites-locations-dcc
- https://data.smartdublin.ie/api/3/action/package_show?id=garda-stations-dlr
- https://data.smartdublin.ie/api/3/action/package_show?id=dublin-fire-brigade-stations-dublin-region

All returned the generic `cc-by` licence identifier and `http://www.opendefinition.org/licenses/cc-by`. The national catalogue explicitly displays CC BY 4.0 for [SCATS](https://data.gov.ie/dataset/traffic-signals-and-scats-sites-locations-dcc) and [Garda DLR](https://data.gov.ie/dataset/garda-stations-dlr). National P0 page requests initially returned HTTP 429 in the web reader, but direct official API requests then succeeded and confirmed `CC-BY-4.0`, title `Creative Commons Attribution 4.0`, URL `https://creativecommons.org/licenses/by/4.0/`, for both datasets:

- https://data.gov.ie/api/3/action/package_show?id=street-lighting-dublin-city
- https://data.gov.ie/api/3/action/package_show?id=dublin-city-centre-footfall-counters

National [licence guidance](https://data.gov.ie/pages/opendatalicence) is explicit about attribution and recommended CC BY 4.0, but source-specific metadata is retained faithfully.

## Verified optional resource URLs (not downloaded or processed)

- SCATS current catalogue CSV: https://data.smartdublin.ie/dataset/5fd277d3-4ece-45b7-982a-b6116c45470b/resource/f64c93a1-2bce-42d0-8a8b-b41c95546d8a/download/dcc-traffic-scats-signals-google-maps-1.csv
- Garda DLR CSV: https://data.smartdublin.ie/dataset/f4742714-ccb5-4676-a3f6-10ec8a0be43c/resource/49ebc41c-2dda-419d-bad3-8c2bf7b95d81/download/garda-stations-dlr.csv
- Fire stations 2025 CSV: https://data.smartdublin.ie/dataset/32c58199-d1da-4676-b9c5-35c01d4748a3/resource/121e57fe-1f0f-40b6-b8c6-579713fc901c/download/dublin-fire-brigade-stations-2025.csv

These are catalogue-confirmed pointers, not evidence that each payload meets our future layer's requirements. No automated download is implemented for them yet.

## Decisions grounded in primary sources

- [RSA's collisions page](https://www.rsa.ie/road-safety/statistics/collisions) says “never web-scrape or change the data values”. Therefore no automated dashboard scraping was attempted; sanctioned machine-readable acquisition and permitted transformations need clarification before this feature.
- [OSM copyright](https://www.openstreetmap.org/copyright) documents ODbL and contributor attribution. [Crossing tags](https://wiki.openstreetmap.org/wiki/Key:crossing) and [hospital tags](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dhospital) guide possible future layers, not assumptions about completeness or access.
- [Current CSO background notes](https://www.cso.ie/en/releasesandpublications/ep/p-rc/recordedcrimeq12026/backgroundnotes/) describe administrative records of reported/known crime. [CSO's methodology overview](https://www.cso.ie/en/methods/crime/) says the “Under Reservation” categorisation was lifted following its 2023 review; older search results still describe the old categorisation. Do not repeat the outdated blanket claim that current statistics remain under reservation. The product's area-context-only restriction still stands.

Open questions: footfall timezone/DST convention; source locations' validity through the counts period; lighting survey currency; whether each optional source actually supports the intended spatial layer. Evidence gaps must appear in documentation and output confidence, not be filled with fabricated measurements.
