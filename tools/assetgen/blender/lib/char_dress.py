"""Clothing, boots, hair, wounds and Bloom growth for Hollowed bodies (all SDF, driven by the
skeleton so every garment fits every body).

Garments are callables g(P, d_base) -> (d, label): an offset of the smoothed cloth base body,
clipped to the garment's region (hem / neckline / sleeves / legs), with folds, ragged edges and
tears. Union with the skin happens in BodyModel._add_layers.
"""
from __future__ import annotations

import math

import numpy as np

from . import char_body as B
from . import char_sdf as S
from .char_body import _n, smoothstep
from .char_skel import rot_axis


# --------------------------------------------------------------------------------------------
# Body-relative measures (vectorized)
# --------------------------------------------------------------------------------------------

class Measures:
    def __init__(self, model):
        self.m = model
        sk = model.skel
        self.pel = sk.head["hips"].copy()
        self.neck0 = sk.head["neck"].copy()
        self.up = _n(self.neck0 - self.pel)
        self.arm_pts = {s: [sk.j[f"shoulder.{s}"], sk.j[f"elbow.{s}"], sk.j[f"wrist.{s}"], sk.j[f"hand_tip.{s}"]]
                        for s in ("L", "R")}
        self.leg_pts = {s: [sk.j[f"hip.{s}"], sk.j[f"knee.{s}"], sk.j[f"ankle.{s}"]] for s in ("L", "R")}

    def h(self, P):
        """Height along the trunk axis above the pelvis joint (m)."""
        return (P - self.pel) @ self.up

    @staticmethod
    def arc(P, pts):
        """Arc length of the closest point on a polyline + distance to it."""
        best_d = np.full(len(P), 1e9)
        best_s = np.zeros(len(P))
        acc = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            ab = b - a
            L2 = float(ab @ ab)
            t = np.clip(((P - a) @ ab) / L2, 0.0, 1.0)
            q = a + t[:, None] * ab
            d = np.sqrt(((P - q) ** 2).sum(-1))
            better = d < best_d
            best_d = np.where(better, d, best_d)
            best_s = np.where(better, acc + t * math.sqrt(L2), best_s)
            acc += math.sqrt(L2)
        return best_s, best_d

    def arm_arc(self, P, side):
        """Arc length along the arm from the shoulder joint; negative-ish inside the torso."""
        s, d = self.arc(P, self.arm_pts[side])
        a0 = self.arm_pts[side][0]
        ax = _n(self.arm_pts[side][1] - a0)
        before = (P - a0) @ ax
        return np.where(before < 0, before, s), d

    def leg_arc(self, P, side):
        s, d = self.arc(P, self.leg_pts[side])
        return s, d

    def in_arm(self, P, side):
        """> 0 inside the arm volume (past the shoulder cut, near the arm axis). The hand counts out
        to 15 cm from the wrist-to-fingertip line: a spread thumb or clawed fingers reach past the
        arm's 10 cm tube, and a thumb counted as "below the waist" came out in denim."""
        m = self.m
        c, n = m.cuts[f"shoulder.{side}"]
        _, d = self.arc(P, self.arm_pts[side])
        _, dh = self.arc(P, self.arm_pts[side][2:])
        return np.minimum((P - c) @ n + 0.015 * m.s, np.maximum(0.10 * m.s - d, 0.15 * m.s - dh))

    def on_foot(self, P, side):
        """> 0 on the foot below the ankle (trousers stop at the ankle; bare feet stay bare)."""
        sk, s = self.m.skel, self.m.s
        _, fd = self.arc(P, [sk.j[f"heel.{side}"], sk.j[f"ball.{side}"], sk.j[f"toe_tip.{side}"]])
        return np.minimum(0.07 * s - fd, (sk.j[f"ankle.{side}"][2] + 0.015 * s) - P[:, 2])


def add_boot(model, side: str, spec: dict):
    s = model.s
    sx = 1.0 if side == "L" else -1.0
    sk = model.skel
    j = sk.j
    ank = j[f"ankle.{side}"]
    fwd, up, out = model.foot_frame(side, sx)
    R = np.stack([out, up, fwd], 1)
    g0 = np.array([ank[0], ank[1], 0.0])
    sh = model.leg[side]["sh"]
    height = float(spec.get("height", 0.15)) * s
    prog = model.boots

    def F(f, u, o=0.0):
        return g0 + fwd * (f * s) + up * (u * s) + out * (o * s)
    # sole
    prog.box(F(0.040, 0.013), np.array([0.050, 0.013, 0.150]) * s, R=R, rounding=0.010 * s, k=0.0, label=B.L_BOOT)
    # heel block
    prog.box(F(-0.050, 0.016), np.array([0.044, 0.016, 0.042]) * s, R=R, rounding=0.008 * s, k=0.004 * s, label=B.L_BOOT)
    # upper over the foot: heel cup + vamp + toe box
    prog.ellipsoid(F(-0.042, 0.055), np.array([0.044, 0.050, 0.050]) * s, R=R, k=0.02 * s, label=B.L_BOOT)
    prog.cone(F(-0.020, 0.060), F(0.110, 0.034, -0.002), 0.046 * s, 0.038 * s, k=0.03 * s, label=B.L_BOOT,
              squash=0.78, up_hint=up)
    prog.ellipsoid(F(0.125, 0.036, -0.003), np.array([0.045, 0.034, 0.055]) * s, R=R, k=0.02 * s, label=B.L_BOOT)
    # shaft around the ankle / lower shin
    top = ank - sh.axis * (height - 0.06 * s)
    prog.cone(F(-0.012, 0.05), top, 0.050 * s, 0.047 * s, k=0.025 * s, label=B.L_BOOT, squash=0.92, up_hint=fwd)
    # padded collar
    prog.cone(top - sh.axis * 0.004 * s, top + sh.axis * 0.006 * s, 0.050 * s, 0.049 * s, k=0.006 * s, label=B.L_BOOT)
    # lace ridge
    prog.capsule(F(0.030, 0.085), top + sh.fwd * 0.040 * s - sh.axis * 0.01 * s, 0.009 * s, k=0.012 * s, label=B.L_BOOT)


def add_hair(model, spec: dict, rng):
    """Patchy hair cap (+ optional stringy locks) owned by the head segment."""
    style = spec.get("style", "short")
    if style == "none":
        return
    s = model.s
    R = model.hR
    prog = model.hair
    thick = {"short": 0.0045, "medium": 0.0075, "long": 0.009, "balding": 0.0035, "stubble": 0.0030}.get(style, 0.005)
    hc = model.HP(0, 0.035, -0.012)
    # the cap follows the skull's own dials (TD-192 face variants), or it sinks in or floats
    fw = model.face("skull_w") if hasattr(model, "face") else 0.0
    fl_ = model.face("skull_len") if hasattr(model, "face") else 0.0
    radii = np.array([0.074 * (1 + 0.06 * fw), 0.088 * (1 + 0.07 * fl_), 0.096]) * s * float(model.p.get("head_scale", 1.0))
    # A Hollowed's hair is matted, thinned and torn (TD-192: it read as a smooth helmet): a raggeder
    # hairline, deeper hanks and tufts standing off the scalp. The living keep theirs groomed.
    rough = 1.0 if model.p.get("face_vary") else 0.0
    Rl = R @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
    line = float(spec.get("hairline", 0.055))        # front hairline height (head-local y)
    bald = float(spec.get("bald", 0.0))
    patchy = float(spec.get("patchy", 0.35))
    nz = model.noise
    hcen = model.hc

    def cap(P):
        d = S.sd_ellipsoid(P, hc, radii + thick * s, Rl)
        q = (P - hcen) @ R / s                        # (left, up, front)
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        # hairline: front edge high, sides above the ears, low nape
        edge_y = np.where(z > 0, line - 0.30 * np.maximum(0.05 - np.abs(x), 0) * 0.0 + 0.0 * z,
                          line - 0.075 * np.clip(-z / 0.09, 0, 1) - 0.035)
        edge_y = edge_y - 0.045 * np.clip((np.abs(x) - 0.03) / 0.05, 0, 1) * (z > -0.02)
        reg = (edge_y + nz.noise(P, 40.0) * (0.006 + 0.006 * rough) + nz.noise(P, 11.0) * 0.008 * rough) - y
        # balding crown / missing patches
        crown = bald * 0.06 - np.sqrt(x * x + (z + 0.01) ** 2 + np.maximum(0.11 - y, 0) ** 2 * 4) + nz.noise(P, 18.0) * 0.01
        patches = nz.fbm(P, 14.0, 2) - (0.75 - 0.6 * patchy)
        reg = np.maximum(reg, np.maximum(crown, patches * 0.03))
        # greasy, matted hanks (the fine strands come from the texture): clumps a few millimetres
        # proud, stretched along the way the hair lies
        lie = P + np.outer(nz.noise(P, 6.0), R[:, 1]) * 0.01 * s
        d = d - np.maximum(nz.fbm(lie * np.array([1.0, 1.0, 1.6]), 24.0, 3) + 0.15, 0) * (0.0032 + 0.0030 * rough) * s
        # matted ridges running down the way the hair lies, and gaps between them
        if rough > 0.0:
            ridge = np.abs(np.sin(((P - hcen) @ R[:, 0]) / s * 140.0 + nz.noise(P, 9.0) * 3.0))
            d = d + (ridge - 0.55) * 0.0022 * s
        return np.maximum(d, reg * s)

    lo = hc - radii - 0.03 * s
    hi = hc + radii + 0.03 * s
    prog.union(cap, lo, hi, k=0.0, label=B.L_HAIR)
    if rough > 0.0 and style not in ("stubble", "none"):
        # stray tufts lifting off the crown and the back, a few centimetres each
        for i in range(int(spec.get("tufts", 9))):
            ang = rng.uniform(-math.pi, math.pi)
            up_k = rng.uniform(0.35, 0.95)
            u = R @ np.array([math.sin(ang) * math.sqrt(1 - up_k * up_k), up_k, math.cos(ang) * math.sqrt(1 - up_k * up_k)])
            root = hc + u * (np.min(radii) + 0.002 * s)
            d = _n(u * 0.6 + R @ np.array([0.0, -0.3, -0.6]) + rng.normal(0, 0.25, 3))
            ln = rng.uniform(0.018, 0.045) * s
            prog.capsule(root, root + d * ln, rng.uniform(0.0022, 0.0034) * s, k=0.003 * s, label=B.L_HAIR)
    if style in ("long", "medium"):
        n = int(spec.get("locks", 12 if style == "long" else 7))
        length = float(spec.get("length", 0.16 if style == "long" else 0.08)) * s
        for i in range(n):
            ang = rng.uniform(math.radians(70), math.radians(290))      # around the back and sides
            ang *= 1 if rng.random() < 0.5 else -1
            dirn = R @ np.array([math.sin(ang), 0.0, math.cos(ang)])
            root = hc + R @ np.array([math.sin(ang) * 0.070, rng.uniform(-0.01, 0.05), math.cos(ang) * 0.085]) * s
            pts = [root]
            d = _n(dirn * 0.4 - R[:, 1])
            for k in range(4):
                d = _n(d + rng.normal(0, 0.15, 3) - R[:, 1] * 0.5)
                pts.append(pts[-1] + d * length / 4)
            for a, bpt in zip(pts[:-1], pts[1:]):
                prog.capsule(a, bpt, rng.uniform(0.004, 0.0065) * s, k=0.006 * s, label=B.L_HAIR)


def add_headgear(model, spec: dict):
    """Hats and head dressings over the hair, owned by the head segment (ADR-0028): a hard hat
    (dome, brim, ridge), a baseball cap, a knit beanie, or a gauze head bandage."""
    kind = spec.get("type", "")
    if not kind:
        return
    s = model.s
    R = model.hR
    Rl = R @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])     # radii (left, front, up)
    hs = float(model.p.get("head_scale", 1.0))
    c = model.HP(0, 0.035, -0.012)
    radii = np.array([0.072, 0.095, 0.087]) * s * hs
    up, front = R[:, 1], R[:, 2]
    tilt = math.radians(float(spec.get("tilt", 0.0)))         # pushed back (+) / forward (-)
    Rt = rot_axis(R[:, 0], tilt) @ Rl
    prog = model.hair
    lo, hi = c - 0.2 * s, c + 0.2 * s
    if kind == "hardhat":
        lab = B.L_HARDHAT
        brim_y = 0.028 * s

        def dome(P):
            q = (P - c) @ Rt
            d = S.sd_ellipsoid(P, c + up * 0.012 * s, radii + np.array([0.019, 0.021, 0.017]) * s, Rt)
            return np.maximum(d, brim_y - q[:, 2])
        prog.union(dome, lo, hi, k=0.0, label=lab)
        # brim: wider at the front (the peak), flattened
        bc = c + Rt @ np.array([0.0, 0.018, 0.030]) * s
        prog.ellipsoid(bc, np.array([0.100, 0.132, 0.0045]) * s * hs, R=Rt, k=0.006 * s, label=lab)
        # the ridge along the crown
        top = c + Rt @ np.array([0.0, 0.0, 0.110]) * s
        prog.capsule(top + Rt @ np.array([0.0, 0.075, -0.030]) * s, top + Rt @ np.array([0.0, -0.075, -0.030]) * s,
                     0.0075 * s, k=0.010 * s, label=lab)
    elif kind == "cap":
        lab = B.L_CAP

        def crown(P):
            q = (P - c) @ Rt
            d = S.sd_ellipsoid(P, c + up * 0.006 * s, radii + np.array([0.008, 0.008, 0.008]) * s, Rt)
            return np.maximum(d, 0.030 * s - q[:, 2] - 0.012 * s * np.clip(q[:, 1] / (0.09 * s), 0, 1))
        prog.union(crown, lo, hi, k=0.0, label=lab)
        bill_R = rot_axis(R[:, 0], math.radians(14)) @ Rt
        prog.ellipsoid(c + Rt @ np.array([0.0, 0.112, 0.024]) * s, np.array([0.062, 0.060, 0.0045]) * s, R=bill_R,
                       k=0.004 * s, label=lab)
        prog.sphere(c + Rt @ np.array([0.0, -0.004, 0.103]) * s, 0.006 * s, k=0.003 * s, label=lab)
    elif kind == "beanie":
        lab = B.L_KNIT

        def knit(P):
            q = (P - c) @ Rt
            d = S.sd_ellipsoid(P, c + up * 0.004 * s, radii + np.array([0.010, 0.010, 0.012]) * s, Rt)
            return np.maximum(d, 0.004 * s - q[:, 2])
        prog.union(knit, lo, hi, k=0.0, label=lab)
        # the turned-up rim
        def rim(P):
            q = (P - c) @ Rt
            d = S.sd_ellipsoid(P, c, radii + np.array([0.016, 0.016, 0.0]) * s, Rt)
            return np.maximum(np.abs(d) - 0.006 * s, np.abs(q[:, 2] - 0.012 * s) - 0.014 * s)
        prog.union(rim, lo, hi, k=0.004 * s, label=lab)
    elif kind == "bandage":
        lab = B.L_SHIRT
        y0 = float(spec.get("height", 0.045)) * s

        def gauze(P):
            q = (P - c) @ Rl
            d = S.sd_ellipsoid(P, c, radii + np.array([0.006, 0.006, 0.006]) * s, Rl)
            wrap = np.abs(q[:, 2] - y0 + 0.012 * s * np.tanh(q[:, 1] / (0.05 * s))) - 0.022 * s
            return np.maximum(np.abs(d) - 0.004 * s, wrap)
        prog.union(gauze, lo, hi, k=0.003 * s, label=lab)
        # blood seeping through over the wound (vertex G)
        model.wounds.append((c + front * (radii[1] + 0.006 * s) + up * y0 * 0.6 + R[:, 0] * 0.03 * s, 0.02 * s, 0.9))


def surface_hit(model, origin, direction, max_dist=0.3):
    """First point where a ray from (inside) origin exits the skin surface; returns (point, normal)."""
    direction = _n(direction)
    steps = np.linspace(0.0, max_dist, 300)
    P = origin + np.outer(steps, direction)
    d, _ = model.eval_points(P, None)
    idx = np.nonzero(d > 0)[0]
    t = steps[idx[0]] if len(idx) else steps[-1]
    p = origin + direction * t
    e = 0.001
    g = np.zeros(3)
    for a in range(3):
        o = np.zeros(3)
        o[a] = e
        g[a] = model.eval_points(np.array([p + o]), None)[0][0] - model.eval_points(np.array([p - o]), None)[0][0]
    return p, _n(g)


def site_point(model, site: dict):
    """Resolves a site spec to (origin on the skeleton, outward direction, segment)."""
    s = model.s
    sk = model.skel
    where = site["at"]
    side = site.get("side", "L")
    sx = 1.0 if side == "L" else -1.0
    t = float(site.get("t", 0.5))
    dl = site.get("dir", [0.0, 0.0, 1.0])     # (lateral(+out), along/up, front) in the part's frame
    if where in ("ua", "fa", "th", "sh"):
        f = (model.arm if where in ("ua", "fa") else model.leg)[side][where]
        origin = f.at(t)
        direction = f.out * dl[0] + f.axis * dl[1] + f.fwd * dl[2]
        seg = {"ua": f"body_upper_arm.{side}", "fa": f"body_forearm.{side}", "th": f"body_thigh.{side}",
               "sh": f"body_shin.{side}"}[where]
    elif where == "head":
        origin = model.hc
        R = model.hR
        direction = R[:, 0] * dl[0] * sx + R[:, 1] * dl[1] + R[:, 2] * dl[2]
        seg = "body_head"
    else:   # torso bones: hips / spine / chest / neck
        R = sk.rest[where]
        origin = sk.head[where] + R[:, 1] * (t * sk.length(where)) + R[:, 2] * 0.035 * s
        direction = R[:, 0] * dl[0] * sx + R[:, 1] * dl[1] + R[:, 2] * dl[2]
        seg = "body_torso"
        if where == "neck" and t > 0.5:
            seg = "body_head"
    return origin, _n(direction), seg


def add_wound(model, w: dict, rng):
    s = model.s
    origin, direction, seg = site_point(model, w)
    p, nrm = surface_hit(model, origin, direction)
    r = float(w.get("r", 0.025)) * s
    depth = float(w.get("depth", 0.6))
    a = _n(np.cross(nrm, (0, 0, 1)) if abs(nrm[2]) < 0.9 else np.cross(nrm, (1, 0, 0)))
    b = np.cross(nrm, a)
    Rw = np.stack([a, b, nrm], 1)
    elong = float(w.get("elong", 1.4))
    # main torn cavity + a few ragged bites around it (subtractions labelled gore)
    model.skin.ellipsoid(p - nrm * r * 0.25, np.array([r * elong, r, r * depth]), R=Rw, k=0.004 * s,
                         label=B.L_GORE, mode="sub")
    for _ in range(int(w.get("bites", 3))):
        off = (a * rng.uniform(-1, 1) * elong + b * rng.uniform(-1, 1)) * r * 0.9
        model.skin.sphere(p + off - nrm * r * 0.1, r * rng.uniform(0.25, 0.45), k=0.003 * s, label=B.L_GORE, mode="sub")
    model.wounds.append((p, r, float(w.get("blood", 1.0))))
    if w.get("exposed_teeth"):
        pass
    if w.get("bloom", True):
        add_bloom_site(model, {"p": p, "n": nrm, "r": r * 0.9, "seg": seg, **w.get("bloom_spec", {})}, rng)
    return p, nrm, seg


def add_bloom_site(model, spec: dict, rng):
    """Lumpy pale fungal mass (SDF, blends into skin) + filaments/shelves (extras)."""
    s = model.s
    p, nrm, r = np.asarray(spec["p"]), _n(spec["n"]), float(spec["r"])
    n_lumps = int(spec.get("lumps", 7))
    for i in range(n_lumps):
        off = _n(nrm * 0.4 + rng.normal(0, 0.7, 3)) * r * rng.uniform(0.2, 1.0)
        c = p + off - nrm * r * 0.15
        rad = r * rng.uniform(0.18, 0.42)
        model.growth.sphere(c, rad, k=0.004 * s, label=B.L_BLOOM)
    model.bloom_sites.append((p, r * 1.4, float(spec.get("amount", 1.0))))
    model.bloom_extras.append({"segment": spec["seg"], "center": p, "normal": nrm, "radius": r,
                               "filaments": int(spec.get("filaments", 5)), "length": float(spec.get("length", 0.06)) * s,
                               "shelves": int(spec.get("shelves", 2)), "shelf_size": float(spec.get("shelf_size", 0.016)),
                               "sag": float(spec.get("sag", 0.6))})


def add_bloom(model, b: dict, rng):
    origin, direction, seg = site_point(model, b)
    p, nrm = surface_hit(model, origin, direction)
    add_bloom_site(model, {"p": p, "n": nrm, "r": float(b.get("r", 0.03)) * model.s, "seg": seg, **b}, rng)


def add_throat_sac(model, spec: dict, rng):
    """Keener: swollen, veined resonating sac on the front/sides of the throat."""
    s = model.s
    sk = model.skel
    R = sk.rest["neck"]
    size = float(spec.get("size", 1.0))
    c = sk.head["neck"] + R @ np.array([0.0, 0.036, 0.058]) * s
    Rl = R @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
    model.skin.ellipsoid(c, np.array([0.056, 0.048, 0.046]) * s * size, R=Rl, k=0.03 * s, label=B.L_SKIN)
    for sx in (1.0, -1.0):
        model.skin.ellipsoid(c + R @ np.array([sx * 0.030, 0.006, -0.008]) * s, np.array([0.034, 0.034, 0.036]) * s * size,
                             R=Rl, k=0.02 * s, label=B.L_SKIN)
    # veins over the sac (ridges)
    nz = model.noise

    def veins(P, c=c):
        v = np.clip(1 - np.abs(nz.noise(P, 34.0)) * 9.0, 0, 1)
        w = 1 - smoothstep(0.04 * s, 0.09 * s, np.sqrt(((P - c) ** 2).sum(-1)))
        return -0.0016 * s * v * w
    model.skin.displace(veins, c - 0.1 * s, c + 0.1 * s)
    for i in range(int(spec.get("bloom_lumps", 3))):
        ang = rng.uniform(-1.2, 1.2)
        dirn = R @ np.array([math.sin(ang), rng.uniform(-0.3, 0.3), math.cos(ang)])
        p, nrm = surface_hit(model, c, dirn)
        add_bloom_site(model, {"p": p, "n": nrm, "r": 0.012 * s, "seg": "body_torso", "lumps": 4, "filaments": 2,
                               "shelves": 0, "length": 0.04}, rng)


# --------------------------------------------------------------------------------------------

def _tear_points(model, tears):
    out = []
    for t in tears:
        origin, direction, _ = site_point(model, t)
        p, _ = surface_hit(model, origin, direction)
        out.append((p, float(t.get("r", 0.04)) * model.s))
    return out


def dress(model, params: dict, rng) -> None:
    from . import char_wardrobe as W
    model.bloom_extras = []
    mz = Measures(model)
    model.measures = mz
    # wounds / bloom first (they carve the skin that clothing then covers or reveals)
    if params.get("throat_sac"):
        add_throat_sac(model, params["throat_sac"], rng)
    for w in params.get("wounds", []):
        add_wound(model, w, rng)
    for b in params.get("bloom", []):
        add_bloom(model, b, rng)
    outfit = params.get("outfit", {})
    boots = params.get("boots", {})
    for side in ("L", "R"):
        if boots.get(side):
            add_boot(model, side, boots if isinstance(boots, dict) else {})
    for top in outfit.get("tops", []):
        spec = dict(top)
        spec["tears"] = _tear_points(model, top.get("tears", []))
        model.garments.append(W.make(model, spec, mz, "top"))
        if top.get("collar"):
            model.garments.append(W.make(model, top, mz, "collar"))
    if "pants" in outfit:
        spec = dict(outfit["pants"])
        spec["tears"] = _tear_points(model, outfit["pants"].get("tears", []))
        model.garments.append(W.make(model, spec, mz, "pants"))
        # an untucked top hanging over the waistband hides the belt (its buckle poked through)
        covered = any(float(t.get("hem", -0.075)) < float(spec.get("waist", 0.075)) - 0.03 and not t.get("tucked")
                      for t in outfit.get("tops", []))
        if spec.get("belt") and not covered:
            model.garments.append(W.make(model, spec, mz, "belt"))
    add_hair(model, params.get("hair", {"style": "short"}), rng)
    add_headgear(model, params.get("hat", {}))
    for g in params.get("straps", []):
        model.garments.append(W.Strap(model, g, mz))
    if params.get("tie"):
        model.garments.append(W.Tie(model, params["tie"], mz))
    if params.get("mantle"):
        model.garments.append(W.Mantle(model, params["mantle"], mz))
    # the specials' features sit on the finished surface (ADR-0028)
    from . import char_specials as SP
    if params.get("armour"):
        SP.add_armour(model, params["armour"], rng)
    if params.get("pustules"):
        SP.add_pustules(model, params["pustules"], rng)
