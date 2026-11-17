#!/usr/bin/env python3
"""Render semantic floorplan JSON to a standalone SVG preview."""

from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

from semantic_floorplan import load_project, opening_points, path_d, svg_points


def render(source: Path, target: Path, level_id: str | None = None) -> None:
    data = load_project(source)
    level = next((item for item in data["levels"] if item["id"] == level_id), data["levels"][0])
    width, height = data["canvas"]["width"], data["canvas"]["height"]
    templates = {item["id"]: item for item in data["templates"]}
    walls = {item["id"]: item for item in level["walls"]}

    template_symbols: list[str] = []
    for template in data["templates"]:
        paths = []
        for item in template["geometry"]["paths"]:
            role = item.get("role", "outline")
            paths.append(f'<path class="template-{role}" d="{path_d(item["points"], item["closed"])}"/>')
        for item in template["geometry"].get("circles", []):
            role = item.get("role", "outline")
            paths.append(f'<circle class="template-{role}" cx="{item["center"][0]}" cy="{item["center"][1]}" r="{item["radius"]}"/>')
        template_symbols.append(f'<g id="template-{html.escape(template["id"])}">{"".join(paths)}</g>')

    excluded: list[str] = []
    regular_spaces: list[str] = []
    labels: list[str] = []
    for space in level["spaces"]:
        polygon = svg_points(space["boundary"])
        if space["kind"] == "excluded":
            excluded.append(f'<polygon points="{polygon}" class="excluded-zone"/>')
        else:
            regular_spaces.append(f'<polygon points="{polygon}" class="space-zone"/>')
        if space.get("labelStyle") != "hidden":
            x, y = space["labelPosition"]
            label = space.get("number") or space["name"]
            label_class = "room-label" if space.get("labelStyle") == "room-tag" else "area-label"
            background = '' if label_class == "room-label" else '<rect x="-430" y="-210" width="860" height="420" rx="120"/>'
            labels.append(f'<g class="{label_class}" transform="translate({x} {y})">{background}<text text-anchor="middle" dominant-baseline="central">{html.escape(label)}</text></g>')

    wall_elements = [f'<polyline points="{svg_points(wall["centerline"])}" stroke-width="{wall["thickness"]}"/>' for wall in level["walls"]]
    opening_elements: list[str] = []
    for opening in level["openings"]:
        wall = walls[opening["wallId"]]
        start, end = opening_points(wall, opening)
        opening_elements.append(f'<line class="opening-cut" x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" stroke-width="{wall["thickness"] + 24}"/>')
        if opening["kind"] == "window":
            opening_elements.append(f'<line class="window-line" x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}"/>')
        elif opening["kind"] == "door":
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            nx, ny = (-dy / length, dx / length) if length else (0, 0)
            side = -1 if "out" in opening.get("swing", "") else 1
            leaf_end = (start[0] + nx * length * side, start[1] + ny * length * side)
            opening_elements.append(f'<path class="door-swing" d="M {end[0]} {end[1]} A {length} {length} 0 0 {1 if side > 0 else 0} {leaf_end[0]} {leaf_end[1]} M {start[0]} {start[1]} L {leaf_end[0]} {leaf_end[1]}"/>')

    instances: list[str] = []
    for instance in level["instances"]:
        template = templates[instance["templateId"]]
        x, y = instance["position"]
        anchor_x, anchor_y = template["anchor"]
        rotation = instance.get("rotation", 0)
        scale_x, scale_y = instance.get("scale", [1, 1])
        transform = f"translate({x} {y}) rotate({rotation}) scale({scale_x} {scale_y}) translate({-anchor_x} {-anchor_y})"
        instances.append(f'<use href="#template-{html.escape(template["id"])}" transform="{transform}"/>')

    details = [f'<path d="{path_d(item["points"], item["closed"])}"/>' for item in level.get("details", [])]
    margin = max(width, height) * 0.02
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-margin:g} {-margin:g} {width + 2 * margin:g} {height + 2 * margin:g}">
<defs>
  {''.join(template_symbols)}
</defs>
<style>
  .paper {{ fill:#fbfaf6; }}
  .space-zone {{ fill:#f7f4ec; stroke:none; }}
  .excluded-zone {{ fill:#b8afa1; fill-opacity:.22; stroke:#8b857b; stroke-width:24; stroke-dasharray:120 72; }}
  .walls polyline {{ fill:none; stroke:#18201f; stroke-linecap:square; stroke-linejoin:miter; }}
  .opening-cut {{ stroke:#fbfaf6; stroke-linecap:butt; }}
  .window-line {{ stroke:#4d7775; stroke-width:64; }}
  .door-swing {{ fill:none; stroke:#53605e; stroke-width:24; }}
  .instances {{ fill:none; stroke:#44514f; stroke-width:22; vector-effect:non-scaling-stroke; }}
  .template-detail {{ stroke-width:14; }}
  .template-fill {{ fill:#d7dfdc; }}
  .details {{ fill:none; stroke:#687370; stroke-width:18; }}
  .room-label text {{ fill:#173f3b; stroke:#fbfaf6; stroke-width:70px; paint-order:stroke fill; stroke-linejoin:round; font:700 270px Arial,sans-serif; }}
  .area-label rect {{ fill:#f0ece2; stroke:#756f65; stroke-width:20; }}
  .area-label text {{ fill:#514c45; font:600 170px Arial,'PingFang SC',sans-serif; }}
</style>
<rect class="paper" x="{-margin:g}" y="{-margin:g}" width="{width + 2 * margin:g}" height="{height + 2 * margin:g}"/>
<g>{''.join(regular_spaces)}{''.join(excluded)}</g>
<g class="walls">{''.join(wall_elements)}</g>
<g class="openings">{''.join(opening_elements)}</g>
<g class="details">{''.join(details)}</g>
<g class="instances">{''.join(instances)}</g>
<g class="labels">{''.join(labels)}</g>
</svg>
'''
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--level")
    args = parser.parse_args()
    render(args.source, args.target, args.level)
    print(f"wrote {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
