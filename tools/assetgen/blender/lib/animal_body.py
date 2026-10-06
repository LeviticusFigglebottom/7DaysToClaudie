"""Quadruped bodies (ADR-0027): signed-distance anatomy on the quadruped skeleton (animal_skel),
meshed with the character pipeline's surface nets, decimated to a budget, skinned by bone
distance with smoothing, UV-mapped for fur flow, coat masks and baked AO in vertex colour.

One mesh object per part, all skinned to `Armature`:
  body            the animal (fur, hooves or claws, the wet nose pad)
  ears            both ears (meshed finer: thin cartilage cupped forward)
  eyes            two glossy eyes
  antlers         a buck's rack (bone; rigid on the head)
Vertex colour (the fur shader, game/assets/shaders/fur.gdshader): R = baked AO, G = the pale
coat (belly, throat, rump patch, tail underside, inner ear), B = the dark coat (nose, the face's
V, ear rims, tail top, hoof bands); A = 1. UVs are metres around and along each part's axis, so
the strand texture's V runs head to tail on the body, down the legs and out along the ears.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np

from . import animal_skel as AS
from . import char_mesh as M
from . import char_sdf as S
from . import common, vcolor

L_FUR, L_HOOF, L_NOSE, L_MOUTH = 0, 1, 2, 3


X_AX = np.array([1.0, 0.0, 0.0])


def _n(v):
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _frame(w, front_hint):
    """Rotation (columns u, v, w): w along the axis, v towards front_hint (orthogonalised)."""
    w = _n(w)
    v = _n(np.asarray(front_hint, dtype=np.float64) - w * float(np.dot(front_hint, w)))
    u = np.cross(v, w)
    return np.stack([u, v, w], axis=1)


class Animal:
    """Shape programs for one animal (rest pose)."""

    def __init__(self, skel, p: dict):
        self.sk = skel
        self.p = p
        self.j = skel.j
        self.s = float(p.get("scale", 1.0))
        self.species = p.get("species", "deer")
        self.noise = S.Noise(int(p.get("seed", 1)))
        self.body = S.Program(L_FUR)
        self.ears = S.Program(L_FUR)
        self.antlers = S.Program(L_FUR)
        self.eye_c: list[np.ndarray] = []
        self.eye_r = 0.0
        if self.species == "deer":
            self._deer()
        else:
            self._hare()

    # --- helpers ------------------------------------------------------------------------
    def P(self, x, y, z):
        return np.array([x, y, z], dtype=np.float64) * self.s

    def mid(self, a, b, t=0.5):
        return self.j[a] * (1 - t) + self.j[b] * t

    def _limb(self, prog, a, b, r1, r2, k, label=L_FUR, squash=1.0, up=(0.0, -1.0, 0.0)):
        prog.cone(a, b, r1 * self.s, r2 * self.s, k=k * self.s, label=label, squash=squash, up_hint=up)

    def _ell(self, prog, c, radii, R=None, k=0.0, label=L_FUR, mode="union"):
        prog.ellipsoid(c, np.asarray(radii) * self.s, R=R, k=k * self.s, label=label, mode=mode)

    def _hoof(self, side, fet, toe, size, ground=True):
        """Cloven hoof: two toes either side of a cleft, a pastern down to them, dewclaws."""
        s = self.s
        fet, toe = self.j[fet], self.j[toe]
        sx = 1.0 if side == "L" else -1.0
        axis = _n(toe - fet)
        coronet = fet + (toe - fet) * 0.45
        self._limb(self.body, fet, coronet, 0.017 * size, 0.0155 * size, 0.012)
        fwd = _n(np.array([0.0, toe[1] - fet[1], 0.0]))
        for t in (-1.0, 1.0):
            off = np.array([t * 0.0115 * size * s, 0.0, 0.0])
            c = toe + (coronet - toe) * 0.42 + off + np.array([0, 0, 0.004 * s])
            R = _frame(_n(toe - coronet + np.array([0, 0, -0.01])), (sx * t, 0.0, 0.0))
            self._ell(self.body, c, (0.0115 * size, 0.0105 * size, 0.034 * size), R=R, k=0.004, label=L_HOOF)
        # the cleft, and a flat sole on the ground
        cl = toe + (coronet - toe) * 0.3
        self.body.box(cl, np.array([0.0014, 0.04, 0.03]) * s * size, R=_frame(fwd, (0, 0, 1)), k=0.002 * s, mode="sub")
        if ground:
            self.body.box(toe + np.array([0, 0, -0.05 * s]), np.array([0.06, 0.08, 0.05]) * s, mode="sub", k=0.003 * s)
        # dewclaws behind the fetlock
        back = -fwd
        for t in (-1.0, 1.0):
            a = fet + back * 0.02 * s * size + np.array([t * 0.012 * s * size, 0, -0.018 * s])
            b = a + back * 0.008 * s + np.array([0, 0, -0.012 * s])
            self.body.cone(a, b, 0.0065 * s * size, 0.0035 * s * size, k=0.004 * s, label=L_HOOF)
        del axis

    # --- deer -----------------------------------------------------------------------------
    def _deer(self):
        j, s, b = self.j, self.s, self.body
        bulk = float(self.p.get("bulk", 1.0))       # a buck's neck and brisket in the rut
        # trunk: ribcage, belly, loin, rump, withers, brisket
        self._ell(b, self.P(0, -0.15, 0.80), (0.150, 0.30, 0.238))
        self._ell(b, self.P(0, 0.10, 0.80), (0.146, 0.27, 0.190), k=0.08)
        self._ell(b, self.P(0, 0.24, 0.885), (0.122, 0.20, 0.105), k=0.06)
        self._ell(b, self.P(0, 0.405, 0.862), (0.128, 0.165, 0.150), k=0.07)
        self._ell(b, self.P(0, -0.30, 0.95), (0.070, 0.15, 0.085), k=0.06)
        self._ell(b, self.P(0, -0.385, 0.80), (0.105 * bulk, 0.10, 0.135), k=0.07)
        # the flank tucks up in front of the stifle; the belly line lifts towards the groin
        self._ell(b, self.P(0, 0.235, 0.615), (0.30, 0.11, 0.065), k=0.05, mode="sub")
        for side, sx in (("L", 1.0), ("R", -1.0)):
            # shoulder blade and its muscle, the haunch
            sc = self.mid(f"scap0.{side}", f"shoulder.{side}", 0.45) + self.P(sx * 0.012, 0, 0)
            R = _frame(j[f"shoulder.{side}"] - j[f"scap0.{side}"], (0, -1, 0))
            self._ell(b, sc, (0.046, 0.090, 0.14), R=R, k=0.08)
            hc = self.mid(f"hip.{side}", f"stifle.{side}", 0.45) + self.P(sx * 0.004, 0.035, 0)
            R = _frame(j[f"stifle.{side}"] - j[f"hip.{side}"], (0, 1, 0))
            self._ell(b, hc, (0.070, 0.145, 0.20), R=R, k=0.09)
            # front leg: upper arm muscle, forearm, carpus, cannon
            self._limb(b, j[f"shoulder.{side}"], j[f"elbow.{side}"], 0.066, 0.046, 0.04)
            self._ell(b, self.mid(f"elbow.{side}", f"carpus.{side}", 0.22), (0.040, 0.045, 0.085), k=0.03)
            self._limb(b, j[f"elbow.{side}"], j[f"carpus.{side}"], 0.040, 0.021, 0.025)
            b.sphere(j[f"carpus.{side}"] + self.P(0, -0.004, 0), 0.0235 * s, k=0.012 * s)
            self._limb(b, j[f"carpus.{side}"], j[f"fetlock_f.{side}"], 0.0185, 0.016, 0.01, squash=1.25)
            b.sphere(j[f"fetlock_f.{side}"] + self.P(0, 0.004, 0.004), 0.020 * s, k=0.01 * s)
            self._hoof(side, f"fetlock_f.{side}", f"toe_f.{side}", 1.0)
            # hind leg: femur under the haunch, gaskin with its calf, hock and point, cannon
            self._limb(b, j[f"hip.{side}"], j[f"stifle.{side}"], 0.075, 0.058, 0.05)
            self._limb(b, j[f"stifle.{side}"], j[f"hock.{side}"], 0.056, 0.026, 0.03)
            self._ell(b, self.mid(f"stifle.{side}", f"hock.{side}", 0.32) + self.P(0, 0.018, 0), (0.038, 0.050, 0.085), k=0.03)
            b.sphere(j[f"hock.{side}"], 0.025 * s, k=0.012 * s)
            hb = j[f"hock.{side}"] + self.P(0, 0.028, 0.012)
            b.capsule(hb, j[f"hock.{side}"] + self.P(0, 0.0, -0.03), 0.014 * s, k=0.012 * s)
            self._limb(b, j[f"hock.{side}"], j[f"fetlock_h.{side}"], 0.020, 0.0165, 0.012, squash=1.3)
            b.sphere(j[f"fetlock_h.{side}"] + self.P(0, 0.004, 0.004), 0.020 * s, k=0.01 * s)
            self._hoof(side, f"fetlock_h.{side}", f"toe_h.{side}", 1.02)
        # neck: deep front to back, a throat under it, the mane line on top
        self._limb(b, self.P(0, -0.33, 0.92), j["neck1"], 0.118 * bulk, 0.076 * bulk, 0.09, squash=1.3)
        self._limb(b, j["neck1"], j["head0"] + self.P(0, -0.02, -0.02), 0.076 * bulk, 0.060, 0.06, squash=1.25)
        self._ell(b, self.mid("neck0", "neck1", 0.6) + self.P(0, -0.05, -0.04), (0.055 * bulk, 0.06, 0.11), k=0.05,
                  R=_frame(j["neck1"] - j["neck0"], (0, -1, 0)))
        # head, built in its own frame: f forward along the skull, u up, x out
        h0 = j["head0"]
        f_ax = _n(j["nose"] - h0)
        u_ax = _n(np.cross(f_ax, X_AX))
        u_ax = u_ax if u_ax[2] > 0 else -u_ax
        Rh = np.stack([X_AX, u_ax, f_ax], axis=1)

        def H(x, u, f):
            return h0 + (X_AX * x + u_ax * u + f_ax * f) * s
        self.H = H
        self._ell(b, H(0, 0.004, 0.062), (0.068, 0.070, 0.088), R=Rh, k=0.04)                     # cranium
        self._limb(b, H(0, 0.000, 0.10), H(0, -0.012, 0.242), 0.060, 0.038, 0.05, squash=0.84)    # muzzle
        self._ell(b, H(0, -0.048, 0.105), (0.040, 0.036, 0.095), R=Rh, k=0.04)                     # jaw and jowl
        self._ell(b, H(0, -0.034, 0.225), (0.028, 0.026, 0.040), R=Rh, k=0.025)                    # lips
        for sx in (1.0, -1.0):
            self._ell(b, H(sx * 0.040, -0.030, 0.085), (0.026, 0.038, 0.050), R=Rh, k=0.03)        # cheek
            self._ell(b, H(sx * 0.052, 0.040, 0.050), (0.018, 0.013, 0.028), R=Rh, k=0.018)       # brow
        nose_c = H(0, -0.010, 0.268)
        self.nose_c = nose_c
        b.sphere(nose_c, 0.026 * s, k=0.016 * s)
        for sx in (1.0, -1.0):
            b.ellipsoid(H(sx * 0.0125, -0.004, 0.284), np.array([0.0055, 0.0075, 0.009]) * s, R=Rh, k=0.003 * s, mode="sub")
            b.capsule(H(sx * 0.004, -0.052, 0.252), H(sx * 0.032, -0.044, 0.190), 0.0032 * s, k=0.003 * s, mode="sub",
                      label=L_MOUTH)
        # eye sockets (the eyes are their own mesh, set into them)
        self.eye_r = 0.0172 * s
        for sx in (1.0, -1.0):
            c = H(sx * 0.0625, 0.016, 0.048)
            self.eye_c.append(c)
            b.sphere(c + X_AX * sx * 0.002 * s, self.eye_r * 1.04, k=0.005 * s, mode="sub")
        # tail: broad and flat, held down
        R = _frame(j["tail1"] - j["tail0"], (0, 0, 1))
        self._ell(b, self.mid("tail0", "tail1", 0.55), (0.048, 0.020, 0.090), R=R, k=0.03)
        # skin over muscle: a faint low-frequency unevenness
        lo, hi = b.bounds()
        nz = self.noise
        b.displace(lambda Q: 0.0016 * s * nz.fbm(Q, 9.0 / s, 2), lo, hi)
        self._deer_ears()
        if self.p.get("antlers"):
            self._antlers(self.p["antlers"])

    def _deer_ears(self):
        s = self.s
        for side, sx in (("L", 1.0), ("R", -1.0)):
            a, c = self.j[f"ear0.{side}"], self.j[f"ear1.{side}"]
            w = c - a
            front = np.array([sx * 0.35, -1.0, 0.15])
            R = _frame(w, front)
            ln = float(np.linalg.norm(w))
            mid = a + w * 0.5
            self._ell(self.ears, mid + w * 0.04, (0.046, 0.011, ln * 0.56 / s), R=R)
            # cupped forward: hollow out the front face, leaving a rim
            self._ell(self.ears, mid + R[:, 1] * 0.0115 * s + w * 0.08, (0.038, 0.0115, ln * 0.47 / s), R=R, mode="sub", k=0.003)
            # the base rolls into a tube where it meets the head
            self.ears.cone(a - w * 0.08, a + w * 0.22, 0.014 * s, 0.012 * s, k=0.008 * s)

    def _antlers(self, spec: dict):
        """A typical white-tail rack: main beams sweeping out, back, then forward, a brow tine
        and `tines` points rising off each beam; burrs and pearling at the base."""
        s = self.s * float(spec.get("size", 1.0))
        tines = int(spec.get("tines", 3))
        A = self.antlers
        nz = self.noise
        for sx in (1.0, -1.0):
            def q(x, y, z, sx=sx):
                # offsets from the pedicle scale with the rack's size; the pedicle stays on the skull
                base = np.array([sx * 0.030, -0.622, 1.414])
                return (base + (np.array([sx * x, y, z]) - base) * (s / self.s)) * self.s
            beam = [q(0.030, -0.622, 1.414), q(0.090, -0.575, 1.495), q(0.158, -0.538, 1.560), q(0.205, -0.580, 1.610),
                    q(0.205, -0.668, 1.655), q(0.160, -0.752, 1.680), q(0.098, -0.795, 1.682)]
            radii = [0.0175, 0.0160, 0.0145, 0.0128, 0.0108, 0.0088, 0.0062]
            for i in range(len(beam) - 1):
                A.cone(beam[i], beam[i + 1], radii[i] * s, radii[i + 1] * s, k=0.006 * s)
            # burr: a knobbly ring at the pedicle
            ax = _n(beam[1] - beam[0])
            R = _frame(ax, (0, 0, 1))
            c0 = beam[0] + ax * 0.008 * s
            A.union(lambda Q, c0=c0, R=R: S.sd_torus(Q, c0, 0.0185 * s, 0.0055 * s, R=R),
                    c0 - 0.03 * s, c0 + 0.03 * s, k=0.004 * s)
            # brow tine
            A.cone(beam[1], q(0.082, -0.600, 1.590), 0.0085 * s, 0.0038 * s, k=0.005 * s)
            # points off the beam
            pts = [(3, q(0.218, -0.600, 1.775)), (4, q(0.196, -0.700, 1.810)), (5, q(0.140, -0.785, 1.790))][:tines]
            for i, tip in pts:
                base = beam[i]
                A.cone(base, tip, radii[i] * 0.85 * s, 0.0036 * s, k=0.006 * s)
        lo, hi = A.bounds()
        # pearling: rough near the base, polished towards the tips
        A.displace(lambda Q: 0.0012 * s * nz.noise(Q, 160.0) * np.clip((1.68 * self.s - Q[:, 2]) / (0.2 * self.s), 0.2, 1.0), lo, hi)

    # --- hare -----------------------------------------------------------------------------
    def _hare(self):
        j, s, b = self.j, self.s, self.body
        # a round body, deep haunches, a short neck under a big head
        self._ell(b, self.P(0, -0.035, 0.195), (0.060, 0.105, 0.072))
        self._ell(b, self.P(0, 0.085, 0.205), (0.066, 0.100, 0.082), k=0.05)
        self._ell(b, self.P(0, -0.105, 0.175), (0.045, 0.045, 0.060), k=0.04)
        for side, sx in (("L", 1.0), ("R", -1.0)):
            hc = self.mid(f"hip.{side}", f"stifle.{side}", 0.4) + self.P(sx * 0.008, 0.02, 0.01)
            R = _frame(j[f"stifle.{side}"] - j[f"hip.{side}"], (0, 1, 0))
            self._ell(b, hc, (0.040, 0.060, 0.075), R=R, k=0.03)
            self._limb(b, j[f"stifle.{side}"], j[f"hock.{side}"], 0.026, 0.012, 0.015)
            # the long hind foot, its furred sole flat on the ground
            self._limb(b, j[f"hock.{side}"], j[f"fetlock_h.{side}"], 0.012, 0.0115, 0.008, squash=0.8, up=(0, 0, 1))
            self._limb(b, j[f"fetlock_h.{side}"], j[f"toe_h.{side}"], 0.0118, 0.0085, 0.006, squash=0.75, up=(0, 0, 1))
            # front legs: slim, short
            self._limb(b, j[f"shoulder.{side}"], j[f"elbow.{side}"], 0.020, 0.014, 0.015)
            self._limb(b, j[f"elbow.{side}"], j[f"carpus.{side}"], 0.012, 0.0085, 0.01)
            self._limb(b, j[f"carpus.{side}"], j[f"fetlock_f.{side}"], 0.0085, 0.0085, 0.005)
            self._limb(b, j[f"fetlock_f.{side}"], j[f"toe_f.{side}"], 0.0088, 0.0072, 0.004, squash=0.75, up=(0, 0, 1))
        b.box(self.P(0, 0, -0.05), np.array([0.2, 0.4, 0.05]) * s, mode="sub", k=0.002 * s)
        # head: rounded skull, a blunt muzzle with the split lip, whisker pads
        self._limb(b, j["neck0"], j["head0"], 0.040, 0.036, 0.03)
        self._ell(b, self.P(0, -0.185, 0.248), (0.034, 0.048, 0.037), k=0.025,
                  R=_frame(j["nose"] - j["head0"], (0, 0, 1)))
        self._limb(b, self.P(0, -0.200, 0.238), self.P(0, -0.240, 0.218), 0.027, 0.0165, 0.02, squash=0.9)
        for sx in (1.0, -1.0):
            self._ell(b, self.P(sx * 0.010, -0.236, 0.207), (0.011, 0.012, 0.010), k=0.006)   # whisker pad
            self._ell(b, self.P(sx * 0.023, -0.198, 0.232), (0.016, 0.022, 0.020), k=0.012)    # cheek
        b.sphere(self.P(0, -0.2475, 0.221), 0.0065 * s, k=0.005 * s)
        b.capsule(self.P(0, -0.247, 0.214), self.P(0, -0.243, 0.204), 0.0016 * s, mode="sub", label=L_MOUTH)
        self.eye_r = 0.0095 * s
        for sx in (1.0, -1.0):
            c = self.P(sx * 0.0285, -0.184, 0.262)
            self.eye_c.append(c)
            b.sphere(c + self.P(sx * 0.001, 0, 0), self.eye_r * 1.03, k=0.003 * s, mode="sub")
        # cotton tail
        b.sphere(self.mid("tail0", "tail1", 0.6), 0.019 * s, k=0.012 * s)
        lo, hi = b.bounds()
        nz = self.noise
        b.displace(lambda Q: 0.0008 * s * nz.fbm(Q, 30.0 / s, 2), lo, hi)
        for side, sx in (("L", 1.0), ("R", -1.0)):
            a, c = self.j[f"ear0.{side}"], self.j[f"ear1.{side}"]
            w = c - a
            R = _frame(w, (sx * 0.5, -1.0, 0.0))
            ln = float(np.linalg.norm(w))
            mid = a + w * 0.52
            self._ell(self.ears, mid, (0.0165, 0.0055, ln * 0.60 / s), R=R)
            self._ell(self.ears, mid + R[:, 1] * 0.0058 * s + w * 0.03, (0.0128, 0.0058, ln * 0.52 / s), R=R, mode="sub", k=0.0015)
            self.ears.cone(a - w * 0.06, a + w * 0.2, 0.008 * s, 0.0075 * s, k=0.004 * s)

    # --- coat ----------------------------------------------------------------------------
    def coat(self, V, N, part: str):
        """(pale, dark) masks 0..1 per vertex (rest pose)."""
        j, s = self.j, self.s
        nz = self.noise
        pale = np.zeros(len(V))
        dark = np.zeros(len(V))
        y, z = V[:, 1], V[:, 2]
        brk = nz.fbm(V, 40.0 / s, 2) * 0.12        # a soft, broken line where colours meet
        def ss(e0, e1, x):
            t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
            return t * t * (3 - 2 * t)
        if part == "ears":
            # pale, furred inside the cup; dark rims and tips
            a_l, a_r = j["ear0.L"], j["ear0.R"]
            for side, a in (("L", a_l), ("R", a_r)):
                c = j[f"ear1.{side}"]
                w = _n(c - a)
                sx = 1.0 if side == "L" else -1.0
                front = _n(np.array([sx * 0.35, -1.0, 0.15]) - w * float(np.dot((sx * 0.35, -1.0, 0.15), w)))
                mine = (V[:, 0] * sx) > 0
                inside = ss(0.1, 0.6, N @ front) * mine
                t = ((V - a) @ w) / max(float(np.linalg.norm(c - a)), 1e-6)
                pale = np.maximum(pale, inside * (0.75 if self.species == "deer" else 0.35))
                tip = ss(0.82, 0.97, t) * mine
                dark = np.maximum(dark, tip * (0.6 if self.species == "deer" else 1.0))
            return np.clip(pale, 0, 1), np.clip(dark, 0, 1)
        if self.species == "deer":
            belly = ss(-0.15, -0.65, N[:, 2]) * ss(0.86 * s, 0.70 * s, z) * (y > -0.42 * s) * (y < 0.48 * s)
            inner_leg = ss(0.2, 0.7, -N[:, 0] * np.sign(V[:, 0] + 1e-9)) * ss(0.72 * s, 0.5 * s, z) * (z > 0.12 * s)
            throat = ss(0.035 * s, 0.0, np.abs(V[:, 0])) * ss(-0.2, -0.75, N[:, 1] - 0.4 * N[:, 2]) * \
                ss(1.02 * s, 1.10 * s, z) * ss(1.28 * s, 1.22 * s, z) * (y < -0.45 * s)
            h0, f_ax = j["head0"], _n(j["nose"] - j["head0"])
            hf = (V - h0) @ f_ax / s
            hr = np.sqrt(np.maximum(((V - h0) ** 2).sum(-1) / (s * s) - hf * hf, 0.0))
            on_head = (hf > 0.0) & (hr < 0.09)
            chin = on_head * (hf > 0.12) * ss(-0.1, -0.6, N @ np.cross(f_ax, X_AX) * -1.0)
            muzzle_band = ss(0.012, 0.0, np.abs(hf - 0.228) - 0.010) * on_head
            eye_ring = np.zeros(len(V))
            for c in self.eye_c:
                d = np.sqrt(((V - c) ** 2).sum(-1))
                eye_ring = np.maximum(eye_ring, ss(0.034 * s, 0.022 * s, d))
            rump = ss(0.45 * s, 0.55 * s, y) * ss(0.70 * s, 0.82 * s, z) * ss(0.3, -0.2, np.abs(N[:, 0]) - 0.35)
            tail_under = ss(0.5 * s, 0.56 * s, y) * ss(0.1, -0.5, N[:, 2]) * (z > 0.74 * s)
            pale = np.maximum.reduce([belly, inner_leg * 0.7, throat, chin * 0.9, muzzle_band * 0.85, eye_ring * 0.9,
                                      rump * 0.55, tail_under])
            nose = ss(0.036 * s, 0.026 * s, np.sqrt(((V - self.nose_c) ** 2).sum(-1)))
            face_v = ss(0.02 * s, 0.0, np.abs(V[:, 0]) - (0.034 - (hf - 0.08) * 0.12) * s) * on_head * \
                (hf > 0.08) * (hf < 0.215) * ss(0.0, 0.5, N[:, 2]) * 0.55
            tail_top = ss(0.58 * s, 0.66 * s, y) * ss(-0.1, 0.5, N[:, 2]) * (z > 0.74 * s) * 0.8
            hoof_band = ss(0.10 * s, 0.07 * s, z) * 0.7
            preorbital = np.zeros(len(V))
            for c in self.eye_c:
                g = c + self.P(0, -0.022, -0.010)
                preorbital = np.maximum(preorbital, ss(0.014 * s, 0.004 * s, np.sqrt(((V - g) ** 2).sum(-1))) * 0.8)
            dorsal = ss(0.02 * s, 0.0, np.abs(V[:, 0])) * ss(0.6, 0.95, N[:, 2]) * (y > -0.45 * s) * (y < 0.5 * s) * 0.3
            dark = np.maximum.reduce([nose, face_v, tail_top, hoof_band, preorbital, dorsal])
        else:
            belly = ss(-0.1, -0.6, N[:, 2]) * ss(0.21 * s, 0.15 * s, z)
            chin = ss(0.215 * s, 0.195 * s, z) * (y < -0.18 * s) * ss(-0.1, -0.6, N[:, 2])
            tail = ss(0.03 * s, 0.0, np.sqrt(((V - self.mid("tail0", "tail1", 0.6)) ** 2).sum(-1)) - 0.012 * s) * \
                ss(0.4, -0.3, N[:, 2])
            eye_ring = np.zeros(len(V))
            for c in self.eye_c:
                d = np.sqrt(((V - c) ** 2).sum(-1))
                eye_ring = np.maximum(eye_ring, ss(0.018 * s, 0.011 * s, d))
            feet = ss(0.02 * s, 0.006 * s, z) * 0.6
            pale = np.maximum.reduce([belly, chin * 0.9, tail, eye_ring * 0.85, feet])
            nose = ss(0.010 * s, 0.004 * s, np.sqrt(((V - self.P(0, -0.247, 0.221)) ** 2).sum(-1)))
            dorsal = ss(0.6, 0.95, N[:, 2]) * (y > -0.15 * s) * 0.35
            dark = np.maximum(nose, dorsal)
        pale = np.clip(pale + brk * (pale > 0.05) * (pale < 0.95), 0, 1)
        return pale, np.clip(dark, 0, 1)


# --------------------------------------------------------------------------------------------
# Meshing
# --------------------------------------------------------------------------------------------

def mesh_program(prog: S.Program, name: str, h: float, tris: int, pad: float = 0.02):
    lo, hi = prog.bounds()
    lo = lo - pad
    hi = hi + pad
    shape = tuple(int(x) for x in np.ceil((hi - lo) / h) + 1)
    d, _ = prog.eval_grid(lo, h, shape)
    V, Q = M.surface_nets(d, lo, h)
    del d
    V = M.project_to_surface(V, lambda P: prog.eval(P)[0], h, iterations=2)
    obj = M.mesh_from_arrays(name, V, Q)
    M.remove_small_islands(obj)
    M.decimate(obj, tris)
    return obj


def label_faces(prog: S.Program, obj) -> np.ndarray:
    C = M.face_centers(obj)
    Nf = M.face_normals(obj)
    _, lab = prog.eval(C - Nf * 0.0006)
    return lab


def eye_mesh(centres, r: float, name: str = "eyes"):
    bm = bmesh.new()
    for c in centres:
        geom = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=r)
        vs = [g for g in geom["verts"]]
        bmesh.ops.translate(bm, vec=tuple(c), verts=vs)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = common.new_object(name, me)
    return obj


# --------------------------------------------------------------------------------------------
# Skinning
# --------------------------------------------------------------------------------------------

def _seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.sqrt(((P - (a + t[:, None] * ab)) ** 2).sum(-1))


def _adjacency(obj):
    me = obj.data
    E = np.zeros(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", E)
    return E.reshape(-1, 2)


def body_weights(skel, V, obj, part: str):
    """(n_verts, n_bones) weights: inverse distance to each bone's segment (opposite-side legs,
    ears, the tail away from the rump and the root are excluded), top four, smoothed over the
    mesh so joints bend in a broad crease rather than a seam."""
    names = skel.names
    nb = len(names)
    D = np.full((len(V), nb), np.inf)
    s = float(skel.params.get("scale", 1.0))
    for bi, bn in enumerate(names):
        if bn == "root":
            continue
        if part == "body" and bn.startswith("ear."):
            continue
        if part == "ears" and not (bn.startswith("ear.") or bn == "head"):
            continue
        d = _seg_dist(V, skel.head[bn], skel.tail[bn])
        side = AS.side_of(bn)
        if side != 0.0:
            d = np.where(V[:, 0] * side < -0.004 * s, np.inf, d)
        if bn == "tail":
            d = np.where(V[:, 1] < skel.head["tail"][1] - 0.02 * s, np.inf, d)
        if bn == "jaw":
            d = np.where(V[:, 2] > skel.head["jaw"][2] + 0.004 * s, np.inf, d * 1.4)
        # the trunk's skin behind the elbow and before the stifle stays with the trunk: limbs
        # swinging under it would otherwise drag the flank into a crease
        if bn.startswith("upper_arm"):
            d = d * (1.0 + 3.5 * np.clip((V[:, 1] - skel.j["elbow" + bn[-2:]][1]) / (0.12 * s), 0.0, 1.0))
        if bn.startswith("thigh"):
            d = d * (1.0 + 2.5 * np.clip((skel.j["stifle" + bn[-2:]][1] - V[:, 1]) / (0.12 * s), 0.0, 1.0))
            # the rump over the hip joint belongs to the pelvis, not the femur
            d = d * (1.0 + 3.0 * np.clip((V[:, 2] - skel.j["hip" + bn[-2:]][2]) / (0.10 * s), 0.0, 1.0))
        if part == "ears" and bn == "head":
            d = d * 2.5
        D[:, bi] = d
    W = 1.0 / (D + 0.012 * s) ** 4
    W[~np.isfinite(D)] = 0.0
    E = _adjacency(obj)
    for _ in range(8):
        acc = np.zeros_like(W)
        cnt = np.zeros(len(V))
        np.add.at(acc, E[:, 0], W[E[:, 1]])
        np.add.at(acc, E[:, 1], W[E[:, 0]])
        np.add.at(cnt, E[:, 0], 1)
        np.add.at(cnt, E[:, 1], 1)
        W = 0.5 * W / np.maximum(W.sum(1, keepdims=True), 1e-12) + 0.5 * acc / np.maximum(acc.sum(1, keepdims=True), 1e-12)
    # keep the top four
    idx = np.argsort(-W, axis=1)[:, 4:]
    np.put_along_axis(W, idx, 0.0, axis=1)
    W[W < 0.02] = 0.0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    return W


def rigid_weights(skel, n: int, bone: str):
    W = np.zeros((n, len(skel.names)))
    W[:, skel.names.index(bone)] = 1.0
    return W


def apply_skin(obj, arm, skel, W):
    names = skel.names
    for bi, bn in enumerate(names):
        col = W[:, bi]
        nzi = np.nonzero(col > 0)[0]
        if len(nzi) == 0:
            continue
        vg = obj.vertex_groups.new(name=bn)
        vals = np.round(col[nzi], 4)
        for v in np.unique(vals):
            sel = nzi[vals == v]
            vg.add([int(x) for x in sel], float(v), "REPLACE")
    obj.parent = arm
    obj.matrix_parent_inverse.identity()
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True


# --------------------------------------------------------------------------------------------
# UVs: metres around and along each part's axis
# --------------------------------------------------------------------------------------------

def _axes_for(skel, bone: str):
    """(origin, axis, seam direction) of the cylinder a bone's faces are mapped on."""
    j = skel.j
    if bone in ("root", "hips", "spine", "chest", "tail") or bone.startswith("scapula") or bone.startswith("thigh"):
        return j["pelvis"], _n(j["neck0"] - j["pelvis"]), np.array([0.0, 0.0, -1.0])
    if bone in ("neck", "neck2"):
        return j["neck0"], _n(j["head0"] - j["neck0"]), np.array([0.0, -1.0, -0.3])
    if bone in ("head", "jaw"):
        return j["head0"], _n(j["nose"] - j["head0"]), np.array([0.0, 0.0, -1.0])
    side = AS.side_of(bone)
    return skel.head[bone], _n(skel.tail[bone] - skel.head[bone]), np.array([-side, 0.0, 0.0]) + np.array([0, 0.01, 0])


def uv_by_bone(obj, skel, W, radius: float):
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active
    nl = len(me.loops)
    lv = np.zeros(nl, np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.zeros(len(me.polygons), np.int32)
    lt = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    V = M.mesh_arrays(obj)
    fol = np.repeat(np.arange(len(ls)), lt)
    # the face's bone: the strongest weight summed over its corners
    fw = np.zeros((len(ls), W.shape[1]))
    np.add.at(fw, fol, W[lv])
    fbone = np.argmax(fw, axis=1)
    uv = np.zeros((nl, 2))
    for bi in np.unique(fbone):
        sel_f = fbone == bi
        sel_l = sel_f[fol]
        o, a, sd = _axes_for(skel, skel.names[bi])
        sd = _n(sd - a * float(np.dot(sd, a)))
        front = -sd
        side = np.cross(a, front)
        P = V[lv[sel_l]] - o
        x, y = P @ front, P @ side
        ang = np.arctan2(y, x)
        ref = np.repeat(ang[np.searchsorted(np.nonzero(sel_l)[0], ls[sel_f])], lt[sel_f])
        ang = np.where(ang - ref > math.pi, ang - 2 * math.pi, np.where(ang - ref < -math.pi, ang + 2 * math.pi, ang))
        rr = float(np.median(np.sqrt(x * x + y * y))) if len(x) else radius
        uv[sel_l, 0] = ang * rr + bi * 3.7
        uv[sel_l, 1] = P @ a + bi * 1.3
    uvl.data.foreach_set("uv", uv.astype(np.float32).ravel())


def coat_colours(obj, animal: Animal, part: str):
    me = obj.data
    V = M.mesh_arrays(obj)
    Nv = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", Nv)
    Nv = Nv.reshape(-1, 3)
    pale, dark = animal.coat(V, Nv, part)
    lv = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    vcolor.set_channel(obj, 1, lambda co, n, li: float(pale[lv[li]]))
    vcolor.set_channel(obj, 2, lambda co, n, li: float(dark[lv[li]]))
    vcolor.fill_channel(obj, 3, 1.0)
