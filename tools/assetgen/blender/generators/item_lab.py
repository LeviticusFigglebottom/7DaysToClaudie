"""Corvane Field Lab items (agent Y): the containment keycard and the vault code card (laminated cards printed
from the lab_signs atlas), the sealed Bloom core canister, the Program research drive in its shock case and the
Cordon's antifungal auto-injector. Origin bottom centre. params: kind, name, seed."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import item_kit as K

UNIT, PX = 256, 2048.0
CELLS = {"containment": (5.5, 3, 2.5, 1.75), "vault": (0, 3, 3, 1)}


def _rect(name):
    x, y, w, h = [v * UNIT for v in CELLS[name]]
    return (x / PX, 1.0 - (y + h) / PX, (x + w) / PX, 1.0 - y / PX)


def _rounded(w, h, r, n=4):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def card(p):
    """A laminated card (85 x 54 mm) on a clip and a short loop of lanyard; its face is an atlas cell."""
    mb = K.MB()
    cell = p.get("cell", "containment")
    w, h = (0.086, 0.06) if cell == "containment" else (0.09, 0.03 * 1.2)
    mb.push(Matrix.Translation((0, 0, 0.0005)))
    K.extrude(mb, _rounded(w, h, 0.004), 0.001, mat="lab_signs", side_mat="item_plastic_white", uv_rect=_rect(cell))
    mb.pop()
    # Punched slot and the clip through it.
    K.box(mb, (0.014, 0.006, 0.0025), (0, h / 2 - 0.006, 0.0012), mat="item_steel_bright", bevel=0.0005)
    K.box(mb, (0.012, 0.03, 0.002), (0, h / 2 + 0.012, 0.0012), mat="item_plastic_black" if cell == "vault" else "item_plastic_clear",
          bevel=0.0006)
    loop = []
    for k in range(20):
        a = 2 * math.pi * k / 20
        loop.append(Vector((math.cos(a) * 0.012, h / 2 + 0.04 + math.sin(a) * 0.016, 0.0016)))
    K.tube(mb, loop, (0.005, 0.0007), profile=K.rect_profile(1, 1, 0.3), mat="item_plastic_red" if cell == "containment" else "item_plastic_blue",
           closed=True, up=Vector((0, 0, 1)))
    return [mb.build(p["name"], sharp_deg=None)], {"settle": None}


def canister(p):
    """A sealed sample canister: a frosted steel body with a screw lid, an orange tamper band of Cordon tape, a
    numbered tag on a wire and frost round its base."""
    mb = K.MB()
    prof = [(0.0, 0.0), (0.044, 0.0), (0.047, 0.004), (0.047, 0.2), (0.044, 0.205)]
    K.lathe(mb, prof, segments=24, mat="item_steel_bright", cap_top=False)
    K.lathe(mb, [(0.049, 0.2), (0.05, 0.204), (0.05, 0.235), (0.046, 0.24), (0.0, 0.242)], segments=24, mat="item_steel_dark", cap_bottom=True)
    K.lathe(mb, [(0.0485, 0.19), (0.0485, 0.215)], segments=24, mat="lab_cordon_orange", cap_bottom=False, cap_top=False)
    K.lathe(mb, [(0.0475, 0.0), (0.05, 0.004), (0.049, 0.03), (0.0475, 0.035)], segments=24, mat="lab_frost", cap_bottom=False, cap_top=False)
    mb.push(Matrix.Translation((0.05, 0.0, 0.13)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    tag = [(-0.018, -0.011), (0.018, -0.011), (0.024, 0.0), (0.018, 0.011), (-0.018, 0.011)]
    K.extrude(mb, tag, 0.0006, mat="item_tag_print", side_mat="item_paper", uv_rect=(0.0, 0.0, 1.0, 1.0))
    mb.pop()
    return [mb.build(p["name"], sharp_deg=40)], {"settle": None}


def drive(p):
    """A ruggedized hard drive in an orange shock case: rubber corners, a black label panel and the port."""
    mb = K.MB()
    K.box(mb, (0.13, 0.085, 0.024), (0, 0, 0.012), mat="lab_cordon_orange", bevel=0.006)
    K.box(mb, (0.08, 0.05, 0.002), (0.01, 0.0, 0.025), mat="item_plastic_black", bevel=0.0005)
    K.box(mb, (0.06, 0.02, 0.0012), (0.005, 0.005, 0.0262), mat="item_paper", bevel=0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.box(mb, (0.02, 0.02, 0.028), (sx * 0.057, sy * 0.034, 0.014), mat="item_rubber", bevel=0.005)
    K.box(mb, (0.004, 0.018, 0.008), (0.066, 0.0, 0.012), mat="item_steel_dark", bevel=0.0)
    return [mb.build(p["name"], sharp_deg=40)], {"settle": None}


def injector(p):
    """An antifungal auto-injector: an orange barrel with a window and a label, a yellow safety cap and a grey
    needle end."""
    mb = K.MB()
    rot = Matrix.Translation((0, 0, 0.012)) @ Matrix.Rotation(math.radians(90), 4, "Y")
    mb.push(rot @ Matrix.Translation((0, 0, -0.075)))
    K.lathe(mb, [(0.0, 0.0), (0.009, 0.0), (0.011, 0.01), (0.011, 0.11), (0.0115, 0.112)], segments=16, mat="lab_cordon_orange", cap_top=False)
    K.lathe(mb, [(0.0118, 0.112), (0.0118, 0.15), (0.009, 0.155), (0.0, 0.155)], segments=16, mat="item_plastic_amber", cap_bottom=False)
    K.lathe(mb, [(0.0113, 0.04), (0.0113, 0.08)], segments=16, mat="item_paper", cap_bottom=False, cap_top=False)
    mb.pop()
    return [mb.build(p["name"], sharp_deg=40)], {"settle": None}


BUILDERS = {"card": card, "canister": canister, "drive": drive, "injector": injector}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              settle_deg=opts.get("settle", 20.0))
