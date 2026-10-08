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
  .tools/venv/bin/python tools/fp_poses.py relax hold[,hold...]
      ADR-0060: turn and move each hold's own hands (its pose and guard; at most 40 degrees and
      6 cm) so both wrists rest inside `wrist.comfort` (a hand on the other's handle included),
      at the least change to where the tool points. Rewrites the hands' grip / dir / knuckles in
      viewmodel.json; check the renders (fp_dev_render.py, fp_preview.gd) before keeping it.

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


def _comfort_score(sol, hands) -> tuple[float, dict]:
    """Degrees outside the comfort range summed over both hands once solved (a hand turned back
    into it counts what it was turned), and each hand's wrist angles."""
    sol.reset()
    sol.clamped = {}
    prm = sol.solve(hands)
    total, angs = 0.0, {}
    for sd in ("R", "L"):
        A, Qh = sol._arm(sd, prm[f"{sd}.wrist"], prm[f"{sd}.pole"], prm[f"{sd}.Rh"])
        a = sol.rig.wrist_angles(sd, Qh)
        angs[sd] = a
        sol.relax(1.0)
        total += sol._over(*a) + sol.clamped.get(sd, 0.0)
    return total, angs


ROT_COST, CM_COST, ROT_MAX, MOVE_LIM = 0.25, 1.5, 40.0, 0.06


def relax(names: list[str]) -> None:
    cfg, _rig_, sol = _rig()
    data = json.loads(VM.read_text())
    for name in names:
        h = data["holds"][name]
        for variant in ("pose", "guard"):
            if variant not in h:
                continue
            spec = h["pose"] if variant == "pose" else F.merge_pose(h["pose"], h["guard"])
            own = [sd for sd in ("R", "L") if sd in spec and "on" not in spec[sd] and "wrist" not in spec[sd]]
            if not own:
                continue

            def hands_for(x):
                out = {}
                for i, sd in enumerate(own):
                    rot, mv = x[i * 6:i * 6 + 3], x[i * 6 + 3:i * 6 + 6]
                    hd = F.pose_hands(F.with_item(spec, h))[sd]
                    out[sd] = F.Hand(hd.g + F.g2b(mv), F.euler_g(rot) @ hd.F, hd.elbow, hd.sc, item=hd.item)
                for sd in ("R", "L"):
                    if sd not in out:
                        out[sd] = F.pose_hands(F.with_item(spec, h))[sd]
                out["_relax"] = 1.0
                return out

            def score(x):
                if any(abs(v) > ROT_MAX for i, v in enumerate(x) if i % 6 < 3):
                    return 1e9
                if any(np.linalg.norm(x[i * 6 + 3:i * 6 + 6]) > MOVE_LIM for i in range(len(own))):
                    return 1e9
                c, _ = _comfort_score(sol, hands_for(x))
                rot = sum(np.linalg.norm(x[i * 6:i * 6 + 3]) for i in range(len(own)))
                mv = sum(np.linalg.norm(x[i * 6 + 3:i * 6 + 6]) for i in range(len(own)))
                return c + ROT_COST * rot + CM_COST * 100 * mv

            x = np.zeros(6 * len(own))
            best = score(x)
            start = best
            for step in (16.0, 8.0, 4.0, 2.0):
                improved = True
                while improved:
                    improved = False
                    for k in range(len(x)):
                        for sg in (-1, 1):
                            y = x.copy()
                            y[k] += sg * (step if k % 6 < 3 else step / 400.0)
                            sc = score(y)
                            if sc < best - 0.25:
                                x, best, improved = y, sc, True
            hands = hands_for(x)
            c, angs = _comfort_score(sol, hands)
            target = h[variant]
            for i, sd in enumerate(own):
                hd = hands[sd]
                d, k = F.g2b(hd.F[:, 2]), F.g2b(hd.F[:, 0])
                t = target.get(sd) if variant == "guard" else target[sd]
                if t is None:
                    continue
                t.pop("back", None)
                t["grip"] = [round(float(v), 3) for v in F.g2b(hd.g)]
                t["dir"] = [round(float(v), 3) for v in d]
                t["knuckles"] = [round(float(v), 3) for v in k]
            print(f"{name}.{variant}: {start:.0f} -> {best:.0f} (outside comfort {c:.0f} deg; " +
                  ", ".join(f"{sd} f{a[0]:+.0f} u{a[1]:+.0f} r{a[2]:+.0f}" for sd, a in angs.items()) +
                  f"; turned {[round(float(v)) for v in x]})", flush=True)
    VM.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("report", "tune", "relax"):
        raise SystemExit(__doc__)
    arg = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    if sys.argv[1] == "report":
        report(arg)
    elif sys.argv[1] == "relax":
        relax(arg)
    else:
        tune(arg)
