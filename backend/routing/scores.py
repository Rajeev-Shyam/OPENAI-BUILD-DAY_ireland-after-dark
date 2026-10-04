"""Edge scores from the data pipeline's bundle (docs/edge-data-contract.md).

Unknown-data policy: evidence can only make an edge cheaper than unknown.

- Lighting: the part of an edge near a recorded light counts as lit. The part
  with no evidence is unknown and costed at config.NEUTRAL_SCORE.
- Activity: the part of an edge near a counter takes that counter's score.
  The rest is unknown and costed at config.NEUTRAL_SCORE.

Unknown is never costed as dark or empty, and never reported as zero.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from data.pipeline.edges import file_sha256

from . import config

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
) -> ScoreBundle:
    """Read the pipeline bundle. A missing bundle gives no scores.

    Refuses a bundle built for a different edge export, so scores are never
    joined onto the wrong graph.
    """
    if not bundle_path.exists():
        return ScoreBundle()
    document = json.loads(bundle_path.read_text(encoding="utf-8"))
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported score bundle schema in {bundle_path}")
    if document["graph"]["sha256"] != file_sha256(edges_path):
        raise ValueError(
            f"{bundle_path} was built for a different graph than {edges_path}; "
            "rebuild it with python -m data.pipeline.build"
        )
    scores = {
        (int(row["u"]), int(row["v"]), int(row["key"])): _edge_score(row)
        for row in document["edges"]
    }
    return ScoreBundle(scores, document["time_slice"])


def apply_scores(G: nx.MultiDiGraph, scores: dict[EdgeKey, EdgeScore]) -> int:
    """Set score and cost-term attributes on every edge. Returns edges matched."""
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
        data["crossing_type"] = score.crossing  # "crossing" is the OSM tag
        # Cost terms: evidence where there is some, neutral for the rest.
        lit = (score.lighting or 0.0) + (1.0 - score.lighting_coverage) * neutral
        active = (
            score.activity_coverage * (score.activity or 0.0)
            + (1.0 - score.activity_coverage) * neutral
        )
        data["dark"] = 1.0 - lit
        data["quiet"] = 1.0 - active
        data["crossing_m"] = config.CROSSING_PENALTY_M.get(score.crossing, 0.0)
    return matched
