#!/usr/bin/env python3
"""Report which polygonized CAD cells contain or are nearest to seed points."""

from __future__ import annotations

import argparse
import json

from shapely.geometry import Point, shape


def parse_seed(value: str) -> tuple[str, float, float]:
    label, x, y = value.split(":", 2)
    return label, float(x), float(y)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("geojson")
    parser.add_argument("seeds", nargs="+", type=parse_seed)
    args = parser.parse_args()

    with open(args.geojson, encoding="utf-8") as handle:
        data = json.load(handle)

    cells = []
    for feature in data["features"]:
        geom = shape(feature["geometry"])
        props = feature.get("properties", {})
        cells.append((geom, props))

    for label, x, y in args.seeds:
        point = Point(x, y)
        containing = [
            (geom.area / 1_000_000, props)
            for geom, props in cells
            if geom.covers(point)
        ]
        nearest = sorted(
            (
                geom.distance(point),
                geom.area / 1_000_000,
                props,
                geom.centroid.x,
                geom.centroid.y,
            )
            for geom, props in cells
        )[:5]
        print(f"{label} ({x:.0f}, {y:.0f})")
        print("  containing:", containing or "none")
        print("  nearest:")
        for distance, area, props, cx, cy in nearest:
            print(
                f"    distance={distance:.1f} area={area:.3f} "
                f"centroid=({cx:.0f},{cy:.0f}) props={props}"
            )


if __name__ == "__main__":
    main()
