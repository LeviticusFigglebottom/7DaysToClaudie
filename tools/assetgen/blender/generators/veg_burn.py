"""Burnt forest (ADR-0041): fire-killed standing snags and fire-hollowed stumps.

build(params, outputs) by params.kind:

  snag  - outputs LOD0, LOD1, LOD2 (.glb), like veg_tree. A grey fir or larch killed by the fire
          years ago. The trunk wears one bark-shader material (`bark_burnt`): its char layer cracks
          the bark into alligator blocks from the roots up to a ragged line, and above it the bark
          has weathered off to silver wood (bark.gdshader, char_*). The top is a thin spike, or the
          crown snapped off and left a splintered break. Fine twigs burnt away, so the crown is a
          skeleton of bare branches: a fir keeps many, drooping and shortening towards the top,
          most of them burnt or broken back; a larch keeps fewer, level ones, mostly broken. The
          lower trunk keeps its self-pruned stubs.
          params: form (fir|larch), seed, height (standing, m), dbh_r (m), full_height (the trunk
          tapers as if this many times taller: > 1 for a snapped crown), top (spike|snapped),
          crown_base (fraction of the full height where the crown was), lean (deg), limbs
          (multiplier on branch count), mat.
  stump - a fire-hollowed stump: a short broken trunk whose heartwood burnt out, the shell
          standing in a jagged rim round a charred cavity, with surface roots. Origin bottom
          centre, convex collision proxy (<name>-convcolonly).
          params: seed, height, radius, shell (wall thickness), mat.
Shared pieces (trunks, roots, branch paths, broken tops) come from generators/veg_tree.py, so the
burnt trees taper, flare and break exactly like the live ones.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector, noise

from generators import veg_tree as VT
from lib import common, export, vcolor
from lib.veg_mesh import MeshBuilder, tube
from lib.veg_tree import Branch, Tree, assemble, lerp, lobe_factor, smooth


# ---------------------------------------------------------------------------------------------
# Snags
# ---------------------------------------------------------------------------------------------

def _limb(rng, tree, mat, start, phi, L, elev, droop, upturn, broken, twigs):
    pts = VT.conifer_branch_path(start, phi, L, elev, droop, upturn, rng, n=4, wander=0.14)
    r0 = min(0.075, 0.012 + 0.024 * L)
    radii = [r0, r0 * 0.68, r0 * 0.44, r0 * (0.38 if broken else 0.16)]
    long_b = L > 1.5
    br = Branch(pts=pts, radii=radii, mat=mat, wind0=0.02, wind1=0.12, tip=not broken,
                sides=(5 if long_b else 4, 3, 3 if L > 2.0 else 0), min_len_lod=(0.0, 0.7, 2.0), broken=broken)
    tree.branches.append(br)
    if twigs and not broken:
        for _ in range(rng.randint(1, 3)):
            sp, stt, sr = br.at(rng.uniform(0.3, 0.8))
            sphi = math.atan2(stt.y, stt.x) + rng.choice((-1, 1)) * rng.uniform(0.5, 1.1)
            sl = L * rng.uniform(0.2, 0.4)
            spts = VT.conifer_branch_path(sp, sphi, sl, rng.uniform(-0.5, 0.2), 0.15, 0.0, rng, n=3, wander=0.3)
            tree.branches.append(Branch(pts=spts, radii=[sr * 0.6, sr * 0.35, sr * 0.14], mat=mat, wind0=0.08,
                                        wind1=0.2, sides=(3, 0, 0), min_len_lod=(0.0, 99, 99)))


def build_snag(p: dict) -> Tree:
    rng = common.rng(p["seed"])
    form = p.get("form", "fir")
    H = float(p["height"])
    r_dbh = float(p["dbh_r"])
    full = H * float(p.get("full_height", 1.0))
    snapped = p.get("top", "spike") == "snapped"
    mat = p.get("mat", "bark_burnt")
    st, axis, radius = VT.conifer_trunk(rng, full, r_dbh, mat=mat, lean_deg=float(p.get("lean", 1.5)), seed=p["seed"],
                                        z_end=H if snapped else None, flare=0.55, wobble=0.06,
                                        top_r=0.02 if form == "fir" else 0.016)
    st.noise_amp = 0.02
    if snapped:
        st.tip = False
        st.break_top = VT._jagged_top(rng, mat, spikes=(2, 4))
    tree = Tree(name=p["name"], stems=[st], foliage_mat="foliage_fir", atlas={}, height=H, crown_base=H * 2.0,
                seed=int(p["seed"]), moss_dir=0.0, moss_height=0.0, trunk_ao_crown=1.0)
    tree.roots = VT.surface_roots(rng, st.lobes, r_dbh, axis, mat, count=rng.randint(3, 5))
    z_cb = full * float(p.get("crown_base", 0.36 if form == "fir" else 0.45))
    z_top = H - (0.25 if snapped else 0.5)
    limbs = float(p.get("limbs", 1.0))
    phi = rng.uniform(0, 2 * math.pi)
    z = z_cb
    while z < z_top:
        u = (z - z_cb) / max(1.0, full - z_cb)
        c = axis(z)
        if form == "fir":
            per = rng.randint(1, 3) if rng.random() < limbs else 1
            for _ in range(per):
                phi += VT.GOLDEN + rng.uniform(-0.3, 0.3)
                start = c + Vector((math.cos(phi), math.sin(phi), 0.0)) * radius(z) * 0.6
                Lfull = full * 0.14 * (1.0 - u) ** 0.85 + 0.25
                broken = rng.random() < 0.5
                L = Lfull * (rng.uniform(0.25, 0.55) if broken else rng.uniform(0.55, 0.95))
                elev = rng.uniform(-0.45, 0.0) + 0.35 * u
                _limb(rng, tree, mat, start, phi, L, elev, rng.uniform(0.1, 0.4) * (1.0 - u), 0.25 * u, broken,
                      twigs=rng.random() < 0.55)
            z += rng.uniform(0.32, 0.6) / max(0.3, limbs)
        else:
            per = 1 if rng.random() < 0.55 else 2
            for _ in range(per):
                phi += VT.GOLDEN + rng.uniform(-0.4, 0.4)
                start = c + Vector((math.cos(phi), math.sin(phi), 0.0)) * radius(z) * 0.6
                Lfull = full * 0.12 * (1.0 - u) ** 0.7 + 0.35
                broken = rng.random() < 0.6
                L = Lfull * (rng.uniform(0.25, 0.55) if broken else rng.uniform(0.6, 1.0))
                elev = rng.uniform(-0.2, 0.2)
                _limb(rng, tree, mat, start, phi, L, elev, rng.uniform(0.0, 0.25), rng.uniform(0.0, 0.25), broken,
                      twigs=rng.random() < 0.45)
            z += rng.uniform(0.38, 0.75) / max(0.3, limbs)
    # the self-pruned lower trunk: stubs, the odd longer dead limb near the old crown base
    VT.dead_branches(rng, tree, axis, radius, 1.0, min(z_cb, H * 0.8), int(min(z_cb, H) * 2.0), mat, atlas_dead=False,
                     long_frac=0.12, max_len=1.1)
    return tree


# ---------------------------------------------------------------------------------------------
# Fire-hollowed stump
# ---------------------------------------------------------------------------------------------

def _hull_proxy(name: str, pts: list[Vector]) -> bpy.types.Object:
    import bmesh
    bm = bmesh.new()
    for q in pts:
        bm.verts.new(q)
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def build_stump(p: dict, name: str):
    rng = common.rng(p["seed"])
    H = float(p["height"])
    R = float(p["radius"])
    shell = float(p.get("shell", 0.07))
    mat = p["mat"]
    sides = 18
    noise.seed_set(int(p["seed"]) % 100000)
    n_l = rng.randint(4, 6)
    a0 = rng.uniform(0, 2 * math.pi)
    lobes = [(a0 + 2 * math.pi * i / n_l + rng.uniform(-0.35, 0.35), rng.uniform(0.2, 0.45)) for i in range(n_l)]
    z_rim = H * 0.68
    zs = [-0.25, -0.1, 0.0, 0.08, 0.2, 0.36, 0.55, z_rim * 0.85, z_rim]

    def radius(z):
        return R * (1.0 + 0.03 * (H - z)) + R * 0.38 * math.exp(-(max(z, -0.25) + 0.08) / 0.22)

    def rfn(i, s, a):
        z = zs[i]
        lf = lobe_factor(lobes, a) * math.exp(-max(0.0, z) / 0.3) * (1.0 + max(0.0, -z) * 3.0)
        return 1.0 + lf + noise.noise(Vector((math.cos(a) * 2.0, math.sin(a) * 2.0, z * 3.0))) * 0.04

    pts = [Vector((0.0, 0.0, z)) for z in zs]
    mb = MeshBuilder()
    u_rep = max(1, round(2 * math.pi * R / 0.8))
    rings, v_end = tube(mb, pts, [radius(z) for z in zs], sides, mat, u_repeats=u_rep, radius_fn=rfn, tip=False)
    m = mb.mat(mat)
    # The shell's broken top: a jagged rim, low on one side where the fire ate through, with a
    # couple of tall splinters.
    burn_side = rng.uniform(0, 2 * math.pi)
    tall = set(rng.sample(range(sides), 3))
    top = rings[-1]
    hs = []
    for j in range(sides):
        a = 2 * math.pi * j / sides
        low = 0.5 + 0.5 * math.cos(a - burn_side)
        # A ragged break: every segment its own height, lower where the fire ate in, a few
        # splinters of the shell standing proud.
        h = z_rim + (H - z_rim) * (0.15 + 0.85 * (1.0 - low) ** 1.3) * rng.uniform(0.35, 1.0)
        if j in tall:
            h += rng.uniform(0.18, 0.42) * H
        hs.append(h)
    outer_top = []
    for j, vi in enumerate(top):
        x, y, _ = mb.co[vi]
        outer_top.append(mb.v((x, y, hs[j])))
    v_circ = u_rep / (2 * math.pi * R)
    for j in range(sides):
        j2 = (j + 1) % sides
        u0, u1 = u_rep * j / sides, u_rep * (j + 1) / sides
        mb.f((top[j], top[j2], outer_top[j2], outer_top[j]),
             ((u0, v_end), (u1, v_end), (u1, v_end + (hs[j2] - z_rim) * v_circ), (u0, v_end + (hs[j] - z_rim) * v_circ)), m)
    # Inner wall: the cavity, rings going down from the rim to a floor of char and ash.
    floor_z = rng.uniform(0.1, 0.25)
    depth_rings = 4
    inner = []
    for k in range(depth_rings + 1):
        t = k / depth_rings
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            x, y, _ = mb.co[outer_top[j]]
            rr = math.hypot(x, y)
            ri = max(0.03, rr - shell * (1.0 + 0.5 * t)) * (1.0 - 0.25 * t * t)
            nz = noise.noise(Vector((math.cos(a) * 3.0, math.sin(a) * 3.0, t * 2.0 + 5.0))) * 0.15
            zt = hs[j] - 0.03 if k == 0 else lerp(min(hs) - 0.05, floor_z, t ** 0.9)
            ring.append(mb.v((math.cos(a) * ri * (1.0 + nz), math.sin(a) * ri * (1.0 + nz), zt)))
        inner.append(ring)
    for j in range(sides):
        j2 = (j + 1) % sides
        u0, u1 = u_rep * j / sides, u_rep * (j + 1) / sides
        # the rim: burnt wood between shell and cavity, facing up
        mb.f((outer_top[j], outer_top[j2], inner[0][j2], inner[0][j]), ((u0, 0.0), (u1, 0.0), (u1, 0.08), (u0, 0.08)), m)
        for k in range(depth_rings):
            va, vb = 0.1 + k * 0.25, 0.1 + (k + 1) * 0.25
            mb.f((inner[k][j], inner[k][j2], inner[k + 1][j2], inner[k + 1][j]), ((u0, va), (u1, va), (u1, vb), (u0, vb)), m)
    c = mb.v((0.0, 0.0, floor_z - 0.02))
    for j in range(sides):
        j2 = (j + 1) % sides
        a1, a2 = 2 * math.pi * j / sides, 2 * math.pi * (j + 1) / sides
        mb.f((inner[-1][j], inner[-1][j2], c), ((0.5 + 0.2 * math.cos(a1), 0.5 + 0.2 * math.sin(a1)),
                                                (0.5 + 0.2 * math.cos(a2), 0.5 + 0.2 * math.sin(a2)), (0.5, 0.5)), m)
    # Surface roots off the lobes, charred like the rest.
    for a, kk in sorted(lobes, key=lambda t: -t[1])[:rng.randint(3, 5)]:
        d = Vector((math.cos(a), math.sin(a), 0.0))
        L = R * rng.uniform(1.6, 2.8)
        side = Vector((-d.y, d.x, 0.0)) * rng.uniform(-0.15, 0.15)
        rp = [d * (R * 0.5) + Vector((0, 0, 0.34)), d * (R * 1.05) + Vector((0, 0, 0.12)),
              (d + side) * (R * 1.35 + L * 0.35), (d + side * 2.0) * (R * 1.35 + L * 0.75) + Vector((0, 0, -0.14))]
        rr = [R * f * (0.8 + 0.6 * kk) for f in (0.42, 0.3, 0.17, 0.08)]
        tube(mb, rp, rr, 7, mat, u_repeats=1, tip=False)
    obj = mb.build(name)
    vcolor.bake_ao([obj], samples=20, distance=R * 1.5, ground=True)
    vcolor.bake_wear(obj, convex_threshold_deg=35.0, seed=int(p["seed"]))
    vcolor.fill_channel(obj, 2, 0.0)
    vcolor.fill_channel(obj, 3, 1.0)
    hull = [Vector(mb.co[i]) for ring in rings for i in ring] + [Vector(mb.co[i]) for i in outer_top]
    col = _hull_proxy(name + "-convcolonly", [q for q in hull if q.z > -0.05])
    return [obj, col]


def build(params: dict, outputs: list[str]) -> None:
    kind = params.get("kind", "snag")
    if kind == "stump":
        objs = build_stump(params, params["name"])
        print(f"[veg_burn] {params['name']}: {common.triangle_count(objs[0])} tris")
        export.export_glb(outputs[0], objs)
        return
    tree = build_snag(params)
    rng = common.rng(str(params["seed"]) + "lod")
    names = [tree.name, tree.name + "_lod1", tree.name + "_lod2"]
    objs = []
    for lod, name in enumerate(names[:len(outputs)]):
        mb = assemble(tree, lod, rng)
        objs.append(mb.build(name))
        print(f"[veg_burn] {name}: {mb.tris()} tris")
    for obj, out in zip(objs, outputs):
        export.export_glb(out, [obj])
