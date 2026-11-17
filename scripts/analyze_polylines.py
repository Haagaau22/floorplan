#!/usr/bin/env python3
"""List closed lightweight polylines and their planar areas in a crop."""

from __future__ import annotations

import csv
import math
import sys

import ezdxf


def signed_area(points):
    return sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    ) / 2.0


def main() -> int:
    source, target = sys.argv[1:3]
    xmin, ymin, xmax, ymax = map(float, sys.argv[3:7])
    doc = ezdxf.readfile(source)
    rows = []
    for entity in doc.modelspace().query("LWPOLYLINE"):
        if not entity.closed:
            continue
        points = [(p[0], p[1]) for p in entity.get_points("xy")]
        if len(points) < 3:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        if max(xs) < xmin or min(xs) > xmax or max(ys) < ymin or min(ys) > ymax:
            continue
        area = abs(signed_area(points)) / 1_000_000.0
        rows.append([
            entity.dxf.handle,
            entity.dxf.layer,
            area,
            len(points),
            sum(xs) / len(xs),
            sum(ys) / len(ys),
            min(xs), min(ys), max(xs), max(ys),
            entity.dxf.const_width,
        ])
    rows.sort(key=lambda row: row[2], reverse=True)
    with open(target, "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "handle", "layer", "area_m2", "vertices", "avg_x", "avg_y",
            "min_x", "min_y", "max_x", "max_y", "const_width",
        ])
        writer.writerows(rows)
    print(f"{len(rows)} closed polylines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
