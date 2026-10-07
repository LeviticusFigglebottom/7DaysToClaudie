#!/usr/bin/env python3
"""First-person hold poses (ADR-0045): what the arms' pose solver does with viewmodel.json, without
Blender (numpy only, seconds per action).

  .tools/venv/bin/python tools/fp_poses.py report [action,...]
      per action and hand: the worst wrist correction (degrees turned back into the wrist's
      range) and grip move (cm), and the frames that needed one
  .tools/venv/bin/python tools/fp_poses.py tune attack[,attack...]
      re-place each key's grip (S.move, 2 cm steps, within 18 cm) where an arm can deliver the
      key's tool angle: the smallest correction plus 1.5 degrees per cm moved. Rewrites
      viewmodel.json; review the diff and the renders (fp_preview.gd) before keeping it.

A hold whose idle needs much correction is asking for a wrist nobody has: rewrite it toward what
the solver reaches (the report says which) rather than widening `wrist`.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "assetgen" / "blender"))
from lib import char_fp as F  # noqa: E402

VM = ROOT / "game" / "data" / "config" / "viewmodel.json"
MOVE_COST = 1.5          # degrees of correction a centimetre of grip move is worth
STEP, REACH = 0.02, 0.18


def _rig():
    cfg = F.load_config()
    sk = F.FPSkeleton(F.fp_joints({}), {}, bones=F.FP_BONES)
    rig = F.FPRig(sk)
    return cfg, rig, F.PoseSolver(rig, cfg.get("wrist"))


def report(only: list[str]) -> None:
    cfg, _rig_, sol = _rig()
    for name, _n, _loop, frames in F.fp_actions(cfg):
        if only and name not in only:
            continue
        sol.reset()
        bad = []
        for i, hands in enumerate(frames):
            sol.clamped, sol.moved = {}, {}
            sol.solve(hands)
            t = {sd: sol.clamped.get(sd, 0.0) for sd in ("R", "L")}
            if max(t.values()) >= 5.0:
                bad.append(f"{i}:{t['R']:.0f}/{t['L']:.0f}")
        sol.reset()
        worst = {"R": 0.0, "L": 0.0}
        moved = {"R": 0.0, "L": 0.0}
        for hands in frames:
            sol.solve(hands)
        for sd in ("R", "L"):
            worst[sd] = sol.clamped.get(sd, 0.0)
            moved[sd] = sol.moved.get(sd, 0.0) * 100
        print(f"{name:24s} R {worst['R']:4.0f}deg {moved['R']:3.0f}cm   L {worst['L']:4.0f}deg {moved['L']:3.0f}cm"
              + (f"   frames {' '.join(bad)}" if bad else ""))


def tune(names: list[str]) -> None:
    cfg, _rig_, sol = _rig()
    sol.MOVE_MAX = 0.0                    # the data carries the move
    data = json.loads(VM.read_text())

    def turned_at(a: dict, fi: int, sd: str) -> float:
        pose = data["holds"][a["hold"]]["pose"]
        if "pose" in a:
            pose = F.merge_pose(pose, a["pose"])
        frames = F._keyed(pose, a["keys"], int(a["frames"]))
        sol.reset()
        sol.solve(frames[fi])
        return sol.clamped.get(sd, 0.0)

    for name in names:
        a = data.get("attacks", {}).get(name) or data.get("uses", {}).get(name)
        if a is None:
            raise SystemExit(f"no attack or use '{name}'")
        for key in a["keys"]:
            ch = key[1]
            for sd in ("R", "L"):
                if not isinstance(ch, dict) or not ch or isinstance(ch.get(sd), dict):
                    continue
                if f"{sd}.rot" not in ch and f"{sd}.move" not in ch:
                    continue
                fi = int(key[0])
                base = list(ch.get(f"{sd}.move", [0.0, 0.0, 0.0]))
                t0 = turned_at(a, fi, sd)
                if t0 < 8.0:
                    continue
                best, score = [0.0, 0.0, 0.0], t0
                improved = True
                while improved:
                    improved = False
                    for ax in range(3):
                        for st in (-STEP, STEP):
                            d = list(best)
                            d[ax] = round(d[ax] + st, 3)
                            if float(np.linalg.norm(d)) > REACH:
                                continue
                            ch[f"{sd}.move"] = [round(b + x, 3) for b, x in zip(base, d)]
                            sc = turned_at(a, fi, sd) + MOVE_COST * 100 * float(np.linalg.norm(d))
                            if sc < score - 0.5:
                                best, score, improved = d, sc, True
                ch[f"{sd}.move"] = [round(b + x, 3) for b, x in zip(base, best)]
                print(f"{name} frame {fi} {sd}: corrected {t0:.0f} -> {turned_at(a, fi, sd):.0f} deg, "
                      f"move {base} -> {ch[f'{sd}.move']}", flush=True)
    VM.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("report", "tune"):
        raise SystemExit(__doc__)
    arg = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    if sys.argv[1] == "report":
        report(arg)
    else:
        tune(arg)
