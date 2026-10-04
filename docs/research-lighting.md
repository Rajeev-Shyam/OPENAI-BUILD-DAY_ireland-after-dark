# Lighting: source evidence and model limits

Checked 4 October 2026. This is a reproducible asset-proximity model, not a
measurement of brightness, working lamps, or personal safety.

## Primary source evidence

[Dublin City Council's catalogue](https://data.smartdublin.ie/dataset/street-lighting-dublin-city)
describes public lighting assets in the DCC administrative area, including DCC,
ESBN and LUAS assets. Its date range is 2021; the catalogue update of 19 June
2025 does not establish a new field survey. Annual update frequency is metadata,
not evidence that this downloaded snapshot is current. The dataset's `Version
2.0` field is not a licence version.

The [CSV resource page](https://data.smartdublin.ie/dataset/street-lighting-dublin-city/resource/41e3bf5e-74a3-4d98-9de7-fdf7c57f7c6b)
identifies a 2021 asset list and reports data updated 3 December 2021. It
documents ID, site name, unit number, unit type, latitude and longitude. There
is no operating-status or measured-brightness field.

Both Smart Dublin pages label the licence Creative Commons Attribution and
link to a [generic CC-BY entry](https://opendefinition.org/licenses/cc-by/).
The [official national catalogue API](https://data.gov.ie/api/3/action/package_show?id=street-lighting-dublin-city)
resolves the version: `license_id` is `CC-BY-4.0`, with title Creative Commons
Attribution 4.0 and the [CC BY 4.0 licence URL](https://creativecommons.org/licenses/by/4.0/).
The acquisition audit preserves this source-specific evidence in
[research-sources.md](research-sources.md). Preserve publisher attribution and
source URL; the dataset's own version field is separate from its licence.

Suggested attribution: “Contains Dublin City Council Public Lighting DCC data,
available under Creative Commons Attribution 4.0. Asset
proximity and routing scores are derived by Dublin After Dark.”

## Inspection of downloaded CSV

The pinned download is
[dcc-pl-assert-list_open-data_260321.csv](https://data.smartdublin.ie/dataset/064a3764-84aa-48d0-ac43-f5b45f229584/resource/41e3bf5e-74a3-4d98-9de7-fdf7c57f7c6b/download/dcc-pl-assert-list_open-data_260321.csv).
The local snapshot has 2,768,433 bytes, 45,017 rows and 45,017 unique IDs. All
coordinates pass the pipeline's broad Ireland sanity envelope. Three records
share a coordinate with another distinct asset. They remain separate assets;
their overlapping proximity footprints are unioned, not added.

| Unit type | Accepted assets |
| --- | ---: |
| PL: Column | 32,803 |
| PL: ESB Pole | 8,581 |
| PL: LUAS Pole/Line | 366 |
| PL: Wall Bracket | 2,261 |
| PL: DCC Housing Light | 993 |
| PL: Catenary System | 13 |

The quantity is **recorded lighting assets**, not verified individual lamp
heads. Source coordinate extent is -6.385932 to -6.143069 longitude, 53.301811
to 53.410764 latitude. This extent is not a verified coverage boundary.

## Processing contract

`clean_lights(path)` returns `(list[Light], report)`. The report gives accepted,
duplicate and rejected row counts, reasons and unit-type frequencies. UTF-8 BOM
is supported. Blank IDs, malformed rows, non-finite/reversed/out-of-envelope
coordinates are rejected with counts. Empty usable inventories fail. Identical
duplicate IDs deduplicate; conflicting duplicates fail explicitly. Different
IDs at one coordinate stay distinct.

`enrich_lighting(edges, lights, buffer_m=20.0, coverage_geometry=None)` accepts
edge dictionaries containing `u`, `v`, `key` and a WGS84 Shapely `LineString`.
It returns one dictionary per input edge in the same order, retaining those
identifiers. Duplicated edge identifiers fail. All distance operations use
EPSG:2157 (Irish Transverse Mercator); longitude is always the first axis.

The default 20-metre radius is a **prototype modelling choice**, not a lamp
illumination radius. An STRtree retrieves nearby points, exact metric distance
filters candidates, and the union of point buffers is intersected with the
edge. Circular buffers use 32 segments per quadrant, so coverage length has
small polygon-approximation error.

| Output | Meaning |
| --- | --- |
| `lighting_asset_count` | Number of recorded assets within the chosen radius |
| `lighting_density_per_km` | Count / projected edge length in kilometres; null when unknown |
| `lighting_proximity_fraction` | Edge-length fraction inside recorded-asset buffers; null when unknown |
| `lighting_score` | Prototype 100 × proximity fraction; null when unknown |
| `has_lighting_data` | Positive length supported by asset proximity, or whole edge within explicitly verified inventory domain |
| `lighting_data_coverage_fraction` | Positive-proximity supported length fraction, or 1 when a supplied verified inventory domain covers the whole edge |
| `lighting_coverage_basis` | `recorded_asset_proximity`, `declared_inventory_coverage`, or `unknown` |
| `lighting_buffer_m` | Radius used for this build |

Without an independently verified inventory domain, zero matches means
**unknown**, not a zero lighting score. Positive matches support the portion
of the edge within the buffers, not an assertion that the rest was surveyed.
For positive matches the score summarises recorded proximity across the whole
edge: unobserved portions remain uncertain and may contain unrecorded assets.
Consumers must show data coverage alongside the score. Do not treat the boolean
flag as 100% edge coverage.

An optional verified WGS84 Polygon/MultiPolygon can establish inventory
applicability. Only whole-edge containment enables this basis; a partially
contained edge remains conservative. No boundary is fabricated from the asset
points. Geographic applicability still does not prove an exhaustive or current
inventory.

Assets can match parallel roads, opposite riverbanks or adjacent paths. The
algorithm does not claim asset ownership by a street or account for occlusion,
lamp height, trees, outages, light direction or colour. Review actual routes
against geography before a demo. Count totals must not be summed over route
edges as unique lamps: the same lamp can support neighbouring edges. Aggregate
proximity and data coverage by edge length instead.

## Verification boundary

Tests exercise metre-based distance, overlapping buffers, stable identifiers,
reverse/split edges, unknown versus declared-zero inventory, invalid schemas,
bad coordinates and conflicting IDs. The actual source passes cleaning with
zero rejected rows. Neither proves field accuracy or end-to-end routing: the
routing team's graph must still be supplied and inspected on a map. Source age
must remain visible; a successful download does not refresh the asset survey.
