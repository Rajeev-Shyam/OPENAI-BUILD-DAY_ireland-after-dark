# Footfall research and implemented assumptions

Checked 4 October 2026. These are historical counter measurements, not live
pedestrian estimates or evidence of personal security.

## Official sources and inspected evidence

- [DCC pedestrian catalogue](https://data.smartdublin.ie/dataset/dublin-city-centre-footfall-counters): describes hourly pedestrian counting, provided by Dublin City Council and the NTA.
- [Pinned count resource](https://data.smartdublin.ie/dataset/dublin-city-centre-footfall-counters/resource/71d3bd5b-3f7a-40fa-94b4-022a97f804e2): title says January–May, filename says January–June. The observed CSV timestamps actually run from **2026-01-01 00:00 to 2026-06-02 23:00**. The resource says updated June 4, 2026. Filename/title alone are insufficient validation.
- [Counter coordinates](https://data.smartdublin.ie/dataset/cc421859-1f4f-43f6-b349-f4ca0e1c60fa/resource/215d83bd-003d-4c1a-ac0d-b1132661746c/download/dublin-city-centre-footfall-counter-locations-18072023.csv): 34 pedestrian counters; location snapshot dated 2023 in filename. The misspelled `Eco-Visio Oupput` field is the join identifier, not a fuzzy location-name search.

Smart Dublin's resource metadata says Creative Commons Attribution without a
version. The source-research agent verified **CC BY 4.0** in the matching
[official data.gov.ie catalogue record](https://data.gov.ie/api/3/action/package_show?id=dublin-city-centre-footfall-counters).
Retain DCC/NTA attribution and original links; the acquisition manifest records
the licence-verification endpoint and source checksums.

The downloaded counts contain 3,672 rows. Most totals are accompanied by IN and
OUT columns. All fully populated triples in this inspected snapshot have total
equal to IN + OUT. Summing all three would double the observed pedestrians.
Another September-labelled resource has been identified as cyclist data: the
loader rejects cyclist column names even if it appears in the pedestrian catalogue.

Exact joins produce 30 mapped counters, of which **17 have usable observed
profiles** after quality handling. Thirteen mapped counters have no readings.
Unmatched/removed series are explicitly reported, never joined by similarity.
Grafton st/Monsoon is entirely blank. This is unknown activity, not zero.

## Temporal handling and data quality

The official metadata does not confirm timezone or whether the timestamp labels
refer to the beginning/end of the observation hour. Profiles group literal labels
by weekday and hour and explicitly record an **unverified Europe/Dublin local-time
assumption**. This uncertainty must remain visible to downstream consumers.

On 29 March 2026, `02:00` occurs twice: one row is empty and one has observations.
There is no `01:00` row that day. The pipeline quarantines both duplicate rows
instead of guessing the intended labels; 3,670 rows remain eligible for use.
Any ambiguous/nonexistent local timestamp under Europe/Dublin rules is also
excluded. This does not establish the publisher's timezone; it limits known
ambiguity under the stated assumption.

For each counter and `(weekday, hour)`, store the arithmetic mean of nonmissing
observations plus its sample count. Monday is 0. An empty bin is absent; a genuine
zero observation can produce an observed bin with mean 0. No directional fallback
is used when the total is absent. Total/direction inconsistencies are quarantined
per observation. Negative, fractional or nonnumeric counts fail ingestion.

The default conservative quality heuristic excludes a calendar day only when it
contains **24 observed hourly totals and all are zero**. This can remove true zero
days; it is a prototype assumption, not an established sensor-fault detector.
`build_profiles(..., exclude_full_zero_days=False)` disables it. A partly observed
day with a zero is retained. Every excluded day is recorded per counter. In the
inspected snapshot, this removes 47 days for Henry Street and 92 for Grand Canal
Street/Google. These unusually quiet series still need publisher/sensor review;
the filter cannot identify every outage, overcount or reporting defect.

## Edge assignment and score

`build_profiles(counts_path, locations_path)` returns JSON-serializable counters,
coordinates, temporal bins, exact source-file hashes and diagnostics.
`match_footfall(edge_geometry_projected, profiles, weekday, hour, radius_m=100)`
accepts a Shapely LineString in **EPSG:2157 metres**.

The default 100 m support radius is a prototype choice, not empirically validated
pedestrian coverage. For counters with an observation in the requested time bin,
choose the one whose buffer covers the greatest edge length, breaking ties by
distance to the edge midpoint, then stable counter id. Record that counter's
identity, sample count, distance, mean and supported-length fraction. A long edge
with one endpoint near a counter receives partial support, not full coverage.
Only one counter is assigned so overlapping counts are not added together.
The returned `expected_pedestrians_per_hour` is the historical **counter mean**,
not a forecast of the number of pedestrians on the matched street.

The score is `min(100, 100 * log1p(mean_count) / log1p(1000))`. The 1,000-person/hour
anchor and logarithmic transform are explicit prototype normalization choices;
they are not a safety scale or a calibrated forecast. Raw means remain available.
The score does not change merely because other requested edges change. Apply it
only to the supported fraction; unsupported parts are unknown. No nearby valid
counter produces `has_footfall_data=false`, zero support fraction and null score
and mean, including outside Dublin.

Radial matching can cross rivers, blocks and parallel streets. This output is
**proximity-based data support**, not proof the particular street was observed.
Freshness, sample counts and the timezone uncertainty must temper route-level
confidence. Historical counts describe the selected period, not current crowds.

## Verification

Tests cover real failure modes: total/IN/OUT double counting, missing versus zero,
full-zero-day filtering and its override, DST/duplicate timestamps, invalid count
values, cyclist input, exact identifier matching, contradictory totals, partial
edge support, absent time bins and out-of-area routes. Real pinned source files
were processed successfully, including observed source defects described above.
This validates ingestion and profile mechanics; it does not validate the spatial
or temporal assumptions as predictions of current street activity.
