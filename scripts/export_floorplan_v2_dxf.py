#!/usr/bin/env python3
"""Export semantic floorplan JSON to an editable DXF with named layers and blocks."""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

import ezdxf

from semantic_floorplan import load_project, split_segment


LAYERS = {
    "WALLS": 7,
    "OPENINGS": 4,
    "SPACES": 3,
    "FURNITURE": 8,
    "ANNOTATIONS": 2,
    "EXCLUDED": 9,
    "DETAILS": 8,
}


def export(source: Path, target: Path, level_id: str | None = None) -> None:
    data = load_project(source)
    level = next((item for item in data["levels"] if item["id"] == level_id), data["levels"][0])
    canvas_height = data["canvas"]["height"]
    document = ezdxf.new("R2018", setup=True)
    document.header["$INSUNITS"] = 4  # millimetres
    for name, color in LAYERS.items():
        document.layers.add(name, color=color)
    modelspace = document.modelspace()

    def point(value: list[float] | tuple[float, float]) -> tuple[float, float]:
        return float(value[0]), float(canvas_height - value[1])

    openings_by_segment: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for opening in level["openings"]:
        openings_by_segment[(opening["wallId"], opening["segmentIndex"])].append(opening)

    walls = {wall["id"]: wall for wall in level["walls"]}
    for wall in level["walls"]:
        for index, (start, end) in enumerate(zip(wall["centerline"], wall["centerline"][1:])):
            for piece_start, piece_end in split_segment(start, end, openings_by_segment[(wall["id"], index)]):
                modelspace.add_lwpolyline(
                    [point(piece_start), point(piece_end)],
                    dxfattribs={"layer": "WALLS", "const_width": wall["thickness"]},
                )

    for opening in level["openings"]:
        wall = walls[opening["wallId"]]
        start, end = wall["centerline"][opening["segmentIndex"] : opening["segmentIndex"] + 2]
        length = math.dist(start, end)
        ratio_start = opening["offset"] / length
        ratio_end = (opening["offset"] + opening["width"]) / length
        opening_start = [start[0] + (end[0] - start[0]) * ratio_start, start[1] + (end[1] - start[1]) * ratio_start]
        opening_end = [start[0] + (end[0] - start[0]) * ratio_end, start[1] + (end[1] - start[1]) * ratio_end]
        if opening["kind"] == "window":
            modelspace.add_line(point(opening_start), point(opening_end), dxfattribs={"layer": "OPENINGS", "lineweight": 70})
        elif opening["kind"] == "door":
            dx, dy = opening_end[0] - opening_start[0], opening_end[1] - opening_start[1]
            leaf_end = [opening_start[0] - dy, opening_start[1] + dx]
            modelspace.add_line(point(opening_start), point(leaf_end), dxfattribs={"layer": "OPENINGS"})
            start_angle = math.degrees(math.atan2(-(opening_end[1] - opening_start[1]), opening_end[0] - opening_start[0]))
            end_angle = math.degrees(math.atan2(-(leaf_end[1] - opening_start[1]), leaf_end[0] - opening_start[0]))
            modelspace.add_arc(point(opening_start), opening["width"], min(start_angle, end_angle), max(start_angle, end_angle), dxfattribs={"layer": "OPENINGS"})

    for template in data["templates"]:
        block_name = f"FP_{template['id'].upper().replace('-', '_')}"
        block = document.blocks.new(block_name, base_point=(template["anchor"][0], -template["anchor"][1]))
        for item in template["geometry"]["paths"]:
            points = [(value[0], -value[1]) for value in item["points"]]
            block.add_lwpolyline(points, close=item["closed"], dxfattribs={"layer": "FURNITURE"})
        for item in template["geometry"].get("circles", []):
            block.add_circle((item["center"][0], -item["center"][1]), item["radius"], dxfattribs={"layer": "FURNITURE"})

    templates = {item["id"]: item for item in data["templates"]}
    for instance in level["instances"]:
        block_name = f"FP_{instance['templateId'].upper().replace('-', '_')}"
        scale_x, scale_y = instance.get("scale", [1, 1])
        modelspace.add_blockref(
            block_name,
            point(instance["position"]),
            dxfattribs={"layer": "FURNITURE", "xscale": scale_x, "yscale": scale_y, "rotation": -instance.get("rotation", 0)},
        )
        assert instance["templateId"] in templates

    for space in level["spaces"]:
        layer = "EXCLUDED" if space["kind"] == "excluded" else "SPACES"
        modelspace.add_lwpolyline([point(value) for value in space["boundary"]], close=True, dxfattribs={"layer": layer})
        if space.get("labelStyle") != "hidden":
            label = space.get("number") or space["name"]
            modelspace.add_text(label, height=240, dxfattribs={"layer": "ANNOTATIONS"}).set_placement(point(space["labelPosition"]), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    for detail in level.get("details", []):
        modelspace.add_lwpolyline([point(value) for value in detail["points"]], close=detail["closed"], dxfattribs={"layer": "DETAILS"})

    target.parent.mkdir(parents=True, exist_ok=True)
    document.saveas(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--level")
    args = parser.parse_args()
    export(args.source, args.target, args.level)
    print(f"wrote {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
