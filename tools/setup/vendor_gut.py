#!/usr/bin/env python3
"""Vendor GUT (Godot Unit Test, MIT) into game/addons/gut at the version pinned in tools/versions.env.

GitHub release archives are not reachable from every build environment, so this pulls the
exact tagged files from the jsDelivr GitHub mirror (file list from data.jsdelivr.com).
The vendored copy is committed; re-run only when bumping GUT_VERSION.
Stdlib only (runs without the asset-pipeline venv).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]


def read_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (ROOT / "tools" / "versions.env").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v.strip().strip('"')
    return out


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hollowmere-vendor/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - retry any network error
            if attempt == 3:
                raise
            print(f"  retry {url}: {e}", file=sys.stderr)
    raise RuntimeError("unreachable")


def main() -> int:
    ver = read_versions()["GUT_VERSION"]
    listing = json.loads(fetch(f"https://data.jsdelivr.com/v1/packages/gh/bitwes/Gut@{ver}?structure=flat"))
    files = [f["name"] for f in listing["files"] if f["name"].startswith("/addons/gut/")]
    if not files:
        print("no addons/gut files found in listing", file=sys.stderr)
        return 1
    dest = ROOT / "game" / "addons" / "gut"
    if dest.exists():
        shutil.rmtree(dest)
    for name in files:
        rel = name[len("/addons/gut/"):]
        data = fetch(f"https://cdn.jsdelivr.net/gh/bitwes/Gut@{ver}{name}")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    if not (dest / "LICENSE.md").exists():
        print("GUT LICENSE.md missing from vendored files", file=sys.stderr)
        return 1
    (dest / "VENDORED_VERSION").write_text(f"GUT {ver} (via jsDelivr mirror of github.com/bitwes/Gut)\n")
    print(f"[gut] vendored {len(files)} files of GUT {ver} into {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
