#!/usr/bin/env python3
"""Find text and mtext entities across DXF model-space and block definitions."""

from __future__ import annotations

import re
import sys

import ezdxf


def plain(entity) -> str:
    if entity.dxftype() == "MTEXT":
        return entity.plain_text()
    return entity.dxf.text


def main() -> int:
    source, pattern = sys.argv[1], sys.argv[2]
    regex = re.compile(pattern)
    doc = ezdxf.readfile(source)
    for block in doc.blocks:
        for entity in block:
            if entity.dxftype() not in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                continue
            text = " ".join(plain(entity).split())
            if not regex.search(text):
                continue
            point = getattr(entity.dxf, "insert", None)
            coords = f"{point.x:.3f}\t{point.y:.3f}" if point else "\t"
            print(f"{block.name}\t{entity.dxf.layer}\t{coords}\t{text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
