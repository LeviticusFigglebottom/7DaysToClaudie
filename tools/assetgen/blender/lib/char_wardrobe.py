"""Garments for Hollowed bodies (ADR-0028): signed-distance clothing over the smoothed cloth base
body, plus the per-vertex marks the cloth shader draws (char_attrs):

  seam  signed distance to seam lines: side and shoulder seams, armholes, sleeve undersides,
        plackets, back yokes, pockets; out- and inseams, waistbands, flies, back pockets and yokes
  trim  signed distance to trim (negative inside): the Cordon's retroreflective tape
  edge  distance to the nearest garment edge, + for a hemmed edge (stitched), - for a torn one

Every garment is driven by the skeleton (char_dress.Measures), so it fits every body. A garment
is an offset of the base body clipped to its region (hem, neckline, sleeves, legs) with folds,
ragged edges and tears; BodyModel._add_layers unions them over the skin.

Kinds (spec "type"): tops flannel, tshirt, jacket, hospital, shirt (dress shirt), knit (cardigan,
sweater), hunter (wool hunting coat), scrubs, hivis (vest), coverall, hide (the Ashen's hide wrap);
pants denim, canvas, wool (slacks), scrubs, coverall, hide.
"""
from __future__ import annotations

import math

import numpy as np

from . import char_body as B
from .char_attrs import FAR, signed_min
from .char_body import _n, smoothstep

THICK_TOP = {"flannel": 0.0055, "tshirt": 0.0038, "jacket": 0.011, "hospital": 0.0050, "shirt": 0.0040,
             "knit": 0.0085, "hunter": 0.012, "scrubs": 0.0042, "hivis": 0.0030, "coverall": 0.0065, "hide": 0.0080,
             "dress": 0.0042, "wool": 0.0070}
# Kinds that button or zip up the front: a placket (two stitched lines) down the centre.
PLACKET = {"flannel": 0.016, "shirt": 0.014, "jacket": 0.020, "hunter": 0.022, "coverall": 0.014, "knit": 0.015,
           "hivis": 0.010, "wool": 0.016}
# Kinds with a back yoke (a seam across the shoulder blades).
YOKE = {"flannel", "shirt", "jacket", "hunter"}


def noise_edge(model, P, freq, amp, seed_off=0.0):
    return model.noise.fbm(P + seed_off, freq, 3) * amp


def wrinkles(model, P, along, freq, amp, seed_off):
    """Irregular cloth wrinkles running round a limb or the trunk: noise-modulated partial rings."""
    nz = model.noise
    phase = along * freq * 2 * math.pi + nz.noise(P + seed_off, 9.0) * 2.5
    ring = np.sin(phase)
    mask = np.clip(nz.noise(P + seed_off * 2, 4.0) * 1.4 + 0.3, 0.0, 1.0)
    return amp * ring * mask


def closest_on_polyline(P, pts):
    """Closest points on a polyline, the arc length there and the segment index."""
    best_d = np.full(len(P), 1e9)
    best_q = np.zeros_like(P)
    best_s = np.zeros(len(P))
    best_i = np.zeros(len(P), np.int32)
    acc = 0.0
    for i, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        ab = b - a
        L2 = float(ab @ ab)
        t = np.clip(((P - a) @ ab) / max(L2, 1e-12), 0.0, 1.0)
        q = a + t[:, None] * ab
        d = np.sqrt(((P - q) ** 2).sum(-1))
        better = d < best_d
        best_d = np.where(better, d, best_d)
        best_q[better] = q[better]
        best_s = np.where(better, acc + t * math.sqrt(L2), best_s)
        best_i = np.where(better, i, best_i)
        acc += math.sqrt(L2)
    return best_q, best_s, best_i, best_d


class TrunkFrame:
    """Per-point trunk axes: the spine polyline's closest point and the (left, up, front) axes of
    the hips, spine or chest bone there (blended), so seams follow a hunched back."""

    def __init__(self, model):
        sk = model.skel
        self.pts = [sk.head["hips"], sk.head["spine"], sk.head["chest"], sk.head["neck"], sk.tail["neck"]]
        self.R = [sk.rest["hips"], sk.rest["spine"], sk.rest["chest"], sk.rest["neck"]]

    def local(self, P):
        """-> (q, axis_point): q = (left, up, front) offsets from the axis point in the local frame."""
        q0, _, idx, _ = closest_on_polyline(P, self.pts)
        q = np.zeros_like(P)
        for i, R in enumerate(self.R):
            m = idx == i
            if m.any():
                q[m] = (P[m] - q0[m]) @ R
        return q, q0


def arm_angle_dist(model, P, side, under=True):
    """Signed arc distance round the arm from its underside line (the sleeve seam): 0 on the line
    facing the body, growing towards the top of the arm."""
    out = np.full(len(P), FAR)
    best = np.full(len(P), 1e9)
    for seg, frame in (("ua", model.arm[side]["ua"]), ("fa", model.arm[side]["fa"])):
        a, b = frame.head, frame.tail
        ab = b - a
        t = np.clip(((P - a) @ ab) / float(ab @ ab), 0.0, 1.0)
        q = P - (a + t[:, None] * ab)
        r = np.sqrt((q * q).sum(-1))
        down = -frame.out if under else frame.out
        ang = np.arctan2(q @ frame.fwd, q @ down)
        d = ang * np.maximum(r, 1e-4)
        dist = np.sqrt(((P - (a + t[:, None] * ab)) ** 2).sum(-1))
        closer = dist < best
        out = np.where(closer, d, out)
        best = np.where(closer, dist, best)
    return out


class Garment:
    """A garment: SDF (the shape) + fields (the marks)."""

    label = B.L_FLANNEL
    kind = "flannel"

    def __call__(self, P, d_base):
        return self.sdf(P, d_base)

    def sdf(self, P, d_base):
        raise NotImplementedError

    def fields(self, P):
        """-> (trim, seam, edge) per point (FAR where the garment marks nothing)."""
        n = len(P)
        return np.full(n, FAR), np.full(n, FAR), np.full(n, FAR)


class Top(Garment):
    """Shirt, t-shirt, jacket, gown, vest or coverall top: upper body + sleeves."""

    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.mz, self.spec = model, mz, spec
        self.kind = kind = spec.get("type", "flannel")
        self.label = B.CLOTH_LABELS.get(kind, B.L_FLANNEL)
        self.thick = float(spec.get("thickness", THICK_TOP.get(kind, 0.005))) * s
        self.hem = float(spec.get("hem", -0.075)) * s       # relative to the pelvis joint along the trunk
        self.sleeve = {sd: float(spec.get("sleeve", 0.55)) for sd in ("L", "R")}
        for key in ("sleeve_L", "sleeve_R"):
            if key in spec:
                self.sleeve[key[-1]] = float(spec[key])
        self.neck_drop = float(spec.get("neck_drop", 0.0)) * s
        self.neck_front = float(spec.get("neck_front", 0.025)) * s
        self.open_front = float(spec.get("open_front", 0.0)) * s
        self.open_back = float(spec.get("open_back", 0.0)) * s
        # a tucked-in shirt ends under the waistband, close to the body
        self.flare = 0.0 if spec.get("tucked") else float(spec.get("flare", 0.010)) * s
        self.torn = float(spec.get("torn", 0.0))
        self.rolled = spec.get("rolled", {})
        self.tears = spec.get("tears", [])
        # Vests: no sleeves, and the armhole cut deep and wide round the shoulder.
        self.armhole = float(spec.get("armhole", 0.0)) * s
        sk = model.skel
        self.arm_len = {sd: float(sum(np.linalg.norm(b - a) for a, b in zip(mz.arm_pts[sd][:2], mz.arm_pts[sd][1:3])))
                        for sd in ("L", "R")}
        self.ua_len = {sd: float(np.linalg.norm(mz.arm_pts[sd][1] - mz.arm_pts[sd][0])) for sd in ("L", "R")}
        self.n_c, self.n_ax = model.cuts["neck"]
        self.neck_base_h = float((sk.head["neck"] - self.n_c) @ self.n_ax)
        self.neck_line = [sk.head["neck"] - self.n_ax * 0.1, sk.head["head"]]
        self.head_h = float((sk.head["head"] - self.n_c) @ self.n_ax) - self.neck_base_h
        self.chestR = sk.rest["chest"]
        self.off = 13.7 * (1 + sum(ord(ch) for ch in kind) % 7) + float(spec.get("seed_off", 0.0))
        self.trunk = TrunkFrame(model)
        self.pockets = spec.get("pockets", [])
        self.trim = spec.get("trim", {})

    # --- shape -----------------------------------------------------------------------------
    def _regions(self, P, h):
        """-> (reg_hem, reg_torn, in_arm per side, arc per side): reg < 0 inside the garment."""
        m, mz, s = self.m, self.mz, self.m.s
        nh = (P - self.n_c) @ self.n_ax - self.neck_base_h
        frontness = np.clip(((P - self.n_c) @ self.chestR[:, 2]) / (0.06 * s), -1, 1)
        line_h = 0.010 * s - self.neck_drop - self.neck_front * np.maximum(frontness, 0) * (1 + 0.3 * frontness)
        d_ax = B.polyline_dist(P, self.neck_line)
        reg_neck = np.maximum(np.minimum(nh - line_h, 0.085 * s - d_ax), nh - self.head_h)
        ragged = 0.4 + self.torn
        hem_noise = noise_edge(m, P, 9.0, 0.010 * s * ragged, self.off)
        reg_hem = np.maximum(reg_neck, (self.hem + hem_noise) - h)
        arms = {}
        for side, sx in (("L", 1.0), ("R", -1.0)):
            a_s, a_d = mz.arm_arc(P, side)
            in_arm_v = mz.in_arm(P, side)
            in_arm = in_arm_v > -0.01 * s
            arms[side] = (a_s, in_arm, in_arm_v)
            if not in_arm.any():
                continue
            frac = a_s / self.arm_len[side]
            sl_noise = noise_edge(m, P, 11.0, 0.012 * ragged, self.off + sx)
            reg_hem = np.where(in_arm, np.maximum(reg_hem, (frac - (self.sleeve[side] + sl_noise)) * self.arm_len[side]), reg_hem)
            if self.armhole > 0:
                # A vest: cut away round the arm root, a little into the torso.
                c, n = m.cuts[f"shoulder.{side}"]
                ah = (P - c) @ n + self.armhole
                reg_hem = np.maximum(reg_hem, np.where(B.polyline_dist(P, mz.arm_pts[side][:2]) < 0.16 * s, ah, -1.0))
        q = (P - mz.pel) @ self.chestR
        if self.open_front > 0:
            gap = self.open_front * (0.6 + 0.4 * smoothstep(0.0, 0.35 * s, h)) - np.abs(q[:, 0] - 0.004 * s)
            reg_hem = np.maximum(reg_hem, np.where(q[:, 2] > 0.02 * s, gap, -1.0))
        if self.open_back > 0:
            w = self.open_back * (0.55 + 0.45 * smoothstep(0.05 * s, 0.35 * s, h)) + noise_edge(m, P, 7.0, 0.01 * s, self.off + 3)
            gap = w - np.abs(q[:, 0])
            win = (q[:, 2] < -0.02 * s) & (h > 0.02 * s)
            reg_hem = np.maximum(reg_hem, np.where(win, gap, -1.0))
        reg_torn = np.full(len(P), -1.0)
        for tc, tr in self.tears:
            dist = np.sqrt(((P - tc) ** 2).sum(-1))
            near = dist < tr * 2.5
            if near.any():
                hole = np.full(len(P), -1.0)
                hole[near] = (tr - dist[near]) + m.noise.fbm(P[near] + self.off * 2, 22.0, 2) * tr * 0.9
                reg_torn = np.maximum(reg_torn, hole)
        if self.torn > 0:
            hole = m.noise.fbm(P + self.off * 3, 5.0, 2) - (1.25 - 0.35 * self.torn)
            reg_torn = np.maximum(reg_torn, hole * 0.05 * s)
        return reg_hem, reg_torn, arms

    def sdf(self, P_all, d_base):
        m, mz, s = self.m, self.mz, self.m.s
        out_d = np.full(len(P_all), 1.0)
        h_all = mz.h(P_all)
        sel = np.nonzero(h_all > self.hem - 0.05 * s)[0]
        if len(sel) == 0:
            return out_d, np.full(len(P_all), self.label, np.int16)
        P = P_all[sel]
        h = h_all[sel]
        db = d_base[sel]
        reg_hem, reg_torn, arms = self._regions(P, h)
        reg = np.maximum(reg_hem, reg_torn)
        t_extra = np.zeros(len(P))
        folds = np.zeros(len(P))
        for side, sx in (("L", 1.0), ("R", -1.0)):
            a_s, in_arm, _ = arms[side]
            if not in_arm.any():
                continue
            frac = a_s / self.arm_len[side]
            end = (self.sleeve[side] - frac) * self.arm_len[side]
            if side in self.rolled:
                t_extra += in_arm * (1 - smoothstep(0.0, 0.035 * s, end)) * 0.007 * s
            else:
                t_extra += in_arm * (1 - smoothstep(0.0, 0.012 * s, end)) * 0.0015 * s
            # elbow: bunching folds on the inner side, loose wrinkles elsewhere
            el = a_s - self.ua_len[side]
            fwin = np.exp(-(el / (0.09 * s)) ** 2) * in_arm
            folds += fwin * wrinkles(m, P, a_s, 1.0 / (0.022 * s), 0.0016 * s, self.off + 5 * sx)
            folds += in_arm * (1 - fwin) * wrinkles(m, P, a_s, 1.0 / (0.05 * s), 0.0009 * s, self.off + 9 * sx)
        # hanging loose towards the hem (untucked): covers belt / waistband
        t_extra += self.flare * (1 - smoothstep(self.hem + 0.10 * s, self.hem + 0.24 * s, h))
        # torso: soft horizontal bunching above the waist + diagonal strain wrinkles
        folds += np.exp(-((h - 0.10 * s) / (0.09 * s)) ** 2) * wrinkles(m, P, h, 1.0 / (0.045 * s), 0.0018 * s, self.off + 2)
        folds += m.noise.fbm(P * 1.0 + self.off, 10.0, 2) * 0.0012 * s
        # Hems are turned and stitched: a slightly thicker band along a hemmed edge.
        hem_band = (1 - smoothstep(0.0, 0.016 * s, -reg_hem)) * (self.torn < 0.5) * 0.0012 * s
        # Pockets stand proud of the panel.
        if self.pockets:
            t_extra += (self._pocket_sd(P) < 0) * 0.0016 * s
        d = db - self.thick - t_extra - folds - hem_band
        out_d[sel] = np.maximum(d, reg)
        return out_d, np.full(len(out_d), self.label, np.int16)

    # --- marks -----------------------------------------------------------------------------
    def _pocket_sd(self, P):
        s = self.m.s
        out = np.full(len(P), FAR)
        if not self.pockets:
            return out
        q, _ = self.trunk.local(P)
        sk = self.m.skel
        ch = sk.head["chest"]
        hh = (P - ch) @ sk.rest["chest"][:, 1]
        for pk in self.pockets:
            sx = 1.0 if pk.get("side", "L") == "L" else -1.0
            cx = sx * float(pk.get("x", 0.065)) * s
            cy = float(pk.get("y", 0.13)) * s
            w = float(pk.get("w", 0.115)) * s * 0.5
            hgt = float(pk.get("h", 0.13)) * s * 0.5
            dx = np.abs(q[:, 0] - cx) - w
            dy = np.abs(hh - cy) - hgt
            box = np.maximum(dx, dy)
            box = np.where(q[:, 2] > 0.0, box, FAR)
            out = signed_min(out, box)
            if pk.get("flap", True):
                flap = np.where((np.abs(q[:, 0] - cx) < w) & (q[:, 2] > 0.0), hh - (cy + hgt - 0.035 * s), FAR)
                out = signed_min(out, flap)
        return out

    def fields(self, P):
        m, mz, s = self.m, self.mz, self.m.s
        n = len(P)
        h = mz.h(P)
        reg_hem, reg_torn, arms = self._regions(P, h)
        e_hem, e_torn = -reg_hem, -reg_torn
        if self.torn >= 0.5:
            edge = -np.minimum(e_hem, e_torn)
        else:
            edge = np.where(e_hem <= e_torn, e_hem, -e_torn)
        in_any_arm = arms["L"][1] | arms["R"][1]
        q, _ = self.trunk.local(P)
        torso = ~in_any_arm
        # Side and shoulder seams: where the front panel meets the back (the trunk's coronal plane,
        # a little in front of the spine bones, which run behind the trunk's centre).
        side = np.where(torso, q[:, 2] - 0.02 * s, FAR)
        seams = [side]
        for sd in ("L", "R"):
            a_s, in_arm, in_arm_v = arms[sd]
            if self.armhole <= 0:
                c, nrm = m.cuts[f"shoulder.{sd}"]
                ring = (P - c) @ nrm - (0.026 + float(self.spec.get("drop_shoulder", 0.0))) * s
                near = np.abs(ring) < 0.05 * s
                near &= B.polyline_dist(P, mz.arm_pts[sd][:2]) < 0.13 * s
                seams.append(np.where(near, ring, FAR))
                under = arm_angle_dist(m, P, sd)
                seams.append(np.where(in_arm & (a_s > 0.03 * s), under, FAR))
        pk = PLACKET.get(self.kind)
        if pk and self.open_front <= 0 and self.spec.get("placket", True):
            w = pk * s * 0.5
            seams.append(np.where(torso & (q[:, 2] > 0.02 * s), np.abs(q[:, 0]) - w, FAR))
        if self.kind in YOKE:
            yoke_h = self.neck_base_h - 0.11 * s
            hh = (P - self.n_c) @ self.n_ax
            seams.append(np.where(torso & (q[:, 2] < -0.02 * s), hh - yoke_h, FAR))
        if self.pockets:
            seams.append(self._pocket_sd(P))
        seam = signed_min(*seams)
        trim = np.full(n, FAR)
        if self.trim:
            trim = self._trim_sd(P, h, q, torso)
        return trim, seam, edge

    def _trim_sd(self, P, h, q, torso):
        s = self.m.s
        t = self.trim
        out = np.full(len(P), FAR)
        w = float(t.get("width", 0.05)) * s * 0.5
        for hc in t.get("bands", []):
            band = np.abs(h - float(hc) * s) - w
            out = signed_min(out, np.where(torso, band, FAR))
        if "braces" in t:
            x0 = float(t["braces"]) * s
            low = min(float(b) for b in t.get("bands", [0.0])) * s
            brace = np.abs(np.abs(q[:, 0]) - x0) - w
            out = signed_min(out, np.where(torso & (h > low), brace, FAR))
        return out


class Collar(Garment):
    """Shirt / jacket collar: a folded band round the base of the neck just outside the shirt,
    open at the front."""

    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.spec = model, spec
        self.kind = spec.get("type", "flannel")
        self.label = B.CLOTH_LABELS.get(self.kind, B.L_FLANNEL)
        self.big = 1.5 if self.kind in ("jacket", "hunter", "coverall") else 1.0
        self.thick = float(spec.get("thickness", THICK_TOP.get(self.kind, 0.0055)))
        sk = model.skel
        self.R = sk.rest["neck"]
        self.base = sk.head["neck"] + self.R @ np.array([0.0, 0.004, 0.0]) * s
        self.n_c, self.n_ax = model.cuts["neck"]
        self.open_deg = float(spec.get("collar_open", 32.0))

    def _parts(self, P, d_base):
        s, big = self.m.s, self.big
        q = (P - self.base) @ self.R
        x, y, z = q[:, 0], q[:, 1], q[:, 2]
        ang = np.arctan2(x, z)
        lift = (0.016 - 0.016 * np.clip(np.cos(ang), 0, 1)) * big * s   # higher at the back
        shell = np.abs(d_base - (self.thick + 0.0075 * big) * s) - 0.0032 * s * big
        yb = np.maximum(y - (0.010 * s + lift), -(0.030 * big * s) + 0.5 * lift - y)
        rad = np.sqrt(x * x + z * z)
        bound = np.maximum(yb, rad - 0.13 * s * big)
        bound = np.maximum(bound, (P - self.n_c) @ self.n_ax + 0.018 * s)
        opening = (np.cos(ang) - math.cos(math.radians(self.open_deg))) * 0.03 * s
        return shell, bound, opening

    def sdf(self, P, d_base):
        shell, bound, opening = self._parts(P, d_base)
        band = np.maximum(np.maximum(shell, bound), opening)
        return band, np.full(len(P), self.label, np.int16)

    def fields(self, P):
        n = len(P)
        db, _ = self.m.base.eval(P)
        _, bound, opening = self._parts(P, db)
        edge = -np.maximum(bound, opening)
        return np.full(n, FAR), np.full(n, FAR), edge


class Pants(Garment):
    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.mz, self.spec = model, mz, spec
        self.kind = kind = spec.get("type", "denim")
        self.label = B.CLOTH_LABELS.get(kind, B.L_DENIM)
        self.thick = float(spec.get("thickness", {"wool": 0.0045, "hide": 0.0075, "coverall": 0.0060}.get(kind, 0.0050))) * s
        self.waist = float(spec.get("waist", 0.075)) * s
        self.length = {sd: float(spec.get("length", 1.0)) for sd in ("L", "R")}
        for k in ("length_L", "length_R"):
            if k in spec:
                self.length[k[-1]] = float(spec[k])
        self.torn = float(spec.get("torn", 0.0))
        self.tears = spec.get("tears", [])
        self.leg_len = {sd: float(sum(np.linalg.norm(b - a) for a, b in zip(mz.leg_pts[sd][:-1], mz.leg_pts[sd][1:])))
                        for sd in ("L", "R")}
        self.th_len = {sd: float(np.linalg.norm(mz.leg_pts[sd][1] - mz.leg_pts[sd][0])) for sd in ("L", "R")}
        self.off = 41.3 + float(spec.get("seed_off", 0.0))
        sk = model.skel
        self.hipsR = sk.rest["hips"]
        # crotch height (relative to the pelvis joint, along the trunk)
        self.crotch = float(min(mz.h(np.array([sk.j["hip.L"]]))[0], 0.0)) - 0.035 * s
        self.trim = spec.get("trim", {})

    def _regions(self, P, h):
        m, mz, s = self.m, self.mz, self.m.s
        reg_hem = h - (self.waist + noise_edge(m, P, 8.0, 0.003 * s, self.off))
        reg_hem = np.maximum(reg_hem, np.maximum(mz.in_arm(P, "L"), mz.in_arm(P, "R")))
        reg_hem = np.maximum(reg_hem, np.maximum(mz.on_foot(P, "L"), mz.on_foot(P, "R")))
        legs = {}
        for side, sx in (("L", 1.0), ("R", -1.0)):
            l_s, l_d = mz.leg_arc(P, side)
            frac = l_s / self.leg_len[side]
            on_leg = (P[:, 0] * sx > -0.01 * s) & (l_d < 0.14 * s)
            legs[side] = (l_s, frac, on_leg)
            if not on_leg.any():
                continue
            end = self.length[side] + noise_edge(m, P, 10.0, 0.015 * (0.3 + self.torn), self.off + sx)
            reg_hem = np.where(on_leg, np.maximum(reg_hem, (frac - end) * self.leg_len[side]), reg_hem)
        reg_torn = np.full(len(P), -1.0)
        for tc, tr in self.tears:
            dist = np.sqrt(((P - tc) ** 2).sum(-1))
            near = dist < tr * 2.5
            if near.any():
                hole = np.full(len(P), -1.0)
                hole[near] = (tr - dist[near]) + m.noise.fbm(P[near] + self.off * 2, 22.0, 2) * tr * 0.9
                reg_torn = np.maximum(reg_torn, hole)
        if self.torn > 0:
            hole = m.noise.fbm(P + self.off * 3, 5.0, 2) - (1.3 - 0.35 * self.torn)
            reg_torn = np.maximum(reg_torn, hole * 0.05 * s)
        return reg_hem, reg_torn, legs

    def sdf(self, P_all, d_base):
        m, mz, s = self.m, self.mz, self.m.s
        out_d = np.full(len(P_all), 1.0)
        h_all = mz.h(P_all)
        sel = np.nonzero(h_all < self.waist + 0.04 * s)[0]
        if len(sel) == 0:
            return out_d, np.full(len(P_all), self.label, np.int16)
        P = P_all[sel]
        h = h_all[sel]
        db = d_base[sel]
        reg_hem, reg_torn, legs = self._regions(P, h)
        reg = np.maximum(reg_hem, reg_torn)
        folds = m.noise.fbm(P + self.off, 10.0, 2) * 0.0011 * s
        t_extra = np.zeros(len(P))
        for side, sx in (("L", 1.0), ("R", -1.0)):
            l_s, frac, on_leg = legs[side]
            if not on_leg.any():
                continue
            end = self.length[side] + noise_edge(m, P, 10.0, 0.015 * (0.3 + self.torn), self.off + sx)
            kn = l_s - self.th_len[side]
            kwin = np.exp(-(kn / (0.07 * s)) ** 2)
            folds += on_leg * kwin * wrinkles(m, P, l_s, 1.0 / (0.025 * s), 0.0015 * s, self.off + 3 * sx)
            hem_d = (end - frac) * self.leg_len[side]
            stack = 1 - smoothstep(0.0, 0.10 * s, hem_d)
            folds += on_leg * stack * wrinkles(m, P, l_s, 1.0 / (0.02 * s), 0.0022 * s, self.off + 7 * sx)
            t_extra += on_leg * stack * 0.004 * s
        # waistband: a firmer, slightly proud band at the top
        t_extra += (1 - smoothstep(0.03 * s, 0.045 * s, self.waist - h)) * (h < self.waist + 0.01 * s) * 0.0012 * s
        d = db - self.thick - t_extra - folds
        out_d[sel] = np.maximum(d, reg)
        return out_d, np.full(len(out_d), self.label, np.int16)

    def fields(self, P):
        m, mz, s = self.m, self.mz, self.m.s
        n = len(P)
        h = mz.h(P)
        reg_hem, reg_torn, legs = self._regions(P, h)
        e_hem, e_torn = -reg_hem, -reg_torn
        ragged = self.torn >= 0.5 or min(self.length.values()) < 0.9
        if ragged:
            # cut-offs and shredded legs: the leg ends fray, the waistband stays hemmed
            e_waist = self.waist - h
            edge = np.where(e_waist <= np.minimum(e_hem, e_torn) + 1e-4, e_waist, -np.minimum(e_hem, e_torn))
        else:
            edge = np.where(e_hem <= e_torn, e_hem, -e_torn)
        q = (P - mz.pel) @ self.hipsR             # (left, up, front) about the pelvis
        seams = []
        crotch = self.crotch
        for side, sx in (("L", 1.0), ("R", -1.0)):
            l_s, frac, on_leg = legs[side]
            th, sh = self.m.leg[side]["th"], self.m.leg[side]["sh"]
            pts = [th.head, th.tail, sh.tail]
            cq, _, idx, _ = closest_on_polyline(P, pts)
            fwd = np.where(idx[:, None] == 0, th.fwd, sh.fwd)
            # out- and inseam: where the leg's front and back panels meet
            sd = ((P - cq) * fwd).sum(-1)
            seams.append(np.where(on_leg & (h < crotch) & (P[:, 0] * sx > 0.0), sd, FAR))
        hips = (h >= crotch - 0.02 * s) & (h < self.waist + 0.01 * s)
        # side seams over the hips, centre seams front and back
        lat = np.abs(q[:, 0])
        seams.append(np.where(hips & (lat > 0.08 * s), q[:, 2] - 0.0 * s, FAR))
        seams.append(np.where(hips & (lat < 0.05 * s), q[:, 0], FAR))
        # waistband
        seams.append(np.where(h > self.waist - 0.08 * s, h - (self.waist - 0.038 * s), FAR))
        if self.kind in ("denim", "canvas", "wool", "coverall"):
            # the fly: a stitched line on the wearer's left, down to above the crotch
            fly = (q[:, 2] > 0.02 * s) & (h > crotch + 0.05 * s) & (h < self.waist - 0.038 * s) & (q[:, 0] > -0.01 * s)
            seams.append(np.where(fly, q[:, 0] - 0.032 * s, FAR))
        if self.kind in ("denim", "canvas"):
            back = q[:, 2] < -0.02 * s
            # back yoke: a V across the seat, and two patch pockets below it
            yoke = self.waist - 0.07 * s - 0.035 * s * (1.0 - np.clip(lat / (0.12 * s), 0, 1))
            seams.append(np.where(back & (h > yoke - 0.04 * s), h - yoke, FAR))
            for sx in (1.0, -1.0):
                cx = sx * 0.075 * s
                cy = yoke - 0.085 * s
                box = np.maximum(np.abs(q[:, 0] - cx) - 0.065 * s, np.abs(h - cy) - 0.07 * s)
                seams.append(np.where(back, box, FAR))
        seam = signed_min(*seams)
        trim = np.full(n, FAR)
        if self.trim:
            w = float(self.trim.get("width", 0.05)) * s * 0.5
            for side, sx in (("L", 1.0), ("R", -1.0)):
                l_s, frac, on_leg = legs[side]
                for band in self.trim.get("leg_bands", []):
                    trim = signed_min(trim, np.where(on_leg, np.abs(frac - float(band)) * self.leg_len[side] - w, FAR))
        return trim, seam, edge


class Belt(Garment):
    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.mz = model, mz
        self.label = B.L_BOOT
        self.z0 = float(spec.get("waist", 0.075)) * s - 0.018 * s
        self.R = model.skel.rest["hips"]

    def sdf(self, P, d_base):
        s, mz = self.m.s, self.mz
        h = mz.h(P)
        band = np.maximum(d_base - 0.0105 * s, np.abs(h - self.z0) - 0.017 * s)
        band = np.maximum(band, np.maximum(mz.in_arm(P, "L"), mz.in_arm(P, "R")) + 0.01 * s)
        q = (P - mz.pel) @ self.R
        buckle = np.maximum(np.maximum(np.abs(q[:, 0]) - 0.026 * s, np.abs(h - self.z0) - 0.022 * s), d_base - 0.016 * s)
        buckle = np.where(q[:, 2] > 0.03 * s, buckle, 1.0)
        return np.minimum(band, buckle), np.full(len(P), B.L_BOOT, np.int16)


class Strap(Garment):
    """Suspenders: two straps from the waistband up over the shoulders, crossing in a Y at the
    back; a few millimetres proud of whatever the torso wears."""

    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.mz, self.spec = model, mz, spec
        self.kind = "strap"
        self.label = {"leather": B.L_BOOT, "canvas": B.L_CANVAS, "cord": B.L_CORD}.get(spec.get("type", "leather"), B.L_BOOT)
        self.x0 = float(spec.get("x", 0.068)) * s
        self.w = float(spec.get("width", 0.030)) * s * 0.5
        self.waist = float(spec.get("waist", 0.07)) * s
        self.trunk = TrunkFrame(model)
        sk = model.skel
        self.top_h = float(mz.h(np.array([sk.head["neck"]]))[0])

    def _band(self, P):
        s = self.m.s
        h = self.mz.h(P)
        q, _ = self.trunk.local(P)
        back = q[:, 2] < 0.0
        # at the back the straps run in to a Y between the shoulder blades
        x0 = np.where(back, self.x0 * np.clip((h - self.waist - 0.10 * s) / (0.22 * s), 0.0, 1.0), self.x0)
        band = np.abs(np.abs(q[:, 0]) - x0) - self.w
        band = np.maximum(band, self.waist - h)
        band = np.maximum(band, h - (self.top_h + 0.04 * s))
        arms = np.maximum(self.mz.in_arm(P, "L"), self.mz.in_arm(P, "R"))
        return np.maximum(band, arms + 0.01 * s)

    def sdf(self, P, d_base):
        s = self.m.s
        d = np.maximum(d_base - 0.0105 * s, self._band(P))
        return d, np.full(len(P), self.label, np.int16)

    def fields(self, P):
        n = len(P)
        edge = -self._band(P)
        return np.full(n, FAR), np.full(n, FAR), np.maximum(edge, 0.0001)


class Tie(Garment):
    """A necktie lying down the shirt front from the knot at the collar to the belt."""

    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.mz, self.spec = model, mz, spec
        self.kind = "tie"
        self.label = B.L_TIE
        sk = model.skel
        self.trunk = TrunkFrame(model)
        self.top_h = float(mz.h(np.array([sk.head["neck"]]))[0]) - 0.012 * s
        self.bottom = float(spec.get("bottom", 0.10)) * s
        self.slack = float(spec.get("loose", 0.0))
        self.knot = model.T("chest", 0.0, 0.222, 0.082)

    def _shape(self, P):
        s = self.m.s
        h = self.mz.h(P)
        q, _ = self.trunk.local(P)
        t = np.clip((self.top_h - h) / max(self.top_h - self.bottom, 1e-3), 0.0, 1.0)
        # a loosened knot hangs off-centre
        x = q[:, 0] - self.slack * 0.02 * s * t
        w = (0.018 + 0.026 * t) * s
        shape = np.abs(x) - w
        tip = (self.bottom - h) + np.abs(x) * 0.9
        shape = np.maximum(shape, tip)
        shape = np.maximum(shape, h - self.top_h)
        shape = np.where(q[:, 2] > 0.0, shape, 1.0)
        return shape

    def sdf(self, P, d_base):
        s = self.m.s
        d = np.maximum(d_base - 0.0115 * s, self._shape(P))
        knot = S_ellipsoid(P, self.knot, np.array([0.016, 0.012, 0.018]) * s, self.m.skel.rest["chest"])
        return np.minimum(d, knot), np.full(len(P), self.label, np.int16)

    def fields(self, P):
        n = len(P)
        return np.full(n, FAR), np.full(n, FAR), np.maximum(-self._shape(P), 0.0001)


class Mantle(Garment):
    """The Ashen's fur mantle: a shaggy ring of pelt over the shoulders and the upper back."""

    def __init__(self, model, spec: dict, mz):
        s = model.s
        self.m, self.mz, self.spec = model, mz, spec
        self.kind = "fur"
        self.label = B.L_FUR
        sk = model.skel
        self.axis = [sk.head["chest"], sk.head["neck"], sk.tail["neck"]]
        self.low = float(spec.get("low", 0.20)) * s           # how far down the chest it hangs
        self.reach = float(spec.get("reach", 0.21)) * s       # out over the shoulders
        self.n_c, self.n_ax = model.cuts["neck"]
        self.chest_h = float(mz.h(np.array([sk.head["chest"]]))[0])
        self.neck_h = float(mz.h(np.array([sk.head["neck"]]))[0])

    def _region(self, P):
        s = self.m.s
        m = self.m
        h = self.mz.h(P)
        d_ax = B.polyline_dist(P, self.axis)
        rag = m.noise.fbm(P, 9.0, 3) * 0.035 * s
        reg = np.maximum((self.neck_h - self.low) - h + rag, d_ax - self.reach + rag)
        reg = np.maximum(reg, (P - self.n_c) @ self.n_ax + 0.012 * s)
        return reg

    def sdf(self, P, d_base):
        s = self.m.s
        m = self.m
        clumps = np.maximum(m.noise.fbm(P * np.array([1.0, 1.0, 0.6]), 30.0, 3), -0.3) * 0.006 * s
        d = d_base - (0.022 * s + clumps)
        return np.maximum(d, self._region(P)), np.full(len(P), self.label, np.int16)

    def fields(self, P):
        n = len(P)
        return np.full(n, FAR), np.full(n, FAR), np.minimum(self._region(P), -0.0001)


def S_ellipsoid(P, c, radii, R):
    from .char_sdf import sd_ellipsoid
    return sd_ellipsoid(P, c, radii, R @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]]))


def make(model, spec: dict, mz, part: str) -> Garment:
    if part == "top":
        return Top(model, spec, mz)
    if part == "collar":
        return Collar(model, spec, mz)
    if part == "pants":
        return Pants(model, spec, mz)
    if part == "belt":
        return Belt(model, spec, mz)
    raise KeyError(part)


def garment_fields(model, V: np.ndarray, labels_v: np.ndarray):
    """Per-vertex (trim, seam, edge) from the garment each vertex wears: among the garments made of
    the vertex's material, the one whose surface it lies on (smallest |sdf|)."""
    n = len(V)
    trim, seam, edge = np.full(n, FAR), np.full(n, FAR), np.full(n, FAR)
    if not model.garments or n == 0:
        return trim, seam, edge
    db, _ = model.base.eval(V)
    ds, _ = model.skin.eval(V)
    db = np.minimum(db, B.S.smin(db, ds + 0.0025 * model.s, 0.006 * model.s))
    best = np.full(n, 1e9)
    for g in model.garments:
        mine = labels_v == g.label
        if not mine.any():
            continue
        idx = np.nonzero(mine)[0]
        dg, _ = g.sdf(V[idx], db[idx])
        closer = np.abs(dg) < best[idx]
        if not closer.any():
            continue
        take = idx[closer]
        t, sm, e = g.fields(V[take])
        trim[take], seam[take], edge[take] = t, sm, e
        best[take] = np.abs(dg[closer])
    return trim, seam, edge
