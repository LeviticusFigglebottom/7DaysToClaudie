"""Small hand-built character meshes: eyes, teeth, Bloom filaments and shelf growths, stump caps.

All return (verts (V,3), faces list[tuple], per-face label list, per-vertex rigid bone name or
weights) so the caller can append them to a segment mesh. Deterministic (seeded RNG).
"""
from __future__ import annotations

import math

import numpy as np

from .char_body import L_BLOOM, L_CORD, L_EYES, L_GORE, L_HARDWARE, L_NAIL, L_SHIRT, L_TEETH, _n
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
        self.gate: list[float] = []  # per vertex: char_attrs gate code (0 = always shown)

    def add(self, verts, faces, label, bone="", uvs=None, gate: float = 0.0):
        base = len(self.V)
        for v in verts:
            self.V.append(np.asarray(v, dtype=np.float64))
            self.bone.append(bone)
            self.gate.append(float(gate))
        for i, f in enumerate(faces):
            self.F.append(tuple(base + k for k in f))
            self.L.append(label)
            self.UV.append(None if uvs is None else uvs[i])

    def merge(self, other: "Part"):
        base = len(self.V)
        self.V += other.V
        self.bone += other.bone
        self.gate += other.gate
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
        c, er = model.eye(sx) if hasattr(model, "eye") else (model.HP(sx * 0.032, 0.012, 0.073), 0.0116 * s)
        gaze = rot_axis(R[:, 1], sx * math.radians(wall)) @ R[:, 2]
        gaze = rot_axis(R[:, 0], math.radians(-3)) @ gaze
        v, f, uv = uv_sphere(c, er, gaze, seg=12, rings=8)
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


def _tooth(center, width, height, depth, R, tip_scale, rng, broken=False):
    """A tooth crown as a tapered, slightly bulged block: R columns = (along the arch, out of the
    mouth, towards the biting edge). Returns verts, quad faces."""
    verts = []
    rows = (0.0, 0.55, 1.0)
    for ri, t in enumerate(rows):
        # widest a little above the neck, narrowing to the biting edge; a broken tooth is short and
        # its edge jagged
        w = width * (0.82 + 0.25 * math.sin(math.pi * min(1.0, t * 1.1)) - (1.0 - tip_scale) * t)
        d = depth * (1.0 - 0.35 * t)
        z = height * t * (0.55 if broken else 1.0)
        for k, (x, y) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
            jag = rng.uniform(-0.3, 0.3) * height * 0.25 if (broken and ri == 2) else 0.0
            verts.append(center + R @ np.array([x * w, y * d, z + jag]))
    faces = []
    for ri in range(len(rows) - 1):
        b0, b1 = ri * 4, (ri + 1) * 4
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((b0 + k, b0 + k2, b1 + k2, b1 + k))
    faces.append((8, 9, 10, 11))       # biting edge
    faces.append((3, 2, 1, 0))         # root end (hidden in the gum)
    return verts, faces


def teeth(model, rng) -> Part:
    """Upper row rigid to the head, lower row rigid to the jaw (rest pose positions). Yellowed,
    uneven crowns, some missing or broken, set in receded dark gums."""
    p = Part()
    s = model.s
    R = model.hR
    left, up, front = R[:, 0], R[:, 1], R[:, 2]
    missing = float(model.p.get("teeth_missing", 0.2))
    recede = float(model.p.get("gum_recede", 0.5))
    jaw0 = model.skel.head["jaw"]
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
        n = 12
        ar = 0.023 * s
        gum_pts = []
        for i in range(n):
            phi = (i + 0.5) / n * math.radians(160) - math.radians(80)
            pos = cen + left * math.sin(phi) * ar * 1.05 + front * math.cos(phi) * ar
            tang = _n(left * math.cos(phi) - front * math.sin(phi) * 1.0)
            outn = _n(np.cross(down, tang) * (1 if row == "upper" else -1))
            gum_pts.append((pos, tang, outn))
            if rng.random() < missing:
                continue
            front_tooth = abs(phi) < math.radians(38)
            w = (0.0031 if front_tooth else 0.0040) * s
            h = (0.0060 if front_tooth else 0.0046) * s * rng.uniform(0.85, 1.15) * (1.0 + 0.35 * recede)
            dpt = (0.0024 if front_tooth else 0.0038) * s
            # crowns grow from the gum line towards the bite: R = (along, out, towards the bite)
            Rt = np.stack([tang, outn, down], 1)
            base = pos - down * 0.0025 * s * recede
            broken = rng.random() < 0.18
            v, f = _tooth(base, w, h, dpt, Rt, 0.75 if front_tooth else 0.9, rng, broken)
            if row == "lower":
                v = [jaw0 + rot @ (np.asarray(x) - jaw0) for x in v]
            p.add(v, f, L_TEETH, bone=bone)
        # the gum: a band along the arch over the roots, dark and wet (gore), drawn back off the teeth
        gv = []
        for pos, tang, outn in gum_pts:
            top = pos - down * (0.0045 + 0.004 * recede) * s
            for off_out, off_dn in ((0.0030, -0.0010), (0.0012, 0.0016 - 0.002 * recede), (-0.0022, 0.0006)):
                q = top + outn * off_out * s + down * off_dn * s
                if row == "lower":
                    q = jaw0 + rot @ (q - jaw0)
                gv.append(q)
        gf = []
        for i in range(n - 1):
            for r in range(2):
                a0, a1 = i * 3 + r, (i + 1) * 3 + r
                gf.append((a0, a1, a1 + 1, a0 + 1) if row == "upper" else (a0 + 1, a1 + 1, a1, a0))
        p.add(gv, gf, L_GORE, bone=bone)
    return p


def nails(model, rng) -> dict[str, Part]:
    """Thick, ridged dead nails on the fingertips (a curved plate standing just proud of the skin),
    some torn off to the nail bed. Rigid to the hand bone; returns {segment: Part}."""
    out = {}
    torn = float(model.p.get("nails_torn", 0.25))
    for side, tips in model.fingertips.items():
        part = out.setdefault(f"body_forearm.{side}", Part())
        for (j, tip, d, dorsal, r) in tips:
            length = float(np.linalg.norm(tip - j))
            lat = _n(np.cross(d, dorsal))
            c = tip - d * length * 0.42
            ln, w = length * 0.62, r * 0.82
            lab = L_GORE if rng.random() < torn else L_NAIL
            verts = []
            for a in (-1.0, 0.0, 1.0):                      # along the finger
                for b in (-1.0, -0.4, 0.4, 1.0):             # across, curving round the fingertip
                    ang = b * 0.9
                    off = dorsal * (r * math.cos(ang) + 0.0004) + lat * (r * math.sin(ang)) * (w / r)
                    lift = 0.00035 if lab == L_NAIL else -0.0002
                    verts.append(c + d * (a * ln * 0.5) + off + dorsal * lift)
            faces = []
            for i in range(2):
                for k in range(3):
                    a0 = i * 4 + k
                    faces.append((a0, a0 + 1, a0 + 5, a0 + 4))
            part.add(verts, faces, lab, bone=f"hand.{side}")
    return out


def disk(center, normal, radius, thick, n=8):
    """A short closed cylinder (button, stud) standing on `center` along `normal`."""
    nrm = _n(normal)
    a = _n(np.cross(nrm, (0.0, 0.0, 1.0)) if abs(nrm[2]) < 0.9 else np.cross(nrm, (1.0, 0.0, 0.0)))
    b = np.cross(nrm, a)
    verts = []
    for z in (0.0, thick):
        for k in range(n):
            ang = 2 * math.pi * k / n
            verts.append(center + nrm * z + (a * math.cos(ang) + b * math.sin(ang)) * radius * (0.92 if z > 0 else 1.0))
    verts.append(center + nrm * thick * 1.15)
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    faces += [(n + k, n + (k + 1) % n, 2 * n) for k in range(n)]
    return verts, faces


def ring_round(model, origin, axis, ref, offset, n=10):
    """Points round a limb or the neck: where rays from `origin` (on the axis), perpendicular to
    it, leave the body's surface (garments included), pushed out by `offset`."""
    from .char_dress import surface_hit
    axis = _n(axis)
    ref = _n(ref - axis * float(ref @ axis))
    oth = np.cross(axis, ref)
    pts, nrms = [], []
    for k in range(n):
        ang = 2 * math.pi * k / n
        d = ref * math.cos(ang) + oth * math.sin(ang)
        p, nrm = surface_hit(model, origin, d, max_dist=0.25 * model.s)
        pts.append(p + d * offset)
        nrms.append(d)
    return pts, nrms


def band(model, origin, axis, ref, width, offset, label, bone, n=10) -> Part:
    """A closed band (wristband, cuff) round a limb."""
    p = Part()
    axis = _n(axis)
    verts = []
    for z in (-0.5, 0.5):
        pts, _ = ring_round(model, origin + axis * z * width, axis, ref, offset, n)
        verts += pts
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    p.add(verts, faces, label, bone=bone)
    return p


def accessories(model, rng) -> dict[str, Part]:
    """Small rigid props a body wears (params "accessories"): a hospital wristband, an IV
    cannula taped to the back of the hand, a necklace of beads or bone charms, a lanyard with an
    ID card. Returns {segment: Part}."""
    from .char_dress import surface_hit
    out: dict[str, Part] = {}
    s = model.s
    sk = model.skel
    for acc in model.p.get("accessories", []):
        kind = acc.get("kind", "")
        side = acc.get("side", "L")
        if kind == "wristband":
            fa = model.arm[side]["fa"]
            part = band(model, fa.at(0.90), fa.axis, fa.out, 0.012 * s, 0.0012 * s, L_HARDWARE, f"forearm.{side}")
            out.setdefault(f"body_forearm.{side}", Part()).merge(part)
        elif kind == "iv":
            hf = model.arm[side]["hand"]
            wr = sk.j[f"wrist.{side}"]
            back = _n(sk.j[f"palm_back.{side}"] - wr)
            o = wr + hf.axis * 0.035 * s
            pnt, nrm = surface_hit(model, o, back, max_dist=0.06 * s)
            part = Part()
            tape_r = np.stack([_n(np.cross(nrm, hf.axis)), hf.axis, nrm], 1)
            v, f = _box(pnt + nrm * 0.0008 * s, np.array([0.014, 0.018, 0.0007]) * s, tape_r)
            part.add(v, f, L_SHIRT, bone=f"hand.{side}")
            v, f = disk(pnt + nrm * 0.0015 * s - hf.axis * 0.006 * s, nrm, 0.0042 * s, 0.006 * s, n=6)
            part.add(v, f, L_HARDWARE, bone=f"hand.{side}")
            out.setdefault(f"body_forearm.{side}", Part()).merge(part)
        elif kind in ("necklace", "lanyard"):
            R = sk.rest["chest"]
            base = sk.head["neck"] + R @ np.array([0.0, -0.012, 0.010]) * s
            n = 14
            pts, nrms = ring_round(model, base, R[:, 1], R[:, 2], 0.004 * s, n)
            # it hangs: lower at the front than at the back
            hang = [max(0.0, float(nr @ R[:, 2])) ** 1.5 * (0.05 if kind == "necklace" else 0.11) * s for nr in nrms]
            pts = [pt - R[:, 1] * hg for pt, hg in zip(pts, hang)]
            part = Part()
            cv = []
            for i, pt in enumerate(pts):
                tan = _n(pts[(i + 1) % n] - pts[i - 1])
                aa = _n(np.cross(tan, nrms[i]))
                for k in range(3):
                    ang = 2 * math.pi * k / 3
                    cv.append(pt + (aa * math.cos(ang) + nrms[i] * math.sin(ang)) * 0.0012 * s)
            cf = []
            for i in range(n):
                j2 = (i + 1) % n
                for k in range(3):
                    k2 = (k + 1) % 3
                    cf.append((i * 3 + k, i * 3 + k2, j2 * 3 + k2, j2 * 3 + k))
            part.add(cv, cf, L_CORD, bone="chest")
            if kind == "necklace":
                lab = L_TEETH if acc.get("beads", "bone") == "bone" else L_HARDWARE
                for i, pt in enumerate(pts):
                    if float(nrms[i] @ R[:, 2]) < -0.2:
                        continue
                    length = (0.020 if lab == L_TEETH and i % 2 == 0 else 0.008) * s
                    v, f = disk(pt - R[:, 1] * length * 0.5 + nrms[i] * 0.002 * s, -R[:, 1], 0.0035 * s, length, n=5)
                    part.add(v, f, lab, bone="chest")
            else:
                front = pts[int(np.argmax([float(nr @ R[:, 2]) for nr in nrms]))]
                card = front - R[:, 1] * 0.045 * s + R[:, 2] * 0.006 * s
                v, f = _box(card, np.array([0.027, 0.0008, 0.042]) * s, np.stack([R[:, 0], R[:, 2], R[:, 1]], 1))
                part.add(v, f, L_HARDWARE, bone="chest")
            out.setdefault("body_torso", Part()).merge(part)
    return out


def buttons(model, rng) -> dict[str, Part]:
    """Buttons down the plackets of the tops that button (spec "buttons": how many)."""
    from .char_dress import surface_hit
    from .char_wardrobe import Top, TrunkFrame, closest_on_polyline
    out: dict[str, Part] = {}
    s = model.s
    for g in model.garments:
        if not isinstance(g, Top) or not g.spec.get("buttons"):
            continue
        n = int(g.spec["buttons"])
        mz = model.measures
        tf = TrunkFrame(model)
        top = g.neck_base_h - 0.03 * s
        bottom = max(g.hem + 0.04 * s, 0.0)
        part = out.setdefault("body_torso", Part())
        for i in range(n):
            if g.torn > 0.3 and rng.random() < g.torn * 0.5:
                continue       # torn off
            h = top - (top - bottom) * i / max(1, n - 1)
            # a point on the trunk axis at that height, and the front there
            probe = mz.pel + mz.up * h
            q0, _, idx, _ = closest_on_polyline(probe[None], tf.pts)
            fr = tf.R[int(idx[0])][:, 2]
            pnt, nrm = surface_hit(model, q0[0], fr, max_dist=0.3 * s)
            v, f = disk(pnt - nrm * 0.0004 * s, nrm, 0.0052 * s, 0.0022 * s, n=8)
            part.add(v, f, L_HARDWARE)
    return out


def fruiting_cap(base, direction, stem_len, stem_r, cap_r, rng):
    """One Bloom fruiting body: a tapered stem and a domed cap with a thin, turned-down margin
    (the skin shader lets light through it). Returns verts, faces."""
    d = _n(direction)
    a = _n(np.cross(d, (0.0, 0.0, 1.0)) if abs(d[2]) < 0.9 else np.cross(d, (1.0, 0.0, 0.0)))
    b = np.cross(d, a)
    bend = _n(d + (a * rng.normal(0, 0.25) + b * rng.normal(0, 0.25)))
    top = base + bend * stem_len
    verts, faces = [], []

    def ring(c, r, n, wob=0.0):
        out = []
        for k in range(n):
            ang = 2 * math.pi * k / n
            rr = r * (1.0 + wob * rng.uniform(-1, 1))
            out.append(c + (a * math.cos(ang) + b * math.sin(ang)) * rr)
        return out
    n = 5
    verts += ring(base - d * stem_r, stem_r * 1.3, n)       # foot, sunk into the host
    verts += ring(top, stem_r * 0.8, n)
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k, k2, n + k2, n + k))
    m = 7
    c0 = len(verts)
    cap_h = cap_r * rng.uniform(0.35, 0.6)
    verts += ring(top - bend * cap_h * 0.35, cap_r, m, 0.12)            # the margin, turned down
    verts += ring(top + bend * cap_h * 0.55, cap_r * 0.72, m, 0.06)
    apex = len(verts)
    verts.append(top + bend * cap_h)
    for k in range(m):
        k2 = (k + 1) % m
        faces.append((c0 + k, c0 + k2, c0 + m + k2, c0 + m + k))
        faces.append((c0 + m + k, c0 + m + k2, apex))
    # underside (gills) back to the stem
    under = len(verts)
    verts.append(top - bend * cap_h * 0.05)
    for k in range(m):
        faces.append((c0 + (k + 1) % m, c0 + k, under))
    return verts, faces


TIER_SITES = [
    # (site, Seeded or Bloomed, cluster size m, caps, strands)
    ({"at": "head", "side": "R", "dir": [0.35, 0.75, -0.55]}, 1, 0.030, 3, 2),
    ({"at": "neck", "side": "L", "t": 0.6, "dir": [0.4, 0.0, -1.0]}, 1, 0.026, 2, 3),
    ({"at": "chest", "side": "L", "t": 0.85, "dir": [0.7, 0.6, -0.4]}, 1, 0.032, 3, 2),
    ({"at": "head", "side": "L", "dir": [-0.2, 0.9, 0.2]}, 2, 0.040, 4, 2),
    ({"at": "chest", "side": "R", "t": 0.80, "dir": [0.75, 0.55, -0.35]}, 2, 0.040, 4, 3),
    ({"at": "spine", "side": "L", "t": 0.6, "dir": [0.15, 0.0, -1.0]}, 2, 0.045, 4, 3),
    ({"at": "chest", "side": "L", "t": 0.35, "dir": [0.05, 0.0, -1.0]}, 2, 0.040, 3, 3),
]


# The tier growths are what tells a Seeded or Bloomed Hollowed apart in the dark at range: drawn
# this much bigger than TIER_SITES' cluster sizes (triangle cost is the same).
TIER_SCALE = 1.5


def tier_growths(model, rng) -> dict[str, Part]:
    """The Bloom erupting as the tier rises (ADR-0028): clusters of pale fruiting caps and creeping
    filament mats from the skull, the nape, the shoulders and the spine. Every body carries them,
    gated: Seeded bodies show the first ring, Bloomed ones all of them (char_attrs gates; the skin
    shader collapses what the tier hides). params "tier_growth": false leaves them out, a list
    replaces the sites."""
    from .char_dress import site_point, surface_hit
    out: dict[str, Part] = {}
    spec = model.p.get("tier_growth", True)
    if spec is False:
        return out
    sites = TIER_SITES if spec is True else [(x["site"], x["gate"], x["size"], x["caps"], x["strands"]) for x in spec]
    s = model.s
    for site, gate, size, ncaps, nstr in sites:
        origin, direction, seg = site_point(model, site)
        p, nrm = surface_hit(model, origin, direction)
        bone = {"body_head": "head", "body_torso": None}.get(seg, "")
        if bone is None:
            at = site["at"]
            bone = at if at in ("hips", "spine", "chest", "neck") else "chest"
        elif seg.startswith("body_upper_arm"):
            bone = "upper_arm." + seg[-1]
        part = out.setdefault(seg, Part())
        t1 = _n(np.cross(nrm, (0.0, 0.0, 1.0)) if abs(nrm[2]) < 0.9 else np.cross(nrm, (1.0, 0.0, 0.0)))
        t2 = np.cross(nrm, t1)
        sz = size * TIER_SCALE * s
        for i in range(ncaps):
            ang = rng.uniform(0, 2 * math.pi)
            rad = sz * math.sqrt(rng.uniform(0.0, 1.0)) * 0.9
            base = p + (t1 * math.cos(ang) + t2 * math.sin(ang)) * rad - nrm * 0.002 * s
            dirn = _n(nrm * 1.0 + (t1 * math.cos(ang) + t2 * math.sin(ang)) * 0.45 + rng.normal(0, 0.15, 3))
            k = rng.uniform(0.5, 1.0)
            v, f = fruiting_cap(base, dirn, sz * 0.55 * k, sz * 0.07, sz * (0.22 + 0.22 * k), rng)
            part.add(v, f, L_BLOOM, bone=bone, gate=float(gate))
        for i in range(nstr):
            ang = rng.uniform(0, 2 * math.pi)
            tang = t1 * math.cos(ang) + t2 * math.sin(ang)
            root = p + tang * sz * rng.uniform(0.2, 0.7)
            v, f = filament(root, _n(tang * 1.0 + nrm * 0.35), sz * rng.uniform(1.2, 2.2), rng.uniform(*FILAMENT_R) * s,
                            rng, sag=0.25)
            part.add(v, f, L_BLOOM, bone=bone, gate=float(gate))
    return out


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
    k = 8
    top, bot = [], []
    thick = size * 0.30
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


# The Bloom's growths have to read at gameplay distance (20 m), not only at arm's length: shelves
# are drawn this much bigger than their site's `shelf_size` and often stacked in tiers like a
# bracket fungus on a stump, and filaments are cords a few millimetres thick (at 1-2 mm they
# vanished past 3 m).
SHELF_SCALE = 1.5
SHELF_TIER_P = 0.6
FILAMENT_R = (0.0022, 0.0034)


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
            v, f = filament(root, _n(nrm * 0.7 + jitter * 0.6), length, rng.uniform(*FILAMENT_R) * model.s,
                            rng, sag=site.get("sag", 0.6))
            part.add(v, f, L_BLOOM)
        for _ in range(int(site.get("shelves", 0))):
            jitter = _n(nrm + rng.normal(0, 0.35, 3))
            sc = c + jitter * site.get("radius", 0.02) * rng.uniform(0.3, 0.9)
            size = rng.uniform(0.6, 1.0) * site.get("shelf_size", 0.018) * SHELF_SCALE * model.s
            v, f = shelf(sc, jitter, size, rng)
            part.add(v, f, L_BLOOM)
            # a smaller bracket stacked above it (tiers read as fungus from far off)
            if rng.random() < SHELF_TIER_P:
                v, f = shelf(sc + np.array([0.0, 0.0, 1.0]) * size * 0.55 - jitter * size * 0.15, jitter,
                             size * rng.uniform(0.55, 0.75), rng)
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
