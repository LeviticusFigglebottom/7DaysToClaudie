"""The special Hollowed's features (ADR-0028): the Husk's armour and the Blister's pustules.

Both are built after the clothes (they sit on the final surface) during char_dress.dress(), as
extra meshes kept on the model (model.extra_parts: {segment: Part}) plus Bloom growth (SDF lumps)
that fuses them into the body:

  armour    curved plates conforming to the body, standing off it a little more at their lower
            edge so the next plate down tucks under, like lamellar armour: riot gear (a chest
            plate, pauldrons, forearm and shin guards), debris (torn sheet steel) and hard fungal
            shell, each rigid to its bone and fused at the edges with growth.
  pustules  taut, translucent domes in clusters (gate 4: gone once burst) over shallow wet pits,
            with a torn lip round each (gate 5: there once burst) (EnemyVisual.burst()).
"""
from __future__ import annotations

import math

import numpy as np

from . import char_body as B
from .char_attrs import GATE_BURST, GATE_PUSTULE
from .char_body import _n
from .char_extras import Part, uv_sphere
from .char_skel import rot_axis

PLATE_LABELS = {"riot": B.L_PLATE, "metal": B.L_DEBRIS, "shell": B.L_BLOOM}


def _bone_for(model, site: dict, seg: str) -> str:
    side = site.get("side", "L")
    at = site["at"]
    if at in ("ua", "fa", "th", "sh"):
        return {"ua": "upper_arm", "fa": "forearm", "th": "thigh", "sh": "shin"}[at] + "." + side
    if at == "head":
        return "head"
    return at if at in ("hips", "spine", "chest", "neck") else "chest"


def plate(model, spec: dict, rng):
    """One armour plate: (Part, segment, edge points). The plate is a grid of rays fanned round the
    bone from the site's origin, each hitting the surface; the top skin stands `standoff + thick`
    off it, the underside `standoff`, and the lower edge leans out by `tilt` so the next plate
    tucks under it."""
    from .char_dress import site_point, surface_hit
    s = model.s
    kind = spec.get("kind", "riot")
    label = PLATE_LABELS.get(kind, B.L_PLATE)
    origin, direction, seg = site_point(model, spec)
    p0, n0 = surface_hit(model, origin, direction)
    r0 = max(float(np.linalg.norm(p0 - origin)), 0.02 * s)
    bone = _bone_for(model, spec, seg)
    if spec["at"] in ("ua", "fa", "th", "sh"):
        f = (model.arm if spec["at"] in ("ua", "fa") else model.leg)[spec.get("side", "L")][spec["at"]]
        up = f.axis * (-1.0 if spec["at"] in ("ua", "fa", "th", "sh") else 1.0)
    else:
        up = model.skel.rest[spec["at"] if spec["at"] in ("hips", "spine", "chest", "neck") else "chest"][:, 1]
    up = _n(up - n0 * float(up @ n0))
    w = float(spec.get("w", 0.14)) * s
    h = float(spec.get("h", 0.12)) * s
    standoff = float(spec.get("standoff", 0.010)) * s
    thick = float(spec.get("thick", 0.007 if kind != "shell" else 0.010)) * s
    tilt = float(spec.get("tilt", 0.012)) * s
    nu, nv = 6, 5
    top = np.zeros((nv, nu, 3))
    bot = np.zeros((nv, nu, 3))
    uvs = np.zeros((nv, nu, 2))
    for iv in range(nv):
        v = (iv / (nv - 1) - 0.5) * h
        for iu in range(nu):
            u = (iu / (nu - 1) - 0.5) * w
            # rounded corners for riot gear, ragged torn outlines for debris, oval for shell
            cu, cv = 2 * u / w, 2 * v / h
            if kind == "riot":
                corner = max(0.0, (abs(cu) ** 4 + abs(cv) ** 4) - 0.75)
                pull = 1.0 - 0.18 * corner
            elif kind == "shell":
                pull = 1.0 - 0.25 * max(0.0, cu * cu + cv * cv - 0.6)
            else:
                pull = 1.0 - (rng.uniform(0.0, 0.22) if (iu in (0, nu - 1) or iv in (0, nv - 1)) else 0.0)
            uu, vv = u * pull, v * pull
            ang = uu / r0
            d = rot_axis(up, ang) @ n0
            o = origin + up * vv
            hit, nh = surface_hit(model, o, d, max_dist=0.35 * s)
            lean = tilt * (0.5 - vv / h)
            bulge = (0.003 * s * (1.0 - cu * cu)) if kind == "riot" else 0.0
            lump = rng.normal(0, 0.0025 * s) if kind == "shell" else 0.0
            bot[iv, iu] = hit + nh * (standoff + lean)
            top[iv, iu] = hit + nh * (standoff + lean + thick + bulge + lump)
            uvs[iv, iu] = (uu, vv)
    verts = list(top.reshape(-1, 3)) + list(bot.reshape(-1, 3))
    nt = nu * nv
    faces, fuv = [], []

    def idx(iv, iu, layer):
        return layer * nt + iv * nu + iu
    for iv in range(nv - 1):
        for iu in range(nu - 1):
            q = (idx(iv, iu, 0), idx(iv, iu + 1, 0), idx(iv + 1, iu + 1, 0), idx(iv + 1, iu, 0))
            faces.append(q)
            fuv.append([tuple(uvs[iv, iu]), tuple(uvs[iv, iu + 1]), tuple(uvs[iv + 1, iu + 1]), tuple(uvs[iv + 1, iu])])
            qb = (idx(iv, iu, 1), idx(iv + 1, iu, 1), idx(iv + 1, iu + 1, 1), idx(iv, iu + 1, 1))
            faces.append(qb)
            fuv.append([tuple(uvs[iv, iu]), tuple(uvs[iv + 1, iu]), tuple(uvs[iv + 1, iu + 1]), tuple(uvs[iv, iu + 1])])
    ring = [(0, iu) for iu in range(nu)] + [(iv, nu - 1) for iv in range(1, nv)] + \
        [(nv - 1, iu) for iu in range(nu - 2, -1, -1)] + [(iv, 0) for iv in range(nv - 2, 0, -1)]
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        faces.append((idx(a[0], a[1], 1), idx(b[0], b[1], 1), idx(b[0], b[1], 0), idx(a[0], a[1], 0)))
        fuv.append([(k * 0.02, 0.0), ((k + 1) * 0.02, 0.0), ((k + 1) * 0.02, thick), (k * 0.02, thick)])
    part = Part()
    # outward winding check: the first top face's normal must point away from the body
    a, b, c = top[0, 0], top[0, 1], top[1, 1]
    if float(np.cross(b - a, c - a) @ n0) < 0:
        faces = [tuple(reversed(f)) for f in faces]
        fuv = [list(reversed(u)) for u in fuv]
    part.add(verts, faces, label, bone=bone, uvs=fuv)
    edge = [top[iv, iu] for iv, iu in ring[::2]]
    return part, seg, edge


def add_armour(model, specs: list, rng) -> None:
    """Plates in the order given (top rows first, so each lower plate tucks under the one above),
    fused into the body with Bloom growth along their edges."""
    s = model.s
    for spec in specs:
        part, seg, edge = plate(model, spec, rng)
        model.extra_parts.setdefault(seg, Part()).merge(part)
        fuse = float(spec.get("fuse", 0.6))
        for p in edge:
            if rng.random() < fuse:
                model.growth.sphere(p + rng.normal(0, 0.004, 3) * s, rng.uniform(0.008, 0.016) * s, k=0.006 * s,
                                    label=B.L_BLOOM)


def add_pustules(model, spec: dict, rng) -> None:
    """Clusters of pustules: a taut translucent dome over a shallow wet pit; once burst, the dome
    is gone and a torn lip rings the pit."""
    from .char_dress import site_point, surface_hit
    s = model.s
    for site in spec.get("sites", []):
        origin, direction, seg = site_point(model, site)
        bone = _bone_for(model, site, seg)
        count = int(site.get("count", 6))
        spread = float(site.get("spread", 0.6))
        size = float(site.get("size", 0.022))
        dirs = []
        for i in range(count):
            d = _n(direction + rng.normal(0, spread * 0.5, 3))
            dirs.append(d)
        for d in dirs:
            p, nrm = surface_hit(model, origin, d)
            r = size * s * rng.uniform(0.45, 1.0)
            part = model.extra_parts.setdefault(seg, Part())
            # the dome: a sphere sunk into the skin, its axis along the surface normal
            c = p + nrm * r * 0.35
            # the big ones are seen up close: rounder outlines for them, cheap ones for the small
            big = r > 0.015 * s
            v, f, uv = uv_sphere(c, r, nrm, seg=10 if big else 7, rings=5 if big else 4)
            part.add(v, f, B.L_PUSTULE, bone=bone, uvs=uv, gate=GATE_PUSTULE)
            # the pit under it (wet and raw once open)
            model.skin.sphere(p + nrm * r * 0.15, r * 0.75, k=0.003 * s, label=B.L_GORE, mode="sub")
            # the torn lip that is left when it bursts
            t1 = _n(np.cross(nrm, (0.0, 0.0, 1.0)) if abs(nrm[2]) < 0.9 else np.cross(nrm, (1.0, 0.0, 0.0)))
            t2 = np.cross(nrm, t1)
            n = 8
            lv = []
            for k in range(n):
                ang = 2 * math.pi * k / n
                rr = r * 0.8 * rng.uniform(0.85, 1.15)
                rim = p + (t1 * math.cos(ang) + t2 * math.sin(ang)) * rr
                lv.append(rim - nrm * 0.0015 * s)
                lv.append(rim + nrm * r * rng.uniform(0.15, 0.4) + (t1 * math.cos(ang) + t2 * math.sin(ang)) * r * 0.15)
            lf = []
            for k in range(n):
                k2 = (k + 1) % n
                lf.append((2 * k, 2 * k2, 2 * k2 + 1, 2 * k + 1))
            part.add(lv, lf, B.L_PUSTULE, bone=bone, gate=GATE_BURST)
        model.bloom_sites.append((origin + direction * 0.05 * s, size * s * 3.0, 0.7))
