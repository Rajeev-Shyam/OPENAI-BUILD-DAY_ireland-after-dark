"""Deterministic explanation/limitation text. Every number traces back to a
field the routing engine computed; nothing here is invented or AI-generated.
"""

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

LIGHTING_CAVEAT = (
    "Recorded lighting shows where assets are logged, not whether lamps work or how bright they are."
)
ACTIVITY_CAVEAT = (
    "Historical activity is a log-scaled proxy from a small number of counters, not a live pedestrian count."
)
NO_CROSSING_DATA = (
    "No crossing-type data is matched to edges yet, so crossing penalties have no effect."
)


def time_slice_note(time_slice: dict | None) -> str | None:
    if not time_slice:
        return None
    weekday = WEEKDAYS[time_slice["weekday"]] if "weekday" in time_slice else None
    hour = time_slice.get("hour")
    if weekday is None or hour is None:
        return None
    return (
        f"Historical activity reflects {weekday} {hour:02d}:00 "
        f"{time_slice.get('timezone', 'Europe/Dublin')} — the time slice the data "
        "pipeline was built for, not necessarily your selected time."
    )


def build_limitations(route: dict, has_scores: bool, time_slice: dict | None) -> list[str]:
    if not has_scores:
        return [
            "No lighting or footfall evidence is available in this area; "
            "only distance and time are shown."
        ]
    limitations = [LIGHTING_CAVEAT, ACTIVITY_CAVEAT, NO_CROSSING_DATA]
    if route["lighting"]["score"] is None:
        limitations.append("No lighting evidence is recorded along this route.")
    if route["activity"]["score"] is None:
        limitations.append("No historical footfall evidence is recorded along this route.")
    note = time_slice_note(time_slice)
    if note:
        limitations.append(note)
    return limitations


def build_explanations(kind: str, status: str, fastest: dict, night: dict, detour: dict) -> list[str]:
    if kind == "fastest":
        return ["Shortest walking distance between these points."]

    if status == "baseline_only":
        return [
            "No lighting or footfall evidence is available here, so this is the same as the fastest route."
        ]
    if status == "same_route":
        return [
            "This is already the best path for your preferences — same as the fastest route."
        ]
    if status == "no_alternative":
        return [
            "The preferred route would exceed your maximum detour, so the fastest route is shown instead."
        ]

    parts = []
    extra_min = detour["extra_min"]
    parts.append(
        f"{extra_min:.0f} min longer than the fastest route" if extra_min > 0 else "same walking time as the fastest route"
    )

    f_light, n_light = fastest["lighting"]["score"], night["lighting"]["score"]
    if f_light is not None and n_light is not None and round(n_light, 3) != round(f_light, 3):
        diff = round((n_light - f_light) * 100)
        direction = "more" if diff > 0 else "less"
        parts.append(f"{abs(diff)}% {direction} recorded lighting coverage than the fastest route")

    f_act, n_act = fastest["activity"]["score"], night["activity"]["score"]
    if f_act is not None and n_act is not None and round(n_act, 3) != round(f_act, 3):
        diff = round((n_act - f_act) * 100)
        direction = "more" if diff > 0 else "less"
        parts.append(f"{abs(diff)}% {direction} historical activity than the fastest route")

    return [", ".join(parts) + "."]
