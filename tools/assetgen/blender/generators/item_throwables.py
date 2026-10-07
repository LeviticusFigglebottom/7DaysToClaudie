"""Throwables and their makings (ADR-0057): the molotov (a green bottle with a twisted rag stuffed in
its neck and hanging down the side; its viewmodel stands up the bottle's axis, +Z, origin at the
bottom centre, with socket_flame where the rag burns), a tin of kerosene and a sealed bottle of
rotgut. Ground pickups: origin bottom centre, settled resting pose. params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import common, item_kit as K, item_props as P

LIE_X = Matrix.Rotation(math.radians(90), 4, "Y")       # +Z axis -> +X (lie a standing object on its side)
RAG_TOP = 0.252


def _rag(mb: K.MB, seed: int) -> None:
    """A strip of rag: a bunched plug down the neck, a knot over the mouth, its tail hanging down."""
    r = common.rng(seed)
    plug = [Vector((0.0, 0.0, z)) for z in (0.196, 0.212, 0.228, 0.24)]
    K.tube(mb, plug, [0.0098, 0.0104, 0.0112, 0.0118], sides=9, mat="item_cloth_rag", twist=1.6, caps=(True, False))
    knot = [Vector((0.0, 0.0, 0.238)), Vector((0.002, -0.001, 0.246)), Vector((0.001, 0.0, RAG_TOP))]
    K.tube(mb, knot, [0.0125, 0.011, 0.004], sides=9, mat="item_cloth_rag", twist=0.8, caps=(False, True))
    # the tail flops over the lip and hangs down the neck, a little twisted, frayed thin at the end
    tail = [Vector((0.006, 0.0, 0.244)), Vector((0.016, 0.001, 0.243)), Vector((0.0175, 0.002, 0.226)),
            Vector((0.0168 + r.uniform(-0.001, 0.001), 0.003, 0.206)), Vector((0.0185, 0.004, 0.186)), Vector((0.021, 0.006, 0.168))]
    prof = [(math.cos(a) * 1.0, math.sin(a) * 0.35) for a in [2 * math.pi * k / 8 for k in range(8)]]
    K.tube(mb, tail, [0.0085, 0.009, 0.0088, 0.0082, 0.0074, 0.0048], profile=prof, mat="item_cloth_rag", twist=0.9,
           up=Vector((1, 0, 0)))


def molotov(p):
    mb = K.MB()
    P.glass_bottle(mb, mat="item_glass_green")
    _rag(mb, int(p["seed"]))
    obj = mb.build(p["name"], sharp_deg=50)
    sockets = [K.socket("socket_flame", (0.0, 0.0, RAG_TOP - 0.004), (0, -1, 0))]
    return [obj], sockets, {"vm": True, "ground": LIE_X @ Matrix.Translation((0, 0, -0.12)), "settle": 30.0}


def kerosene(p):
    """A round lamp-oil tin, red paint over tinplate, a domed shoulder and a screw cap off-centre."""
    mb = K.MB()
    R, H = 0.046, 0.13
    prof = [(R * 0.6, 0.002), (R * 0.94, 0.0), (R, 0.004), (R, 0.012), (R * 0.985, 0.014), (R * 0.985, H - 0.022), (R, H - 0.02),
            (R, H - 0.014), (R * 0.82, H - 0.004), (R * 0.45, H)]
    K.lathe(mb, prof, segments=28, mat="item_paint_red", regions=[(0, 3, "item_can_tin", "metric"), (6, 9, "item_can_tin", "metric")],
            cap_bottom=True, cap_top=True, cap_mat_top="item_can_tin")
    mb.push(Matrix.Translation((R * 0.45, 0.0, H - 0.006)))
    K.lathe(mb, [(0.0125, 0.0), (0.0125, 0.012), (0.0115, 0.0145), (0.0, 0.015)], segments=18, mat="item_steel_dark", cap_bottom=False)
    mb.pop()
    # a folded wire carry handle across the top
    bail = [Vector((math.cos(t) * R * 0.8, 0.0, H + 0.002 + math.sin(t) * 0.028)) for t in [math.pi * i / 12 for i in range(13)]]
    K.tube(mb, bail, 0.0016, sides=5, mat="item_steel_dark")
    return [mb.build(p["name"], sharp_deg=50)], (), {"settle": 20.0}


def rotgut(p):
    mb = K.MB()
    P.glass_bottle(mb, mat="item_glass_clear")
    return [mb.build(p["name"], sharp_deg=50)], (), {"ground": LIE_X @ Matrix.Translation((0, 0, -0.11)), "settle": 30.0}


BUILDERS = {"molotov": molotov, "kerosene": kerosene, "rotgut": rotgut}


def build(params: dict, outputs: list[str]) -> None:
    parts, sockets, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              viewmodel=bool(opts.get("vm", False)), sockets=sockets, ground_rot=opts.get("ground"),
              settle_deg=opts.get("settle", 20.0), wear_deg=30.0)
