"""Conservative OSM way evidence, kept separate from routing penalties."""
from __future__ import annotations

EVIDENCE_VERSION = "direct-way-v1"
WAY_TAGS = ("highway", "footway", "crossing", "crossing:signals")


def classify_way(tags: dict) -> str | None:
    """Recognise explicit pedestrian crossing ways only; conflicts stay unknown."""
    if tags.get("highway") != "footway" or tags.get("footway") != "crossing":
        return None
    signals, legacy = tags.get("crossing:signals"), tags.get("crossing")
    if signals not in (None, "yes"):
        return None
    if legacy not in (None, "traffic_signals"):
        return None
    return "signal" if signals == "yes" or legacy == "traffic_signals" else None


def export_crossing_evidence(edge: dict, *, way_tags_complete: bool = False) -> dict:
    """Classify only an original direct way, never a simplified aggregate.

    OSMnx creates geometry attributes only for simplified edges. A scalar way
    ID plus absent geometry identifies an original segment in our download
    path. Cache metadata confirms all required way tags were requested.
    """
    direct = (way_tags_complete and "geometry" not in edge
              and type(edge.get("osmid")) is int)
    tags = {key: edge[key] for key in (*WAY_TAGS, "osmid") if key in edge}
    return {
        "classification": classify_way(tags) if direct else None,
        "evidence_available": direct,
        "scope": "original_way" if direct else "unverified_or_simplified",
        "tags": tags,
    }
