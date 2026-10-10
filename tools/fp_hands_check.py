"""Checks the first-person hands without Blender (player report 5, ADR-0061): solves every fp_*
action from game/data/config/viewmodel.json as the fp_arms bake does and reports each frame where
a finger or thumb joint bends past what a hand can do, neighbouring fingers pass through each other,
a fingertip comes within the lens's near zone, or the thumb is drawn too wide beside the fingers.
The bake runs the same check and fails on any of them; this is the quick way to try a pose.

  .tools/venv/bin/python tools/fp_hands_check.py [--only fp_lighter,fp_light] [--every 2] [--table]

Exit 1 on a violation. --table prints each action's range per joint (min..max over its frames).
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "assetgen" / "blender"))

from lib import char_fp as F, fp_anatomy as A  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="", help="comma-separated action names (fp_...) or prefixes")
    ap.add_argument("--every", type=int, default=1, help="measure every Nth frame (the solve still runs on all)")
    ap.add_argument("--table", action="store_true", help="print each action's joint ranges")
    a = ap.parse_args()
    only = tuple(x for x in a.only.split(",") if x)
    cfg = F.load_config()
    bad, summary = A.check(cfg, every=a.every, only=only)
    if a.table:
        for name, worst in summary.items():
            for sd in ("R", "L"):
                parts = []
                for k, (lo, hi) in worst.items():
                    if not k.startswith(sd + "."):
                        continue
                    if ".tip." in k:
                        parts.append(f"{k[2:]} {lo * 100:.0f}cm")
                    elif ".cross." in k:
                        parts.append(f"{k[2:]} {hi * 1000:+.0f}mm")
                    elif ".loom." in k:
                        parts.append(f"{k[2:]} {hi:.2f}x")
                    else:
                        parts.append(f"{k[2:]} {lo:.0f}..{hi:.0f}")
                print(f"{name} {sd}: " + ", ".join(parts))
    for line in A.summarize(bad, limit=400):
        print(line)
    print(f"[fp_hands_check] {len(summary)} actions, {len(bad)} frame violation(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
