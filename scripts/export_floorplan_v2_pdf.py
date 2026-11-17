#!/usr/bin/env python3
"""Export semantic floorplan JSON to a vector PDF."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from semantic_floorplan import load_project, opening_points


MM_TO_PT = 72 / 25.4


def export(source: Path, target: Path, level_id: str | None = None) -> None:
    data = load_project(source)
    level = next((item for item in data["levels"] if item["id"] == level_id), data["levels"][0])
    width, height = data["canvas"]["width"], data["canvas"]["height"]
    page_width, page_height = 420 * MM_TO_PT, 297 * MM_TO_PT
    margin = 15 * MM_TO_PT
    title_height = 18 * MM_TO_PT
    scale = min((page_width - margin * 2) / width, (page_height - margin * 2 - title_height) / height)
    offset_x = (page_width - width * scale) / 2
    offset_y = margin

    target.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(target), pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle(data["project"]["name"])
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        label_font = "STSong-Light"
    except Exception:
        label_font = "Helvetica"

    def point(value: list[float] | tuple[float, float]) -> tuple[float, float]:
        return offset_x + value[0] * scale, offset_y + (height - value[1]) * scale

    def line(start, end) -> None:
        x1, y1 = point(start)
        x2, y2 = point(end)
        pdf.line(x1, y1, x2, y2)

    pdf.setFillColor(HexColor("#fbfaf6"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    for space in level["spaces"]:
        boundary = space["boundary"]
        path = pdf.beginPath()
        x, y = point(boundary[0])
        path.moveTo(x, y)
        for value in boundary[1:]:
            x, y = point(value)
            path.lineTo(x, y)
        path.close()
        if space["kind"] == "excluded":
            pdf.setFillColor(HexColor("#e8e4dc"))
            pdf.setStrokeColor(HexColor("#8b857b"))
        else:
            pdf.setFillColor(HexColor("#f7f4ec"))
            pdf.setStrokeColor(Color(0, 0, 0, alpha=0))
        pdf.drawPath(path, fill=1, stroke=1)
        if space["kind"] == "excluded":
            pdf.saveState()
            pdf.clipPath(path, stroke=0, fill=0)
            pdf.setStrokeColor(HexColor("#aaa49a"))
            pdf.setLineWidth(0.35)
            step = 8 * MM_TO_PT
            for hatch_x in range(int(offset_x - page_height), int(offset_x + width * scale + page_height), int(step)):
                pdf.line(hatch_x, offset_y, hatch_x + height * scale, offset_y + height * scale)
            pdf.restoreState()

    pdf.setStrokeColor(HexColor("#18201f"))
    pdf.setLineCap(2)
    pdf.setLineJoin(0)
    for wall in level["walls"]:
        pdf.setLineWidth(wall["thickness"] * scale)
        for start, end in zip(wall["centerline"], wall["centerline"][1:]):
            line(start, end)

    walls = {item["id"]: item for item in level["walls"]}
    for opening in level["openings"]:
        wall = walls[opening["wallId"]]
        start, end = opening_points(wall, opening)
        pdf.setStrokeColor(HexColor("#fbfaf6"))
        pdf.setLineWidth((wall["thickness"] + 24) * scale)
        line(start, end)
        if opening["kind"] == "window":
            pdf.setStrokeColor(HexColor("#4d7775"))
            pdf.setLineWidth(max(0.8, 64 * scale))
            line(start, end)
        elif opening["kind"] == "door":
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            nx, ny = (-dy / length, dx / length) if length else (0, 0)
            leaf_end = (start[0] + nx * length, start[1] + ny * length)
            pdf.setStrokeColor(HexColor("#53605e"))
            pdf.setLineWidth(max(0.5, 20 * scale))
            line(start, leaf_end)

    pdf.setStrokeColor(HexColor("#687370"))
    pdf.setLineWidth(0.28)
    for detail in level.get("details", []):
        path = pdf.beginPath()
        x, y = point(detail["points"][0])
        path.moveTo(x, y)
        for value in detail["points"][1:]:
            x, y = point(value)
            path.lineTo(x, y)
        if detail["closed"]:
            path.close()
        pdf.drawPath(path, fill=0, stroke=1)

    templates = {item["id"]: item for item in data["templates"]}
    pdf.setStrokeColor(HexColor("#44514f"))
    pdf.setLineWidth(0.55)
    for instance in level["instances"]:
        template = templates[instance["templateId"]]
        px, py = instance["position"]
        anchor_x, anchor_y = template["anchor"]
        scale_x, scale_y = instance.get("scale", [1, 1])
        angle = math.radians(instance.get("rotation", 0))

        def transform(value: list[float]) -> tuple[float, float]:
            local_x = (value[0] - anchor_x) * scale_x
            local_y = (value[1] - anchor_y) * scale_y
            return px + local_x * math.cos(angle) - local_y * math.sin(angle), py + local_x * math.sin(angle) + local_y * math.cos(angle)

        for item in template["geometry"]["paths"]:
            path = pdf.beginPath()
            x, y = point(transform(item["points"][0]))
            path.moveTo(x, y)
            for value in item["points"][1:]:
                x, y = point(transform(value))
                path.lineTo(x, y)
            if item["closed"]:
                path.close()
            pdf.drawPath(path, fill=0, stroke=1)

    for space in level["spaces"]:
        if space.get("labelStyle") == "hidden":
            continue
        x, y = point(space["labelPosition"])
        label = space.get("number") or space["name"]
        is_room_tag = space.get("labelStyle") == "room-tag"
        baseline_y = y - (2.0 if is_room_tag else 2.2)
        pdf.setFont(label_font, 6.2 if is_room_tag else 6.5)
        if is_room_tag:
            pdf.setFillColor(white)
            for offset_x, offset_y in ((-.5, 0), (.5, 0), (0, -.5), (0, .5)):
                pdf.drawCentredString(x + offset_x, baseline_y + offset_y, label)
            pdf.setFillColor(HexColor("#173f3b"))
        else:
            pdf.setFillColor(HexColor("#514c45"))
        pdf.drawCentredString(x, baseline_y, label)

    pdf.setFillColor(HexColor("#173f3b"))
    pdf.setFont(label_font, 15)
    pdf.drawString(margin, page_height - margin - 14, data["project"]["name"])
    pdf.setFillColor(HexColor("#687370"))
    pdf.setFont(label_font, 8)
    pdf.drawRightString(page_width - margin, page_height - margin - 12, f"语义 JSON v{data['schemaVersion']} · 单位 mm")
    pdf.showPage()
    pdf.save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--level")
    args = parser.parse_args()
    export(args.source, args.target, args.level)
    print(f"wrote {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
