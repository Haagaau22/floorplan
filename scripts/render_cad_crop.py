#!/usr/bin/env python3
"""Render a selected model-space rectangle from a DXF to a readable PNG."""

from __future__ import annotations

import sys

import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext, config, matplotlib


def make_crop_filter(xmin: float, ymin: float, xmax: float, ymax: float):
    margin = 2000.0
    xmin -= margin
    ymin -= margin
    xmax += margin
    ymax += margin

    def overlaps(left: float, bottom: float, right: float, top: float) -> bool:
        return not (right < xmin or left > xmax or top < ymin or bottom > ymax)

    def crop_filter(entity) -> bool:
        kind = entity.dxftype()
        if kind == "LINE":
            a, b = entity.dxf.start, entity.dxf.end
            return overlaps(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))
        if kind == "LWPOLYLINE":
            points = list(entity.get_points("xy"))
            if not points:
                return False
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            return overlaps(min(xs), min(ys), max(xs), max(ys))
        if kind in {"CIRCLE", "ARC"}:
            c, r = entity.dxf.center, entity.dxf.radius
            return overlaps(c.x - r, c.y - r, c.x + r, c.y + r)
        if kind in {"TEXT", "MTEXT", "INSERT"}:
            p = entity.dxf.insert
            return overlaps(p.x, p.y, p.x, p.y)
        if kind == "DIMENSION":
            return False
        if kind == "LEADER":
            points = list(entity.vertices)
            if not points:
                return False
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            return overlaps(min(xs), min(ys), max(xs), max(ys))
        return False

    return crop_filter


def main() -> int:
    source, target = sys.argv[1:3]
    xmin, ymin, xmax, ymax = map(float, sys.argv[3:7])
    width = float(sys.argv[7]) if len(sys.argv) > 7 else 24.0
    aspect = (xmax - xmin) / (ymax - ymin)
    height = width / aspect

    doc = ezdxf.readfile(source)
    fig = plt.figure(figsize=(width, height), dpi=200, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1], facecolor="white")
    ctx = RenderContext(doc)
    backend = matplotlib.MatplotlibBackend(ax)
    render_config = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.BLACK,
        hatch_policy=config.HatchPolicy.SHOW_OUTLINE,
        image_policy=config.ImagePolicy.IGNORE,
        proxy_graphic_policy=config.ProxyGraphicPolicy.IGNORE,
        lineweight_policy=config.LineweightPolicy.RELATIVE,
        min_lineweight=0.08,
    )
    Frontend(ctx, backend, config=render_config).draw_layout(
        doc.modelspace(), filter_func=make_crop_filter(xmin, ymin, xmax, ymax)
    )
    backend.finalize()
    fig.set_size_inches(width, height, forward=True)
    fig.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_position([0, 0, 1, 1])
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_axis_off()
    fig.savefig(target, dpi=200, facecolor="white", bbox_inches=None, pad_inches=0)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
