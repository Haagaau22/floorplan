#!/usr/bin/env python3
"""Render linework and reconstruct readable linear dimensions without DIMASSOC."""

from __future__ import annotations

import math
import sys

import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext, config, matplotlib

from render_cad_crop import make_crop_filter


def main() -> int:
    source, target = sys.argv[1:3]
    xmin, ymin, xmax, ymax = map(float, sys.argv[3:7])
    width = float(sys.argv[7]) if len(sys.argv) > 7 else 16.0
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
        min_lineweight=0.06,
    )
    Frontend(ctx, backend, config=render_config).draw_layout(
        doc.modelspace(), filter_func=make_crop_filter(xmin, ymin, xmax, ymax)
    )
    backend.finalize()

    for entity in doc.modelspace().query("DIMENSION"):
        d = entity.dxf.defpoint
        if not (xmin <= d.x <= xmax and ymin <= d.y <= ymax):
            continue
        try:
            value = float(entity.get_measurement())
        except Exception:
            continue
        if not (200 <= value <= 20000):
            continue
        p2, p3 = entity.dxf.defpoint2, entity.dxf.defpoint3
        dx, dy = abs(p3.x - p2.x), abs(p3.y - p2.y)
        if dx >= dy:
            start, end = (p2.x, d.y), (p3.x, d.y)
            tx, ty, rotation = (p2.x + p3.x) / 2, d.y, 0
        else:
            start, end = (d.x, p2.y), (d.x, p3.y)
            tx, ty, rotation = d.x, (p2.y + p3.y) / 2, 90
        ax.plot([start[0], end[0]], [start[1], end[1]], color="#D00000", linewidth=0.35)
        ax.text(
            tx,
            ty,
            f"{value:.0f}",
            color="#D00000",
            fontsize=4.6,
            rotation=rotation,
            ha="center",
            va="bottom",
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.2, "alpha": 0.85},
        )

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
