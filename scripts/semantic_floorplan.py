"""Shared validation and geometry helpers for semantic floorplan JSON."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


Point = tuple[float, float]


def load_project(source: Path) -> dict[str, Any]:
    return json.loads(source.read_text(encoding="utf-8"))


def validate_project(data: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in validator.iter_errors(data)]

    template_ids = [item["id"] for item in data.get("templates", []) if "id" in item]
    errors.extend(_duplicate_errors("template", template_ids))
    template_id_set = set(template_ids)

    for level in data.get("levels", []):
        level_id = level.get("id", "<unknown>")
        walls = {wall["id"]: wall for wall in level.get("walls", []) if "id" in wall}
        spaces = {space["id"]: space for space in level.get("spaces", []) if "id" in space}
        all_ids: list[str] = []
        for collection in ("walls", "openings", "spaces", "instances"):
            all_ids.extend(item["id"] for item in level.get(collection, []) if "id" in item)
        errors.extend(f"level {level_id}: {message}" for message in _duplicate_errors("object", all_ids))

        for opening in level.get("openings", []):
            wall = walls.get(opening.get("wallId"))
            if wall is None:
                errors.append(f"level {level_id}: opening {opening.get('id')} references missing wall {opening.get('wallId')}")
                continue
            segment_index = opening.get("segmentIndex", -1)
            if not 0 <= segment_index < len(wall["centerline"]) - 1:
                errors.append(f"level {level_id}: opening {opening.get('id')} has invalid segmentIndex")
                continue
            start, end = wall["centerline"][segment_index : segment_index + 2]
            length = math.dist(start, end)
            if opening.get("offset", 0) + opening.get("width", 0) > length + 0.01:
                errors.append(f"level {level_id}: opening {opening.get('id')} extends beyond its wall segment")

        for instance in level.get("instances", []):
            if instance.get("templateId") not in template_id_set:
                errors.append(f"level {level_id}: instance {instance.get('id')} references missing template {instance.get('templateId')}")
            if instance.get("spaceId") and instance["spaceId"] not in spaces:
                errors.append(f"level {level_id}: instance {instance.get('id')} references missing space {instance['spaceId']}")
    return sorted(errors)


def _duplicate_errors(kind: str, values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        (duplicates if value in seen else seen).add(value)
    return [f"duplicate {kind} id: {value}" for value in sorted(duplicates)]


def point_on_segment(start: list[float], end: list[float], distance: float) -> Point:
    length = math.dist(start, end)
    if length == 0:
        return float(start[0]), float(start[1])
    ratio = distance / length
    return start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio


def opening_points(wall: dict[str, Any], opening: dict[str, Any]) -> tuple[Point, Point]:
    start, end = wall["centerline"][opening["segmentIndex"] : opening["segmentIndex"] + 2]
    return point_on_segment(start, end, opening["offset"]), point_on_segment(start, end, opening["offset"] + opening["width"])


def split_segment(start: list[float], end: list[float], openings: list[dict[str, Any]]) -> list[tuple[Point, Point]]:
    length = math.dist(start, end)
    cursor = 0.0
    pieces: list[tuple[Point, Point]] = []
    for opening in sorted(openings, key=lambda item: item["offset"]):
        opening_start = max(0.0, min(length, opening["offset"]))
        opening_end = max(opening_start, min(length, opening["offset"] + opening["width"]))
        if opening_start > cursor:
            pieces.append((point_on_segment(start, end, cursor), point_on_segment(start, end, opening_start)))
        cursor = max(cursor, opening_end)
    if cursor < length:
        pieces.append((point_on_segment(start, end, cursor), point_on_segment(start, end, length)))
    return pieces


def svg_points(points: list[list[float]]) -> str:
    return " ".join(f"{point[0]:g},{point[1]:g}" for point in points)


def path_d(points: list[list[float]], closed: bool) -> str:
    result = "M " + " L ".join(f"{point[0]:g} {point[1]:g}" for point in points)
    return result + (" Z" if closed else "")
