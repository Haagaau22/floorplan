#!/usr/bin/env python3
"""Extract CAD dimension measurements and defining points from a rectangle."""

from __future__ import annotations

import csv
import sys

import ezdxf


def point(entity, name):
    value = getattr(entity.dxf, name, None)
    if value is None:
        return (None, None)
    return (value.x, value.y)


def main() -> int:
    source, target = sys.argv[1:3]
    xmin, ymin, xmax, ymax = map(float, sys.argv[3:7])
    doc = ezdxf.readfile(source)
    rows = []
    for entity in doc.modelspace().query("DIMENSION"):
        x, y = point(entity, "defpoint")
        if x is None or not (xmin <= x <= xmax and ymin <= y <= ymax):
            continue
        try:
            measurement = float(entity.get_measurement())
        except Exception:
            measurement = None
        p2 = point(entity, "defpoint2")
        p3 = point(entity, "defpoint3")
        p4 = point(entity, "defpoint4")
        rows.append([
            entity.dxf.handle,
            entity.dxf.layer,
            entity.dimtype,
            entity.dxf.text,
            measurement,
            x,
            y,
            *p2,
            *p3,
            *p4,
        ])
    with open(target, "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "handle", "layer", "dimtype", "text_override", "measurement",
            "def_x", "def_y", "p2_x", "p2_y", "p3_x", "p3_y", "p4_x", "p4_y",
        ])
        writer.writerows(rows)
    print(f"{len(rows)} dimensions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
