#!/usr/bin/env python3
"""Convert the vendored CC0 SVG seed library into semantic JSON templates."""

from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


MM_PER_INCH = 25.4
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def mm(value: str | float) -> int:
    return int(round(float(value) * MM_PER_INCH))


def tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def rectangle(element: ET.Element) -> dict:
    x, y = float(element.get("x", 0)), float(element.get("y", 0))
    width, height = float(element.get("width", 0)), float(element.get("height", 0))
    return {"points": [[mm(x), mm(y)], [mm(x + width), mm(y)], [mm(x + width), mm(y + height)], [mm(x), mm(y + height)]], "closed": True, "role": "outline"}


def line(element: ET.Element) -> dict:
    return {"points": [[mm(element.get("x1", 0)), mm(element.get("y1", 0))], [mm(element.get("x2", 0)), mm(element.get("y2", 0))]], "closed": False, "role": "detail"}


def ellipse(element: ET.Element) -> dict:
    cx, cy = float(element.get("cx", 0)), float(element.get("cy", 0))
    rx, ry = float(element.get("rx", 0)), float(element.get("ry", 0))
    points = [[mm(cx + rx * math.cos(index * math.tau / 32)), mm(cy + ry * math.sin(index * math.tau / 32))] for index in range(32)]
    return {"points": points, "closed": True, "role": "outline"}


def simple_path(element: ET.Element) -> dict | None:
    tokens = re.findall(rf"[MLZmlz]|{NUMBER}", element.get("d", ""))
    points: list[list[int]] = []
    closed = False
    command = ""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command.lower() == "z":
                closed = True
            continue
        if command not in {"M", "L"} or index + 1 >= len(tokens):
            return None
        points.append([mm(tokens[index]), mm(tokens[index + 1])])
        index += 2
    return {"points": points, "closed": closed, "role": "detail"} if len(points) >= 2 else None


def category(value: str, template_id: str) -> str:
    if template_id in {"stairs", "elevator"}:
        return "circulation"
    if template_id == "electric_panel":
        return "equipment"
    if value in {"Bathroom", "Kitchen"}:
        return "fixture"
    return "furniture"


def convert_template(root: Path, record: dict) -> dict:
    svg = ET.parse(root / record["file"]).getroot()
    paths: list[dict] = []
    circles: list[dict] = []
    for element in svg:
        kind = tag_name(element)
        if kind == "rect":
            paths.append(rectangle(element))
        elif kind == "line":
            paths.append(line(element))
        elif kind == "ellipse":
            paths.append(ellipse(element))
        elif kind == "circle":
            circles.append({"center": [mm(element.get("cx", 0)), mm(element.get("cy", 0))], "radius": max(1, mm(element.get("r", 0))), "role": "detail"})
        elif kind == "path":
            converted = simple_path(element)
            if converted:
                paths.append(converted)
    width, depth = mm(record["width_in"]), mm(record["depth_in"])
    geometry: dict = {"paths": paths}
    if circles:
        geometry["circles"] = circles
    return {
        "id": f"cc0-{record['id'].replace('_', '-')}",
        "name": record["name"],
        "category": category(record["category"], record["id"]),
        "size": {"width": width, "depth": depth},
        "anchor": [width // 2, depth // 2],
        "geometry": geometry,
        "source": {
            "kind": "catalog",
            "name": "pjm4github/FloorPlanner furnishings",
            "url": f"https://github.com/pjm4github/FloorPlanner/blob/main/assets/furnishings/{record['file']}",
            "license": "CC0-1.0",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", default=Path("catalog/cc0-floorplanner"))
    parser.add_argument("target", type=Path, nargs="?", default=Path("catalog/standard-templates.json"))
    args = parser.parse_args()
    manifest = json.loads((args.source / "manifest.json").read_text(encoding="utf-8"))
    payload = {
        "catalogVersion": "1.0.0",
        "units": "mm",
        "license": "CC0-1.0",
        "templates": [convert_template(args.source, record) for record in manifest],
    }
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.target}: {len(payload['templates'])} templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
