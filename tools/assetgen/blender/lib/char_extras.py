"""Small hand-built character meshes: eyes, teeth, Bloom filaments and shelf growths, stump caps.

All return (verts (V,3), faces list[tuple], per-face label list, per-vertex rigid bone name or
weights) so the caller can append them to a segment mesh. Deterministic (seeded RNG).
"""
from __future__ import annotations

import math

import numpy as np

from .char_body import L_BLOOM, L_EYES, L_GORE, L_TEETH, _n
from .char_skel import rot_axis


class Part:
    """Accumulates geometry for one target object."""

    def __init__(self):
        self.V: list[np.ndarray] = []
        self.F: list[tuple] = []
        self.L: list[int] = []
        self.bone: list[str] = []   # rigid bone per vertex ('' = use the segment weight function)
        self.uvmode: list[str] = []  # per face: 'keep' (explicit uv) or 'auto'
        self.UV: list = []           # per face list of per-corner uv or None

    def add(self, verts, faces, label, bone="", uvs=None):
        base = len(self.V)
        for v in verts:
            self.V.append(np.asarray(v, dtype=np.float64))
            self.bone.append(bone)
        for i, f in enumerate(faces):
            self.F.append(tuple(base + k for k in f))
            self.L.append(label)
            self.UV.append(None if uvs is None else uvs[i])

    def merge(self, other: "Part"):
        base = len(self.V)
        self.V += other.V
        self.bone += other.bone
        self.F += [tuple(base + k for k in f) for f in other.F]
        self.L += other.L
        self.UV += other.UV


def uv_sphere(center, radius, axis, seg=8, rings=6):
    """Sphere with poles along `axis`; returns verts, faces, per-face uvs (planar along axis)."""
    axis = _n(axis)
    t1 = _n(np.cross(axis, (0, 0, 1) if abs(axis[2]) < 0.9 else (1, 0, 0)))
    t2 = np.cross(axis, t1)
    verts = [center + axis * radius]
    for r in range(1, rings):
        th = math.pi * r / rings
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            verts.append(center + axis * radius * math.cos(th) + (t1 * math.cos(ph) + t2 * math.sin(ph)) * radius * math.sin(th))
    verts.append(center - axis * radius)
    faces = []
    for k in range(seg):
        faces.append((0, 1 + k, 1 + (k + 1) % seg))
    for r in range(rings - 2):
        b0 = 1 + r * seg
        b1 = b0 + seg
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((b0 + k, b1 + k, b1 + k2, b0 + k2))
    last = len(verts) - 1
    b0 = 1 + (rings - 2) * seg
    for k in range(seg):
        faces.append((b0 + k, last, b0 + (k + 1) % seg))
    # planar uv along the axis: centre of the texture = front pole
    uvs = []
    for f in faces:
        uvs.append([(0.5 + 0.5 * float((verts[i] - center) @ t1) / radius,
                     0.5 + 0.5 * float((verts[i] - center) @ t2) / radius) for i in f])
    return verts, faces, uvs


def eyes(model) -> Part:
    p = Part()
    s = model.s
    R = model.hR
    wall = float(model.p.get("wall_eye", 4.0))
    for sx in (1.0, -1.0):
        c = model.HP(sx * 0.032, 0.012, 0.073)
        gaze = rot_axis(R[:, 1], sx * math.radians(wall)) @ R[:, 2]
        gaze = rot_axis(R[:, 0], math.radians(-3)) @ gaze
        v, f, uv = uv_sphere(c, 0.0116 * s, gaze, seg=8, rings=5)
        p.add(v, f, L_EYES, bone="head", uvs=uv)
    return p


def _box(center, half, R):
    corners = []
    for z in (-1, 1):
        for y in (-1, 1):
            for x in (-1, 1):
                corners.append(center + R @ (np.array([x, y, z]) * half))
    # faces (outward): -x, +x, -y, +y, -z, +z
    faces = [(0, 4, 6, 2), (1, 3, 7, 5), (0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6)]
    return corners, faces


def teeth(model, rng) -> Part:
    """Upper row rigid to the head, lower row rigid to the jaw (rest pose positions)."""
    p = Part()
    s = model.s
    R = model.hR
    left, up, front = R[:, 0], R[:, 1], R[:, 2]
    missing = float(model.p.get("teeth_missing", 0.2))
    jaw0 = model.skel.head["jaw"]
    jaw_rest = model.skel.rest["jaw"]
    # upper arc (behind the upper lip)
    for row in ("upper", "lower"):
        if row == "upper":
            cen = model.HP(0, -0.0605, 0.064)
            rot = np.eye(3)
            down = -up
            bone = "head"
        else:
            # lower teeth follow the jaw: build at the closed-jaw spot then rotate by the rest drop
            cen = model.HP(0, -0.0665, 0.061)
            drop = math.radians(float(model.p.get("jaw_drop", 6.0)) - 6.0)
            rot = rot_axis(left, drop)
            down = up
            bone = "jaw"
        n = 10
        for i in range(n):
            phi = (i + 0.5) / n * math.radians(150) - math.radians(75)
            if rng.random() < missing:
                continue
            ar = 0.023 * s
            pos = cen + left * math.sin(phi) * ar * 1.05 + front * math.cos(phi) * ar
            tang = _n(left * math.cos(phi) - front * math.sin(phi) * 1.0)
            outn = _n(np.cross(down, tang) * (1 if row == "upper" else -1))
            front_tooth = abs(phi) < math.radians(35)
            w = (0.0034 if front_tooth else 0.0042) * s
            h = (0.0052 if front_tooth else 0.0042) * s * rng.uniform(0.75, 1.15)
            dpt = (0.0025 if front_tooth else 0.0040) * s
            Rt = np.stack([tang, outn, -down], 1)
            c = pos + down * h * 0.6
            if row == "lower":
                c = jaw0 + rot @ (c - jaw0)
                Rt = rot @ Rt
            v, f = _box(c, np.array([w, dpt, h]), Rt)
            p.add(v, f, L_TEETH, bone=bone)
    return p


def filament(root, direction, length, radius, rng, sag=0.6, segs=4):
    """Thin drooping fungal strand (triangular tube)."""
    d = _n(direction)
    pts = [np.asarray(root, dtype=np.float64)]
    for i in range(segs):
        d = _n(d + np.array([0.0, 0.0, -sag / segs]) + rng.normal(0, 0.18, 3))
        pts.append(pts[-1] + d * length / segs)
    verts = []
    faces = []
    for i, c in enumerate(pts):
        t = i / segs
        r = radius * (1.0 - 0.75 * t)
        tan = _n(pts[min(i + 1, segs)] - pts[max(i - 1, 0)])
        a = _n(np.cross(tan, (0.3, 0.5, 0.8)))
        b = np.cross(tan, a)
        for k in range(3):
            ang = 2 * math.pi * k / 3
            verts.append(c + (a * math.cos(ang) + b * math.sin(ang)) * r)
    for i in range(segs):
        for k in range(3):
            k2 = (k + 1) % 3
            faces.append((i * 3 + k, i * 3 + k2, (i + 1) * 3 + k2, (i + 1) * 3 + k))
    tip = len(verts)
    verts.append(pts[-1] + _n(pts[-1] - pts[-2]) * radius)
    for k in range(3):
        faces.append((segs * 3 + k, segs * 3 + (k + 1) % 3, tip))
    return verts, faces


def shelf(center, normal, size, rng, up=(0, 0, 1)):
    """Bracket-fungus plate: a lumpy half-disc sticking out of the surface along `normal`."""
    n = _n(normal)
    upv = np.asarray(up, dtype=np.float64)
    upv = _n(upv - n * float(upv @ n)) if abs(float(upv @ n)) < 0.95 else _n(np.cross(n, (1, 0, 0)))
    side = np.cross(upv, n)
    k = 6
    top, bot = [], []
    thick = size * 0.22
    for i in range(k + 1):
        a = math.pi * i / k
        rr = size * (0.75 + 0.25 * rng.random())
        p = center + side * math.cos(a) * rr * 1.2 + n * math.sin(a) * rr - upv * size * 0.15 * math.sin(a)
        top.append(p + upv * thick * 0.5)
        bot.append(p - upv * thick * 0.5)
    c_top = center + upv * thick * 0.6
    c_bot = center - upv * thick * 0.4
    verts = top + bot + [c_top, c_bot]
    ct, cb = len(verts) - 2, len(verts) - 1
    faces = []
    for i in range(k):
        faces.append((ct, i + 1, i))                       # top fan
        faces.append((cb, k + 1 + i, k + 1 + i + 1))       # bottom fan
        faces.append((i, i + 1, k + 1 + i + 1, k + 1 + i))  # rim
    return verts, faces


def bloom(model, rng) -> dict[str, Part]:
    """Filaments + shelf growths at the body's Bloom sites; returns {segment: Part}."""
    out: dict[str, Part] = {}
    for site in model.bloom_extras:
        seg = site["segment"]
        part = out.setdefault(seg, Part())
        c = np.asarray(site["center"])
        nrm = _n(site["normal"])
        for _ in range(int(site.get("filaments", 0))):
            jitter = _n(nrm + rng.normal(0, 0.45, 3))
            root = c + jitter * site.get("radius", 0.02) * 0.6
            length = rng.uniform(0.6, 1.0) * site.get("length", 0.06)
            v, f = filament(root, _n(nrm * 0.7 + jitter * 0.6), length, rng.uniform(0.0011, 0.0019) * model.s,
                            rng, sag=site.get("sag", 0.6))
            part.add(v, f, L_BLOOM)
        for _ in range(int(site.get("shelves", 0))):
            jitter = _n(nrm + rng.normal(0, 0.35, 3))
            sc = c + jitter * site.get("radius", 0.02) * rng.uniform(0.3, 0.9)
            v, f = shelf(sc, jitter, rng.uniform(0.6, 1.0) * site.get("shelf_size", 0.018) * model.s, rng)
            part.add(v, f, L_BLOOM)
    return out


def stump_cap(model, cut: str, rng, n_ang: int = 8):
    """Gore cap for a cut: a ragged dome inside the child's surface plus a bone end.
    Returns (verts, faces, labels) in rest armature space."""
    c, nrm = model.cuts[cut]
    nrm = _n(nrm)
    # in-plane basis
    a = _n(np.cross(nrm, (0.0, 1.0, 0.0)) if abs(nrm[1]) < 0.9 else np.cross(nrm, (1.0, 0.0, 0.0)))
    b = np.cross(nrm, a)
    # radial profile of the body cross-section on the cut plane (first exit along each ray)
    angs = [2 * math.pi * i / n_ang for i in range(n_ang)]
    steps = np.linspace(0.004, 0.22, 110) * model.s
    R = []
    for th in angs:
        dvec = a * math.cos(th) + b * math.sin(th)
        P = c + np.outer(steps, dvec)
        d, _ = model.eval_points(P, None)
        out_idx = np.nonzero(d > 0)[0]
        R.append(float(steps[out_idx[0]]) if len(out_idx) else float(steps[-1]))
    R = np.array(R)
    # centroid of the section (rays from the cut point may be off-centre, e.g. hips)
    pts2 = np.stack([R * np.cos(angs), R * np.sin(angs)], -1)
    cen2 = pts2.mean(0)
    centre = c + a * cen2[0] + b * cen2[1]
    rel = pts2 - cen2
    radii = np.sqrt((rel ** 2).sum(-1))
    dirs = rel / radii[:, None]
    verts, faces, labels = [], [], []
    rings = [(-0.003, 0.95), (0.008, 0.80), (0.015, 0.45)]
    for (off, sc) in rings:
        for i in range(n_ang):
            jitter = 1.0 + rng.uniform(-0.08, 0.06)
            p = centre + nrm * off * model.s + (a * dirs[i, 0] + b * dirs[i, 1]) * radii[i] * sc * jitter
            verts.append(p)
    apex = len(verts)
    verts.append(centre + nrm * 0.019 * model.s)
    for r in range(len(rings) - 1):
        for i in range(n_ang):
            i2 = (i + 1) % n_ang
            faces.append((r * n_ang + i, r * n_ang + i2, (r + 1) * n_ang + i2, (r + 1) * n_ang + i))
            labels.append(L_GORE)
    base = (len(rings) - 1) * n_ang
    for i in range(n_ang):
        faces.append((base + i, base + (i + 1) % n_ang, apex))
        labels.append(L_GORE)
    # bone end: small hexagonal prism sticking out of the dome
    br = max(0.006, 0.17 * float(np.median(radii)))
    b0 = len(verts)
    for k in range(6):
        ang = 2 * math.pi * k / 6
        verts.append(centre + nrm * 0.006 * model.s + (a * math.cos(ang) + b * math.sin(ang)) * br)
    for k in range(6):
        ang = 2 * math.pi * k / 6
        verts.append(centre + nrm * (0.024 + rng.uniform(-0.004, 0.004)) * model.s + (a * math.cos(ang) + b * math.sin(ang)) * br * 0.92)
    for k in range(6):
        k2 = (k + 1) % 6
        faces.append((b0 + k, b0 + k2, b0 + 6 + k2, b0 + 6 + k))
        labels.append(L_TEETH)
    faces.append(tuple(b0 + 6 + k for k in range(6)))
    labels.append(L_TEETH)
    return verts, faces, labels
