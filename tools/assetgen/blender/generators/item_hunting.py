"""The hunting bow and its arrows (ADR-0057).

hunting_bow (ground item + first-person model): a self bow split from a straight branch, sinew-backed,
the grip wrapped in rawhide. Modelled in the viewmodel frame of item_tools: grip at the origin,
limbs along +-Z, the back of the bow (its face toward the target) at -Y, the belly toward the
archer at +Y; strung, so the limbs sweep back toward the archer (+Y) to the tips. No string: the
game's BowRig strings it to the drawing hand every frame (game/src/player/bow_rig.gd: tips at
z = +-0.6, 0.1 back of the grip). The ground model lies on its side.

arrow (kind "arrow", head "stone" | "bone"): a peeled shoot, the point lashed on, three split-fibre
vanes and a sinew-wrapped nock. Modelled in the projectile frame (game/src/combat/arrow.gd): tip at
the origin, the shaft back along -Y (Godot +Z). outputs[0] the ground pickup, outputs[1] the
first-person / projectile model (the canonical frame, exported like a viewmodel).

params: kind, name, seed (+ head for arrows).
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import common, item_kit as K

TIP_Z = 0.6          # matches BowRig.TIP_Y
TIP_BACK = 0.1       # matches BowRig.TIP_BACK
ARROW_LEN = 0.74     # matches Arrow.LENGTH


def _limb_y(z: float) -> float:
    u = z / TIP_Z
    return TIP_BACK * u * u


def hunting_bow(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    # The stave: one continuous tube tip to tip, wide across X and thin along Y, thickest at the
    # grip (a round-ish handle the fist closes on) and tapering to narrow tips.
    n = 41
    pts, radii = [], []
    for i in range(n):
        t = i / (n - 1)
        z = -TIP_Z + 2 * TIP_Z * t
        a = abs(z) / TIP_Z
        grip = math.exp(-(z / 0.06) ** 4)
        fade = math.exp(-((abs(z) - 0.11) / 0.05) ** 2)       # the fades from grip to limb
        wx = 0.0165 * (1 - 0.55 * a ** 1.4) * (1 - 0.35 * grip) + 0.002 * fade
        ty = 0.0085 * (1 - 0.35 * a) + 0.0085 * grip + 0.003 * fade
        wob = 0.0007 * math.sin(z * 31 + seed)
        pts.append(Vector((wob, _limb_y(z), z)))
        radii.append((ty, wx))
    K.tube(mb, pts, radii, profile=K.rect_profile(1.0, 1.0, 0.55), mat="item_wood_handle", up=Vector((0, 1, 0)),
           cap_mat="item_wood_end", cap_uv="disc")
    # Sinew backing: a thin skin laid along the back (-Y) of both limbs.
    for sgn in (1, -1):
        bpts, brad = [], []
        for i in range(17):
            t = i / 16
            z = sgn * (0.09 + (TIP_Z - 0.12) * t)
            a = abs(z) / TIP_Z
            wx = 0.0165 * (1 - 0.55 * a ** 1.4) * 0.92
            ty = 0.0085 * (1 - 0.35 * a)
            bpts.append(Vector((0.0, _limb_y(z) - ty - 0.0006, z)))
            brad.append((0.0007, wx))
        K.tube(mb, bpts, brad, profile=K.rect_profile(1.0, 1.0, 0.45), mat="item_sinew", up=Vector((0, 1, 0)), caps=(True, True))
    # Rawhide grip wrap and sinew wraps under the nocks.
    K.lashing(mb, Vector((0, 0, -0.065)), Vector((0, 0, 0.065)), 0.0175, cord=0.0022, turns=14, per_turn=14, mat="item_rawhide",
              phase=r.uniform(0, 6.28), wobble=0.0004, seed=seed)
    for sgn in (1, -1):
        z0, z1 = sgn * (TIP_Z - 0.06), sgn * (TIP_Z - 0.035)
        K.lashing(mb, Vector((0, _limb_y(z0), z0)), Vector((0, _limb_y(z1), z1)), 0.0075, cord=0.0011, turns=6, per_turn=10,
                  mat="item_sinew", phase=seed * 0.3)
    obj = mb.build("hunting_bow", sharp_deg=None)
    sockets = [K.socket("socket_tip_top", (0, _limb_y(TIP_Z), TIP_Z), (0, 0, 1)),
               K.socket("socket_tip_bottom", (0, _limb_y(-TIP_Z), -TIP_Z), (0, 0, -1))]
    return [obj], sockets, Matrix.Rotation(math.radians(90), 4, "Y")


def arrow(p):
    seed = int(p["seed"])
    head = str(p.get("head", "stone"))
    r = common.rng(seed)
    mb = K.MB()
    L = ARROW_LEN
    # Shaft: a peeled shoot, the barest bend, from behind the head to the nock.
    shaft = [Vector((0.0006 * math.sin(i * 0.7 + seed), -(0.035 + (L - 0.035) * i / 12), 0.0005 * math.cos(i * 0.9))) for i in range(13)]
    K.tube(mb, shaft, [0.0044 - 0.0006 * (i / 12) for i in range(13)], sides=7, mat="item_wood_raw", cap_mat="item_wood_end",
           cap_uv="disc")
    # Nock: a sinew wrap at the end.
    K.lashing(mb, Vector((0, -(L - 0.03), 0)), Vector((0, -(L - 0.008), 0)), 0.0041, cord=0.0009, turns=8, per_turn=8, mat="item_sinew",
              phase=seed * 0.4)
    # Fletching: three split-fibre vanes, 9 cm, a little spiral.
    for k in range(3):
        a0 = 2 * math.pi * k / 3 + 0.4
        vpts, vrad = [], []
        for i in range(7):
            t = i / 6
            y = -(L - 0.045) + 0.095 * t
            a = a0 + 0.12 * t
            h = 0.0055 * math.sin(math.pi * min(1.0, t * 1.2)) + 0.0015
            rad = 0.0044 + h
            vpts.append(Vector((math.cos(a) * rad, y, math.sin(a) * rad)))
            vrad.append((h, 0.00045))
        K.tube(mb, vpts, vrad, profile=K.rect_profile(1.0, 1.0, 0.0), mat="item_plant_fiber",
               up=Vector((math.cos(a0), 0, math.sin(a0))), caps=(True, True), smooth=False)
    # The point's lashing.
    bind = "item_sinew" if head == "bone" else "item_plant_fiber"
    K.lashing(mb, Vector((0, -0.03, 0)), Vector((0, -0.062, 0)), 0.0046, cord=0.0011, turns=9, per_turn=8, mat=bind, phase=seed)
    parts = [mb.build("arrow", sharp_deg=None)]
    if head == "stone":
        pt = K.knapped("point", length=0.05, width=0.022, thickness=0.006, seed=seed + 3, scars=24, cortex=0.0,
                       mat="item_flint", tris=600)
        # knapped: length along Y with the edge at -Y; turn so the length runs along -Y from the tip
        pt.data.transform(Matrix.Translation((0, -0.026, 0)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
        parts.append(pt)
    else:
        hb = K.MB()
        hp = [Vector((0, -0.002 - 0.05 * i / 6, 0)) for i in range(7)]
        K.tube(hb, hp, [(0.0007 + 0.0048 * (i / 6) ** 0.8, 0.0018 + 0.0035 * (i / 6) ** 0.8) for i in range(7)], sides=6,
               mat="item_bone", caps=(True, True), smooth=False, rot=r.uniform(0, 1))
        parts.append(hb.build("point", sharp_deg=40))
    return parts, [], Matrix.Rotation(math.radians(90), 4, "Z")


BUILDERS = {"hunting_bow": hunting_bow, "arrow": arrow}


def build(params: dict, outputs: list[str]) -> None:
    parts, sockets, ground = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              viewmodel=len(outputs) > 1, ground_rot=ground, sockets=sockets, settle_deg=float(params.get("settle", 12.0)),
              wear_deg=28.0)
