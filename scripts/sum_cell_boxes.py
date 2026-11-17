#!/usr/bin/env python3
"""Intersect polygonized floor cells with labelled rectangles."""

from __future__ import annotations

import json
import sys

from shapely.geometry import box, shape
from shapely.ops import unary_union


def main() -> int:
    source = sys.argv[1]
    data = json.load(open(source, encoding="utf-8"))
    cells = unary_union([shape(feature["geometry"]) for feature in data["features"]])
    for spec in sys.argv[2:]:
        label, coords = spec.split(":", 1)
        xmin, ymin, xmax, ymax = map(float, coords.split(","))
        target = box(xmin, ymin, xmax, ymax)
        covered = cells.intersection(target).area / 1_000_000
        gross = target.area / 1_000_000
        print(f"{label}\tcovered={covered:.3f}\tgross={gross:.3f}\tcoverage={covered/gross:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
