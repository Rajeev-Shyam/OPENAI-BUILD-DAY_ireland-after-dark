"""Bounded route diversity search; never claims exhaustive 'best' routes.

Uses the existing engine/graph, avoids mutating shared edge costs, and keeps
the existing five-minute walking detour bound. Near-identical corridors are omitted.
"""
import networkx as nx

from . import config
from .engine import night_cost
from .diversity import same_corridor


def add_alternatives(engine, result, prefs, limit=3):
    routes = [result['fastest'], result['night']]
    distinct = [routes[0]]
    if not same_corridor(*routes):
        distinct.append(routes[1])
    def edge_set(route):
        return {frozenset((s['u'],s['v'])) for s in route['segments']}
    used = set().union(*(edge_set(route) for route in routes))
    source, target = result['snap']['origin']['node'], result['snap']['destination']['node']
    cap = result['fastest']['distance_m'] + config.DEFAULT_MAX_EXTRA_MIN * 60 * config.WALK_SPEED_MPS
    alternatives = []
    for penalty in (0.3, 0.7, 1.5, 3.0, 6.0):
        if len(distinct) >= limit:
            break
        def cost(u, v, data):
            return night_cost(data, prefs) + (penalty * data['length'] if frozenset((u,v)) in used else 0)
        def weight(u, v, parallel):
            return min(cost(u,v,data) for data in parallel.values())
        try:
            _, nodes = nx.bidirectional_dijkstra(engine.G, source, target, weight=weight)
        except nx.NetworkXNoPath:
            break
        edges = [(u,v,min(engine.G[u][v],key=lambda k:cost(u,v,engine.G[u][v][k])))
                 for u,v in zip(nodes,nodes[1:])]
        if engine._length(edges) > cap:
            continue
        candidate = engine._describe(edges, prefs)
        used.update(edge_set(candidate))
        if any(same_corridor(candidate, previous) for previous in distinct):
            continue
        distinct.append(candidate)
        alternatives.append(candidate)
    result['alternatives'] = alternatives
    return result
