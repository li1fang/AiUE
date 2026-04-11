from __future__ import annotations

from math import sqrt


def axis_value(payload: dict | None, axis: str) -> float:
    return float(((payload or {}).get(axis)) or 0.0)


def vector_payload(x: float, y: float, z: float) -> dict:
    return {
        "x": float(x),
        "y": float(y),
        "z": float(z),
    }


def bounds_payload(component_payload: dict | None) -> dict:
    return dict(((component_payload or {}).get("bounds")) or {})


def attach_location_payload(component_payload: dict | None) -> dict:
    return dict((((component_payload or {}).get("attach")) or {}).get("world_transform") or {}).get("location") or {}


def non_zero_bounds(bounds: dict | None) -> bool:
    payload = dict(bounds or {})
    if not payload.get("non_zero"):
        return False
    extent = dict(payload.get("extent") or {})
    return any(abs(axis_value(extent, axis)) > 1e-6 for axis in ("x", "y", "z"))


def bounds_origin(bounds: dict | None) -> dict:
    return dict((bounds or {}).get("origin") or {})


def bounds_extent(bounds: dict | None) -> dict:
    return dict((bounds or {}).get("extent") or {})


def bounds_min_max(bounds: dict | None) -> dict:
    origin = bounds_origin(bounds)
    extent = bounds_extent(bounds)
    minimum = {
        axis: axis_value(origin, axis) - axis_value(extent, axis)
        for axis in ("x", "y", "z")
    }
    maximum = {
        axis: axis_value(origin, axis) + axis_value(extent, axis)
        for axis in ("x", "y", "z")
    }
    return {
        "min": minimum,
        "max": maximum,
    }


def bounds_volume(bounds: dict | None) -> float:
    extent = bounds_extent(bounds)
    return float(
        8.0
        * max(axis_value(extent, "x"), 0.0)
        * max(axis_value(extent, "y"), 0.0)
        * max(axis_value(extent, "z"), 0.0)
    )


def bounds_diagonal(bounds: dict | None) -> float:
    extent = bounds_extent(bounds)
    return float(
        sqrt(
            max(axis_value(extent, "x"), 0.0) ** 2
            + max(axis_value(extent, "y"), 0.0) ** 2
            + max(axis_value(extent, "z"), 0.0) ** 2
        )
    )


def vector_subtract(left: dict | None, right: dict | None) -> dict:
    return {
        axis: axis_value(left, axis) - axis_value(right, axis)
        for axis in ("x", "y", "z")
    }


def aabb_payload(*, center: dict, extent: dict, source: str) -> dict:
    minimum = {
        axis: axis_value(center, axis) - axis_value(extent, axis)
        for axis in ("x", "y", "z")
    }
    maximum = {
        axis: axis_value(center, axis) + axis_value(extent, axis)
        for axis in ("x", "y", "z")
        }
    volume = float(
        8.0
        * max(axis_value(extent, "x"), 0.0)
        * max(axis_value(extent, "y"), 0.0)
        * max(axis_value(extent, "z"), 0.0)
    )
    return {
        "center": {
            axis: axis_value(center, axis)
            for axis in ("x", "y", "z")
        },
        "extent": {
            axis: axis_value(extent, axis)
            for axis in ("x", "y", "z")
        },
        "min": minimum,
        "max": maximum,
        "volume": volume,
        "source": source,
    }


def bounds_debug_payload(bounds: dict | None) -> dict:
    payload = dict(bounds or {})
    min_max = bounds_min_max(payload)
    return {
        "origin": {
            axis: axis_value(bounds_origin(payload), axis)
            for axis in ("x", "y", "z")
        },
        "extent": {
            axis: axis_value(bounds_extent(payload), axis)
            for axis in ("x", "y", "z")
        },
        "min": min_max["min"],
        "max": min_max["max"],
        "volume": bounds_volume(payload),
        "diagonal_length": float(payload.get("diagonal_length") or bounds_diagonal(payload)),
        "non_zero": bool(payload.get("non_zero")),
        "source": str(payload.get("source") or ""),
    }


def aabb_intersection(first: dict | None, second: dict | None, *, source: str) -> dict:
    first_payload = dict(first or {})
    second_payload = dict(second or {})
    minimum = {}
    maximum = {}
    extent = {}
    for axis in ("x", "y", "z"):
        axis_min = max(axis_value((first_payload.get("min") or {}), axis), axis_value((second_payload.get("min") or {}), axis))
        axis_max = min(axis_value((first_payload.get("max") or {}), axis), axis_value((second_payload.get("max") or {}), axis))
        axis_extent = max((axis_max - axis_min) / 2.0, 0.0)
        minimum[axis] = float(axis_min)
        maximum[axis] = float(axis_max)
        extent[axis] = float(axis_extent)
    center = {
        axis: float((minimum[axis] + maximum[axis]) / 2.0)
        for axis in ("x", "y", "z")
    }
    volume = float(8.0 * extent["x"] * extent["y"] * extent["z"])
    return {
        "center": center,
        "extent": extent,
        "min": minimum,
        "max": maximum,
        "volume": volume,
        "non_zero": bool(volume > 1e-6),
        "source": source,
    }


def clamp01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))
