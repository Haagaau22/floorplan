#!/usr/bin/env python3
"""Compact inspection of a DXF converted from the apartment DWG."""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import ezdxf


def entity_text(entity):
    kind = entity.dxftype()
    if kind == "TEXT":
        return entity.dxf.text
    if kind == "MTEXT":
        return entity.plain_text()
    if kind in {"ATTRIB", "ATTDEF"}:
        return entity.dxf.text
    return None


def main() -> int:
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    print(f"reading {source}", file=sys.stderr, flush=True)
    doc = ezdxf.readfile(source)
    print("loaded", file=sys.stderr, flush=True)

    result = {
        "dxfversion": doc.dxfversion,
        "insunits": doc.header.get("$INSUNITS"),
        "extmin": list(doc.header.get("$EXTMIN", ())),
        "extmax": list(doc.header.get("$EXTMAX", ())),
        "layers": [],
        "layouts": [],
        "blocks": [],
        "text_counts": [],
        "texts": [],
    }

    for layer in doc.layers:
        result["layers"].append({
            "name": layer.dxf.name,
            "on": layer.is_on(),
            "frozen": layer.is_frozen(),
            "color": layer.color,
        })

    all_texts = collections.Counter()
    for layout in doc.layouts:
        counts = collections.Counter(e.dxftype() for e in layout)
        layer_counts = collections.Counter(e.dxf.layer for e in layout)
        texts = []
        for entity in layout:
            value = entity_text(entity)
            if value:
                cleaned = " ".join(value.split())
                all_texts[cleaned] += 1
                if len(texts) < 3000:
                    texts.append({
                        "type": entity.dxftype(),
                        "layer": entity.dxf.layer,
                        "text": cleaned,
                        "insert": list(getattr(entity.dxf, "insert", ()))[:2],
                    })
        result["layouts"].append({
            "name": layout.name,
            "entity_count": len(layout),
            "entity_types": counts.most_common(),
            "layers": layer_counts.most_common(100),
            "texts": texts,
        })

    for block in doc.blocks:
        counts = collections.Counter(e.dxftype() for e in block)
        if len(block) or not block.name.startswith("*"):
            result["blocks"].append({
                "name": block.name,
                "entity_count": len(block),
                "entity_types": counts.most_common(),
            })

    result["blocks"].sort(key=lambda x: x["entity_count"], reverse=True)
    result["text_counts"] = all_texts.most_common(5000)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
