#!/usr/bin/env python3
"""Render Floorplan JSON to a standalone SVG for conversion verification."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()

    data = json.loads(args.source.read_text(encoding="utf-8"))
    viewport = data["viewport"]
    width = viewport["maxX"] - viewport["minX"]
    height = viewport["maxY"] - viewport["minY"]

    def x(value: float) -> float:
        return value - viewport["minX"]

    def y(value: float) -> float:
        return viewport["maxY"] - value

    paths_by_layer: dict[str, list[str]] = {}
    texts = []
    for entity in data["entities"]:
        if entity["kind"] == "path":
            points = entity["points"]
            commands = [f"M {number(x(points[0][0]))} {number(y(points[0][1]))}"]
            commands.extend(f"L {number(x(px))} {number(y(py))}" for px, py in points[1:])
            if entity["closed"]:
                commands.append("Z")
            paths_by_layer.setdefault(entity["layerId"], []).append(" ".join(commands))
        else:
            px, py = entity["position"]
            content = html.escape(entity["content"])
            rotation = -entity["rotation"]
            texts.append(
                f'<text x="{number(x(px))}" y="{number(y(py))}" '
                f'font-size="{number(entity["height"])}" '
                f'transform="rotate({number(rotation)} {number(x(px))} {number(y(py))})">{content}</text>'
            )

    layer_styles = {
        "linework": "#18201f",
        "fixtures": "#53605e",
        "annotations": "#2f3a38",
        "dimensions": "#b34c32",
    }
    body = []
    for layer, commands in paths_by_layer.items():
        body.append(
            f'<path data-layer="{html.escape(layer)}" d="{" ".join(commands)}" '
            f'fill="none" stroke="{layer_styles.get(layer, "#18201f")}" stroke-width="18"/>'
        )
    body.extend(texts)
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {number(width)} {number(height)}" '
        'style="background:#f8f7f2">\n'
        '<g font-family="Arial, PingFang SC, sans-serif" fill="#25302e">\n'
        + "\n".join(body)
        + "\n</g>\n</svg>\n"
    )
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(svg, encoding="utf-8")
    print(f"wrote {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
