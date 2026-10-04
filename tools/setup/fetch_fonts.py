#!/usr/bin/env python3
"""Fetch the open-licensed fonts used by the game into game/assets/fonts (committed).

Fonts are the only third-party *content* allowed (see THIRD_PARTY.md). Each file is
pinned by SHA-256; a mismatch means upstream changed and must be reviewed by a human.
Stdlib only.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEST = ROOT / "game" / "assets" / "fonts"
BASE = "https://raw.githubusercontent.com/google/fonts/main/"

# (repo path, local name, sha256 or None to print it)
FONTS: list[tuple[str, str, str | None]] = [
    ("ofl/ibmplexmono/IBMPlexMono-Regular.ttf", "IBMPlexMono-Regular.ttf", None),
    ("ofl/ibmplexmono/IBMPlexMono-Bold.ttf", "IBMPlexMono-Bold.ttf", None),
    ("ofl/ibmplexmono/OFL.txt", "IBMPlexMono-OFL.txt", None),
    ("apache/specialelite/SpecialElite-Regular.ttf", "SpecialElite-Regular.ttf", None),
    ("apache/specialelite/LICENSE.txt", "SpecialElite-LICENSE.txt", None),
    ("ofl/caveat/Caveat%5Bwght%5D.ttf", "Caveat-Variable.ttf", None),
    ("ofl/caveat/OFL.txt", "Caveat-OFL.txt", None),
    ("ofl/ebgaramond/EBGaramond%5Bwght%5D.ttf", "EBGaramond-Variable.ttf", None),
    ("ofl/ebgaramond/OFL.txt", "EBGaramond-OFL.txt", None),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hollowmere-fonts/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    pins: dict[str, str] = {}
    pin_file = DEST / "SHA256SUMS"
    if pin_file.exists():
        for line in pin_file.read_text().splitlines():
            h, name = line.split(maxsplit=1)
            pins[name.strip()] = h
    bad = 0
    lines = []
    for repo_path, name, _ in FONTS:
        data = fetch(BASE + repo_path)
        digest = hashlib.sha256(data).hexdigest()
        if name in pins and pins[name] != digest:
            print(f"[fonts] HASH CHANGED upstream for {name}: {pins[name]} -> {digest}", file=sys.stderr)
            bad += 1
            continue
        (DEST / name).write_bytes(data)
        lines.append(f"{digest}  {name}")
        print(f"[fonts] {name} ({len(data)} bytes)")
    if not bad:
        pin_file.write_text("\n".join(lines) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
