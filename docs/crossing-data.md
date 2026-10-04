# OSM crossing evidence

Status: explicit way evidence is exported; crossing routing penalties and crossing confidence are **not enabled by this pipeline**. SCATS points are a separate contextual layer. Unknown evidence never means an unsignalised or minor crossing.

## Build and output

Rebuild an old graph cache with `python -m backend.routing --area dublin --force`. The downloader retains `highway`, `footway`, `crossing`, `crossing:signals` and OSM way IDs. It preserves OSMnx's original buffered-download → simplification → bbox-truncation ordering. Moving simplification after bbox truncation can remove boundary intersections and alter the walking graph; this implementation does not do that.

The GeoJSON edge properties include `osm_crossing_evidence`:

```json
{
  "classification": "signal",
  "evidence_available": true,
  "scope": "original_way",
  "tags": {"osmid": 123, "highway": "footway", "footway": "crossing", "crossing:signals": "yes"}
}
```

Classification is deliberately restricted to an **original direct way segment**, identified by scalar OSM way ID and absence of OSMnx-created simplified geometry, in a graph marked `dad_crossing_evidence_version=direct-way-v1`. This marker confirms the downloader requested the required tags. A direct edge receives `signal` only with `highway=footway`, `footway=crossing`, and either `crossing:signals=yes` or older `crossing=traffic_signals`, without contradictory values.

**Every simplified edge remains unknown**, even when its aggregate tags look uniformly positive. OSMnx's default aggregation drops absent tags: a short tagged crossing merged with a long untagged footpath can misleadingly appear fully tagged. We retain aggregate tags for inspection under `scope=unverified_or_simplified`; `classification=null` and `evidence_available=false` prevent promoting them into crossing claims. Old caches without the marker also remain unknown. This intentionally undercounts crossings, including node-only mappings and otherwise valid simplified crossing ways.

`evidence_available=true` describes an original way record with known requested tags, not crossing coverage or proof a signal operates. The exact exported-file fingerprint changes with evidence properties; rebuild lighting/footfall score bundles after the export changes even though the walking topology is preserved.

## Why this does not yet change route costs

A crossing way may span several graph edges or meet a crossing node with multiple incident edges. Applying a fixed cost to every incident edge would count one physical crossing multiple times. A correct future integration needs crossing-event identity, direction-aware route traversal and de-duplicated costs; ideally the graph also distinguishes walking across a road from following its centreline. This release neither adds a penalty at both ends nor invents unsupported minor/major-unsignalised categories. The existing core score builder ignores this optional evidence; its lighting and footfall contract is unchanged.

Nearby SCATS traffic signals/detectors do not prove a pedestrian crossing controls a particular traversed road. Spatial proximity must not be promoted into signal classification. Signal-operation status, accessibility, crossing wait times and completeness are unknown.

## Sources and verification

- [OSM crossing ways](https://wiki.openstreetmap.org/wiki/Tag:footway%3Dcrossing): explicit pedestrian crossing way convention.
- [OSM crossing signals](https://wiki.openstreetmap.org/wiki/Key:crossing:signals): `yes`/`no` signal-control semantics.
- [OSMnx simplification](https://osmnx.readthedocs.io/en/stable/user-reference.html#osmnx.simplification.simplify_graph): removed intermediate nodes and attribute aggregation behavior.
- OSM attribution: © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright).

Research checked 2026-10-04. Tests cover explicit/contradictory/nonpedestrian tags, simplified aggregates with absent constituent tags, GraphML save/load, direct-way GeoJSON export, old-cache fallback and a regression guard preserving upstream simplification ordering. A full real-graph acceptance receipt belongs in the integration validation document; unit tests alone do not establish map completeness.
