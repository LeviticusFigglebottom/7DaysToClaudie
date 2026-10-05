"""The Hollowed Ashen (characters/ashen_a, ashen_b): the watch camp's people, turned (enemy
ashen_hollow, game/data/enemies/outskirts.json).

The body is character_body's -- the shared skeleton, segments, stump caps and the full action set,
built from the same params (docs/CHARACTERS.md) -- and only its look changes: just before export the
cloth, skin and hair materials are re-labelled with the Ashen set (game/data/materials/
props_outskirts.json): lichen-ash smeared skin (ashen_skin), smoked hide coats (ashen_hide) over wool
(ashen_wool), hide leggings (ashen_leggings), hide moccasins and matted, ash-grey hair (ashen_hair).
Wrapping the export rather than adding labels to char_build keeps the shared character code untouched.
"""
from __future__ import annotations

import bpy

from generators import character_body
from lib import export

SWAP = {
    "skin_hollow": "ashen_skin",
    "cloth_jacket": "ashen_hide",
    "cloth_flannel": "ashen_wool",
    "cloth_tshirt": "ashen_wool",
    "cloth_denim": "ashen_leggings",
    "leather_boot": "ashen_hide",
    "hair": "ashen_hair",
}


def _reskin(objects) -> None:
    """Re-labels the M_<id> materials the body's meshes use (each datablock is shared by all of
    them). Two labels can map to one Ashen material (the coat and the moccasins are both hide):
    the second slot takes the first's datablock rather than a renamed copy ("M_ashen_hide.001"
    would miss its .tres at import)."""
    for o in objects or []:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is None or not m.name.startswith("M_"):
                continue
            base = m.name[2:].split(".")[0]
            if base not in SWAP:
                continue
            target = "M_" + SWAP[base]
            existing = bpy.data.materials.get(target)
            if existing is not None and existing is not m:
                slot.material = existing
            else:
                m.name = target


def build(params: dict, outputs: list[str]) -> None:
    orig = export.export_glb

    def export_ashen(path, objects=None, **kw):
        _reskin(objects)
        return orig(path, objects, **kw)

    export.export_glb = export_ashen
    try:
        character_body.build(params, outputs)
    finally:
        export.export_glb = orig
