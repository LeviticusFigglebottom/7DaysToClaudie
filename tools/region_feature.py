#!/usr/bin/env python3
"""Add, replace, remove or list features of a handcrafted region (world/main_map/regions/*/region.json).

Several authors (or agents) placing POIs at once would clobber each other's edits to the one
region file, so every change here is a read-modify-write under an exclusive lock on
build/.region.lock. Features are matched by their "id"; the file keeps json.dump(indent=2) layout.

    python3 tools/region_feature.py d6_larch_hollow list
    python3 tools/region_feature.py d6_larch_hollow upsert '{"type": "poi", "id": "x", "poi": "x", "origin": [0, 0], "rotation": 0}'
    python3 tools/region_feature.py d6_larch_hollow remove x
"""
from __future__ import annotations

import fcntl
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ROOT / "game" / "world" / "main_map" / "regions"


def _region_file(name: str) -> Path:
    p = REGIONS / name / "region.json"
    if not p.exists():
        matches = sorted(REGIONS.glob(f"*{name}*/region.json"))
        if len(matches) != 1:
            sys.exit(f"region '{name}' not found (have: {', '.join(d.name for d in REGIONS.iterdir())})")
        p = matches[0]
    return p


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("list", "upsert", "remove"):
        print(__doc__)
        return 2
    path = _region_file(argv[0])
    lock_path = ROOT / "build" / ".region.lock"
    lock_path.parent.mkdir(exist_ok=True)
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text())
        feats: list = data["features"]
        if argv[1] == "list":
            for f in feats:
                where = f.get("origin") or f.get("pos") or f.get("circle") or f.get("ellipse") or ""
                print(f"{f.get('type', '?'):10} {f.get('id', '-'):28} {where}")
            return 0
        if argv[1] == "upsert":
            feat = json.loads(argv[2])
            if not feat.get("id") or not feat.get("type"):
                sys.exit("a feature needs an 'id' and a 'type'")
            for i, f in enumerate(feats):
                if f.get("id") == feat["id"]:
                    feats[i] = feat
                    break
            else:
                feats.append(feat)
        else:
            before = len(feats)
            feats[:] = [f for f in feats if f.get("id") != argv[2]]
            if len(feats) == before:
                sys.exit(f"no feature with id '{argv[2]}'")
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        tmp.replace(path)
        print(f"{argv[1]} ok: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
