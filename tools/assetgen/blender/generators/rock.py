"""Granite boulders and pebble clusters.

params: kind ("boulder" | "pebbles"), seed, size [x, y, z] (m), detail (icosphere subdivisions),
        tris (target triangle budget), flatten (fraction of height cut flat at the base),
        chips (number of planar fractures for faceted granite), moss (0..1 up-facing moss mask in B).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector, noise

from lib import common, export, materials, primitives, vcolor, uv
from lib.lod import decimated_copy


def _boulder(p: dict, name: str):
    """Radially displaced sphere with planar 'chips' clamped in (stays manifold, no spikes)."""
    r = common.rng(p["seed"])
    sx, sy, sz = (v * 0.5 for v in p.get("size", [1.6, 1.3, 1.1]))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=int(p.get("detail", 5)), radius=1.0)
    obj = common.mesh_from_bmesh(name, bm)
    noise.seed_set(int(p["seed"]) % 100000)
    off = Vector((r.uniform(0, 100), r.uniform(0, 100), r.uniform(0, 100)))
    planes = []
    for _ in range(int(p.get("chips", 4))):
        n = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-0.15, 1.0))).normalized()
        extent = math.sqrt((n.x * sx) ** 2 + (n.y * sy) ** 2 + (n.z * sz) ** 2)
        planes.append((n, extent * r.uniform(0.66, 0.86)))
    me = obj.data
    for v in me.vertices:
        d = v.co.normalized()
        q = d * 1.25 + off
        lump = noise.fractal(q, 0.6, 2.1, 4, noise_basis="PERLIN_ORIGINAL") * 0.13
        ridge = (1.0 - abs(noise.noise(q * 2.6, noise_basis="PERLIN_ORIGINAL"))) ** 4 * 0.035
        pos = Vector((d.x * sx, d.y * sy, d.z * sz)) * (1.0 + lump + ridge)
        for n, dist in planes:
            t = pos.dot(n) - dist
            if t > 0.0:
                pos -= n * t * 0.94
        v.co = pos
    # Flatten the base so it sits on terrain.
    zs = [v.co.z for v in me.vertices]
    zmin, zmax = min(zs), max(zs)
    cut = zmin + (zmax - zmin) * float(p.get("flatten", 0.18))
    for v in me.vertices:
        if v.co.z < cut:
            v.co.z = cut + (v.co.z - cut) * 0.06
    me.update()
    common.origin_to_bottom_center(obj)
    obj.data.transform(Matrix.Translation((0, 0, -0.05 * sz * 2)))
    return obj


def _pebbles(p: dict, name: str):
    r = common.rng(p["seed"])
    parts = []
    for i in range(int(p.get("count", 5))):
        s = r.uniform(0.07, 0.16)
        o = primitives.sphere(f"peb{i}", s, subdiv=1, center=(r.uniform(-0.25, 0.25), r.uniform(-0.25, 0.25), s * 0.45))
        o.scale = (r.uniform(0.9, 1.4), r.uniform(0.8, 1.2), r.uniform(0.5, 0.8))
        o.rotation_euler = (0, 0, r.uniform(0, math.tau))
        common.apply_transforms(o)
        primitives.displace(o, s * 0.18, scale=6.0, seed=int(p["seed"]) + i)
        parts.append(o)
    return common.join(parts, name)


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "rock")
    obj = _boulder(params, name) if params.get("kind", "boulder") == "boulder" else _pebbles(params, name)
    mat = params.get("material", "rock_granite")
    materials.assign_all(obj, mat)
    uv.box_project(obj, scale=0.5)
    common.shade_smooth(obj, angle_deg=55.0)
    tris = int(params.get("tris", 1400))
    if common.triangle_count(obj) > tris:
        low = decimated_copy(obj, tris / common.triangle_count(obj), name + "_d")
        obj.name = name + "_hi"
        bpy_remove(obj)
        obj = low
        obj.name = name
        common.shade_smooth(obj, angle_deg=55.0)
    vcolor.bake_ao([obj], samples=20, distance=max(params.get("size", [1, 1, 1])) * 0.6)
    vcolor.bake_wear(obj, convex_threshold_deg=30.0, seed=int(params["seed"]))
    moss = float(params.get("moss", 0.6))
    vcolor.set_channel(obj, 2, lambda co, n, li: max(0.0, n.z) ** 2 * moss)
    vcolor.fill_channel(obj, 3, 1.0)
    out = [obj]
    if params.get("kind", "boulder") == "boulder":
        col = decimated_copy(obj, min(1.0, 48 / max(1, common.triangle_count(obj))), name + "-convcolonly")
        col.data.materials.clear()
        out.append(col)
    export.export_glb(outputs[0], out)


def bpy_remove(obj) -> None:
    import bpy
    bpy.data.objects.remove(obj, do_unlink=True)
