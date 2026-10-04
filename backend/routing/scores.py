"""Edge scores from the data pipeline's bundle (docs/edge-data-contract.md).

Unknown-data policy: unsupported portions use a neutral preference score.

- Lighting: the part of an edge near a recorded light counts as lit. The part
  with no evidence is unknown and costed at config.NEUTRAL_SCORE.
- Activity: the part of an edge near a counter takes that counter's score.
  The rest is unknown and costed at config.NEUTRAL_SCORE.

Unknown is never costed as dark or empty, and never reported as zero.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import networkx as nx

from data.pipeline.time_scores import departure_slot, load_time_scores, validate_profiles

from . import config
from .crossings import classify_crossings

EdgeKey = tuple[int, int, int]
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class EdgeScore:
    lighting: float | None = None  # share of the edge near a recorded light
    lighting_coverage: float = 0.0  # share of the edge with lighting evidence
    activity: float | None = None  # counter activity, 0 to 1, on the covered part
    activity_coverage: float = 0.0  # share of the edge near a counter
    crossing: str | None = None


@dataclass(frozen=True)
class ScoreBundle:
    scores: dict[EdgeKey, EdgeScore] = field(default_factory=dict)
    time_slice: dict | None = None  # weekday and hour the activity scores are for
    # Counter profiles for every weekday and hour, and their matching radius,
    # when the bundle carries them: lets activity follow the departure time.
    profiles: dict | None = None
    footfall_radius_m: float | None = None


def quiet_term(activity: float | None, coverage: float) -> float:
    """NightCost activity term: the counter's score where covered, neutral elsewhere."""
    return 1.0 - (coverage * (activity or 0.0) + (1.0 - coverage) * config.NEUTRAL_SCORE)


def _edge_score(row: dict) -> EdgeScore:
    crossing = row.get("crossing")
    if crossing is not None and crossing not in config.CROSSING_PENALTY_M:
        raise ValueError(f"Unknown crossing type {crossing!r} in score bundle")
    lighting, activity = row["lighting_score"], row["footfall_score"]
    return EdgeScore(
        lighting=None if lighting is None else lighting / 100,
        lighting_coverage=row["lighting_data_coverage_fraction"],
        activity=None if activity is None else activity / 100,
        activity_coverage=row["footfall_coverage_fraction"],
        crossing=crossing,
    )


def load_edge_scores(
    bundle_path: Path = config.EDGE_SCORES_PATH,
    edges_path: Path = config.EDGES_GEOJSON_PATH,
    *, departure_time: datetime | None = None,
) -> ScoreBundle:
    """Read the pipeline bundle. A missing bundle gives no scores.

    Refuses a bundle built for a different edge export, so scores are never
    joined onto the wrong graph.
    """
    if departure_time is not None:
        departure_slot(departure_time)  # reject naive times even without data
    bundle_path, edges_path = Path(bundle_path), Path(edges_path)
    if not bundle_path.exists():
        return ScoreBundle()
    rows, time_slice = load_time_scores(bundle_path, edges_path, departure_time=departure_time)
    scores = {}
    for identity, row in rows.items():
        key = tuple(int(part) for part in identity)
        if any(str(value) != raw for value, raw in zip(key, identity)) or key in scores:
            raise ValueError("Routing requires canonical integer edge identities")
        scores[key] = _edge_score(row)

    document = json.loads(bundle_path.read_text(encoding="utf-8"))
    profiles = document.get("footfall_profiles")
    if profiles is None:
        return ScoreBundle(scores, time_slice)
    validate_profiles(profiles, document.get("sources", {}))
    return ScoreBundle(scores, time_slice, profiles, document["parameters"]["footfall_radius_m"])


def apply_scores(G: nx.MultiDiGraph, scores: dict[EdgeKey, EdgeScore]) -> int:
    """Set score and cost-term attributes on every edge. Returns edges matched.

    Crossing types come from OSM tags unless the bundle supplies its own.
    """
    osm_crossings = classify_crossings(G)
    unknown = EdgeScore()
    neutral = config.NEUTRAL_SCORE
    matched = 0
    for u, v, key, data in G.edges(keys=True, data=True):
        score = scores.get((u, v, key)) or scores.get((v, u, key))
        if score is not None:
            matched += 1
        else:
            score = unknown
        data["lighting"] = score.lighting
        data["lighting_coverage"] = score.lighting_coverage
        data["activity"] = score.activity
        data["activity_coverage"] = score.activity_coverage
        # "crossing" itself is the OSM tag, so the type gets its own name.
        crossing = score.crossing or osm_crossings.get((u, v, key))
        data["crossing_type"] = crossing
        # Cost terms: evidence where there is some, neutral for the rest.
        lit = (score.lighting or 0.0) + (1.0 - score.lighting_coverage) * neutral
        data["dark"] = 1.0 - lit
        data["quiet"] = quiet_term(score.activity, score.activity_coverage)
        data["crossing_m"] = config.CROSSING_PENALTY_M.get(crossing, 0.0) / 2
    return matched
