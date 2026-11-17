#!/usr/bin/env python3
"""Validate Floorplan JSON against the schema and project invariants."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--schema", type=Path, default=Path("schema/floorplan.schema.json"))
    parser.add_argument("--expected-rooms", type=int, default=32)
    args = parser.parse_args()

    data = json.loads(args.source.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if errors:
        for error in errors[:30]:
            location = ".".join(str(part) for part in error.path) or "<root>"
            print(f"schema error at {location}: {error.message}")
        return 1

    viewport = data["viewport"]
    if not (viewport["minX"] < viewport["maxX"] and viewport["minY"] < viewport["maxY"]):
        raise SystemExit("invalid viewport ordering")

    layers = data["layers"]
    layer_ids = [layer["id"] for layer in layers]
    if len(layer_ids) != len(set(layer_ids)):
        raise SystemExit("duplicate layer ids")

    entities = data["entities"]
    entity_ids = [entity["id"] for entity in entities]
    if len(entity_ids) != len(set(entity_ids)):
        raise SystemExit("duplicate entity ids")
    unknown_layers = sorted({entity["layerId"] for entity in entities} - set(layer_ids))
    if unknown_layers:
        raise SystemExit(f"entities reference unknown layers: {unknown_layers}")

    rooms = [space for space in data["spaces"] if space["type"] == "room"]
    space_ids = [space["id"] for space in data["spaces"]]
    labels = [space["label"] for space in rooms]
    if len(space_ids) != len(set(space_ids)):
        raise SystemExit("duplicate space ids")
    if len(labels) != len(set(labels)):
        raise SystemExit("duplicate room labels")
    expected = {str(number) for number in range(1, args.expected_rooms + 1)}
    actual_labels = set(labels)
    if actual_labels != expected:
        raise SystemExit(f"room labels mismatch: missing={sorted(expected-actual_labels)} extra={sorted(actual_labels-expected)}")

    for entity in entities:
        coordinates = entity["points"] if entity["kind"] == "path" else [entity["position"]]
        for coordinate in coordinates:
            if not all(math.isfinite(value) for value in coordinate):
                raise SystemExit(f"non-finite coordinate in {entity['id']}")

    stats = data["statistics"]
    actual_stats = {
        "exportedEntities": len(entities),
        "pathCount": sum(entity["kind"] == "path" for entity in entities),
        "textCount": sum(entity["kind"] == "text" for entity in entities),
        "vertexCount": sum(len(entity["points"]) for entity in entities if entity["kind"] == "path"),
        "spaceCount": len(data["spaces"]),
    }
    for key, value in actual_stats.items():
        if stats[key] != value:
            raise SystemExit(f"statistics mismatch for {key}: declared={stats[key]} actual={value}")

    entity_counts = Counter(entity["layerId"] for entity in entities)
    for layer in layers:
        if layer["entityCount"] != entity_counts[layer["id"]]:
            raise SystemExit(
                f"layer count mismatch for {layer['id']}: "
                f"declared={layer['entityCount']} actual={entity_counts[layer['id']]}"
            )

    dimension_ids = [dimension["id"] for dimension in data["dimensions"]]
    if len(dimension_ids) != len(set(dimension_ids)):
        raise SystemExit("duplicate dimension ids")

    if stats["pathCount"] < 1_000 or stats["vertexCount"] < 5_000:
        raise SystemExit("drawing export is unexpectedly small")
    print(
        f"valid: {stats['pathCount']} paths, {stats['textCount']} texts, "
        f"{stats['vertexCount']} vertices, {len(rooms)} rooms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
