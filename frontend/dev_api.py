"""Local-only HTTP bridge to Person 1's engine, pending Person 4's API."""

import argparse
import json
import math
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


class InputError(ValueError):
    pass


def parse_request(document):
    required = {"origin", "destination", "departure_time", "timezone"}
    if not isinstance(document, dict) or set(document) != required:
        raise InputError("Provide origin, destination, departure_time and timezone only.")
    for name in ("origin", "destination"):
        point = document[name]
        if (not isinstance(point, list) or len(point) != 2
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                or abs(point[0]) > 180 or abs(point[1]) > 90):
            raise InputError("Coordinates must be valid [longitude, latitude] pairs.")
    if document["timezone"] != "Europe/Dublin":
        raise InputError("Timezone must be Europe/Dublin.")
    try:
        instant = datetime.fromisoformat(document["departure_time"].replace("Z", "+00:00"))
        if instant.utcoffset() is None:
            raise ValueError
        local = instant.astimezone(ZoneInfo("Europe/Dublin"))
    except (ValueError, TypeError, AttributeError):
        raise InputError("Departure time must include an explicit timezone offset.") from None
    return tuple(reversed(document["origin"])), tuple(reversed(document["destination"])), local


def normalize_result(result, bounds, time_slice, sources, activity_enabled):
    status = result["status"]
    if all(result[kind]["lighting"]["score"] is None
           and (not activity_enabled or result[kind]["activity"]["score"] is None)
           for kind in ("fastest", "night")):
        status = "baseline_only"
    routes = []
    for kind in ("fastest", "night"):
        route = result[kind]
        lighting = route["lighting"]["score"]
        activity = route["activity"]["score"] if activity_enabled else None
        limitations = [
            "Overall route preference score and factor breakdown are not supplied by the routing engine.",
            "Routes start and end at snapped graph nodes; access walks to those nodes are excluded from distance and time.",
            "OSM paths do not establish current access or closures. Recorded lights do not establish lamp operation.",
            "Recorded lighting uses spatial proximity, not measured brightness; proximity matching can cross barriers or parallel streets.",
        ]
        if lighting is None:
            limitations.append("No recorded lighting evidence is available on this route.")
        else:
            limitations.append(f"Lighting evidence covers {route['lighting']['coverage'] * 100:.1f}% of route length; other portions remain unknown.")
        if activity is None:
            limitations.append("Historical pedestrian activity is unavailable for this route and selected time.")
        else:
            limitations.append(f"Historical activity covers {route['activity']['coverage'] * 100:.1f}% of route length. The normalized index is not a pedestrian count.")
        if time_slice:
            limitations.append(f"Activity snapshot: weekday {time_slice['weekday']} (Monday=0), {time_slice['hour']:02}:00 Europe/Dublin; source timezone interpretation remains unverified.")
        if not activity_enabled and time_slice:
            limitations.append("Selected weekday/hour differs from the snapshot. Activity is excluded from route preferences and display; lighting may still be used.")
        explanations = ["Shortest route by walking distance." if kind == "fastest" else "Engine-selected route using recorded evidence and its walking detour limit."]
        if status == "baseline_only":
            explanations = ["Only the distance-based route is available. A Night alternative cannot be established without evidence."]
        elif status == "same_route":
            explanations.append("The engine returned the same path for both options.")
        elif status == "no_alternative":
            explanations.append("No preferred alternative fitted the engine's detour limit; the fastest route is returned.")
        routes.append({
            "kind": kind, "geometry": route["geometry"], "distance_m": route["distance_m"],
            "duration_s": round(route["duration_min"] * 60, 2),
            "lighting_coverage_pct": None if lighting is None else round(route["lighting"]["coverage"] * 100, 1),
            "historical_activity": None if activity is None else {"value": activity, "unit": "normalized index (0–1), covered portions only"},
            "waiting": None, "score": None, "score_breakdown": [],
            "confidence": "Low" if lighting is None and activity is None else None,
            "limitations": limitations, "explanations": explanations, "sources": sources,
        })
    return {"mode": "walking", "comparison_status": status,
            "coverage": {"bounds": bounds, "description": "Local cached walking graph only. Bounds are graph extent, not complete evidence coverage or guaranteed connectivity. No request-time graph downloads."},
            "routes": routes}


class RoutingBridge:
    def __init__(self, area):
        from backend.routing import config
        from backend.routing.graph import cache_path
        from backend.routing.store import GraphStore

        if not cache_path(area).exists():
            raise RuntimeError(f"Build the cached graph first: python -m backend.routing --area {area}")
        self.store = GraphStore(area=area, allow_download=False)
        self.area = area
        self.bounds = list(config.AREAS[area])
        self.metadata = {}
        if config.EDGE_SCORES_PATH.exists():
            document = json.loads(config.EDGE_SCORES_PATH.read_text(encoding="utf-8"))
            self.metadata = {key: document.get(key, {}) for key in ("graph", "sources")}
        if self.metadata.get("graph", {}).get("is_test_fixture"):
            raise RuntimeError("Refusing a synthetic graph bundle in the real routing bridge.")

    def route(self, document):
        from backend.routing.engine import Preferences
        from backend.routing.graph import graph_bbox

        origin, destination, local_time = parse_request(document)
        _, engine = self.store.engine_for(origin, destination)
        time_slice = self.store.bundle.time_slice
        activity_enabled = bool(time_slice and (time_slice["weekday"], time_slice["hour"]) == (local_time.weekday(), local_time.hour))
        result = engine.route(origin, destination, Preferences(busier=0.5 if activity_enabled else 0.0))
        sources = [{"name": "OpenStreetMap walking graph", "date": None,
                    "attribution": f"© OpenStreetMap contributors, ODbL. Graph fetched {engine.G.graph.get('fetched', 'date unknown')}; source content date unknown."}]
        for name, source in self.metadata.get("sources", {}).items():
            sources.append({"name": name, "date": source.get("content_date"),
                            "attribution": f"{source['attribution']} · {source['license']['title']} · {source['source_url']}"})
        return normalize_result(result, list(graph_bbox(engine.G) or self.bounds), time_slice, sources, activity_enabled)


def handler_for(bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_arguments):
            pass

        def send_json(self, status, document):
            body = json.dumps(document, allow_nan=False).encode("utf-8")
            self.send_response(status)
            origin = self.headers.get("Origin")
            if origin in ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if (self.path != "/route" or self.headers.get("Origin") not in ALLOWED_ORIGINS
                    or self.headers.get("Access-Control-Request-Method") != "POST"):
                self.send_json(403, {"error": {"code": "FORBIDDEN", "message": "Origin or preflight not permitted."}})
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Vary", "Origin")
            self.end_headers()

        def do_GET(self):
            if self.path == "/health":
                self.send_json(200, {"status": "ready", "service": "local-routing-bridge", "area": bridge.area, "bounds": bridge.bounds})
            else:
                self.send_json(404, {"error": {"code": "NOT_FOUND", "message": "Endpoint not found."}})

        def do_POST(self):
            from backend.routing.engine import RoutingError

            if self.path != "/route":
                self.send_json(404, {"error": {"code": "NOT_FOUND", "message": "Endpoint not found."}})
                return
            if self.headers.get("Origin") not in ALLOWED_ORIGINS | {None}:
                self.send_json(403, {"error": {"code": "FORBIDDEN", "message": "Origin not permitted."}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192 or self.headers.get_content_type() != "application/json":
                    raise InputError("Send a JSON request smaller than 8 KiB.")
                self.connection.settimeout(5)
                document = json.loads(self.rfile.read(length))
                self.send_json(200, bridge.route(document))
            except (InputError, ValueError, UnicodeDecodeError):
                self.send_json(400, {"error": {"code": "INVALID_INPUT", "message": "Check coordinates, explicit departure offset and Europe/Dublin timezone. No preferences are supported yet."}})
            except RoutingError as error:
                mapping = {"outside_coverage": (422, "UNSUPPORTED_AREA", "Outside the cached walking network, or no nearby walking path. Check the supported bounds."),
                           "too_far": (422, "UNSUPPORTED_AREA", "This journey exceeds the supported routing extent."),
                           "same_point": (400, "INVALID_INPUT", "Both endpoints snap to the same graph node."),
                           "no_route": (404, "NO_ROUTE", "No connected walking route was found.")}
                status, code, message = mapping.get(error.code, (503, "GRAPH_UNAVAILABLE", "The walking graph is unavailable."))
                if code == "UNSUPPORTED_AREA":
                    message += f" Cached bounds (west, south, east, north): {bridge.bounds}."
                self.send_json(status, {"error": {"code": code, "message": message}})
            except Exception:
                self.send_json(500, {"error": {"code": "INTERNAL_ERROR", "message": "Routing failed. Check the local graph and bundle configuration."}})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--area", choices=("dublin", "dublin-centre"), default="dublin")
    args = parser.parse_args()
    bridge = RoutingBridge(args.area)
    server = HTTPServer(("127.0.0.1", args.port), handler_for(bridge))
    print(f"Local routing bridge ready at http://127.0.0.1:{args.port}; cached area {args.area}. No journey logging.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
