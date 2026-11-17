#!/usr/bin/env python3
"""Close orthogonal wall gaps and polygonize floor cells from a CAD plan row."""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import LineString, mapping
from shapely.ops import polygonize, unary_union


def cluster(value: float, tolerance: float = 12.0) -> float:
    return round(value / tolerance) * tolerance


def merge_intervals(intervals, gap: float):
    if not intervals:
        return []
    intervals = sorted((min(a, b), max(a, b)) for a, b in intervals)
    out = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def main() -> int:
    source, prefix = sys.argv[1:3]
    xmin, ymin, xmax, ymax = map(float, sys.argv[3:7])
    door_gap = float(sys.argv[7]) if len(sys.argv) > 7 else 1050.0
    doc = ezdxf.readfile(source)

    horizontals = defaultdict(list)
    verticals = defaultdict(list)

    def add_segment(a, b):
        x1, y1 = a
        x2, y2 = b
        if max(x1, x2) < xmin or min(x1, x2) > xmax or max(y1, y2) < ymin or min(y1, y2) > ymax:
            return
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 70:
            return
        if abs(y2 - y1) <= 6:
            y = cluster((y1 + y2) / 2)
            horizontals[y].append((x1, x2))
        elif abs(x2 - x1) <= 6:
            x = cluster((x1 + x2) / 2)
            verticals[x].append((y1, y2))

    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == "LINE":
            add_segment((entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y))
        elif kind == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points("xy")]
            for a, b in zip(points, points[1:]):
                add_segment(a, b)
            if entity.closed and len(points) > 2:
                add_segment(points[-1], points[0])

    lines = []
    line_rows = []
    for y, intervals in horizontals.items():
        for a, b in merge_intervals(intervals, door_gap):
            lines.append(LineString([(a, y), (b, y)]))
            line_rows.append(["H", y, a, b, b - a])
    for x, intervals in verticals.items():
        for a, b in merge_intervals(intervals, door_gap):
            lines.append(LineString([(x, a), (x, b)]))
            line_rows.append(["V", x, a, b, b - a])

    with open(prefix + "_lines.csv", "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["orientation", "coordinate", "start", "end", "length"])
        writer.writerows(sorted(line_rows, key=lambda row: (row[0], row[1], row[2])))

    network = unary_union(lines)
    polygons = [p for p in polygonize(network) if 0.8 <= p.area / 1_000_000 <= 250]
    polygons.sort(key=lambda p: (p.centroid.y, p.centroid.x))

    features = []
    rows = []
    for index, polygon in enumerate(polygons, start=1):
        area = polygon.area / 1_000_000
        perimeter = polygon.length / 1000
        c = polygon.centroid
        rows.append([index, area, perimeter, c.x, c.y, *polygon.bounds])
        features.append({
            "type": "Feature",
            "properties": {"id": index, "area_m2": area, "perimeter_m": perimeter},
            "geometry": mapping(polygon),
        })

    with open(prefix + ".csv", "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "area_m2", "perimeter_m", "centroid_x", "centroid_y", "min_x", "min_y", "max_x", "max_y"])
        writer.writerows(rows)
    with open(prefix + ".geojson", "w", encoding="utf-8") as stream:
        json.dump({"type": "FeatureCollection", "features": features}, stream, ensure_ascii=False)

    fig, ax = plt.subplots(figsize=(24, 10), dpi=180, facecolor="white")
    ax.set_facecolor("white")
    for line in lines:
        xs, ys = line.xy
        ax.plot(xs, ys, color="#555555", linewidth=0.25)
    cmap = plt.get_cmap("tab20")
    for index, polygon in enumerate(polygons, start=1):
        coords = list(polygon.exterior.coords)
        patch = MplPolygon(coords, closed=True, facecolor=cmap(index % 20), edgecolor="#111111", linewidth=0.5, alpha=0.5)
        ax.add_patch(patch)
        c = polygon.representative_point()
        ax.text(c.x, c.y, f"{index}\n{polygon.area/1_000_000:.1f}", fontsize=5, ha="center", va="center")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    fig.savefig(prefix + ".png", facecolor="white", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"{len(lines)} merged lines, {len(polygons)} polygons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
