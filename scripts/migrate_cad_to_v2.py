#!/usr/bin/env python3
"""Migrate the apartment CAD regression fixture into self-contained semantic JSON v2.

The CAD is used only by this migration command. Runtime rendering and exports use
the generated JSON, including reusable block definitions and their instances.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import re
from pathlib import Path

import ezdxf
from ezdxf import disassemble, path

from export_floorplan import DEFAULT_BOUNDS, quick_entity_overlap


# Apartment ownership regions for the CAD regression fixture. These follow the
# inside faces of the unit boundary walls (and window lines), so selection
# highlights the complete unit without spilling into public corridors or stairs.
ROOM_BOUNDARIES_LOCAL: dict[int, tuple[int, int, int, int] | list[list[int]]] = {
    1: [
        [13_313, 10_784],
        [25_338, 10_784],
        [25_338, 12_129],
        [23_371, 12_129],
        [23_371, 13_188],
        [13_313, 13_188],
    ],
    2: [
        [13_313, 13_286],
        [23_371, 13_286],
        [23_371, 16_046],
        [20_653, 16_046],
        [20_653, 15_745],
        [13_313, 15_745],
    ],
    # The toilet projecting upward at the corridor side belongs to room 4.
    # Furniture outlines inside either apartment must not alter this ownership.
    3: [
        [13_313, 15_854],
        [20_653, 15_854],
        [20_653, 16_046],
        [23_321, 16_046],
        [23_321, 18_644],
        [13_313, 18_644],
    ],
    4: [
        [13_313, 18_760],
        [23_321, 18_760],
        [23_321, 17_251],
        [24_901, 17_251],
        [24_901, 22_094],
        [13_313, 22_094],
    ],
    5: (13_313, 22_216, 24_901, 26_104),
    6: (13_313, 26_221, 24_901, 29_122),
    7: (13_313, 29_245, 24_901, 32_141),
    8: (13_313, 32_258, 24_901, 35_264),
    9: (26_953, 17_762, 30_339, 27_026),
    10: [
        [30_459, 17_762],
        [35_125, 17_762],
        [35_125, 19_268],
        [33_560, 19_268],
        [33_560, 27_026],
        [30_459, 27_026],
    ],
    11: [
        [40_203, 15_942],
        [44_057, 15_942],
        [44_057, 22_630],
        [36_723, 22_630],
        [36_723, 19_096],
        [40_203, 19_096],
    ],
    12: (44_131, 15_942, 47_297, 26_233),
    13: (47_420, 15_942, 50_494, 26_233),
    14: (50_690, 15_942, 53_887, 26_233),
    15: (54_004, 15_942, 57_059, 26_233),
    16: (57_176, 15_942, 60_693, 26_233),
    17: (60_809, 17_552, 64_209, 26_233),
    18: (64_326, 17_550, 67_510, 27_038),
    19: (67_633, 17_550, 70_781, 27_038),
    20: (70_996, 17_548, 74_242, 27_038),
    21: (74_359, 17_546, 77_746, 26_239),
    22: (77_863, 15_985, 81_379, 26_239),
    23: (81_497, 15_985, 84_527, 26_239),
    24: (84_650, 15_985, 87_650, 26_239),
    25: (84_638, 1_028, 87_644, 14_270),
    26: (80_949, 1_028, 84_521, 14_270),
    27: (77_814, 1_028, 80_826, 14_270),
    28: [
        [57_545, 1_028],
        [60_736, 1_028],
        [60_736, 8_534],
        [59_420, 8_534],
        [59_420, 13_876],
        [57_545, 13_876],
    ],
    29: (54_158, 1_028, 57_427, 13_876),
    30: (50_611, 1_028, 54_041, 13_876),
    # Rooms 31 and 32 are divided by one continuous vertical wall. The lower
    # furniture edge must not introduce a sideways step into this boundary.
    31: (47_157, 1_028, 50_488, 13_876),
    32: [
        [43_670, 1_028],
        [47_033, 1_028],
        [47_033, 13_876],
        [41_740, 13_876],
        [41_740, 10_772],
        [43_670, 10_772],
    ],
}

ROOM_LABEL_OVERRIDES_LOCAL: dict[int, list[int]] = {
    10: [32_010, 21_393],
}

EXCLUDED_RIGHT_LOCAL: list[list[int]] = [
    [60_994, 1_028],
    [70_781, 1_028],
    [70_781, 8_761],
    [72_385, 8_761],
    [72_385, 10_790],
    [75_607, 10_790],
    [75_607, 12_364],
    [70_473, 12_364],
    [70_473, 15_776],
    [68_174, 15_776],
    [68_174, 13_182],
    [65_758, 13_182],
    [65_758, 10_563],
    [62_383, 10_563],
    [62_383, 8_534],
    [60_994, 8_534],
]

WATER_ELECTRIC_ROOM_LOCAL: list[list[int]] = [
    [59_540, 8_755],
    [60_945, 8_755],
    [60_945, 13_876],
    [59_540, 13_876],
]


def apartment_boundary(number: int, fallback: list[list[int]]) -> list[list[int]]:
    bounds = ROOM_BOUNDARIES_LOCAL.get(number)
    if bounds is None:
        return fallback
    if isinstance(bounds, list):
        return bounds
    left, top, right, bottom = bounds
    return [[left, top], [right, top], [right, bottom], [left, bottom]]


def integer(value: float) -> int:
    return int(round(float(value)))


def point_to_polygon_distance(x: float, y: float, polygon: list[list[int]]) -> float:
    inside = False
    distance_squared = math.inf
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        ax, ay = first
        bx, by = second
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
        dx, dy = bx - ax, by - ay
        if dx or dy:
            ratio = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            nearest_x, nearest_y = ax + ratio * dx, ay + ratio * dy
        else:
            nearest_x, nearest_y = ax, ay
        distance_squared = min(distance_squared, (x - nearest_x) ** 2 + (y - nearest_y) ** 2)
    distance = math.sqrt(distance_squared)
    return distance if inside else -distance


def polygon_centroid(polygon: list[list[int]]) -> tuple[float, float]:
    area_twice = 0.0
    x_sum = 0.0
    y_sum = 0.0
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        cross = first[0] * second[1] - second[0] * first[1]
        area_twice += cross
        x_sum += (first[0] + second[0]) * cross
        y_sum += (first[1] + second[1]) * cross
    if not area_twice:
        return polygon[0][0], polygon[0][1]
    return x_sum / (3 * area_twice), y_sum / (3 * area_twice)


def polygon_visual_center(polygon: list[list[int]], precision: float = 40.0) -> list[int]:
    """Find a stable label anchor at the polygon's pole of inaccessibility."""
    min_x = min(point[0] for point in polygon)
    min_y = min(point[1] for point in polygon)
    max_x = max(point[0] for point in polygon)
    max_y = max(point[1] for point in polygon)
    cell_size = min(max_x - min_x, max_y - min_y)
    if not cell_size:
        return [integer(min_x), integer(min_y)]

    def cell(x: float, y: float, half_size: float) -> tuple[float, float, float, float, float]:
        distance = point_to_polygon_distance(x, y, polygon)
        maximum = distance + half_size * math.sqrt(2)
        return (-maximum, x, y, half_size, distance)

    queue: list[tuple[float, float, float, float, float]] = []
    half_size = cell_size / 2
    x = min_x
    while x < max_x:
        y = min_y
        while y < max_y:
            heapq.heappush(queue, cell(x + half_size, y + half_size, half_size))
            y += cell_size
        x += cell_size

    centroid_x, centroid_y = polygon_centroid(polygon)
    best = cell(centroid_x, centroid_y, 0)
    bbox_center = cell((min_x + max_x) / 2, (min_y + max_y) / 2, 0)
    if bbox_center[4] > best[4]:
        best = bbox_center

    while queue:
        current = heapq.heappop(queue)
        _, cell_x, cell_y, half_size, distance = current
        if distance > best[4]:
            best = current
        if -current[0] - best[4] <= precision:
            continue
        half_size /= 2
        for offset_x in (-half_size, half_size):
            for offset_y in (-half_size, half_size):
                heapq.heappush(queue, cell(cell_x + offset_x, cell_y + offset_y, half_size))
    return [integer(best[1]), integer(best[2])]


def is_room_number_circle(entity, label_positions: list[list[float]]) -> bool:
    if entity.dxftype() != "CIRCLE":
        return False
    radius = float(entity.dxf.radius)
    if not 210 <= radius <= 225:
        return False
    center = entity.dxf.center
    return any(math.hypot(center.x - x, center.y - y) <= 320 for x, y in label_positions)


def room_label_anchors(source_entities, spaces: list[dict], xmin: float, ymax: float) -> dict[int, list[int]]:
    circles = [
        entity
        for entity in source_entities
        if entity.dxftype() == "CIRCLE" and 210 <= float(entity.dxf.radius) <= 225
    ]
    anchors: dict[int, list[int]] = {}
    for space in spaces:
        label_x, label_y = space["labelPosition"]
        candidates = [
            entity
            for entity in circles
            if math.hypot(entity.dxf.center.x - label_x, entity.dxf.center.y - label_y) <= 320
        ]
        if not candidates:
            continue
        nearest = min(
            candidates,
            key=lambda entity: math.hypot(entity.dxf.center.x - label_x, entity.dxf.center.y - label_y),
        )
        anchors[int(space["label"])] = [
            integer(nearest.dxf.center.x - xmin),
            integer(ymax - nearest.dxf.center.y),
        ]
    return anchors


def safe_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "unnamed"


def flattened(entity, tolerance: float = 5.0) -> list[dict]:
    try:
        source_path = path.make_path(entity)
    except (TypeError, ValueError, AttributeError, ezdxf.DXFError):
        return []
    candidates = source_path.sub_paths() if source_path.has_sub_paths else (source_path,)
    results: list[dict] = []
    for candidate in candidates:
        try:
            vertices = list(candidate.flattening(distance=tolerance, segments=4))
        except (TypeError, ValueError, AttributeError):
            continue
        if len(vertices) < 2:
            continue
        results.append({
            "points": [[integer(vertex.x), integer(-vertex.y)] for vertex in vertices],
            "closed": bool(getattr(candidate, "is_closed", False)),
            "role": "outline",
        })
    return results


def localize(points: list[list[int]], xmin: float, ymax: float) -> list[list[int]]:
    # `flattened` has already inverted Y, hence ymax + inverted_y.
    return [[integer(point[0] - xmin), integer(ymax + point[1])] for point in points]


def build_template(document, block_name: str, template_id: str) -> dict | None:
    block = document.blocks.get(block_name)
    paths: list[dict] = []
    for leaf in disassemble.recursive_decompose(block):
        if leaf.dxftype() in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
            continue
        paths.extend(flattened(leaf))
    if not paths:
        return None
    xs = [point[0] for item in paths for point in item["points"]]
    ys = [point[1] for item in paths for point in item["points"]]
    base = block.block.dxf.base_point
    return {
        "id": template_id,
        "name": f"CAD 项目块 {block_name}",
        "category": "fixture",
        "size": {"width": max(1, max(xs) - min(xs)), "depth": max(1, max(ys) - min(ys))},
        "anchor": [integer(base.x), integer(-base.y)],
        "geometry": {"paths": paths},
        "source": {"kind": "project", "name": block_name},
    }


def migrate(args: argparse.Namespace) -> dict:
    xmin, ymin, xmax, ymax = tuple(args.bounds)
    document = ezdxf.readfile(args.source)
    modelspace = document.modelspace()
    source_entities = [entity for entity in modelspace if quick_entity_overlap(entity, tuple(args.bounds))]
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    room_label_positions = [space["labelPosition"] for space in baseline["spaces"]]
    label_anchors = room_label_anchors(source_entities, baseline["spaces"], xmin, ymax)

    insert_entities = [entity for entity in source_entities if entity.dxftype() == "INSERT"]
    block_names = sorted({entity.dxf.name for entity in insert_entities})
    template_ids = {name: f"cad-{index:02d}-{safe_id(name)}" for index, name in enumerate(block_names, start=1)}
    templates: list[dict] = []
    valid_templates: set[str] = set()
    for block_name in block_names:
        template = build_template(document, block_name, template_ids[block_name])
        if template is not None:
            templates.append(template)
            valid_templates.add(block_name)

    instances = []
    for index, entity in enumerate(insert_entities, start=1):
        if entity.dxf.name not in valid_templates:
            continue
        insert = entity.dxf.insert
        instances.append({
            "id": f"cad-instance-{index:03d}",
            "templateId": template_ids[entity.dxf.name],
            "position": [integer(insert.x - xmin), integer(ymax - insert.y)],
            "rotation": round(-float(entity.dxf.rotation), 6),
            "scale": [round(float(entity.dxf.xscale), 6), round(float(entity.dxf.yscale), 6)],
        })

    details: list[dict] = []
    for entity in source_entities:
        if entity.dxftype() in {"INSERT", "TEXT", "MTEXT", "DIMENSION"}:
            continue
        if is_room_number_circle(entity, room_label_positions):
            continue
        try:
            leaves = disassemble.recursive_decompose((entity,))
            for leaf in leaves:
                if leaf.dxftype() in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                    continue
                for item in flattened(leaf):
                    item["points"] = localize(item["points"], xmin, ymax)
                    item.pop("role", None)
                    details.append(item)
        except (TypeError, ValueError, AttributeError, ezdxf.DXFError):
            continue

    spaces = []
    for space in baseline["spaces"]:
        number = space["label"]
        room_num = int(number)
        fallback_boundary = [[integer(x - xmin), integer(ymax - y)] for x, y in space["selectionBoundary"]]
        boundary = apartment_boundary(room_num, fallback_boundary)
        spaces.append({
            "id": f"room-{number}",
            "kind": "apartment",
            "name": f"{number}号房",
            "number": number,
            "boundary": boundary,
            "labelPosition": label_anchors.get(
                room_num,
                ROOM_LABEL_OVERRIDES_LOCAL.get(room_num, polygon_visual_center(boundary)),
            ),
            "labelStyle": "room-tag",
            "boundaryStatus": "verified",
            "boundarySource": "generated",
        })

    spaces.append({
        "id": "utility-water-electric",
        "kind": "utility",
        "name": "水电房",
        "boundary": WATER_ELECTRIC_ROOM_LOCAL,
        "labelPosition": polygon_visual_center(WATER_ELECTRIC_ROOM_LOCAL),
        "labelStyle": "area-name",
        "boundaryStatus": "verified",
        "boundarySource": "generated",
    })

    # Non-project land immediately left of the corridor beside room 27. This
    # polygon follows the exact hatched outline in the CAD fixture.
    spaces.append({
        "id": "excluded-left-of-room-27-corridor",
        "kind": "excluded",
        "name": "非项目区域",
        "boundary": EXCLUDED_RIGHT_LOCAL,
        "labelPosition": [integer(1_596_500 - xmin), integer(ymax - 630_000)],
        "labelStyle": "area-name",
        "boundaryStatus": "verified",
        "boundarySource": "generated",
    })

    return {
        "schemaVersion": "2.0.0",
        "project": {
            "id": "apartment",
            "name": "公寓户型图",
            "status": "review",
            "source": "CAD regression fixture migrated to semantic JSON",
            "notes": "CAD 仅用于回归迁移；运行时以本 JSON 为唯一数据源。旧图结构线暂存为 details，家具与设备已转换为模板实例。",
        },
        "coordinateSystem": {"units": "mm", "xAxis": "right", "yAxis": "down"},
        "canvas": {"width": integer(xmax - xmin), "height": integer(ymax - ymin)},
        "templates": templates,
        "levels": [{
            "id": "level-01",
            "name": "标准层",
            "elevation": 0,
            "walls": [],
            "openings": [],
            "spaces": spaces,
            "instances": instances,
            "details": details,
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--baseline", type=Path, default=Path("data/projects/apartment/floorplan.json"))
    parser.add_argument("--bounds", type=float, nargs=4, default=DEFAULT_BOUNDS, metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    args = parser.parse_args()
    data = migrate(args)
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"wrote {args.target}: {len(data['templates'])} templates, "
        f"{len(data['levels'][0]['instances'])} instances, {len(data['levels'][0]['details'])} details"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
