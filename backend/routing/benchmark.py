"""Measure route latency on the cached graph.

    python -m backend.routing.benchmark --requests 200
"""

import argparse
import collections
import math
import random
import statistics
import time

from .engine import RoutingError, _haversine_m
from .store import GraphStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--max-km", type=float, default=6.0, help="straight-line limit")
    parser.add_argument("--seed", type=int, default=4)
    args = parser.parse_args()

    start = time.perf_counter()
    store = GraphStore(allow_download=False)
    _, engine = next(iter(store._engines.values()))
    print(f"startup: {time.perf_counter() - start:.1f} s")

    rng = random.Random(args.seed)
    nodes = list(engine.G.nodes(data=True))
    timings, statuses = [], collections.Counter()
    while len(timings) < args.requests:
        (_, a), (_, b) = rng.sample(nodes, 2)
        apart_km = float(_haversine_m(*map(math.radians, (a["y"], a["x"], b["y"], b["x"])))) / 1000
        if not 0.3 <= apart_km <= args.max_km:
            continue
        began = time.perf_counter()
        try:
            statuses[engine.route((a["y"], a["x"]), (b["y"], b["x"]))["status"]] += 1
        except RoutingError as error:
            statuses[error.code] += 1
        timings.append((apart_km, (time.perf_counter() - began) * 1000))

    def report(label: str, values: list[float]) -> None:
        ordered = sorted(values)
        p95 = ordered[int(0.95 * (len(ordered) - 1))]
        print(
            f"{label}: n={len(ordered)} median {statistics.median(ordered):.0f} ms, "
            f"p95 {p95:.0f} ms, max {ordered[-1]:.0f} ms"
        )

    report("all requests", [ms for _, ms in timings])
    for low, high in [(0.3, 1), (1, 3), (3, args.max_km)]:
        bucket = [ms for km, ms in timings if low <= km < high]
        if bucket:
            report(f"  {low:g}-{high:g} km apart", bucket)
    print("statuses:", dict(statuses))


if __name__ == "__main__":
    main()
