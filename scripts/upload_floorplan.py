#!/usr/bin/env python3
"""Upload one Floorplan JSON project with an HMAC-signed PUT request."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--base-url", default="https://floorplan.221231.xyz")
    parser.add_argument("--project-id", default="apartment")
    parser.add_argument("--secret-env", default="FLOORPLAN_WRITE_SECRET")
    args = parser.parse_args()

    secret = os.environ.get(args.secret_env)
    if not secret:
        raise SystemExit(f"missing environment variable: {args.secret_env}")
    body = args.source.read_bytes()
    payload = json.loads(body)
    if payload.get("project", {}).get("id") != args.project_id:
        raise SystemExit("JSON project id does not match --project-id")

    path = f"/api/projects/{args.project_id}"
    url = args.base_url.rstrip("/") + path
    if urlsplit(url).scheme != "https":
        raise SystemExit("uploads require an https URL")
    timestamp = str(int(time.time()))
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = f"PUT\n{path}\n{timestamp}\n{body_hash}".encode()
    signature = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()

    request = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "floorplan-agent/1.0 (+https://floorplan.221231.xyz)",
            "X-Floorplan-Timestamp": timestamp,
            "X-Floorplan-Signature": signature,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            print(response.read().decode())
    except urllib.error.HTTPError as error:
        print(error.read().decode())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
