"""Quadrupeds (ADR-0027): deer and hare on the shared quadruped skeleton, with fur coat masks,
baked AO and the full action set (lib/animal_anim.py).

params: name, seed, species (deer / hare), scale, bulk (neck and brisket), antlers ({tines, size}
or absent), budget ({body, ears, antlers} triangles), grid (body grid spacing, m), materials
({fur, hoof, nose, mouth, eye, antler}). See tools/assetgen/blender_catalogs/animals.py.
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
    for o in parts:
        common.shade_smooth(o, angle_deg=80.0)

    # weights first: the fur UVs follow each face's strongest bone
    Wb = AB.body_weights(skel, M.mesh_arrays(body), body, "body")
    We = AB.body_weights(skel, M.mesh_arrays(ears), ears, "ears")
    AB.uv_by_bone(body, skel, Wb, 0.1 * s)
    AB.uv_by_bone(ears, skel, We, 0.02 * s)
    for o in (eyes,) + ((antlers,) if antlers else ()):
        AB.uv_by_bone(o, skel, AB.rigid_weights(skel, len(o.data.vertices), "head"), 0.02 * s)

    vcolor.bake_ao(parts, samples=16, distance=0.25 * s, strength=0.85, ground=True)
    AB.coat_colours(body, animal, "body")
    AB.coat_colours(ears, animal, "ears")
    for o in parts[2:]:
        vcolor.fill_channel(o, 1, 0.0)
        vcolor.fill_channel(o, 2, 0.0)
        vcolor.fill_channel(o, 3, 1.0)

    AB.apply_skin(body, arm, skel, Wb)
    AB.apply_skin(ears, arm, skel, We)
    AB.apply_skin(eyes, arm, skel, AB.rigid_weights(skel, len(eyes.data.vertices), "head"))
    if antlers:
        AB.apply_skin(antlers, arm, skel, AB.rigid_weights(skel, len(antlers.data.vertices), "head"))

    lengths = animal_anim.build_all(arm, skel, params, only=params.get("_only_actions"))
    scene.frame_set(0)
    export.export_glb(outputs[0], [arm] + parts, animations=True, skins=True)
    tris = {o.name: common.triangle_count(o) for o in parts}
    print(f"[animal_quad] {params.get('name')}: tris {tris} total {sum(tris.values())} actions {sorted(lengths)}")
