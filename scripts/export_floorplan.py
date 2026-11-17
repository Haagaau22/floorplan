#!/usr/bin/env python3
"""Export a cropped DXF drawing as the canonical Floorplan JSON format."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import ezdxf
from ezdxf import disassemble, path


DEFAULT_BOUNDS = (1_531_000.0, 598_000.0, 1_625_000.0, 637_000.0)
ROOM_PATTERN = re.compile(r"^(?:[1-9]|[12][0-9]|3[0-2])$")
EXCLUDED_TEXT = {"平面布置图"}

LAYERS = (
    ("linework", "建筑线条", True),
    ("fixtures", "家具与设备", True),
    ("annotations", "文字", True),
    ("dimensions", "尺寸", True),
)


def rounded(value: float) -> float:
    return round(float(value), 3)


def point(value) -> list[float]:
    return [rounded(value.x), rounded(value.y)]


def overlaps(bounds: tuple[float, float, float, float], points: Iterable) -> bool:
    values = list(points)
    if not values:
        return False
    xs = [float(value[0]) for value in values]
    ys = [float(value[1]) for value in values]
    xmin, ymin, xmax, ymax = bounds
    return not (max(xs) < xmin or min(xs) > xmax or max(ys) < ymin or min(ys) > ymax)


def quick_entity_overlap(entity, bounds: tuple[float, float, float, float], margin: float = 2_000.0) -> bool:
    xmin, ymin, xmax, ymax = bounds
    padded = (xmin - margin, ymin - margin, xmax + margin, ymax + margin)
    kind = entity.dxftype()
    try:
        if kind == "LINE":
            return overlaps(padded, (entity.dxf.start, entity.dxf.end))
        if kind == "LWPOLYLINE":
            return overlaps(padded, entity.get_points("xy"))
        if kind in {"CIRCLE", "ARC"}:
            center = entity.dxf.center
            radius = entity.dxf.radius
            return not (
                center.x + radius < padded[0]
                or center.x - radius > padded[2]
                or center.y + radius < padded[1]
                or center.y - radius > padded[3]
            )
        if kind in {"TEXT", "MTEXT", "INSERT"}:
            insert = entity.dxf.insert
            return padded[0] <= insert.x <= padded[2] and padded[1] <= insert.y <= padded[3]
        if kind == "DIMENSION":
            anchor = entity.dxf.defpoint
            return padded[0] <= anchor.x <= padded[2] and padded[1] <= anchor.y <= padded[3]
        if kind == "LEADER":
            return overlaps(padded, entity.vertices)
    except (AttributeError, TypeError, ValueError):
        return False
    return False


def text_content(entity) -> str:
    if entity.dxftype() == "MTEXT":
        return " ".join(entity.plain_text().split())
    return " ".join(str(entity.dxf.text).split())


def export_text(entity, entity_id: str, layer_id: str, bounds) -> dict | None:
    content = text_content(entity)
    if not content or content in EXCLUDED_TEXT:
        return None
    insert = entity.dxf.insert
    if not overlaps(bounds, (insert,)):
        return None
    height = getattr(entity.dxf, "char_height", None) or getattr(entity.dxf, "height", 250.0)
    rotation = getattr(entity.dxf, "rotation", 0.0)
    return {
        "id": entity_id,
        "kind": "text",
        "layerId": layer_id,
        "position": point(insert),
        "content": content,
        "height": max(rounded(height), 1.0),
        "rotation": rounded(rotation),
    }


def flattened_paths(entity, entity_id: str, layer_id: str, bounds) -> list[dict]:
    try:
        drawing_path = path.make_path(entity)
    except (TypeError, ValueError, AttributeError):
        return []

    candidates = drawing_path.sub_paths() if drawing_path.has_sub_paths else (drawing_path,)
    exported = []
    for index, candidate in enumerate(candidates):
        try:
            vertices = list(candidate.flattening(distance=5.0, segments=4))
        except (ValueError, TypeError, AttributeError):
            continue
        if len(vertices) < 2 or not overlaps(bounds, vertices):
            continue
        exported.append({
            "id": entity_id if index == 0 else f"{entity_id}-{index}",
            "kind": "path",
            "layerId": layer_id,
            "points": [point(vertex) for vertex in vertices],
            "closed": bool(getattr(candidate, "is_closed", False)),
        })
    return exported


def dimension_record(entity) -> dict | None:
    try:
        measurement = float(entity.get_measurement())
        start = entity.dxf.defpoint2
        end = entity.dxf.defpoint3
    except (AttributeError, TypeError, ValueError, ezdxf.DXFError):
        return None
    if not math.isfinite(measurement) or measurement < 0:
        return None
    record = {
        "id": f"dimension-{entity.dxf.handle}",
        "measurement": rounded(measurement),
        "start": point(start),
        "end": point(end),
    }
    override = str(getattr(entity.dxf, "text", "")).strip()
    if override:
        record["textOverride"] = override
    return record


def load_baseline(pathname: Path | None) -> tuple[dict[int, dict], dict]:
    if pathname is None or not pathname.exists():
        return {}, {}
    data = json.loads(pathname.read_text(encoding="utf-8"))
    fields = data.get("roomMeasurements", {}).get("fields", [])
    result = {}
    for row in data.get("roomMeasurements", {}).get("rooms", []):
        values = dict(zip(fields, row))
        result[int(values["roomNumber"])] = values
    return result, data


def selection_boundary(position: list[float], area_m2: float | None) -> list[list[float]]:
    # A conservative hit region around the CAD room label. It is deliberately
    # marked as non-verified until the apartment ownership boundaries are audited.
    radius = min(max(math.sqrt(area_m2 or 16.0) * 155.0, 650.0), 1_050.0)
    x, y = position
    return [
        [rounded(x - radius), rounded(y - radius)],
        [rounded(x + radius), rounded(y - radius)],
        [rounded(x + radius), rounded(y + radius)],
        [rounded(x - radius), rounded(y + radius)],
    ]


def build_spaces(room_positions: dict[int, list[float]], baseline: dict[int, dict]) -> list[dict]:
    if 10 not in room_positions and 9 in room_positions and 11 in room_positions:
        # Room 10 has no visible number in the source drawing. Its location is
        # between room 9 and the central stair, as recorded by the baseline audit.
        x9, y9 = room_positions[9]
        x11, y11 = room_positions[11]
        room_positions[10] = [rounded(x9 + (x11 - x9) * 0.37), rounded((y9 + y11) / 2)]

    spaces = []
    for number in range(1, 33):
        if number not in room_positions:
            continue
        values = baseline.get(number, {})
        total_area = values.get("totalFloorM2")
        bathroom_area = values.get("bathroomFloorM2")
        closed_kitchen = bool(values.get("closedKitchen", False))
        business = {
            "bathroomAreaM2": bathroom_area,
            "bathroomPerimeterM": values.get("bathroomPerimeterM"),
            "closedKitchen": closed_kitchen,
            "closedKitchenAreaM2": values.get("closedKitchenFloorM2"),
            "kitchenWallLengthM": values.get("kitchenWallLengthM"),
            "floorTile": "40×40 cm" if closed_kitchen else "80×80 cm",
            "wallTile": "40×80 cm",
        }
        position = room_positions[number]
        spaces.append({
            "id": f"room-{number}",
            "label": str(number),
            "type": "room",
            "labelPosition": position,
            "selectionBoundary": selection_boundary(position, total_area),
            "boundaryStatus": "selection-region",
            "metrics": {"areaM2": total_area, "perimeterM": None},
            "business": business,
            "verification": {
                "status": "needs-review",
                "note": "面积来自现有 CAD 量取基线；房间归属边界和周长仍需逐房复核。",
            },
        })
    return spaces


def export(args: argparse.Namespace) -> dict:
    bounds = tuple(args.bounds)
    document = ezdxf.readfile(args.source)
    source_entities = [
        entity for entity in document.modelspace()
        if quick_entity_overlap(entity, bounds)
    ]

    exported_entities: list[dict] = []
    dimensions: list[dict] = []
    room_positions: dict[int, list[float]] = {}
    entity_index = 0

    for source in source_entities:
        source_kind = source.dxftype()
        if source_kind == "DIMENSION":
            record = dimension_record(source)
            if record is not None:
                dimensions.append(record)
            layer_id = "dimensions"
        elif source_kind == "INSERT":
            layer_id = "fixtures"
        elif source_kind in {"TEXT", "MTEXT"}:
            layer_id = "annotations"
        else:
            layer_id = "linework"

        if source_kind in {"TEXT", "MTEXT"}:
            content = text_content(source)
            if ROOM_PATTERN.fullmatch(content):
                insert = source.dxf.insert
                room_positions[int(content)] = point(insert)

        try:
            leaves = disassemble.recursive_decompose((source,))
            for leaf in leaves:
                entity_index += 1
                leaf_id = f"entity-{entity_index}"
                if leaf.dxftype() in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                    text = export_text(leaf, leaf_id, layer_id, bounds)
                    if text is not None:
                        exported_entities.append(text)
                else:
                    exported_entities.extend(flattened_paths(leaf, leaf_id, layer_id, bounds))
        except (ezdxf.DXFError, ValueError, TypeError, AttributeError):
            continue

    baseline_rooms, baseline_data = load_baseline(args.baseline)
    spaces = build_spaces(room_positions, baseline_rooms)
    layer_counts = Counter(entity["layerId"] for entity in exported_entities)
    path_count = sum(entity["kind"] == "path" for entity in exported_entities)
    text_count = sum(entity["kind"] == "text" for entity in exported_entities)
    vertex_count = sum(len(entity["points"]) for entity in exported_entities if entity["kind"] == "path")

    return {
        "schemaVersion": "1.0.0",
        "project": {
            "id": args.project_id,
            "name": args.project_name,
            "source": Path(args.source).name,
            "sourceDrawing": args.source_drawing,
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "working-baseline",
            "statusNote": baseline_data.get("statusNote", "CAD geometry exported; business data needs review."),
        },
        "coordinateSystem": {
            "units": "mm",
            "xAxis": "right",
            "yAxis": "up",
            "origin": [0, 0],
        },
        "viewport": {
            "minX": bounds[0],
            "minY": bounds[1],
            "maxX": bounds[2],
            "maxY": bounds[3],
        },
        "layers": [
            {
                "id": layer_id,
                "name": name,
                "defaultVisible": visible,
                "entityCount": layer_counts[layer_id],
            }
            for layer_id, name, visible in LAYERS
        ],
        "entities": exported_entities,
        "spaces": spaces,
        "dimensions": dimensions,
        "statistics": {
            "sourceEntities": len(source_entities),
            "exportedEntities": len(exported_entities),
            "pathCount": path_count,
            "textCount": text_count,
            "vertexCount": vertex_count,
            "spaceCount": len(spaces),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--project-id", default="apartment")
    parser.add_argument("--project-name", default="32 套公寓")
    parser.add_argument("--source-drawing", default="平面布置图")
    parser.add_argument("--bounds", nargs=4, type=float, default=DEFAULT_BOUNDS, metavar=("MIN_X", "MIN_Y", "MAX_X", "MAX_Y"))
    args = parser.parse_args()

    result = export(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(result["statistics"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output} ({args.output.stat().st_size / 1_000_000:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
