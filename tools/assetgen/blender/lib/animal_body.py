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
        # the hound's extra parts (None for deer and hare): teeth on the upper jaw (rigid on the
        # head), teeth and tongue on the lower jaw (rigid on the jaw), the Bloom's growths
        self.teeth_upper = None
        self.teeth_lower = None
        self.growths = None
        if self.species == "deer":
            self._deer()
        elif self.species == "hound":
            self._hound()
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

    # --- hound ----------------------------------------------------------------------------
    # A Bloom-infected dog (DESIGN §6): starved to the frame (ribs, spine, hip bones and the
    # point of the shoulder stand out, the flank is sunk behind the last rib, the belly tucked up
    # to the spine), the lips drawn back off the teeth in a fixed snarl, a torn ear, and the
    # Bloom's shelf plates and threads breaking out along the back, over the shoulders and down
    # one flank. params: breed (mongrel / shepherd), bulk (chest and neck), gaunt (0..1), ears
    # (drop / erect), torn_ear (L / R), growth ({spine, shoulder, flank: count, side}).

    def _surface(self, prog, p0, dirn, reach=0.3):
        """First point where a ray from p0 (outside) along dirn enters prog's surface."""
        dirn = _n(dirn)
        ts = np.linspace(0.0, reach * self.s, 241)
        d, _ = prog.eval(p0[None, :] + ts[:, None] * dirn[None, :])
        inside = np.nonzero(d < 0.0)[0]
        if len(inside) == 0:
            return None
        i = int(inside[0])
        if i == 0:
            return p0.copy()
        t0, t1 = ts[i - 1], ts[i]
        for _ in range(12):
            tm = 0.5 * (t0 + t1)
            dm, _ = prog.eval((p0 + tm * dirn)[None, :])
            if dm[0] < 0.0:
                t1 = tm
            else:
                t0 = tm
        return p0 + t1 * dirn

    def _normal(self, prog, p):
        e = 0.0015 * self.s
        off = np.array([[e, 0, 0], [-e, 0, 0], [0, e, 0], [0, -e, 0], [0, 0, e], [0, 0, -e]])
        d, _ = prog.eval(p[None, :] + off)
        return _n(np.array([d[0] - d[1], d[2] - d[3], d[4] - d[5]]))

    def _paw(self, side, fet, toe, size, front):
        """A dog's paw: the metacarpal pad under the knuckles, four toes in an arc with their pads
        and blunt dark claws, a front dewclaw on the inside; the sole flat on the ground."""
        s, b = self.s, self.body
        sx = 1.0 if side == "L" else -1.0
        fet, toe = self.j[fet], self.j[toe]
        fwd = _n(np.array([0.0, toe[1] - fet[1], 0.0]))
        base = np.array([fet[0], fet[1], 0.0])
        q = lambda x, f, z: base + np.array([x * sx, 0.0, 0.0]) * s * size + fwd * f * s * size + np.array([0, 0, z * s * size])  # noqa: E731
        self._ell(b, q(0.0, 0.010, 0.016), (0.022 * size, 0.024 * size, 0.017 * size), k=0.012)
        self._limb(b, fet, q(0.0, 0.012, 0.018), 0.015 * size, 0.019 * size, 0.012)
        R = _frame(fwd, (0, 0, 1))
        for x, f, z in ((0.008, 0.042, 0.011), (-0.008, 0.042, 0.011), (0.021, 0.032, 0.010), (-0.021, 0.032, 0.010)):
            c = q(x, f, z)
            self._ell(b, c, (0.0092 * size, 0.0105 * size, 0.0125 * size), R=_frame(fwd + np.array([0, 0, -0.25]), (0, 0, 1)), k=0.006)
            # the claw: worn blunt, curving down to the ground in front of the toe
            a = c + fwd * 0.008 * s * size + np.array([0, 0, 0.002 * s])
            e = c + fwd * 0.019 * s * size + np.array([0, 0, -0.008 * s * size])
            b.cone(a, e, 0.0042 * s * size, 0.0016 * s * size, k=0.002 * s, label=L_HOOF)
        del R
        if front:
            # dewclaw on the inside of the pastern, a little up off the ground
            c = q(-0.017, -0.006, 0.050)
            b.sphere(c, 0.0065 * s * size, k=0.006 * s)
            b.cone(c + fwd * 0.004 * s, c + fwd * 0.012 * s + np.array([0, 0, -0.007 * s]), 0.003 * s, 0.0012 * s, k=0.0015 * s,
                   label=L_HOOF)
        b.box(base + np.array([0, 0, -0.03 * s]), np.array([0.05, 0.08, 0.03]) * s, mode="sub", k=0.0025 * s)

    def _hound(self):
        j, s, b, p = self.j, self.s, self.body, self.p
        bulk = float(p.get("bulk", 1.0))
        gaunt = float(p.get("gaunt", 1.0))
        shep = p.get("breed") == "shepherd"
        # a living wolf (ADR-0055): the dog's frame in health; no bones showing, no snarl, no Bloom,
        # and a thick double coat over it (ruff, cheeks, breeches, a brush of a tail)
        wolf = p.get("breed") == "wolf"
        nz = self.noise
        sp, ch, pe = j["spine0"], j["chest0"], j["pelvis"]
        # --- trunk: a deep, narrow ribcage, a tight loin, a bony croup
        rib_c = ch + self.P(0, 0.002, -0.106)
        # an egg, deepest at the elbows, its floor rising towards the last ribs
        ax = _n(np.array([0.0, 1.0, 0.34]))
        Rr = np.stack([X_AX, np.cross(ax, X_AX), ax], axis=1)
        self._ell(b, rib_c, (0.095 * bulk, 0.148 * (0.5 + 0.5 * bulk), 0.172), R=Rr)
        self._ell(b, ch + self.P(0, -0.112, -0.118), (0.060 * bulk, 0.060, 0.090 * bulk), k=0.05)      # brisket
        self._ell(b, ch + self.P(0, 0.010, 0.002), (0.050, 0.120, 0.060), k=0.05)                       # withers
        self._ell(b, sp + self.P(0, 0.040, -0.030), (0.060, 0.135, 0.052), k=0.07)                     # loin
        self._ell(b, sp + self.P(0, 0.020, -0.062), (0.062, 0.110, 0.055 - 0.010 * gaunt), k=0.07)     # what belly is left
        self._ell(b, pe + self.P(0, 0.035, -0.035), (0.072, 0.105, 0.072), k=0.06)                     # croup
        # the belly tucks up hard behind the ribs
        self._ell(b, sp + self.P(0, 0.070, -0.212), (0.20, 0.175, 0.100 + 0.015 * gaunt), k=0.035, mode="sub")
        for side, sx in (("L", 1.0), ("R", -1.0)):
            # the hollow behind the last rib, under the loin
            self._ell(b, sp + self.P(sx * 0.088, 0.085, -0.055), (0.030, 0.055, 0.045), k=0.03 * gaunt + 0.01, mode="sub")
        # --- spine knobs, hip bones and pin bones push up through the skin
        top = []
        for y in (np.linspace(float(ch[1]) - 0.06 * s, float(pe[1]) + 0.13 * s, 19) if not wolf else []):
            q = self._surface(b, np.array([0.0, y, 0.9 * s]), (0, 0, -1), reach=0.5)
            if q is not None:
                top.append(q)
        for i, q in enumerate(top):
            r = (0.0085 + 0.0025 * (i % 2)) * s * (0.6 + 0.4 * gaunt)
            b.sphere(q + self.P(0, 0, -0.004), r, k=0.008 * s)
        for sx in ((1.0, -1.0) if not wolf else ()):
            b.sphere(pe + self.P(sx * 0.056, -0.045, 0.012), 0.019 * s, k=0.016 * s)        # point of the hip
            b.sphere(pe + self.P(sx * 0.040, 0.112, -0.040), 0.017 * s, k=0.014 * s)        # pin bone
        # --- ribs: hoops round the barrel from the spine to the sternum, raking back as they go down
        n_ribs = 9 if not wolf else 0
        ribs = []
        rr = np.random.default_rng(int(p.get("seed", 1)) * 31 + 5)
        jit = rr.uniform(-0.004, 0.004, n_ribs)
        for i in range(n_ribs):
            y0 = float(ch[1]) + (-0.040 + 0.025 * i + jit[i]) * s
            show = (0.45 + 0.55 * i / (n_ribs - 1)) * gaunt
            for sx in (1.0, -1.0):
                pts = []
                for th in np.linspace(math.radians(32), math.radians(150), 10):
                    y = y0 + 0.045 * s * (1 - math.cos(th)) * 0.5
                    c0 = np.array([0.0, y, float(rib_c[2])])
                    d = np.array([sx * math.sin(th), 0.0, math.cos(th)])
                    q = self._surface(b, c0 + d * 0.4 * s, -d, reach=0.4)
                    if q is not None:
                        pts.append(q - d * 0.0012 * s)
                ribs.append(pts)
        # each rib a hoop standing proud, and the gutter between it and the next sunk in
        for pts in ribs:
            for a, c in zip(pts[:-1], pts[1:]):
                b.capsule(a, c, 0.0085 * s, k=0.007 * s)
        for p0, p1 in zip(ribs[:-2], ribs[2:]):
            for a0, a1, c0, c1 in zip(p0[:-1], p1[:-1], p0[1:], p1[1:]):
                b.capsule((a0 + a1) * 0.5, (c0 + c1) * 0.5, 0.0045 * s * gaunt, k=0.004 * s, mode="sub")
        # --- shoulders and forelegs
        for side, sx in (("L", 1.0), ("R", -1.0)):
            sc0, sh, el = j[f"scap0.{side}"], j[f"shoulder.{side}"], j[f"elbow.{side}"]
            ca, fe, to = j[f"carpus.{side}"], j[f"fetlock_f.{side}"], j[f"toe_f.{side}"]
            Rs = _frame(sh - sc0, (0, -1, 0))
            self._ell(b, self.mid(f"scap0.{side}", f"shoulder.{side}", 0.45) + self.P(sx * 0.010, 0, 0),
                      (0.024, 0.052, 0.098), R=Rs, k=0.05)
            # the spine of the shoulder blade, a ridge down its middle
            if not wolf:
                b.capsule(sc0 + self.P(sx * 0.018, 0.0, -0.01), sh + self.P(sx * 0.016, 0.02, 0.03), 0.0065 * s * (0.5 + 0.5 * gaunt),
                          k=0.012 * s)
            b.sphere(sh + self.P(sx * 0.004, -0.008, 0), 0.034 * s, k=0.03 * s)                 # point of the shoulder
            self._limb(b, sh, el, 0.038, 0.030, 0.03)
            self._ell(b, self.mid(f"shoulder.{side}", f"elbow.{side}", 0.55) + self.P(0, 0.022, 0), (0.026, 0.030, 0.055),
                      R=_frame(el - sh, (0, 1, 0)), k=0.03)                                     # wasted triceps
            b.sphere(el + self.P(0, 0.018, 0.004), 0.016 * s, k=0.012 * s)                     # point of the elbow
            self._limb(b, el, ca, 0.022, 0.0145, 0.018)
            self._ell(b, self.mid(f"elbow.{side}", f"carpus.{side}", 0.25) + self.P(0, -0.006, 0), (0.021, 0.022, 0.050), k=0.02)
            b.sphere(ca + self.P(0, -0.002, 0), 0.0175 * s, k=0.01 * s)
            b.sphere(ca + self.P(0, 0.014, -0.012), 0.008 * s, k=0.008 * s)                    # carpal pad
            self._limb(b, ca, fe, 0.0142, 0.0150, 0.010)
            self._paw(side, f"fetlock_f.{side}", f"toe_f.{side}", 1.0 * (1.06 if shep else 1.0), True)
            del to
            # --- hind leg: a wasted thigh, the stifle, a gaskin over the long tibia, the hock
            hp, st, hk = j[f"hip.{side}"], j[f"stifle.{side}"], j[f"hock.{side}"]
            self._ell(b, self.mid(f"hip.{side}", f"stifle.{side}", 0.45) + self.P(sx * 0.002, 0.030, 0),
                      (0.044, 0.070, 0.105), R=_frame(st - hp, (0, 1, 0)), k=0.05)
            self._limb(b, hp, st, 0.042, 0.032, 0.04)
            b.sphere(st + self.P(0, -0.004, 0), 0.025 * s, k=0.016 * s)
            self._limb(b, st, hk, 0.028, 0.0155, 0.02)
            self._ell(b, self.mid(f"stifle.{side}", f"hock.{side}", 0.30) + self.P(0, 0.014, 0), (0.022, 0.026, 0.055),
                      R=_frame(hk - st, (0, 1, 0)), k=0.02)
            b.sphere(hk, 0.0175 * s, k=0.01 * s)
            calc = hk + self.P(0, 0.020, 0.012)
            b.capsule(calc, hk + self.P(0, 0.004, -0.016), 0.0085 * s, k=0.01 * s)               # point of the hock
            b.capsule(calc, self.mid(f"stifle.{side}", f"hock.{side}", 0.45) + self.P(0, 0.022, 0), 0.0055 * s, k=0.01 * s)
            self._limb(b, hk, j[f"fetlock_h.{side}"], 0.0150, 0.0145, 0.010)
            self._paw(side, f"fetlock_h.{side}", f"toe_h.{side}", 0.96 * (1.06 if shep else 1.0), False)
        # --- neck: thin, the windpipe and the jugular groove showing
        nb = 1.18 if shep else 1.0
        self._limb(b, ch + self.P(0, -0.075, -0.020), j["neck1"], 0.056 * bulk * nb, 0.046 * nb, 0.05, squash=1.25)
        self._limb(b, j["neck1"], j["head0"] + self.P(0, -0.015, -0.012), 0.046 * nb, 0.045, 0.045, squash=1.2)
        self._limb(b, ch + self.P(0, -0.140, -0.075), j["jaw0"] + self.P(0, 0.02, -0.035), 0.016, 0.014, 0.03)
        # --- head, in its own frame: f forward along the skull, u up, x out
        h0 = j["head0"]
        f_ax = _n(j["nose"] - h0)
        u_ax = _n(np.cross(f_ax, X_AX))
        u_ax = u_ax if u_ax[2] > 0 else -u_ax
        Rh = np.stack([X_AX, u_ax, f_ax], axis=1)
        L = float(np.linalg.norm(j["nose"] - h0)) / s       # skull length at scale 1
        ms = L / 0.250                                     # muzzle stretch (a shepherd's is longer)

        def H(x, u, f):
            return h0 + (X_AX * x + u_ax * u + f_ax * f) * s
        self.H = H
        self.Rh = Rh
        self.f_ax, self.u_ax = f_ax, u_ax
        self._ell(b, H(0, 0.012, 0.058), (0.056, 0.048, 0.066), R=Rh, k=0.03)                      # cranium
        b.capsule(H(0, 0.050, 0.002), H(0, 0.056, 0.070), 0.0075 * s, k=0.016 * s)                  # sagittal crest
        b.sphere(H(0, 0.030, -0.012), 0.020 * s, k=0.02 * s)                                         # occiput
        for sx in (1.0, -1.0):
            # starved temples: the jaw muscle has wasted off the skull
            self._ell(b, H(sx * 0.049, 0.018, 0.048), (0.014, 0.024, 0.032), R=Rh, k=0.014 * gaunt + 0.004, mode="sub")
            b.capsule(H(sx * 0.047, -0.010, 0.046), H(sx * 0.040, -0.006, 0.104), 0.0105 * s, k=0.014 * s)   # cheekbone
            self._ell(b, H(sx * 0.031, 0.034, 0.090), (0.014, 0.010, 0.017), R=Rh, k=0.012)        # brow
        # the upper jaw and the lower, a closed mouth between them
        mf = 0.250 * ms
        self._limb(b, H(0, -0.002, 0.100), H(0, -0.010, mf - 0.016), 0.039, 0.026, 0.035, squash=1.05, up=tuple(u_ax))
        self._limb(b, H(0, -0.046, 0.075), H(0, -0.041, mf - 0.026), 0.023, 0.0145, 0.025, squash=0.9, up=tuple(u_ax))
        if wolf:
            # a broad skull and a deep, blunt muzzle, not a dog's narrow snout
            self._ell(b, H(0, 0.004, 0.030), (0.066, 0.046, 0.042), R=Rh, k=0.03)
            self._ell(b, H(0, -0.018, 0.130 * ms), (0.035, 0.034, 0.085 * ms), R=Rh, k=0.025)
        for sx in (1.0, -1.0):
            self._ell(b, H(sx * 0.034, -0.034, 0.064), (0.020, 0.028, 0.030), R=Rh, k=0.025)       # masseter
            if wolf:
                # relaxed lips: the upper hangs over the lower and closes the mouth line
                b.capsule(H(sx * 0.030, -0.027, 0.082), H(sx * 0.020, -0.030, mf - 0.028), 0.0072 * s, k=0.008 * s)
                b.capsule(H(sx * 0.023, -0.041, 0.080), H(sx * 0.015, -0.041, mf - 0.040), 0.0050 * s, k=0.007 * s)
                continue
            # the upper lip, drawn back and bunched in a ridge above the bared gum
            b.capsule(H(sx * 0.031, -0.011, 0.090), H(sx * 0.0225, -0.008, mf - 0.040), 0.0065 * s, k=0.008 * s)
            # the lower lip pulled down off the lower teeth
            b.capsule(H(sx * 0.024, -0.050, 0.080), H(sx * 0.016, -0.049, mf - 0.050), 0.005 * s, k=0.007 * s)
        # mouth: a slit from the corner (far back, under the eye) out through the front
        mouth_u = -0.0335
        self.mouth_u, self.mouth_f0 = mouth_u, 0.068
        b.box(H(0, mouth_u, 0.068 + 0.11 * ms), np.array([0.06, 0.0034, 0.11 * ms]) * s, R=Rh,
              k=0.0015 * s, mode="sub", label=L_MOUTH)
        # bared gums above and below the slit (lips retracted)
        gum = lambda u0, h, x0: (lambda P: S.sd_box(P, H(0, u0, 0.07 + 0.105 * ms), np.array([x0, h, 0.105 * ms]) * s, Rh))  # noqa: E731
        lo, hi = H(0, 0, 0) - 0.3 * s, H(0, 0, 0) + 0.4 * s
        if wolf:
            # only the black lip line shows along the closed mouth
            b.paint(gum(-0.0335, 0.0050, 0.06), lo, hi, L_MOUTH)
        else:
            b.paint(gum(-0.0225, 0.0085, 0.06), lo, hi, L_MOUTH)
            b.paint(gum(-0.0445, 0.0080, 0.06), lo, hi, L_MOUTH)
        # snarl wrinkles across the bridge of the nose
        for f in ((0.158, 0.180) if not wolf else ()):
            ff = f * ms
            ctr = H(0, -0.008, ff)
            rr = 0.0355 * s * (1.0 - 0.3 * (ff - 0.10) / 0.15)
            def wr(P, ctr=ctr, rr=rr):
                q = (P - ctr) @ Rh
                ring = np.sqrt((np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2) - rr) ** 2 + q[:, 2] ** 2) - 0.0022 * s
                return np.maximum(ring, -q[:, 1] + 0.018 * s)
            b.sub(wr, ctr - 0.06 * s, ctr + 0.06 * s, k=0.002 * s)
        # nose leather with its nostrils
        nose_c = H(0, -0.004, mf + 0.001)
        self.nose_c = nose_c
        b.sphere(nose_c, 0.0205 * s, k=0.010 * s, label=L_NOSE)
        b.box(nose_c + u_ax * -0.016 * s, np.array([0.0016, 0.012, 0.018]) * s, R=Rh, k=0.002 * s, mode="sub", label=L_NOSE)
        for sx in (1.0, -1.0):
            b.ellipsoid(H(sx * 0.0085, -0.002, mf + 0.018), np.array([0.0055, 0.0042, 0.007]) * s, R=Rh, k=0.002 * s, mode="sub",
                        label=L_NOSE)
        # eyes: deep in starved sockets, looking forward and out
        self.eye_r = 0.0112 * s
        for sx in (1.0, -1.0):
            c = H(sx * 0.0355, 0.023, 0.093)
            self.eye_c.append(c)
            b.sphere(c + (X_AX * sx * 0.002 + f_ax * 0.003) * s, self.eye_r * 1.12, k=0.004 * s, mode="sub")
            b.capsule(H(sx * 0.031, 0.006, 0.086), H(sx * 0.028, 0.002, 0.112), 0.0045 * s, k=0.006 * s, mode="sub")  # tear trough
        # tail: a thin, mangy whip (a shepherd's is a ragged brush)
        tr = (0.026, 0.024, 0.014) if shep else (0.020, 0.015, 0.0075)
        if wolf:
            tr = (0.034, 0.044, 0.026)   # a full brush, thickest two thirds down
        self._limb(b, j["tail0"] + self.P(0, -0.02, 0.004), j["tail1"], tr[0], tr[1], 0.02)
        self._limb(b, j["tail1"], j["tail2"], tr[1], tr[2], 0.015)
        if wolf:
            self._wolf_coat_volume()
            # hide: a thick, shaggy coat, lying in tufts
            lo, hi = b.bounds()
            b.displace(lambda Q: s * (0.0020 * nz.fbm(Q, 18.0 / s, 2) + 0.0010 * nz.noise(Q, 90.0 / s)), lo, hi)
        else:
            # hide: mangy, lumpy where the coat has fallen out, matted where it hasn't
            lo, hi = b.bounds()
            b.displace(lambda Q: s * (0.0011 * nz.fbm(Q, 26.0 / s, 2) + 0.0009 * nz.noise(Q, 140.0 / s)
                                      - 0.0012 * self._mange(Q)), lo, hi)
        self._hound_ears()
        self._hound_teeth()
        if not wolf:
            self._hound_growths()

    def _wolf_coat_volume(self):
        """A wolf's double coat over the dog's frame: the ruff standing off the neck and shoulders,
        the cheek tufts, a full chest, breeches on the thighs, a level back without bones."""
        j, s, b = self.j, self.s, self.body
        ch, sp, pe = j["chest0"], j["spine0"], j["pelvis"]
        n0, n1, h0 = j["neck0"], j["neck1"], j["head0"]
        # a thick neck: the coat makes it as deep as the head
        self._limb(b, ch + self.P(0, -0.050, -0.010), h0 + self.P(0, 0.030, -0.035), 0.088, 0.066, 0.05, squash=1.15)
        # the ruff: over the withers and up the back of the neck, and the bib under the throat
        self._ell(b, (n0 + n1) * 0.5 + self.P(0, 0.020, 0.030), (0.092, 0.115, 0.085), k=0.05)
        self._ell(b, ch + self.P(0, -0.040, 0.032), (0.088, 0.120, 0.068), k=0.06)
        self._ell(b, (n0 + n1) * 0.5 + self.P(0, -0.020, -0.060), (0.072, 0.080, 0.085), k=0.05)
        self._ell(b, ch + self.P(0, -0.120, -0.080), (0.074, 0.070, 0.095), k=0.05)            # chest
        # a level back over the loin, the barrel filled out
        self._ell(b, sp + self.P(0, 0.000, 0.010), (0.080, 0.150, 0.060), k=0.07)
        self._ell(b, ch + self.P(0, 0.010, -0.090), (0.100, 0.135, 0.125), k=0.06)
        # cheek tufts flaring back below the ears
        for sx in (1.0, -1.0):
            self._ell(b, h0 + self.P(sx * 0.050, 0.012, -0.036), (0.044, 0.050, 0.056), k=0.03)
            # breeches: the long hair down the back of the thigh
            hp, st = j[f"hip.{'L' if sx > 0 else 'R'}"], j[f"stifle.{'L' if sx > 0 else 'R'}"]
            self._ell(b, (hp + st) * 0.5 + self.P(sx * 0.006, 0.040, 0.000), (0.046, 0.058, 0.090),
                      R=_frame(st - hp, (0, 1, 0)), k=0.05)
            # the coat on the upper foreleg and the gaskin: sturdier legs than a starved dog's
            sd = "L" if sx > 0 else "R"
            el, ca, hk = j[f"elbow.{sd}"], j[f"carpus.{sd}"], j[f"hock.{sd}"]
            self._limb(b, el + self.P(0, 0.006, 0.010), (el + ca) * 0.5, 0.034, 0.024, 0.03)
            self._limb(b, st, (st + hk) * 0.5 + self.P(0, 0.010, 0), 0.040, 0.028, 0.03)
        del pe

    def _mange(self, Q):
        """0..1: where the coat has fallen out (rest pose). A wolf has its coat."""
        if self.p.get("breed") == "wolf":
            return np.zeros(len(Q))
        s = self.s
        nz = self.noise
        n = nz.fbm(Q + 3.7, 11.0 / s, 3)
        y, z = Q[:, 1], Q[:, 2]
        ch = self.j["chest0"]
        flank = np.exp(-((y - (ch[1] + 0.08 * s)) / (0.22 * s)) ** 2) * np.exp(-((z - (ch[2] - 0.12 * s)) / (0.12 * s)) ** 2)
        legs = np.clip((0.36 * s - z) / (0.2 * s), 0, 1)
        bias = -0.18 + 0.30 * flank + 0.18 * legs
        t = np.clip((n + bias - 0.02) / 0.16, 0.0, 1.0)
        return t * t * (3 - 2 * t)

    def _hound_ears(self):
        s, p = self.s, self.p
        torn = p.get("torn_ear", "L")
        erect = p.get("ears", "drop") == "erect"
        for side, sx in (("L", 1.0), ("R", -1.0)):
            a, c = self.j[f"ear0.{side}"], self.j[f"ear1.{side}"]
            w = c - a
            ln = float(np.linalg.norm(w))
            if erect:
                # pricked: a tall cupped triangle, opening forward and a little out
                front = np.array([sx * 0.45, -1.0, 0.0])
                R = _frame(w, front)
                if p.get("breed") == "wolf":
                    # short, thick, furred and round-tipped
                    self.ears.cone(a - w * 0.10, c, 0.046 * s, 0.011 * s, k=0.012 * s, squash=0.34, up_hint=tuple(R[:, 1]))
                    self.ears.cone(a + R[:, 1] * 0.010 * s + w * 0.10, c + R[:, 1] * 0.005 * s - w * 0.12, 0.032 * s, 0.004 * s,
                                   k=0.003 * s, squash=0.22, up_hint=tuple(R[:, 1]), mode="sub")
                    continue
                self.ears.cone(a - w * 0.04, c, 0.042 * s, 0.006 * s, k=0.01 * s, squash=0.26, up_hint=tuple(R[:, 1]))
                self.ears.cone(a + R[:, 1] * 0.0085 * s + w * 0.12, c + R[:, 1] * 0.004 * s - w * 0.08, 0.033 * s, 0.003 * s,
                               k=0.003 * s, squash=0.20, up_hint=tuple(R[:, 1]), mode="sub")
            else:
                # dropped: a soft leaf folding over at the base and hanging flat against the cheek
                out = np.array([sx, 0.15, 0.25])
                R = _frame(w, out)
                # narrow where it folds over at the base, broadest low down, a rounded end
                self.ears.cone(a + w * 0.08, a + w * 0.80, 0.014 * s, 0.029 * s, k=0.004 * s, squash=0.16, up_hint=tuple(R[:, 1]))
                self.ears.cone(a - w * 0.06, a + w * 0.22, 0.011 * s, 0.012 * s, k=0.008 * s, squash=0.6, up_hint=tuple(R[:, 1]))
            if side == torn:
                # bitten: the end torn away in a ragged line and a notch out of the edge
                tip = a + w * (0.98 if erect else 0.92)
                big = 1.45 if erect else 1.0
                for i, (tt, rr) in enumerate(((0.0, 0.030), (0.16, 0.020), (-0.15, 0.022), (0.30, 0.014), (-0.28, 0.012))):
                    q = tip + R[:, 0] * (tt * ln + (0.012 * s if erect else 0.0)) + w * (0.05 * (i % 2)) * ln
                    self.ears.sphere(q, rr * big * s, k=0.0015 * s, mode="sub")
                for tt, rr in ((0.50, 0.011), (0.60, 0.008), (0.40, 0.007)):
                    q = a + w * tt + R[:, 0] * (0.030 if erect else 0.034) * s
                    self.ears.sphere(q, rr * s, k=0.0015 * s, mode="sub")

    def _hound_teeth(self):
        """Yellowed teeth in the gum lines the drawn lips leave bare: incisors, long canines,
        the premolar blades and carnassials; a tongue lying in the lower jaw."""
        s = self.s
        H = self.H
        ms = float(np.linalg.norm(self.j["nose"] - self.j["head0"])) / s / 0.250
        mf = 0.250 * ms
        mu = self.mouth_u
        T_UP, T_LO = S.Program(0), S.Program(0)
        self.teeth_upper, self.teeth_lower = T_UP, T_LO
        # a hidden gum bar each side ties every tooth into one piece
        for sx in (1.0, -1.0):
            T_UP.capsule(H(sx * 0.012, mu + 0.011, mf - 0.012), H(sx * 0.026, mu + 0.013, 0.085), 0.0045 * s, k=0.003 * s, label=1)
            T_LO.capsule(H(sx * 0.010, mu - 0.011, mf - 0.020), H(sx * 0.020, mu - 0.012, 0.085), 0.0042 * s, k=0.003 * s, label=1)
        T_UP.capsule(H(0.012, mu + 0.011, mf - 0.012), H(-0.012, mu + 0.011, mf - 0.012), 0.0045 * s, k=0.003 * s, label=1)
        T_LO.capsule(H(0.010, mu - 0.011, mf - 0.020), H(-0.010, mu - 0.011, mf - 0.020), 0.0042 * s, k=0.003 * s, label=1)

        def tooth(prog, root, tip, r0, r1):
            prog.cone(root, tip, r0 * s, r1 * s, k=0.0015 * s, label=0)
        # upper incisors: six pegs across the front, the outer pair longer
        for i, x in enumerate((-0.0125, -0.0075, -0.0025, 0.0025, 0.0075, 0.0125)):
            outer = abs(x) > 0.01
            f = mf - 0.010 - 0.003 * abs(x) / 0.0125
            tooth(T_UP, H(x, mu + 0.010, f), H(x * 1.02, mu - 0.003 - 0.003 * outer, f + 0.002), 0.0028, 0.0011)
        # lower incisors
        for x in (-0.010, -0.006, -0.002, 0.002, 0.006, 0.010):
            f = mf - 0.018 - 0.003 * abs(x) / 0.010
            tooth(T_LO, H(x, mu - 0.010, f), H(x, mu + 0.002, f + 0.002), 0.0025, 0.0010)
        for sx in (1.0, -1.0):
            # canines: long, curved back, the upper outside the lower
            a = H(sx * 0.0195, mu + 0.012, mf - 0.026)
            m = H(sx * 0.0215, mu - 0.006, mf - 0.025)
            e = H(sx * 0.0205, mu - 0.019, mf - 0.030)
            T_UP.cone(a, m, 0.0052 * s, 0.0040 * s, k=0.002 * s, label=0)
            T_UP.cone(m, e, 0.0040 * s, 0.0008 * s, k=0.002 * s, label=0)
            a = H(sx * 0.0150, mu - 0.012, mf - 0.034)
            m = H(sx * 0.0165, mu + 0.004, mf - 0.034)
            e = H(sx * 0.0160, mu + 0.015, mf - 0.040)
            T_LO.cone(a, m, 0.0046 * s, 0.0035 * s, k=0.002 * s, label=0)
            T_LO.cone(m, e, 0.0035 * s, 0.0007 * s, k=0.002 * s, label=0)
            # premolar blades and the carnassial, stepping back along the jaw
            for f, h, wv in ((mf - 0.052, 0.006, 0.0035), (mf - 0.072, 0.008, 0.004), (mf - 0.094, 0.009, 0.0045),
                             (0.118, 0.011, 0.0055)):
                fx = 0.020 + 0.012 * (mf - 0.040 - f) / max(mf - 0.150, 1e-3)
                base_u = H(sx * fx, mu + 0.010, f)
                T_UP.cone(base_u, H(sx * fx, mu - h + 0.006, f + 0.002), wv * s, 0.0012 * s, k=0.002 * s, label=0)
                T_UP.cone(H(sx * fx, mu + 0.008, f - 0.006), H(sx * fx, mu - h * 0.5 + 0.006, f - 0.003), wv * 0.8 * s, 0.001 * s,
                          k=0.002 * s, label=0)
                fl = f + 0.004
                fxl = fx - 0.004
                T_LO.cone(H(sx * fxl, mu - 0.010, fl), H(sx * fxl, mu + h - 0.006, fl + 0.002), wv * 0.9 * s, 0.0011 * s,
                          k=0.002 * s, label=0)
        # the tongue, lying in the floor of the mouth
        T_LO.ellipsoid(H(0, mu - 0.0075, 0.150 * ms), np.array([0.0145, 0.0048, 0.070 * ms]) * s, R=self.Rh, k=0.004 * s, label=1)

    def _hound_growths(self):
        """The Bloom breaking out of the hide: tiers of pale shelf plates (label 0) erupting along
        the spine, over the shoulders and down one flank, rooted in mats of threads (label 1)
        that run off over the skin."""
        s, p, b = self.s, self.p, self.body
        g = p.get("growth", {})
        rng = np.random.default_rng(int(p.get("seed", 1)) * 7919 + 13)
        G = S.Program(0)
        self.growths = G
        self.growth_sites: list[tuple[np.ndarray, float]] = []
        j = self.j
        ch, sp, pe = j["chest0"], j["spine0"], j["pelvis"]
        flank_side = 1.0 if g.get("flank_side", "R") == "L" else -1.0
        sites = []
        # along the spine: plates standing up off the backbone like a broken crest
        for y in np.linspace(float(ch[1]) - 0.02 * s, float(pe[1]) + 0.02 * s, int(g.get("spine", 5))):
            y = y + rng.uniform(-0.015, 0.015) * s
            x = rng.uniform(-0.012, 0.012) * s
            sites.append(("spine", np.array([x, y, 1.0 * s]), np.array([0.0, 0.0, -1.0]), rng.uniform(0.8, 1.15)))
        # shoulders: both, one heavier
        for sx, w in ((1.0, 1.0), (-1.0, 0.7)):
            c = self.mid(f"scap0.{'L' if sx > 0 else 'R'}", f"shoulder.{'L' if sx > 0 else 'R'}", 0.3)
            for k in range(int(g.get("shoulder", 2))):
                o = np.array([sx * 0.4, rng.uniform(-0.12, 0.12), rng.uniform(-0.05, 0.12)]) * s
                sites.append(("shoulder", c + o + np.array([sx * 0.3 * s, 0, 0.1 * s]),
                              _n(np.array([-sx, 0.0, -0.45])), w * rng.uniform(0.75, 1.0)))
        # one flank: a spreading eruption over the ribs
        for k in range(int(g.get("flank", 5))):
            y = float(ch[1]) + rng.uniform(-0.02, 0.17) * s
            z = float(ch[2]) + rng.uniform(-0.15, -0.03) * s
            sites.append(("flank", np.array([flank_side * 0.35 * s, y, z]), np.array([-flank_side, 0.0, 0.0]), rng.uniform(0.75, 1.2)))
        for kind, p0, dirn, size in sites:
            q = self._surface(b, p0, dirn, reach=0.5)
            if q is None:
                continue
            n = self._normal(b, q)
            self.growth_sites.append((q, size))
            # brackets: on the flanks and shoulders, shelves standing out level from the hide and
            # stacked in tiers like fungus on a log; along the spine, a broken crest of fans
            t = _n(np.array([0.0, 1.0, 0.0]) - n * n[1])
            if kind == "spine":
                # fins raked back like a broken crest, staggered along the backbone
                lean = math.radians(rng.uniform(-16, 16))
                rake = math.radians(rng.uniform(15, 35))
                out0 = _n(n * math.cos(lean) + np.cross(t, n) * math.sin(lean))
                out0 = _n(out0 * math.cos(rake) + t * math.sin(rake))
                t = _n(t - out0 * float(np.dot(t, out0)))
                stack = t
            else:
                h = np.array([n[0], n[1] * 0.3, 0.0])
                h = _n(h) if np.linalg.norm(h) > 0.2 else np.array([1.0 if q[0] >= 0 else -1.0, 0.0, 0.0])
                out0 = _n(h * math.cos(math.radians(14)) + np.array([0.0, 0.0, math.sin(math.radians(14))]))
                t = _n(np.array([0.0, 1.0, 0.0]) - out0 * out0[1])
                stack = np.array([0.0, 0.0, 1.0])
            bt = np.cross(n, t)
            tiers = 2 + int(rng.integers(0, 3))
            for k in range(tiers):
                r = (0.046 - 0.007 * k) * size * s * rng.uniform(0.85, 1.12)
                thick = r * rng.uniform(0.20, 0.25)
                fin = kind == "spine"
                if fin:
                    off = stack * (k - (tiers - 1) * 0.5) * r * 0.85
                    tilt = 0.0
                else:
                    off = stack * (k - (tiers - 1) * 0.5) * thick * 3.2 + t * rng.uniform(-0.35, 0.35) * r
                    tilt = math.radians(rng.uniform(-6, 10))
                out = _n(out0 * math.cos(tilt) + stack * math.sin(tilt))
                c = q + off + out * r * (0.55 if fin else 0.40)
                Rf = np.stack([t, out, _n(np.cross(t, out))], axis=1)
                G.ellipsoid(c, np.array([r * (0.75 if fin else 1.0), r * (1.05 if fin else 0.80), thick]), R=Rf, k=0.004 * s, label=0)
                # a thick, knobbly root where it bursts out of the hide
                G.ellipsoid(q + off * 0.9 - n * 0.002 * s, np.array([r * 0.55, r * 0.35, thick * 1.5]), R=Rf, k=0.006 * s, label=1)
            # threads running out from the site over the skin, forking and thinning
            for k in range(int(5 + size * 4)):
                ang = rng.uniform(0, 2 * math.pi)
                dvec = _n(t * math.cos(ang) + bt * math.sin(ang))
                pos = q.copy()
                rad = 0.0028 * s * rng.uniform(0.8, 1.25)
                steps = int(rng.integers(5, 10))
                for st in range(steps):
                    nxt = pos + dvec * 0.012 * s
                    nn = self._normal(b, nxt)
                    sq = self._surface(b, nxt + nn * 0.02 * s, -nn, reach=0.06)
                    if sq is None:
                        break
                    sq = sq + nn * 0.0006 * s
                    G.capsule(pos, sq, rad, k=0.0015 * s, label=1)
                    if st in (2, 5) and rng.random() < 0.5:
                        G.sphere(sq, rad * 1.7, k=0.0015 * s, label=1)
                    dvec = _n(dvec + rng.normal(0, 0.35, 3) - nn * float(np.dot(dvec, nn)))
                    pos = sq
                    rad *= 0.88
        lo, hi = G.bounds()
        nz = self.noise
        G.displace(lambda Q: 0.0010 * s * nz.fbm(Q, 160.0 / s, 2), lo, hi)

    def _hound_coat(self, V, N, part: str):
        """(pale, dark): pale is bare skin where the mange has taken the coat (and the belly, the
        insides of the legs, round the eyes and the growths); dark is the nose, the muzzle, a back
        stripe (the shepherd's black saddle and mask) and crusted edges round the bare patches."""
        if self.p.get("breed") == "wolf":
            return self._wolf_coat(V, N, part)
        j, s = self.j, self.s
        nz = self.noise
        shep = self.p.get("breed") == "shepherd"

        def ss(e0, e1, x):
            t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
            return t * t * (3 - 2 * t)
        if part == "ears":
            pale = np.zeros(len(V))
            dark = np.zeros(len(V))
            for side in ("L", "R"):
                a, c = j[f"ear0.{side}"], j[f"ear1.{side}"]
                w = _n(c - a)
                sx = 1.0 if side == "L" else -1.0
                mine = (V[:, 0] * sx) > 0
                t = ((V - a) @ w) / max(float(np.linalg.norm(c - a)), 1e-6)
                if self.p.get("ears", "drop") == "erect":
                    inside = ss(0.1, 0.6, N @ _n(np.array([sx * 0.45, -1.0, 0.0]))) * mine
                    dark = np.maximum(dark, (1.0 - inside) * mine * (0.75 if shep else 0.4))
                    dark = np.maximum(dark, ss(0.6, 0.9, t) * mine * 0.8)
                    inside = inside * 0.5
                else:
                    inside = ss(0.1, 0.6, -(N[:, 0] * sx)) * mine
                    dark = np.maximum(dark, ss(0.5, 0.95, t) * mine * 0.35)
                pale = np.maximum(pale, inside * 0.85)
                pale = np.maximum(pale, self._mange(V) * mine)
            return np.clip(pale, 0, 1), np.clip(dark, 0, 1)
        y, z = V[:, 1], V[:, 2]
        mange = self._mange(V)
        belly = ss(-0.2, -0.7, N[:, 2]) * ss(0.48 * s, 0.36 * s, z) * (z > 0.2 * s)
        inner_leg = ss(0.2, 0.7, -N[:, 0] * np.sign(V[:, 0] + 1e-9)) * ss(0.42 * s, 0.25 * s, z) * (z > 0.06 * s)
        eye_ring = np.zeros(len(V))
        for c in self.eye_c:
            eye_ring = np.maximum(eye_ring, ss(0.026 * s, 0.014 * s, np.sqrt(((V - c) ** 2).sum(-1))))
        sites = np.zeros(len(V))
        for c, size in getattr(self, "growth_sites", []):
            d = np.sqrt(((V - c) ** 2).sum(-1))
            sites = np.maximum(sites, ss(0.075 * s * size, 0.025 * s * size, d))
        # calluses on the elbows and hocks, and the bony points rubbed bare
        pressure = np.zeros(len(V))
        for side in ("L", "R"):
            for jn, r in (("elbow", 0.035), ("hock", 0.03), ("hip", 0.035)):
                c = j[f"{jn}.{side}"] + (self.P(0, 0.02, 0) if jn != "hip" else self.P(0, -0.05, 0.06))
                pressure = np.maximum(pressure, ss(r * s, r * 0.3 * s, np.sqrt(((V - c) ** 2).sum(-1))))
        pale = np.maximum.reduce([mange, belly * 0.85, inner_leg * 0.6, eye_ring * 0.8, sites, pressure * 0.8])
        # the head frame: muzzle and mask
        h0 = j["head0"]
        hf = (V - h0) @ self.f_ax / s
        hu = (V - h0) @ self.u_ax / s
        on_head = (hf > -0.02) & (np.abs(V[:, 0]) < 0.08 * s) & (hu > -0.08)
        ms = float(np.linalg.norm(j["nose"] - h0)) / s / 0.250
        muzzle = on_head * ss(0.09 * ms, 0.15 * ms, hf)
        nose = ss(0.026 * s, 0.018 * s, np.sqrt(((V - self.nose_c) ** 2).sum(-1)))
        dorsal = ss(0.035 * s, 0.0, np.abs(V[:, 0])) * ss(0.4, 0.9, N[:, 2]) * (y > j["neck0"][1]) * (y < j["tail0"][1])
        crust = ss(0.15, 0.45, mange) * ss(0.95, 0.6, mange)
        tail = ss(j["tail0"][1] - 0.01 * s, j["tail0"][1] + 0.04 * s, y) * (z < j["tail0"][2] + 0.02 * s)
        if shep:
            # the black saddle over the back, the mask, the dark tail
            sad_y = ss(j["chest0"][1] - 0.06 * s, j["chest0"][1] + 0.02 * s, y) * ss(j["pelvis"][1] + 0.12 * s, j["pelvis"][1] + 0.04 * s, y)
            saddle = sad_y * ss(0.42 * s, 0.50 * s, z + 0.02 * s * nz.fbm(V, 14.0 / s, 2)) * ss(-0.2, 0.3, N[:, 2])
            mask = muzzle * 0.85 + on_head * ss(0.06, 0.10, hf) * ss(0.12, 0.08, hf) * 0.5
            dark = np.maximum.reduce([saddle * 0.82, mask, nose, tail * ss(-0.3, 0.3, -N[:, 1]) * 0.7, crust * 0.4])
        else:
            dark = np.maximum.reduce([muzzle * 0.45, nose, dorsal * 0.35, crust * 0.5])
        brk = nz.fbm(V, 40.0 / s, 2) * 0.10
        pale = np.clip(pale + brk * (pale > 0.05) * (pale < 0.95), 0, 1)
        dark = np.clip(dark * (1.0 - 0.6 * pale), 0, 1)
        return pale, np.clip(np.maximum(dark, nose), 0, 1)

    def _wolf_coat(self, V, N, part: str):
        """(pale, dark) for a grey wolf: cream under the jaw, on the throat and chest, the belly,
        the insides and lower legs, the cheeks and the brows; a dark saddle over the back and
        shoulders, a dark line on the tail and its tip, dark ear backs and rims, the nose; the
        agouti of the guard hairs broken through all of it."""
        j, s = self.j, self.s
        nz = self.noise

        def ss(e0, e1, x):
            t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
            return t * t * (3 - 2 * t)
        if part == "ears":
            pale = np.zeros(len(V))
            dark = np.zeros(len(V))
            for side in ("L", "R"):
                a, c = j[f"ear0.{side}"], j[f"ear1.{side}"]
                sx = 1.0 if side == "L" else -1.0
                mine = (V[:, 0] * sx) > 0
                t = ((V - a) @ _n(c - a)) / max(float(np.linalg.norm(c - a)), 1e-6)
                inside = ss(0.1, 0.6, N @ _n(np.array([sx * 0.45, -1.0, 0.0]))) * mine
                pale = np.maximum(pale, inside * 0.9)
                dark = np.maximum(dark, (1.0 - inside) * mine * 0.55)
                dark = np.maximum(dark, ss(0.75, 0.98, t) * mine * 0.7)
            return np.clip(pale, 0, 1), np.clip(dark, 0, 1)
        y, z = V[:, 1], V[:, 2]
        brk = nz.fbm(V, 34.0 / s, 2)
        belly = ss(-0.15, -0.65, N[:, 2]) * ss(0.50 * s, 0.38 * s, z)
        inner_leg = ss(0.15, 0.6, -N[:, 0] * np.sign(V[:, 0] + 1e-9)) * ss(0.44 * s, 0.30 * s, z)
        lower_leg = ss(0.26 * s, 0.14 * s, z) * 0.4
        # throat and chest: the front of the neck and the brisket, facing forward and down
        front = ss(-0.1, -0.7, N[:, 1] + 0.6 * N[:, 2]) * (y < j["chest0"][1] + 0.02 * s) * (z > 0.30 * s) * \
            ss(0.07 * s, 0.03 * s, np.abs(V[:, 0]) - 0.02 * s)
        h0 = j["head0"]
        hf = (V - h0) @ self.f_ax / s
        hu = (V - h0) @ self.u_ax / s
        on_head = (hf > -0.05) & (np.abs(V[:, 0]) < 0.10 * s)
        ms = float(np.linalg.norm(j["nose"] - h0)) / s / 0.250
        cheeks = on_head * ss(0.0, -0.035, hu) * ss(-0.04, 0.0, hf)
        muzzle_side = on_head * ss(0.06 * ms, 0.11 * ms, hf) * ss(-0.005, -0.030, hu)
        brows = np.zeros(len(V))
        for c in self.eye_c:
            brows = np.maximum(brows, ss(0.016 * s, 0.006 * s, np.sqrt(((V - (c + self.u_ax * 0.020 * s)) ** 2).sum(-1))))
        pale = np.maximum.reduce([belly * 0.95, inner_leg * 0.75, lower_leg, front * 0.9, cheeks * 0.85,
                                  muzzle_side * 0.8, brows * 0.7])
        # dark: the saddle (back and shoulders), the muzzle's top line, the tail's top and its tip
        top = ss(0.25, 0.85, N[:, 2]) * (y > j["neck0"][1] - 0.04 * s) * (y < j["tail0"][1])
        saddle = top * (0.8 + 0.2 * ss(-0.2, 0.2, brk))
        muzzle_top = on_head * ss(0.07 * ms, 0.12 * ms, hf) * ss(0.005, 0.025, hu) * 0.45
        tail = ss(j["tail0"][1] - 0.01 * s, j["tail0"][1] + 0.03 * s, y) * (z < j["tail0"][2] + 0.02 * s)
        tail_top = tail * ss(-0.3, 0.4, N[:, 1]) * 0.55
        tail_tip = tail * ss(j["tail2"][2] + 0.09 * s, j["tail2"][2] + 0.02 * s, z) * 0.95
        tail_gland = tail * ss(j["tail0"][2] - 0.04 * s, j["tail0"][2] - 0.08 * s, z) * \
            ss(j["tail0"][2] - 0.14 * s, j["tail0"][2] - 0.10 * s, z) * ss(-0.2, 0.4, N[:, 1]) * 0.7
        nose = ss(0.026 * s, 0.018 * s, np.sqrt(((V - self.nose_c) ** 2).sum(-1)))
        dark = np.maximum.reduce([saddle * 0.75, muzzle_top, tail_top, tail_tip, tail_gland, nose])
        # agouti: guard hairs break up every edge
        pale = np.clip(pale + brk * 0.18 * (pale > 0.05) * (pale < 0.95), 0, 1)
        dark = np.clip((dark + brk * 0.12 * (dark > 0.05)) * (1.0 - 0.7 * pale), 0, 1)
        return pale, np.clip(np.maximum(dark, nose), 0, 1)

    # --- coat ----------------------------------------------------------------------------
    def coat(self, V, N, part: str):
        """(pale, dark) masks 0..1 per vertex (rest pose)."""
        if self.species == "hound":
            return self._hound_coat(V, N, part)
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

def mesh_program(prog: S.Program, name: str, h: float, tris: int, pad: float = 0.02, keep_islands: bool = False):
    lo, hi = prog.bounds()
    lo = lo - pad
    hi = hi + pad
    shape = tuple(int(x) for x in np.ceil((hi - lo) / h) + 1)
    d, _ = prog.eval_grid(lo, h, shape)
    V, Q = M.surface_nets(d, lo, h)
    del d
    V = M.project_to_surface(V, lambda P: prog.eval(P)[0], h, iterations=2)
    obj = M.mesh_from_arrays(name, V, Q)
    if not keep_islands:
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


def body_weights(skel, V, obj, part: str, animal: Animal | None = None):
    """(n_verts, n_bones) weights: inverse distance to each bone's segment (opposite-side legs,
    ears, the tail away from the rump and the root are excluded), top four, smoothed over the
    mesh so joints bend in a broad crease rather than a seam. A hound's lower jaw is the skin
    below its mouth slit (`animal` gives the head frame)."""
    names = skel.names
    nb = len(names)
    D = np.full((len(V), nb), np.inf)
    s = float(skel.params.get("scale", 1.0))
    hound = animal is not None and animal.species == "hound"
    if hound:
        h0 = skel.j["head0"]
        hf = (V - h0) @ animal.f_ax / s
        hu = (V - h0) @ animal.u_ax / s
        below = hu < animal.mouth_u + 0.004 * np.clip((animal.mouth_f0 - hf) / 0.03, 0.0, 1.0) - 0.0005
        lower_jaw = below & (hf > 0.035) & (np.abs(V[:, 0]) < 0.06 * s)
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
        if bn == "jaw" and hound:
            d = np.where(lower_jaw, d * 0.7, np.inf)
        elif bn == "jaw":
            d = np.where(V[:, 2] > skel.head["jaw"][2] + 0.004 * s, np.inf, d * 1.4)
        if hound and bn in ("head", "neck2") :
            # the lower jaw's skin is the jaw's alone, back to the corner of the mouth
            d = np.where(lower_jaw & (hf > animal.mouth_f0 + 0.01), np.inf, d)
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


def transfer_weights(src_V, src_W, V):
    """Weights for a mesh lying on another (the hound's growths on its hide): each vertex takes
    the weights of the nearest source vertex, so it moves exactly with the skin under it."""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(src_V))
    for i, v in enumerate(src_V):
        kd.insert(tuple(float(x) for x in v), i)
    kd.balance()
    idx = np.array([kd.find(tuple(float(x) for x in v))[1] for v in V], np.int64)
    return src_W[idx].copy()


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
