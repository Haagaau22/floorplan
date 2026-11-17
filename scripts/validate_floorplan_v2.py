#!/usr/bin/env python3
"""Validate a semantic floorplan JSON file and all cross references."""

from __future__ import annotations

import argparse
from pathlib import Path

from semantic_floorplan import load_project, validate_project


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).parents[1] / "schema/floorplan-v2.schema.json")
    args = parser.parse_args()
    data = load_project(args.source)
    errors = validate_project(data, args.schema)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    level_count = len(data["levels"])
    template_count = len(data["templates"])
    print(f"valid semantic floorplan: {args.source} ({level_count} level, {template_count} template)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
