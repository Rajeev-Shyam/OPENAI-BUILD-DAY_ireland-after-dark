"""Historical activity for any weekday and hour, without a full-graph recompute.

The pipeline's load_time_scores(departure_time=...) re-matches every edge to
the footfall counters, which takes about 45 s on the Dublin graph. Only edges
within the counter radius can have activity, so this re-matches just those,
with the pipeline's own match_footfall, and caches each weekday and hour.
"""

import threading
from dataclasses import dataclass, field

from data.pipeline.footfall import match_footfall

from .engine import RoutingEngine
from .scores import EdgeKey, quiet_term


@dataclass(frozen=True)
class ActivitySlot:
    time_slice: dict  # weekday, hour and timezone these scores are for
    # edge -> (counter activity 0 to 1, share of the edge near that counter)
    scores: dict[EdgeKey, tuple[float, float]] = field(default_factory=dict)
    quiet: dict[EdgeKey, float] = field(default_factory=dict)  # NightCost term


class ActivitySlots:
    def __init__(self, engine: RoutingEngine, profiles: dict, radius_m: float):
        self._profiles = profiles
        self._radius_m = radius_m
        self._slots: dict[tuple[int, int], ActivitySlot] = {}
        self._lock = threading.Lock()
        # Every directed edge near a counter, with its own projected geometry.
        self._candidates = {}
        G = engine.G
        for counter in profiles["counters"]:
            point = (counter["latitude"], counter["longitude"])
            for u, v, _ in engine.streets_within(point, radius_m):
                for a, b in ((u, v), (v, u)):
                    for key in G[a][b] if G.has_edge(a, b) else ():
                        line = engine.metric_line((a, b, key))
                        if line.length > 0:
                            self._candidates[(a, b, key)] = line

    def slot(self, weekday: int, hour: int) -> ActivitySlot:
        """Activity for Monday=0..Sunday=6 and a Europe/Dublin hour. Cached."""
        with self._lock:
            if (weekday, hour) not in self._slots:
                self._slots[(weekday, hour)] = self._build(weekday, hour)
            return self._slots[(weekday, hour)]

    def _build(self, weekday: int, hour: int) -> ActivitySlot:
        def at_slot(counter: dict) -> list[dict]:
            return [b for b in counter["bins"] if (b["weekday"], b["hour"]) == (weekday, hour)]

        # Counters with no observation for this slot cannot be matched.
        selected = {
            **self._profiles,
            "counters": [
                {**counter, "bins": at_slot(counter)}
                for counter in self._profiles["counters"]
                if at_slot(counter)
            ],
        }
        slot = ActivitySlot(
            {
                "weekday": weekday,
                "hour": hour,
                "timezone": self._profiles["timezone"],
                "timezone_verified": self._profiles["timezone_verified"],
            }
        )
        for edge, line in self._candidates.items():
            match = match_footfall(line, selected, weekday, hour, radius_m=self._radius_m)
            if match["has_footfall_data"]:
                score, coverage = match["footfall_score"] / 100, match["footfall_coverage_fraction"]
                slot.scores[edge] = (score, coverage)
                slot.quiet[edge] = quiet_term(score, coverage)
        return slot
