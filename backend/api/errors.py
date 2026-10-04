from backend.routing import RoutingError

# RoutingError subclass .code -> (contract error code, HTTP status).
# Codes/statuses per frontend/API_CONTRACT_PROPOSED.md.
ROUTING_ERROR_MAP: dict[str, tuple[str, int]] = {
    "same_point": ("INVALID_INPUT", 400),
    "outside_coverage": ("UNSUPPORTED_AREA", 422),
    "too_far": ("UNSUPPORTED_AREA", 422),
    "no_route": ("NO_ROUTE", 404),
    "graph_unavailable": ("INTERNAL_ERROR", 500),
}


def map_routing_error(error: RoutingError) -> tuple[str, int, str]:
    code, status = ROUTING_ERROR_MAP.get(error.code, ("INTERNAL_ERROR", 500))
    return code, status, str(error)
