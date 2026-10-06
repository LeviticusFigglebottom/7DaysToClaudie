"""Quadrupeds (ADR-0027): deer and hare on the shared quadruped skeleton, with fur coat masks,
baked AO and the full action set (lib/animal_anim.py).

params: name, seed, species (deer / hare / hound), scale, bulk (neck and brisket), antlers
({tines, size} or absent), budget ({body, ears, antlers, teeth, growths} triangles), grid (body grid
spacing, m), materials ({fur, hoof, nose, mouth, eye, antler, teeth, gums, plates, threads}).
The hound (breed, gaunt, ears, torn_ear, growth: see lib/animal_body.py) adds two parts: `teeth`
(upper teeth rigid on the head; lower teeth and the tongue on the jaw) and `growths` (the Bloom's
shelf plates and threads, weighted like the hide under them; vertex G = the plates' undersides,
B = their thin margins, for the bloom_fungus shader). See tools/assetgen/blender_catalogs/animals.py.
"""
from __future__ import annotations

import bpy
import numpy as np

from lib import animal_anim, animal_body as AB, animal_skel, char_mesh as M, char_skel, common, export, vcolor


def build(params: dict, outputs: list[str]) -> None:
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    skel = animal_skel.make_skeleton(params)
    arm = char_skel.create_armature(skel)
    animal = AB.Animal(skel, params)
    mats = params.get("materials", {})
    budget = params.get("budget", {})
    s = float(params.get("scale", 1.0))
    h = float(params.get("grid", 0.006 if params.get("species") == "deer" else 0.0028)) * s

    body = AB.mesh_program(animal.body, "body", h, int(budget.get("body", 11000)))
    labels = AB.label_faces(animal.body, body)
    M.assign_labels(body, labels, {AB.L_FUR: mats.get("fur", "fur_deer"), AB.L_HOOF: mats.get("hoof", "hoof"),
                                   AB.L_NOSE: mats.get("nose", "nose_wet"), AB.L_MOUTH: mats.get("mouth", "nose_wet")})
    ears = AB.mesh_program(animal.ears, "ears", h * 0.42, int(budget.get("ears", 900)), pad=0.01 * s)
    M.assign_labels(ears, np.zeros(len(ears.data.polygons), np.int32), {0: mats.get("fur", "fur_deer")})
    eyes = AB.eye_mesh(animal.eye_c, animal.eye_r)
    M.assign_labels(eyes, np.zeros(len(eyes.data.polygons), np.int32), {0: mats.get("eye", "eye_animal")})
    parts = [body, ears, eyes]
    antlers = None
    if params.get("antlers"):
        antlers = AB.mesh_program(animal.antlers, "antlers", h * 0.55, int(budget.get("antlers", 2600)), pad=0.01 * s)
        M.assign_labels(antlers, np.zeros(len(antlers.data.polygons), np.int32), {0: mats.get("antler", "antler")})
        parts.append(antlers)
    teeth = growths = None
    if animal.teeth_upper is not None:
        teeth = _hound_teeth(animal, h, s, budget, mats)
        growths = AB.mesh_program(animal.growths, "growths", h * 0.5, int(budget.get("growths", 2600)), pad=0.008 * s,
                                  keep_islands=True)
        M.assign_labels(growths, AB.label_faces(animal.growths, growths),
                        {0: mats.get("plates", "hound_bloom_plates"), 1: mats.get("threads", "bloom_growth")})
        parts += [teeth, growths]
    for o in parts:
        common.shade_smooth(o, angle_deg=80.0)

    # weights first: the fur UVs follow each face's strongest bone
    if teeth is None:
        Wb = AB.body_weights(skel, M.mesh_arrays(body), body, "body")
    else:
        Wb = AB.body_weights(skel, M.mesh_arrays(body), body, "body", animal)
    We = AB.body_weights(skel, M.mesh_arrays(ears), ears, "ears")
    AB.uv_by_bone(body, skel, Wb, 0.1 * s)
    AB.uv_by_bone(ears, skel, We, 0.02 * s)
    for o in (eyes,) + ((antlers,) if antlers else ()):
        AB.uv_by_bone(o, skel, AB.rigid_weights(skel, len(o.data.vertices), "head"), 0.02 * s)
    if teeth is not None:
        Wt = _teeth_weights(skel, teeth)
        Wg = AB.transfer_weights(M.mesh_arrays(body), Wb, M.mesh_arrays(growths))
        AB.uv_by_bone(teeth, skel, AB.rigid_weights(skel, len(teeth.data.vertices), "head"), 0.01 * s)
        AB.uv_by_bone(growths, skel, Wg, 0.02 * s)

    vcolor.bake_ao(parts, samples=16, distance=0.25 * s, strength=0.85, ground=True)
    AB.coat_colours(body, animal, "body")
    AB.coat_colours(ears, animal, "ears")
    for o in parts[2:]:
        vcolor.fill_channel(o, 1, 0.0)
        vcolor.fill_channel(o, 2, 0.0)
        vcolor.fill_channel(o, 3, 1.0)
    if growths is not None:
        _growth_colours(growths, animal, s)

    AB.apply_skin(body, arm, skel, Wb)
    AB.apply_skin(ears, arm, skel, We)
    AB.apply_skin(eyes, arm, skel, AB.rigid_weights(skel, len(eyes.data.vertices), "head"))
    if antlers:
        AB.apply_skin(antlers, arm, skel, AB.rigid_weights(skel, len(antlers.data.vertices), "head"))
    if teeth is not None:
        AB.apply_skin(teeth, arm, skel, Wt)
        AB.apply_skin(growths, arm, skel, Wg)

    if teeth is None:
        lengths = animal_anim.build_all(arm, skel, params, only=params.get("_only_actions"))
    else:
        probes = animal_anim.Probes(skel, M.mesh_arrays(body), Wb)
        lengths = animal_anim.build_all(arm, skel, params, only=params.get("_only_actions"), probes=probes)
    scene.frame_set(0)
    export.export_glb(outputs[0], [arm] + parts, animations=True, skins=True)
    tris = {o.name: common.triangle_count(o) for o in parts}
    print(f"[animal_quad] {params.get('name')}: tris {tris} total {sum(tris.values())} actions {sorted(lengths)}")


def _hound_teeth(animal, h: float, s: float, budget: dict, mats: dict):
    """One `teeth` object: the upper teeth, then the lower teeth and tongue (tagged `_jaw` so the
    weights can find them after the join). Label 0 enamel, 1 gum and tongue."""
    n = int(budget.get("teeth", 1400))
    up = AB.mesh_program(animal.teeth_upper, "teeth", h * 0.22, n // 2, pad=0.006 * s, keep_islands=True)
    M.assign_labels(up, AB.label_faces(animal.teeth_upper, up), {0: mats.get("teeth", "teeth"), 1: mats.get("gums", "hound_gums")})
    lo = AB.mesh_program(animal.teeth_lower, "teeth_lower", h * 0.22, n - n // 2, pad=0.006 * s, keep_islands=True)
    M.assign_labels(lo, AB.label_faces(animal.teeth_lower, lo), {0: mats.get("teeth", "teeth"), 1: mats.get("gums", "hound_gums")})
    lo.vertex_groups.new(name="_jaw").add(list(range(len(lo.data.vertices))), 1.0, "REPLACE")
    return common.join([up, lo], "teeth")


def _teeth_weights(skel, teeth):
    gi = teeth.vertex_groups["_jaw"].index
    jaw = np.array([any(g.group == gi for g in v.groups) for v in teeth.data.vertices])
    teeth.vertex_groups.remove(teeth.vertex_groups["_jaw"])
    W = np.zeros((len(jaw), len(skel.names)))
    W[:, skel.names.index("head")] = ~jaw
    W[:, skel.names.index("jaw")] = jaw
    return W


def _growth_colours(obj, animal, s: float) -> None:
    """bloom_fungus: G = the plates' undersides (greyer, faintly glowing at night), B = thin
    margins that let light through (how far out from the hide)."""
    me = obj.data
    V = M.mesh_arrays(obj)
    N = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", N)
    N = N.reshape(-1, 3)
    d, _ = animal.body.eval(V)
    out = np.clip((d - 0.004 * s) / (0.026 * s), 0.0, 1.0)
    thin = out * out * (3 - 2 * out)
    under = np.clip((-N[:, 2] - 0.15) / 0.5, 0.0, 1.0) * np.clip(d / (0.008 * s), 0.0, 1.0)
    lv = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    vcolor.set_channel(obj, 1, lambda co, n, li: float(under[lv[li]]))
    vcolor.set_channel(obj, 2, lambda co, n, li: float(thin[lv[li]]))
