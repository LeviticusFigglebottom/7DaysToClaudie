"""Long guns (ADR-0057): the bolt-action hunting rifle and its .308 rounds.

The rifle is modelled side-on with +Y as "forward" (f) and the bore on f at z = 0, then turned 180
deg about Z so the muzzle faces -Y (the pointing frame of item_gear's revolver: Godot +Z forward,
+Y up, the gun's right side on -X). Its origin is the support hand's grip under the fore-end: the
left hand holds the rifle in first person (viewmodel.json holds.rifle) so the right is free to work
the bolt. Two parts are their own nodes for the game to animate or hide:
* `bolt`: body, shroud and handle, its node origin on the bore axis at the bolt face's rest, so a
  turn about its local Z (Godot) lifts the handle and a slide along it draws the bolt back
  (uses.fire_rifle / reload_rifle `parts`);
* `scope`: the 3-9x tube, bells, turrets and rings.
Sockets: socket_muzzle (shot effects), socket_sight (the ocular lens centre, looking down the
sight line) and socket_grip_r (the firing hand's grip on the wrist of the stock, for posing).
params: kind, name, seed."""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Matrix, Vector

from lib import item_kit as K

TURN = Matrix.Rotation(math.pi, 4, "Z")              # local +Y forward -> world -Y forward
SIDE = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # extrude local (x, y, z) -> (z, x, y)
ALONG_Y = Matrix.Rotation(math.radians(-90), 4, "X")  # lathe +Z -> +Y

# Where the support hand grips the fore-end (f, z): the model's origin.
SUPPORT = (0.30, -0.032)
# Rest of the bolt face (f) and how far it draws back.
BOLT_F = 0.0
# Scope axis height over the bore.
SCOPE_Z = 0.043
# How far the bolt handle is bent down about the bore (deg, TD-294): enough that the lifted knob
# shows clear of the ocular bell from the first-person camera (fp_measure FP_READ, >= 2 cm).
BOLT_BEND = 35.0


def _side(mb, outline, thick, mat, *, x=0.0, chamfer=0.0, uv_scale=1.0):
    """Extrude a side profile drawn in (f, z) along X, centred at x."""
    mb.push(Matrix.Translation((x, 0, 0)) @ SIDE)
    K.extrude(mb, outline, thick, mat=mat, chamfer=chamfer, uv_scale=uv_scale)
    mb.pop()


def _lathe_y(mb, prof, at, **kw):
    """Lathe around an axis parallel to +Y through point `at` (profile z = distance along +Y)."""
    mb.push(Matrix.Translation(at) @ ALONG_Y)
    rings = K.lathe(mb, prof, **kw)
    mb.pop()
    return rings


def _stock(mb):
    """Walnut sporter stock: butt with a cheek comb, a pistol-grip wrist, the action inlet and a
    long fore-end with an ebony tip, in three extrusions of their own widths."""
    butt = [(-0.362, -0.012), (-0.362, -0.136), (-0.300, -0.122), (-0.200, -0.100), (-0.120, -0.086), (-0.095, -0.082),
            (-0.090, -0.040), (-0.105, -0.022), (-0.135, -0.012), (-0.250, -0.006), (-0.330, -0.006)]
    _side(mb, butt, 0.040, "item_wood_grip", chamfer=0.006, uv_scale=6.0)
    # the wrist and pistol grip, down to the grip cap; narrower
    wrist = [(-0.112, -0.020), (-0.104, -0.060), (-0.088, -0.096), (-0.058, -0.104), (-0.044, -0.098), (-0.046, -0.080),
             (-0.030, -0.052), (0.000, -0.046), (0.000, -0.006), (-0.090, -0.008)]
    _side(mb, wrist, 0.032, "item_wood_grip", chamfer=0.005, uv_scale=6.0)
    fore = [(-0.004, -0.050), (0.120, -0.052), (0.300, -0.050), (0.395, -0.044), (0.398, -0.012), (0.300, -0.006),
            (0.120, -0.004), (-0.004, -0.004)]
    _side(mb, fore, 0.040, "item_wood_grip", chamfer=0.007, uv_scale=6.0)
    _side(mb, [(0.395, -0.044), (0.425, -0.040), (0.428, -0.014), (0.398, -0.012)], 0.034, "item_plastic_black", chamfer=0.005)
    # rubber recoil pad and the black grip cap
    _side(mb, [(-0.384, -0.009), (-0.384, -0.140), (-0.361, -0.137), (-0.361, -0.011)], 0.042, "item_rubber", chamfer=0.006)
    _side(mb, [(-0.092, -0.098), (-0.060, -0.106), (-0.054, -0.100), (-0.086, -0.092)], 0.031, "item_plastic_black", chamfer=0.003)


def _action(mb):
    """Receiver, barrel, trigger group, floorplate and sling studs (the frame part)."""
    # receiver: a round action from the tang to the barrel ring, its lower half in the stock
    _lathe_y(mb, [(0.0, 0.0), (0.0128, 0.002), (0.0136, 0.010), (0.0136, 0.186), (0.0128, 0.192), (0.0, 0.194)],
             (0, -0.090, 0), segments=24, mat="item_steel_blued")
    # rear tang down into the wrist
    _side(mb, [(-0.118, -0.006), (-0.090, -0.012), (-0.090, 0.006), (-0.112, 0.004)], 0.012, "item_steel_blued", chamfer=0.002)
    # ejection port: a darker inset on the right side (pre-turn +X), behind which the bolt shows
    K.box(mb, (0.002, 0.060, 0.014), (0.0128, 0.040, 0.004), mat="item_steel_dark", bevel=0.0006)
    # barrel: shank, taper and crowned muzzle with its bore
    _lathe_y(mb, [(0.0118, 0.0), (0.0118, 0.030), (0.0098, 0.060), (0.0082, 0.480), (0.0079, 0.554), (0.0060, 0.556),
                  (0.0034, 0.553)], (0, 0.104, 0), segments=20, mat="item_steel_blued", cap_bottom=True, cap_top=True,
             cap_mat_top="item_charcoal")
    # trigger guard bow and the trigger blade
    guard = K.bezier((0, 0.062, -0.046), (0, 0.060, -0.078), (0, -0.010, -0.082), (0, -0.026, -0.048), 14)
    K.tube(mb, guard, (0.0045, 0.0022), profile=K.rect_profile(1, 1, 0.4), mat="item_steel_blued")
    _side(mb, [(0.020, -0.050), (0.020, -0.062), (0.014, -0.070), (0.018, -0.072), (0.026, -0.066), (0.030, -0.054),
               (0.026, -0.046)], 0.006, "item_steel_dark", chamfer=0.0008)
    # hinged floorplate of the internal magazine, under the action
    K.box(mb, (0.030, 0.064, 0.004), (0, 0.100, -0.052), mat="item_steel_blued", bevel=0.001)
    # sling studs (fore-end and butt)
    for f, z in ((0.33, -0.052), (-0.29, -0.118)):
        mb.push(Matrix.Translation((0, f, z)))
        K.lathe(mb, [(0.0035, 0.0), (0.0035, -0.006), (0.0, -0.007)], segments=8, mat="item_steel_tool", cap_bottom=False)
        mb.pop()
    # recoil-lug and action screws on the floorplate
    for f in (0.072, 0.128):
        mb.push(Matrix.Translation((0, f, -0.054)) @ Matrix.Rotation(math.pi, 4, "X"))
        K.lathe(mb, [(0.0032, 0.0), (0.0032, 0.0006), (0.0022, 0.0012)], segments=8, mat="item_steel_tool", cap_bottom=False)
        mb.pop()


def _bolt():
    """The bolt: body in the receiver, the shroud behind it, the handle on the right with its knob."""
    mb = K.MB()
    _lathe_y(mb, [(0.0, 0.0), (0.0085, 0.001), (0.0088, 0.004), (0.0088, 0.150), (0.0, 0.151)], (0, -0.112, 0),
             segments=16, mat="item_steel_bright")
    # bolt shroud (cocking piece) out the back
    _lathe_y(mb, [(0.0, 0.0), (0.0070, 0.002), (0.0102, 0.012), (0.0105, 0.026), (0.0, 0.027)], (0, -0.137, 0.001),
             segments=14, mat="item_steel_blued")
    # handle: root on the body at the rear, out to the right over the stock's edge, then bent down
    # (BOLT_BEND about the bore) as a sporter's is to clear a low scope: lifted straight, its knob
    # came up beside the ocular bell, and a hand on it read as a hand on the scope (TD-294)
    root = Vector((0.006, -0.082, 0.002))
    bend = Matrix.Rotation(math.radians(BOLT_BEND), 4, "Y")
    arm = K.bezier(root, root + Vector((0.020, -0.002, 0.000)), bend @ (root + Vector((0.040, -0.010, -0.010))),
                   bend @ (root + Vector((0.050, -0.016, -0.024))), 10)
    K.tube(mb, arm, [(0.0042, 0.0042)] * 4 + [(0.0036, 0.0036)] * 6, sides=10, mat="item_steel_blued")
    knob = arm[-1]
    mb.push(Matrix.Translation(knob) @ bend @ Matrix.Rotation(math.radians(70), 4, "Y"))
    K.lathe(mb, [(0.0, -0.010), (0.0060, -0.008), (0.0085, -0.002), (0.0085, 0.003), (0.0055, 0.008), (0.0, 0.010)],
            segments=14, mat="item_steel_blued")
    mb.pop()
    return mb.build("bolt", sharp_deg=40)


def _scope():
    """3-9x hunting scope on two rings: tube, objective and ocular bells with lenses, turrets."""
    mb = K.MB()
    z = SCOPE_Z
    # tube, objective bell (front) and ocular bell (rear), open at both ends over recessed lenses
    prof = [(0.0150, 0.0), (0.0180, 0.001), (0.0185, 0.004), (0.0185, 0.050), (0.0150, 0.060), (0.0128, 0.074),
            (0.0128, 0.250), (0.0150, 0.270), (0.0210, 0.300), (0.0215, 0.340), (0.0196, 0.344)]
    _lathe_y(mb, prof, (0, -0.170, z), segments=28, mat="item_steel_dark", cap_bottom=False, cap_top=False)
    for f, r in ((-0.167, 0.0152), (0.170, 0.0200)):
        _lathe_y(mb, [(r, 0.0), (r, 0.0005)], (0, f, z), segments=24, mat="item_glass_lens")
    # elevation (top) and windage (right) turrets
    mb.push(Matrix.Translation((0, 0.010, z + 0.012)))
    K.lathe(mb, [(0.0095, 0.0), (0.0095, 0.012), (0.0085, 0.014), (0.0, 0.014)], segments=16, mat="item_steel_dark")
    mb.pop()
    mb.push(Matrix.Translation((0.012, 0.010, z)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    K.lathe(mb, [(0.0090, 0.0), (0.0090, 0.010), (0.0080, 0.012), (0.0, 0.012)], segments=16, mat="item_steel_dark")
    mb.pop()
    # power ring knurl on the ocular end
    _lathe_y(mb, [(0.0192, 0.0), (0.0195, 0.002), (0.0195, 0.014), (0.0192, 0.016)], (0, -0.122, z), segments=24,
             mat="item_rubber", cap_bottom=False, cap_top=False)
    # rings and bases down to the receiver
    for f in (-0.058, 0.064):
        _lathe_y(mb, [(0.0150, 0.0), (0.0150, 0.014)], (0, f - 0.007, z), segments=20, mat="item_steel_blued",
                 cap_bottom=False, cap_top=False)
        K.box(mb, (0.018, 0.014, 0.022), (0, f, 0.021), mat="item_steel_blued", bevel=0.0012)
    return mb.build("scope", sharp_deg=40)


def hunting_rifle(p):
    mb = K.MB()
    _stock(mb)
    _action(mb)
    obj = mb.build("hunting_rifle", sharp_deg=38)
    bolt = _bolt()
    scope = _scope()
    # origin on the support hand's grip, then point the muzzle along -Y
    xf = TURN @ Matrix.Translation((0, -SUPPORT[0], -SUPPORT[1]))
    for o in (obj, bolt, scope):
        o.data.transform(xf)
    # the bolt's node origin on the bore axis at the bolt face's rest
    piv = xf @ Vector((0, BOLT_F, 0))
    bolt.data.transform(Matrix.Translation(-piv))
    bolt.location = piv
    bpy.context.view_layer.update()
    sockets = [K.socket("socket_muzzle", xf @ Vector((0, 0.660, 0)), (0, -1, 0)),
               K.socket("socket_sight", xf @ Vector((0, -0.170, SCOPE_Z)), (0, -1, 0)),
               K.socket("socket_grip_r", xf @ Vector((0, -0.070, -0.062)), (0, -1, 0))]
    return [obj], sockets, [bolt, scope]


def _cartridge(mb):
    """A .308: rimless brass case with its shoulder and neck, the copper soft-point bullet."""
    prof = [(0.0020, 0.0002), (0.0024, 0.0), (0.0059, 0.0), (0.0060, 0.0012), (0.0050, 0.0016), (0.0050, 0.0024),
            (0.0060, 0.0030), (0.0059, 0.0390), (0.0057, 0.0400), (0.0046, 0.0430), (0.0044, 0.0510),
            (0.0039, 0.0515), (0.0039, 0.0560), (0.0034, 0.0620), (0.0022, 0.0670), (0.0010, 0.0700)]
    K.lathe(mb, prof, segments=12, mat="item_brass", regions=[(10, 15, "item_copper", "metric")], cap_bottom=True,
            cap_top=True, cap_mat_bottom="item_copper", cap_mat_top="item_lead")


def ammo_308(p):
    r = random.Random(int(p["seed"]))
    mb = K.MB()
    for i in range(5):
        y = -0.028 + i * 0.0135 + r.uniform(-0.002, 0.002)
        yaw = r.uniform(-0.12, 0.12) + (math.pi if i % 2 else 0.0)
        lie = Matrix.Translation((r.uniform(-0.006, 0.006), y, 0.0060)) @ Matrix.Rotation(yaw, 4, "Z") @ \
            Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Translation((0, 0, -0.035))
        mb.push(lie)
        _cartridge(mb)
        mb.pop()
    return [mb.build("ammo_308", sharp_deg=40)], []


# kind -> (builder, viewmodel?, ground rotation, settle degrees)
BUILDERS = {
    "hunting_rifle": (hunting_rifle, True, Matrix.Rotation(math.radians(90), 4, "Y"), 12.0),
    "ammo_308": (ammo_308, False, None, None),
}


def build(params: dict, outputs: list[str]) -> None:
    fn, vm, ground, settle = BUILDERS[params["kind"]]
    out = fn(params)
    parts, sockets = out[0], out[1]
    separate = out[2] if len(out) > 2 else ()
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]), viewmodel=vm,
              ground_rot=ground, sockets=sockets, separate=separate, settle_deg=settle,
              wear_deg=float(params.get("wear_deg", 30.0)))
