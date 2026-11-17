#!/usr/bin/env python3
"""Migrate the apartment CAD regression fixture into self-contained semantic JSON v2.

The CAD is used only by this migration command. Runtime rendering and exports use
the generated JSON, including reusable block definitions and their instances.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import ezdxf
from ezdxf import disassemble, path

from export_floorplan import DEFAULT_BOUNDS, quick_entity_overlap


def integer(value: float) -> int:
    return int(round(float(value)))


def safe_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "unnamed"


def flattened(entity, tolerance: float = 5.0) -> list[dict]:
    try:
        source_path = path.make_path(entity)
    except (TypeError, ValueError, AttributeError, ezdxf.DXFError):
        return []
    candidates = source_path.sub_paths() if source_path.has_sub_paths else (source_path,)
    results: list[dict] = []
    for candidate in candidates:
        try:
            vertices = list(candidate.flattening(distance=tolerance, segments=4))
        except (TypeError, ValueError, AttributeError):
            continue
        if len(vertices) < 2:
            continue
        results.append({
            "points": [[integer(vertex.x), integer(-vertex.y)] for vertex in vertices],
            "closed": bool(getattr(candidate, "is_closed", False)),
            "role": "outline",
        })
    return results


def localize(points: list[list[int]], xmin: float, ymax: float) -> list[list[int]]:
    # `flattened` has already inverted Y, hence ymax + inverted_y.
    return [[integer(point[0] - xmin), integer(ymax + point[1])] for point in points]


def build_template(document, block_name: str, template_id: str) -> dict | None:
    block = document.blocks.get(block_name)
    paths: list[dict] = []
    for leaf in disassemble.recursive_decompose(block):
        if leaf.dxftype() in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
            continue
        paths.extend(flattened(leaf))
    if not paths:
        return None
    xs = [point[0] for item in paths for point in item["points"]]
    ys = [point[1] for item in paths for point in item["points"]]
    base = block.block.dxf.base_point
    return {
        "id": template_id,
        "name": f"CAD 项目块 {block_name}",
        "category": "fixture",
        "size": {"width": max(1, max(xs) - min(xs)), "depth": max(1, max(ys) - min(ys))},
        "anchor": [integer(base.x), integer(-base.y)],
        "geometry": {"paths": paths},
        "source": {"kind": "project", "name": block_name},
    }


def migrate(args: argparse.Namespace) -> dict:
    xmin, ymin, xmax, ymax = tuple(args.bounds)
    document = ezdxf.readfile(args.source)
    modelspace = document.modelspace()
    source_entities = [entity for entity in modelspace if quick_entity_overlap(entity, tuple(args.bounds))]

    insert_entities = [entity for entity in source_entities if entity.dxftype() == "INSERT"]
    block_names = sorted({entity.dxf.name for entity in insert_entities})
    template_ids = {name: f"cad-{index:02d}-{safe_id(name)}" for index, name in enumerate(block_names, start=1)}
    templates: list[dict] = []
    valid_templates: set[str] = set()
    for block_name in block_names:
        template = build_template(document, block_name, template_ids[block_name])
        if template is not None:
            templates.append(template)
            valid_templates.add(block_name)

    instances = []
    for index, entity in enumerate(insert_entities, start=1):
        if entity.dxf.name not in valid_templates:
            continue
        insert = entity.dxf.insert
        instances.append({
            "id": f"cad-instance-{index:03d}",
            "templateId": template_ids[entity.dxf.name],
            "position": [integer(insert.x - xmin), integer(ymax - insert.y)],
            "rotation": round(-float(entity.dxf.rotation), 6),
            "scale": [round(float(entity.dxf.xscale), 6), round(float(entity.dxf.yscale), 6)],
        })

    details: list[dict] = []
    for entity in source_entities:
        if entity.dxftype() in {"INSERT", "TEXT", "MTEXT"}:
            continue
        try:
            leaves = disassemble.recursive_decompose((entity,))
            for leaf in leaves:
                if leaf.dxftype() in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                    continue
                for item in flattened(leaf):
                    item["points"] = localize(item["points"], xmin, ymax)
                    item.pop("role", None)
                    details.append(item)
        except (TypeError, ValueError, AttributeError, ezdxf.DXFError):
            continue

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    spaces = []
    for space in baseline["spaces"]:
        number = space["label"]
        spaces.append({
            "id": f"room-{number}",
            "kind": "apartment",
            "name": f"{number}号房",
            "number": number,
            "boundary": [[integer(x - xmin), integer(ymax - y)] for x, y in space["selectionBoundary"]],
            "labelPosition": [integer(space["labelPosition"][0] - xmin), integer(ymax - space["labelPosition"][1])],
            "labelStyle": "room-tag",
            "boundaryStatus": "estimated",
        })

    # Non-project land immediately left of the corridor beside room 27. This
    # hand-audited polygon follows the visible hatched outline in the CAD fixture.
    excluded_cad = [
        [1_590_200, 636_000],
        [1_601_200, 636_000],
        [1_601_200, 625_600],
        [1_603_000, 625_600],
        [1_603_000, 622_500],
        [1_596_800, 622_500],
        [1_596_800, 625_000],
        [1_590_200, 625_000]
    ]
    spaces.append({
        "id": "excluded-left-of-room-27-corridor",
        "kind": "excluded",
        "name": "非项目区域",
        "boundary": [[integer(x - xmin), integer(ymax - y)] for x, y in excluded_cad],
        "labelPosition": [integer(1_596_500 - xmin), integer(ymax - 630_000)],
        "labelStyle": "area-name",
        "boundaryStatus": "estimated",
    })

    return {
        "schemaVersion": "2.0.0",
        "project": {
            "id": "apartment",
            "name": "公寓户型图",
            "status": "review",
            "source": "CAD regression fixture migrated to semantic JSON",
            "notes": "CAD 仅用于回归迁移；运行时以本 JSON 为唯一数据源。旧图结构线暂存为 details，家具与设备已转换为模板实例。",
        },
        "coordinateSystem": {"units": "mm", "xAxis": "right", "yAxis": "down"},
        "canvas": {"width": integer(xmax - xmin), "height": integer(ymax - ymin)},
        "templates": templates,
        "levels": [{
            "id": "level-01",
            "name": "标准层",
            "elevation": 0,
            "walls": [],
            "openings": [],
            "spaces": spaces,
            "instances": instances,
            "details": details,
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--baseline", type=Path, default=Path("data/projects/apartment/floorplan.json"))
    parser.add_argument("--bounds", type=float, nargs=4, default=DEFAULT_BOUNDS, metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    args = parser.parse_args()
    data = migrate(args)
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(
        f"wrote {args.target}: {len(data['templates'])} templates, "
        f"{len(data['levels'][0]['instances'])} instances, {len(data['levels'][0]['details'])} details"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
