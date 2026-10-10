#!/usr/bin/env python3
"""Adds the right-hand misses fp_measure.gd measured (--fix --fix-out FILE) to viewmodel.json's
R.grip of each key (or hold pose), keeping the file's formatting (TD-294).

  python3 tools/fp_fix_grips.py FILE [--gain 1.0]

Then re-bake fp_arms (tools/build_assets.py --names model:characters/fp_arms) and measure again:
the pose solver moves grips too, so it may take two rounds to settle."""
from __future__ import annotations

import json
import pathlib
import sys

VM = pathlib.Path(__file__).resolve().parent.parent / "game" / "data" / "config" / "viewmodel.json"


def main() -> int:
    fixes = json.loads(pathlib.Path(sys.argv[1]).read_text())
    gain = float(sys.argv[sys.argv.index("--gain") + 1]) if "--gain" in sys.argv else 1.0
    data = json.loads(VM.read_text())
    n = 0
    for f in fixes:
        if "hold" in f:
            r = data["holds"][f["hold"]]["pose"]["R"]
        else:
            r = None
            for key in data["uses"][f["use"]]["keys"]:
                if int(key[0]) == int(f["frame"]) and isinstance(key[1].get("R"), dict):
                    r = key[1]["R"]
            if r is None:
                continue
        r["grip"] = [round(float(g) + gain * float(m), 3) for g, m in zip(r["grip"], f["miss"])]
        n += 1
    VM.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"fp_fix_grips: {n} grips moved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
