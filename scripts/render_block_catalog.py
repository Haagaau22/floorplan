#!/usr/bin/env python3
"""Render repeated DXF block definitions as an SVG identification sheet."""

from __future__ import annotations

import argparse
import html
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import bbox, disassemble, path

from export_floorplan import DEFAULT_BOUNDS, quick_entity_overlap


def number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def block_paths(block) -> list[tuple[list[tuple[float, float]], bool]]:
    result = []
    for entity in disassemble.recursive_decompose(block):
        try:
            drawing_path = path.make_path(entity)
        except (TypeError, ValueError, AttributeError):
            continue
        candidates = drawing_path.sub_paths() if drawing_path.has_sub_paths else (drawing_path,)
        for candidate in candidates:
            try:
                points = [(float(vertex.x), float(vertex.y)) for vertex in candidate.flattening(distance=3.0, segments=6)]
            except (TypeError, ValueError, AttributeError):
                continue
            if len(points) >= 2:
                result.append((points, bool(candidate.is_closed)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--bounds", nargs=4, type=float, default=DEFAULT_BOUNDS)
    args = parser.parse_args()

    document = ezdxf.readfile(args.source)
    counts = Counter(
        entity.dxf.name
        for entity in document.modelspace().query("INSERT")
        if quick_entity_overlap(entity, tuple(args.bounds), margin=2_000)
    )
    templates = []
    for name, count in counts.most_common():
        block = document.blocks.get(name)
        paths = block_paths(block)
        try:
            extents = bbox.extents(list(block), fast=True)
            min_x, min_y = extents.extmin.x, extents.extmin.y
            width, height = max(extents.size.x, 1), max(extents.size.y, 1)
        except (ezdxf.DXFError, ValueError, TypeError):
            min_x = min_y = 0
            width = height = 1
        templates.append((name, count, paths, min_x, min_y, width, height))

    columns = 4
    cell_width, cell_height = 340, 270
    rows = (len(templates) + columns - 1) // columns
    body = []
    for index, (name, count, paths, min_x, min_y, width, height) in enumerate(templates):
        col, row = index % columns, index // columns
        x, y = col * cell_width, row * cell_height
        padding = max(width, height) * 0.08
        view_x, view_y = min_x - padding, min_y - padding
        view_w, view_h = width + padding * 2, height + padding * 2
        drawing = []
        for points, closed in paths:
            commands = [f"M {number(points[0][0])} {number(-points[0][1])}"]
            commands.extend(f"L {number(px)} {number(-py)}" for px, py in points[1:])
            if closed:
                commands.append("Z")
            drawing.append(f'<path d="{" ".join(commands)}"/>')
        body.append(
            f'<g transform="translate({x} {y})">'
            f'<rect x="8" y="8" width="324" height="254" rx="8" class="cell"/>'
            f'<text x="20" y="30" class="name">{html.escape(name)}</text>'
            f'<text x="320" y="30" text-anchor="end" class="count">{count} instances · {number(width)}×{number(height)} mm</text>'
            f'<svg x="20" y="42" width="300" height="200" viewBox="{number(view_x)} {number(-(min_y + height + padding))} {number(view_w)} {number(view_h)}" preserveAspectRatio="xMidYMid meet">'
            f'<g class="drawing">{"".join(drawing)}</g></svg>'
            '</g>'
        )

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {columns * cell_width} {rows * cell_height}">'
        '<style>'
        'svg{background:#f3f2ec}.cell{fill:#fff;stroke:#ccd2ca}.drawing{fill:none;stroke:#172522;stroke-width:3;vector-effect:non-scaling-stroke}'
        '.name{font:700 14px ui-monospace,monospace;fill:#172522}.count{font:10px ui-monospace,monospace;fill:#65716d}'
        '</style>'
        + ''.join(body)
        + '</svg>'
    )
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(svg, encoding="utf-8")
    print(f"wrote {args.target}: {len(templates)} templates, {sum(counts.values())} instances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
