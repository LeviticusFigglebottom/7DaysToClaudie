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
        """> 0 inside the arm volume (past the shoulder cut, near the arm axis)."""
        m = self.m
        c, n = m.cuts[f"shoulder.{side}"]
        _, d = self.arc(P, self.arm_pts[side])
        return np.minimum((P - c) @ n + 0.015 * m.s, 0.10 * m.s - d)


def _noise_edge(model, P, freq, amp, seed_off=0.0):
    return model.noise.fbm(P + seed_off, freq, 3) * amp


# --------------------------------------------------------------------------------------------
# Garments
# --------------------------------------------------------------------------------------------

def _wrinkles(model, P, axis, along, freq, amp, seed_off):
    """Irregular cloth wrinkles running around a limb/torso axis: noise-modulated partial rings."""
    nz = model.noise
    phase = along * freq * 2 * math.pi + nz.noise(P + seed_off, 9.0) * 2.5
    ring = np.sin(phase)
    mask = np.clip(nz.noise(P + seed_off * 2, 4.0) * 1.4 + 0.3, 0.0, 1.0)
    return amp * ring * mask


def make_top(model, spec: dict, mz: Measures):
    """Shirt / t-shirt / jacket / hospital gown (upper body + sleeves)."""
    s = model.s
    kind = spec.get("type", "flannel")
    label = B.CLOTH_LABELS.get(kind, B.L_FLANNEL)
    thick = float(spec.get("thickness", {"flannel": 0.0055, "tshirt": 0.0038, "jacket": 0.011,
                                         "hospital": 0.0050}.get(kind, 0.005))) * s
    hem = float(spec.get("hem", -0.075)) * s           # relative to the pelvis joint along the trunk
    sleeve = {L: float(spec.get("sleeve", 0.55)) for L in ("L", "R")}
    for side_key in ("sleeve_L", "sleeve_R"):
        if side_key in spec:
            sleeve[side_key[-1]] = float(spec[side_key])
    neck_drop = float(spec.get("neck_drop", 0.0)) * s
    neck_front = float(spec.get("neck_front", 0.025)) * s
    open_front = float(spec.get("open_front", 0.0)) * s
    open_back = float(spec.get("open_back", 0.0)) * s
    flare = float(spec.get("flare", 0.010)) * s
    torn = float(spec.get("torn", 0.0))
    rolled = spec.get("rolled", {})
    tears = spec.get("tears", [])
    # sleeve fractions are measured shoulder -> wrist (1.0 = full sleeve to the wrist)
    arm_len = {side: float(sum(np.linalg.norm(b - a) for a, b in zip(mz.arm_pts[side][:2], mz.arm_pts[side][1:3])))
               for side in ("L", "R")}
    ua_len = {side: float(np.linalg.norm(mz.arm_pts[side][1] - mz.arm_pts[side][0])) for side in ("L", "R")}
    sk = model.skel
    n_c, n_ax = model.cuts["neck"]
    neck_base_h = float((sk.head["neck"] - n_c) @ n_ax)
    neck_line = [sk.head["neck"] - n_ax * 0.1, sk.head["head"]]
    head_h = float((sk.head["head"] - n_c) @ n_ax) - neck_base_h
    chestR = sk.rest["chest"]
    off = 13.7 * (1 + sum(ord(ch) for ch in kind) % 7)

    def g(P, d_base):
        out_d = np.full(len(P), 1.0)
        h_all = mz.h(P)
        sel = np.nonzero(h_all > hem - 0.05 * s)[0]
        if len(sel) == 0:
            return out_d, np.full(len(P), label, np.int16)
        P = P[sel]
        h = h_all[sel]
        db = d_base[sel]
        # --- region: below the neckline (only inside the neck tube), above the hem, sleeves ---
        nh = (P - n_c) @ n_ax - neck_base_h          # height above the neck base
        frontness = np.clip(((P - n_c) @ chestR[:, 2]) / (0.06 * s), -1, 1)
        line_h = 0.010 * s - neck_drop - neck_front * np.maximum(frontness, 0) * (1 + 0.3 * frontness)
        d_ax = B.polyline_dist(P, neck_line)
        reg_neck = np.maximum(np.minimum(nh - line_h, 0.085 * s - d_ax), nh - head_h)
        hem_noise = _noise_edge(model, P, 9.0, 0.010 * s * (0.4 + torn), off)
        reg = np.maximum(reg_neck, (hem + hem_noise) - h)
        t_extra = np.zeros(len(P))
        folds = np.zeros(len(P))
        for side, sx in (("L", 1.0), ("R", -1.0)):
            a_s, a_d = mz.arm_arc(P, side)
            in_arm_v = mz.in_arm(P, side)
            in_arm = in_arm_v > -0.01 * s
            if not in_arm.any():
                continue
            frac = a_s / arm_len[side]
            sl_noise = _noise_edge(model, P, 11.0, 0.012 * (0.4 + torn), off + sx)
            reg = np.where(in_arm, np.maximum(reg, (frac - (sleeve[side] + sl_noise)) * arm_len[side]), reg)
            end = (sleeve[side] - frac) * arm_len[side]
            if side in rolled:
                t_extra += in_arm * (1 - smoothstep(0.0, 0.035 * s, end)) * 0.007 * s
            else:
                t_extra += in_arm * (1 - smoothstep(0.0, 0.012 * s, end)) * 0.0015 * s
            # elbow: bunching folds on the inner side, loose wrinkles elsewhere
            el = a_s - ua_len[side]
            fwin = np.exp(-(el / (0.09 * s)) ** 2) * in_arm
            folds += fwin * _wrinkles(model, P, None, a_s, 1.0 / (0.022 * s), 0.0016 * s, off + 5 * sx)
            folds += in_arm * (1 - fwin) * _wrinkles(model, P, None, a_s, 1.0 / (0.05 * s), 0.0009 * s, off + 9 * sx)
        # hanging loose towards the hem (untucked): covers belt / waistband
        t_extra += flare * (1 - smoothstep(hem + 0.10 * s, hem + 0.24 * s, h))
        # torso: soft horizontal bunching above the waist + diagonal strain wrinkles
        folds += np.exp(-((h - 0.10 * s) / (0.09 * s)) ** 2) * _wrinkles(model, P, None, h, 1.0 / (0.045 * s),
                                                                          0.0018 * s, off + 2)
        folds += model.noise.fbm(P * 1.0 + off, 10.0, 2) * 0.0012 * s
        d = db - thick - t_extra - folds
        q = (P - mz.pel) @ chestR
        if open_front > 0:
            gap = open_front * (0.6 + 0.4 * smoothstep(0.0, 0.35 * s, h)) - np.abs(q[:, 0] - 0.004 * s)
            reg = np.maximum(reg, np.where(q[:, 2] > 0.02 * s, gap, -1.0))
        if open_back > 0:
            w = open_back * (0.55 + 0.45 * smoothstep(0.05 * s, 0.35 * s, h)) + _noise_edge(model, P, 7.0, 0.01 * s, off + 3)
            gap = w - np.abs(q[:, 0])
            win = (q[:, 2] < -0.02 * s) & (h > 0.02 * s)
            reg = np.maximum(reg, np.where(win, gap, -1.0))
        for tc, tr in tears:
            dist = np.sqrt(((P - tc) ** 2).sum(-1))
            near = dist < tr * 2.5
            if near.any():
                hole = np.full(len(P), -1.0)
                hole[near] = (tr - dist[near]) + model.noise.fbm(P[near] + off * 2, 22.0, 2) * tr * 0.9
                reg = np.maximum(reg, hole)
        if torn > 0:
            hole = model.noise.fbm(P + off * 3, 5.0, 2) - (1.25 - 0.35 * torn)
            reg = np.maximum(reg, hole * 0.05 * s)
        out_d[sel] = np.maximum(d, reg)
        return out_d, np.full(len(out_d), label, np.int16)

    return g


def make_collar(model, spec: dict, mz: Measures):
    """Shirt/jacket collar: a folded band lying around the base of the neck just outside the
    shirt surface, open at the front."""
    s = model.s
    label = B.CLOTH_LABELS.get(spec.get("type", "flannel"), B.L_FLANNEL)
    big = 1.5 if spec.get("type") == "jacket" else 1.0
    thick = float(spec.get("thickness", {"flannel": 0.0055, "tshirt": 0.0038, "jacket": 0.011}.get(spec.get("type"), 0.0055)))
    sk = model.skel
    R = sk.rest["neck"]
    base = sk.head["neck"] + R @ np.array([0.0, 0.004, 0.0]) * s
    n_c, n_ax = model.cuts["neck"]

    def g(P, d_base):
        q = (P - base) @ R            # (left, up, front)
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        ang = np.arctan2(x, z)        # 0 = front
        lift = (0.016 - 0.016 * np.clip(np.cos(ang), 0, 1)) * big * s   # higher at the back
        shell = np.abs(d_base - (thick + 0.0075 * big) * s) - 0.0032 * s * big
        yb = np.maximum(y - (0.010 * s + lift), -(0.030 * big * s) + 0.5 * lift - y)
        band = np.maximum(shell, yb)
        rad = np.sqrt(x * x + z * z)
        band = np.maximum(band, rad - 0.13 * s * big)
        band = np.maximum(band, (P - n_c) @ n_ax + 0.018 * s)      # stays below the neck cut
        opening = np.cos(ang) - math.cos(math.radians(32))
        band = np.maximum(band, opening * 0.03 * s)
        return band, np.full(len(P), label, np.int16)

    return g


def make_pants(model, spec: dict, mz: Measures):
    s = model.s
    kind = spec.get("type", "denim")
    label = B.CLOTH_LABELS.get(kind, B.L_DENIM)
    thick = float(spec.get("thickness", 0.0050)) * s
    waist = float(spec.get("waist", 0.075)) * s
    length = {sd: float(spec.get("length", 1.0)) for sd in ("L", "R")}
    for k in ("length_L", "length_R"):
        if k in spec:
            length[k[-1]] = float(spec[k])
    torn = float(spec.get("torn", 0.0))
    tears = spec.get("tears", [])
    leg_len = {side: float(sum(np.linalg.norm(b - a) for a, b in zip(mz.leg_pts[side][:-1], mz.leg_pts[side][1:])))
               for side in ("L", "R")}
    th_len = {side: float(np.linalg.norm(mz.leg_pts[side][1] - mz.leg_pts[side][0])) for side in ("L", "R")}
    off = 41.3

    def g(P, d_base):
        out_d = np.full(len(P), 1.0)
        h_all = mz.h(P)
        sel = np.nonzero(h_all < waist + 0.04 * s)[0]
        if len(sel) == 0:
            return out_d, np.full(len(P), label, np.int16)
        P = P[sel]
        h = h_all[sel]
        db = d_base[sel]
        reg = h - (waist + _noise_edge(model, P, 8.0, 0.003 * s, off))
        # exclude the arms/hands hanging next to the thighs
        reg = np.maximum(reg, np.maximum(mz.in_arm(P, "L"), mz.in_arm(P, "R")))
        folds = model.noise.fbm(P + off, 10.0, 2) * 0.0011 * s
        t_extra = np.zeros(len(P))
        for side, sx in (("L", 1.0), ("R", -1.0)):
            l_s, l_d = mz.leg_arc(P, side)
            frac = l_s / leg_len[side]
            on_leg = (P[:, 0] * sx > -0.01 * s) & (l_d < 0.14 * s)
            if not on_leg.any():
                continue
            end = length[side] + _noise_edge(model, P, 10.0, 0.015 * (0.3 + torn), off + sx)
            reg = np.where(on_leg, np.maximum(reg, (frac - end) * leg_len[side]), reg)
            kn = l_s - th_len[side]
            kwin = np.exp(-(kn / (0.07 * s)) ** 2)
            folds += on_leg * kwin * _wrinkles(model, P, None, l_s, 1.0 / (0.025 * s), 0.0015 * s, off + 3 * sx)
            hem_d = (end - frac) * leg_len[side]
            stack = 1 - smoothstep(0.0, 0.10 * s, hem_d)
            folds += on_leg * stack * _wrinkles(model, P, None, l_s, 1.0 / (0.02 * s), 0.0022 * s, off + 7 * sx)
            t_extra += on_leg * stack * 0.004 * s
        d = db - thick - t_extra - folds
        for tc, tr in tears:
            dist = np.sqrt(((P - tc) ** 2).sum(-1))
            near = dist < tr * 2.5
            if near.any():
                hole = np.full(len(P), -1.0)
                hole[near] = (tr - dist[near]) + model.noise.fbm(P[near] + off * 2, 22.0, 2) * tr * 0.9
                reg = np.maximum(reg, hole)
        if torn > 0:
            hole = model.noise.fbm(P + off * 3, 5.0, 2) - (1.3 - 0.35 * torn)
            reg = np.maximum(reg, hole * 0.05 * s)
        out_d[sel] = np.maximum(d, reg)
        return out_d, np.full(len(out_d), label, np.int16)

    return g


def make_belt(model, spec: dict, mz: Measures):
    s = model.s
    z0 = float(spec.get("waist", 0.075)) * s - 0.018 * s
    chestR = model.skel.rest["hips"]

    def g(P, d_base):
        h = mz.h(P)
        band = np.maximum(d_base - 0.0105 * s, np.abs(h - z0) - 0.017 * s)
        band = np.maximum(band, np.maximum(mz.in_arm(P, "L"), mz.in_arm(P, "R")) + 0.01 * s)
        # buckle at the front
        q = (P - mz.pel) @ chestR
        buckle = np.maximum(np.maximum(np.abs(q[:, 0]) - 0.026 * s, np.abs(h - z0) - 0.022 * s), d_base - 0.016 * s)
        buckle = np.where(q[:, 2] > 0.03 * s, buckle, 1.0)
        return np.minimum(band, buckle), np.full(len(P), B.L_BOOT, np.int16)

    return g


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
    radii = np.array([0.074, 0.088, 0.096]) * s * float(model.p.get("head_scale", 1.0))
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
        reg = (edge_y + nz.noise(P, 40.0) * 0.006) - y
        # balding crown / missing patches
        crown = bald * 0.06 - np.sqrt(x * x + (z + 0.01) ** 2 + np.maximum(0.11 - y, 0) ** 2 * 4) + nz.noise(P, 18.0) * 0.01
        patches = nz.fbm(P, 14.0, 2) - (0.75 - 0.6 * patchy)
        reg = np.maximum(reg, np.maximum(crown, patches * 0.03))
        # soft clumps (fine strands come from the texture)
        d = d - np.maximum(nz.fbm(P, 22.0, 2), 0) * 0.0018 * s
        return np.maximum(d, reg * s)

    lo = hc - radii - 0.03 * s
    hi = hc + radii + 0.03 * s
    prog.union(cap, lo, hi, k=0.0, label=B.L_HAIR)
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
        model.garments.append(make_top(model, spec, mz))
        if top.get("collar"):
            model.garments.append(make_collar(model, top, mz))
    if "pants" in outfit:
        spec = dict(outfit["pants"])
        spec["tears"] = _tear_points(model, outfit["pants"].get("tears", []))
        model.garments.append(make_pants(model, spec, mz))
        if spec.get("belt"):
            model.garments.append(make_belt(model, spec, mz))
    add_hair(model, params.get("hair", {"style": "short"}), rng)
