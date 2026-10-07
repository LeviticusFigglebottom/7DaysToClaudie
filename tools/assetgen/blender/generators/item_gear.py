"""Found gear: revolver, flashlight, lighter (pointing viewmodels: grip at the origin, barrel / beam /
flame axis along -Y, top +Z), .38 rounds, the Program tether wrist unit, repair kit, can-chime bundle.

Pointing items are modelled with +Y as "forward" (f) and turned 180 deg about Z at the end, so the
business end faces -Y. params: kind, name, seed."""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector, noise

from lib import common, item_kit as K, item_props as P

TURN = Matrix.Rotation(math.pi, 4, "Z")              # local +Y forward -> world -Y forward
SIDE = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # extrude local (x, y, z) -> (z, x, y)
ALONG_Y = Matrix.Rotation(math.radians(-90), 4, "X")  # lathe +Z -> +Y


def _side(mb, outline, thick, mat, *, x=0.0, chamfer=0.0, holes=None, uv_scale=1.0):
    """Extrude a side profile drawn in (f, z) along X, centred at x."""
    mb.push(Matrix.Translation((x, 0, 0)) @ SIDE)
    K.extrude(mb, outline, thick, mat=mat, chamfer=chamfer, holes=holes, uv_scale=uv_scale)
    mb.pop()


def _lathe_y(mb, prof, at, **kw):
    """Lathe around an axis parallel to +Y through point `at` (profile z = distance along +Y)."""
    mb.push(Matrix.Translation(at) @ ALONG_Y)
    rings = K.lathe(mb, prof, **kw)
    mb.pop()
    return rings


def _superellipse(n_pts=16, power=4.0):
    pts = []
    for k in range(n_pts):
        a = 2 * math.pi * k / n_pts
        c, s = math.cos(a), math.sin(a)
        pts.append((math.copysign(abs(c) ** (2 / power), c), math.copysign(abs(s) ** (2 / power), s)))
    return pts


# ------------------------------------------------------------------------------------------------

# The crane pin (model frame, before the turn): low in the bottom strap, left of centre.
PIVOT = (-0.003, 0.04, 0.029)


def revolver(p):
    mb = K.MB()
    zb = 0.068                    # bore axis height
    zc = zb - 0.0135              # cylinder axis
    # frame: rear block (recoil shield + hammer housing), narrow top strap, front shank and bottom
    # strap, leaving the cylinder window open
    rear = [(0.022, 0.0275), (0.022, 0.0858), (0.000, 0.0852), (-0.016, 0.0804), (-0.024, 0.0705), (-0.028, 0.0565),
            (-0.029, 0.0425), (-0.022, 0.0325), (-0.008, 0.0272), (0.006, 0.0270)]
    _side(mb, rear, 0.0262, "item_steel_blued", chamfer=0.0016)
    _side(mb, [(0.019, 0.0735), (0.064, 0.0735), (0.064, 0.0862), (0.019, 0.0862)], 0.0158, "item_steel_blued", chamfer=0.0035)
    _side(mb, [(0.0605, 0.0310), (0.0752, 0.0310), (0.0752, 0.0836), (0.072, 0.0858), (0.0605, 0.0858)], 0.0192, "item_steel_blued",
          chamfer=0.0032)
    _side(mb, [(0.019, 0.0272), (0.0752, 0.0300), (0.0752, 0.0358), (0.019, 0.0358)], 0.0195, "item_steel_blued", chamfer=0.002)
    # barrel + muzzle crown with bore
    _lathe_y(mb, [(0.0088, 0.0), (0.0088, 0.094), (0.0083, 0.0985), (0.0050, 0.0990), (0.0046, 0.090)], (0, 0.072, zb),
             segments=18, mat="item_steel_blued", cap_bottom=False, cap_top=True, cap_mat_top="item_charcoal")
    # ejector-rod shroud (underlug)
    lug = [Vector((0, f, zb - 0.0108)) for f in (0.074, 0.11, 0.152)]
    K.tube(mb, lug, (0.0052, 0.0072), profile=_superellipse(12, 3.0), mat="item_steel_blued")
    # front sight ramp, rear sight notch block
    _side(mb, [(0.146, zb + 0.0078), (0.167, zb + 0.0078), (0.167, zb + 0.0142), (0.161, zb + 0.0156)], 0.0032, "item_steel_blued")
    K.box(mb, (0.010, 0.006, 0.0018), (0, -0.004, 0.0866), mat="item_steel_blued", bevel=0.0005)
    # cylinder with flutes and chamber mouths: its own node `cylinder` (with the crane, the ejector rod
    # and the rounds' heads on its rear face) that swings out to the left about the crane pin in the
    # bottom strap, so the reload can open it (viewmodel.json uses.reload_pistol.parts)
    frame_mb, mb = mb, K.MB()
    segs = 36

    def flute(k, i, r, z):
        if r < 0.017:
            return 1.0
        a = 2 * math.pi * k / segs
        fz = common.smoothstep(0.0085, 0.012, z) * (1 - common.smoothstep(0.026, 0.030, z))
        best = 1.0
        for j in range(6):
            da = abs(math.atan2(math.sin(a - (j * math.pi / 3 + math.pi / 6)), math.cos(a - (j * math.pi / 3 + math.pi / 6))))
            best = min(best, 1.0 - 0.17 * fz * max(0.0, 1 - (da / 0.24) ** 2))
        return best
    cyl = [(0.0150, 0.0), (0.0178, 0.0012), (0.0185, 0.0035), (0.0185, 0.0085), (0.0185, 0.0105), (0.0185, 0.012),
           (0.0185, 0.0195), (0.0185, 0.026), (0.0185, 0.028), (0.0185, 0.030), (0.0185, 0.0365), (0.0176, 0.0392), (0.0140, 0.0398)]
    _lathe_y(mb, cyl, (0, 0.0215, zc), segments=segs, mat="item_steel_blued", radial_fn=flute, angle0=math.pi / 6)
    for j in range(6):
        a = j * math.pi / 3 + math.pi / 2
        _lathe_y(mb, [(0.0044, 0.0), (0.0044, 0.0003)], (math.cos(a) * 0.0118, 0.0613, zc + math.sin(a) * 0.0118), segments=10,
                 mat="item_charcoal", cap_bottom=False, cap_top=True)
    for j in range(6):
        a = j * math.pi / 3 + math.pi / 2
        at = (math.cos(a) * 0.0118, 0.0215 - 0.0007, zc + math.sin(a) * 0.0118)
        _lathe_y(mb, [(0.0049, 0.0), (0.0049, 0.0007)], at, segments=12, mat="item_brass", cap_bottom=True, cap_top=False)
        _lathe_y(mb, [(0.0017, 0.0), (0.0017, 0.0002)], (at[0], at[1] - 0.0002, at[2]), segments=8, mat="item_copper",
                 cap_bottom=True, cap_top=False)
    # crane (the yoke from the pin up to the cylinder's front) and the ejector rod under the barrel
    _side(mb, [(0.0613, PIVOT[2] - 0.003), (0.0655, PIVOT[2] - 0.003), (0.0655, zc + 0.004), (0.0613, zc + 0.004)], 0.007,
          "item_steel_blued", x=PIVOT[0] * 0.5, chamfer=0.001)
    _lathe_y(mb, [(0.0024, 0.0), (0.0024, 0.0905)], (0, 0.0613, zc), segments=10, mat="item_steel_tool", cap_bottom=False,
             cap_top=False)
    _lathe_y(mb, [(0.0031, 0.0), (0.0031, 0.0045), (0.0026, 0.0055)], (0, 0.152, zc), segments=10, mat="item_steel_tool",
             cap_bottom=False, cap_top=True)
    cylinder = mb.build("cylinder", sharp_deg=38)
    mb = frame_mb
    # hammer, trigger, guard
    _side(mb, [(-0.004, 0.058), (0.003, 0.066), (0.000, 0.0772), (-0.009, 0.0832), (-0.019, 0.0868), (-0.030, 0.0892), (-0.0345, 0.0872),
               (-0.028, 0.0828), (-0.020, 0.0768), (-0.016, 0.064), (-0.011, 0.057)], 0.0058, "item_steel_dark", chamfer=0.0012)
    _side(mb, [(0.012, 0.028), (0.016, 0.022), (0.016, 0.014), (0.012, 0.006), (0.006, 0.002), (0.004, 0.004), (0.009, 0.010),
               (0.010, 0.018), (0.007, 0.026)], 0.0055, "item_steel_dark", chamfer=0.0006)
    guard = K.bezier((0, 0.040, 0.031), (0, 0.046, 0.004), (0, 0.006, -0.008), (0, -0.012, 0.027), 12)
    K.tube(mb, guard, (0.0034, 0.0017), profile=K.rect_profile(1, 1, 0.45), mat="item_steel_blued")
    # grip: walnut panels over a steel grip frame
    g0, g1 = Vector((0, -0.016, 0.034)), Vector((0, -0.043, -0.064))
    gp = [g0.lerp(g1, i / 7) for i in range(8)]
    gr = [(0.0152 + 0.0008 * (i / 7), 0.0168 + 0.0042 * math.sin(i / 7 * math.pi * 0.8) + 0.0016 * (i / 7)) for i in range(8)]
    K.tube(mb, gp, gr, profile=_superellipse(16, 2.6), mat="item_wood_grip", cap_mat="item_wood_grip")
    K.tube(mb, gp, [(0.0052, ry + 0.0009) for _, ry in gr], profile=K.rect_profile(1, 1, 0.3), mat="item_steel_blued")
    for side in (1, -1):
        mid = gp[3]
        mb.push(Matrix.Translation((side * 0.0150, mid.y, mid.z)) @ Matrix.Rotation(math.radians(90 * side), 4, "Y"))
        K.lathe(mb, [(0.0042, 0.0), (0.0042, 0.0008), (0.0034, 0.0014)], segments=12, mat="item_steel_tool", cap_bottom=False, cap_top=True)
        mb.pop()
    # cylinder release (left side = local -X), side-plate screws
    K.box(mb, (0.0032, 0.012, 0.0066), (-0.0135, 0.007, 0.061), mat="item_steel_dark", bevel=0.0008)
    for (f, z) in ((0.004, 0.046), (0.032, 0.0318)):
        mb.push(Matrix.Translation((0.0123, f, z)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
        K.lathe(mb, [(0.0022, 0.0), (0.0022, 0.0004), (0.0016, 0.0007)], segments=8, mat="item_steel_tool", cap_bottom=False, cap_top=True)
        mb.pop()
    obj = mb.build("revolver", sharp_deg=38)
    # grip centre -> origin, then point the barrel along -Y
    gc = (g0 + g1) / 2
    xf = TURN @ Matrix.Translation(-gc)
    obj.data.transform(xf)
    cylinder.data.transform(xf)
    # the cylinder's node origin on the crane pin (its axis along the bore): a turn about its local
    # Y (Godot Z) swings it out
    piv = xf @ Vector(PIVOT)
    cylinder.data.transform(Matrix.Translation(-piv))
    cylinder.location = piv
    bpy.context.view_layer.update()
    sockets = [K.socket("socket_muzzle", xf @ Vector((0, 0.1702, zb)), (0, -1, 0))]
    return [obj], sockets, [cylinder]


def flashlight(p):
    seed = int(p["seed"])
    mb = K.MB()
    noise.seed_set(seed)
    r = common.rng(seed)
    dents = [(r.uniform(0, 6.28), r.uniform(-0.06, 0.02), 0.06), (r.uniform(0, 6.28), 0.10, 0.09)]
    segs = 20

    def dent(k, i, rr, z):
        a = 2 * math.pi * k / segs
        m = 1.0
        for a0, z0, d in dents:
            da = math.atan2(math.sin(a - a0), math.cos(a - a0))
            m -= d * 0.12 * math.exp(-(da / 0.35) ** 2 - ((z - z0) / 0.012) ** 2)
        return m
    prof = [(0.0172, -0.130), (0.0196, -0.1295), (0.0200, -0.1270), (0.0200, -0.1120), (0.0205, -0.1100), (0.0198, -0.1080),
            (0.0205, -0.1060), (0.0198, -0.1040), (0.0200, -0.1000), (0.0192, -0.0985), (0.0196, -0.0965), (0.0196, -0.085),
            (0.0196, 0.030), (0.0196, 0.050), (0.0200, 0.052), (0.0206, 0.060), (0.0225, 0.072), (0.0255, 0.085), (0.0272, 0.095),
            (0.0277, 0.098), (0.0270, 0.100), (0.0277, 0.102), (0.0270, 0.104), (0.0277, 0.106), (0.0284, 0.110), (0.0289, 0.1215),
            (0.0285, 0.1245), (0.0263, 0.1250), (0.0256, 0.1236)]
    knurl = (11, 12, "item_alu_knurl", "metric")
    lens = (len(prof) - 2, len(prof) - 1, "item_alu_anodized", "metric")
    K.lathe(mb, prof, segments=segs, mat="item_alu_anodized", regions=[knurl, lens], cap_bottom=True, cap_top=True,
            cap_mat_top="item_glass_lens", radial_fn=dent)
    # switch boot on top (+Y local, becomes +Z)
    mb.push(Matrix.Translation((0, 0.0190, 0.040)) @ ALONG_Y)
    K.lathe(mb, [(0.0064, 0.0), (0.0060, 0.0018), (0.0045, 0.0032), (0.0020, 0.0038)], segments=12, mat="item_rubber",
            cap_bottom=False, cap_top=True)
    mb.pop()
    obj = mb.build("flashlight", sharp_deg=40)
    # grip at the body (f = -0.03); local +Z (beam) -> -Y, local +Y (switch) -> +Z
    xf = Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation((0, 0, 0.03))
    obj.data.transform(xf)
    sockets = [K.socket("socket_light", xf @ Vector((0, 0, 0.1245)), (0, -1, 0))]
    return [obj], sockets


def lighter(p):
    mb = K.MB()
    prof = _superellipse(16, 3.6)
    body = [Vector((0, 0, z)) for z in (0.0, 0.002, 0.03, 0.061, 0.0635)]
    K.tube(mb, body, [(0.0110, 0.0052), (0.0122, 0.0058), (0.0123, 0.0059), (0.0122, 0.0058), (0.0116, 0.0054)], profile=prof,
           mat="item_plastic_red")
    # chrome hood: thin rectangular sleeve
    outer = [(x * 0.0109, y * 0.0057) for x, y in _superellipse(16, 5.0)]
    inner = [(x * 0.0099, y * 0.0047) for x, y in _superellipse(16, 5.0)]
    mb.push(Matrix.Translation((0, 0, 0.0675)))
    K.extrude(mb, outer, 0.0145, holes=[inner], mat="item_chrome", uv_scale=4.0)
    mb.pop()
    # flint wheel (knurled) on the back (+Y), gas lever in front, valve nozzle
    mb.push(Matrix.Translation((0, 0.0024, 0.0742)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
    K.lathe(mb, [(0.0045, -0.0031), (0.0047, -0.0024), (0.0047, 0.0024), (0.0045, 0.0031)], segments=16, mat="item_alu_knurl",
            cap_bottom=True, cap_top=True)
    mb.pop()
    K.box(mb, (0.0092, 0.0068, 0.0045), (0, -0.0022, 0.0655), mat="item_plastic_black", bevel=0.001)
    K.lathe(mb, [(0.0013, 0.0675), (0.0013, 0.0712), (0.0009, 0.0716)], segments=8, mat="item_steel_tool", cap_bottom=False)
    obj = mb.build("lighter", sharp_deg=45)
    xf = Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation((0, 0, -0.033))
    obj.data.transform(xf)
    sockets = [K.socket("socket_flame", xf @ Vector((0, -0.0010, 0.0760)), (0, -1, 0))]
    return [obj], sockets


def _cartridge(mb):
    prof = [(0.0021, 0.0002), (0.0024, 0.0001), (0.0052, 0.0), (0.0056, 0.0004), (0.0056, 0.0013), (0.0046, 0.0016), (0.0048, 0.0022),
            (0.0048, 0.0150), (0.0048, 0.0288), (0.0046, 0.0292), (0.00455, 0.0293), (0.00455, 0.0325), (0.0042, 0.0350),
            (0.0034, 0.0370), (0.0022, 0.0384), (0.0009, 0.0391)]
    K.lathe(mb, prof, segments=11, mat="item_brass", regions=[(10, 15, "item_lead", "metric")], cap_bottom=True, cap_top=True,
            cap_mat_bottom="item_copper", cap_mat_top="item_lead")


def ammo_38(p):
    seed = int(p["seed"])
    r = common.rng(seed)
    mb = K.MB()
    spots = [(-0.022, -0.012), (0.004, -0.018), (0.026, -0.006), (-0.014, 0.014), (0.012, 0.016)]
    for i, (x, y) in enumerate(spots):
        yaw = r.uniform(0, math.tau)
        lie = Matrix.Translation((x, y, 0.0052)) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "Y") @ \
            Matrix.Translation((0, 0, -0.0195))
        mb.push(lie)
        _cartridge(mb)
        mb.pop()
    mb.push(Matrix.Translation((0.03, 0.022, 0.0)))
    _cartridge(mb)
    mb.pop()
    return [mb.build("ammo_38", sharp_deg=40)], []


def tether(p):
    mb = K.MB()
    z0 = 0.026
    dy = -0.0075
    # housing
    K.box(mb, (0.052, 0.017, 0.044), (0, dy, z0), mat="item_plastic_olive", bevel=0.0045)
    # raised bezel ring + recessed screen (faces -Y)
    face = dy - 0.0085
    mb.push(Matrix.Translation((0, face - 0.0006, z0)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    K.extrude(mb, [(-0.0195, -0.0145), (0.0195, -0.0145), (0.0195, 0.0145), (-0.0195, 0.0145)], 0.0016,
              holes=[[(-0.0158, -0.0108), (0.0158, -0.0108), (0.0158, 0.0108), (-0.0158, 0.0108)]], mat="item_plastic_olive",
              chamfer=0.0004, uv_scale=6.0)
    mb.pop()
    mb.push(Matrix.Translation((0, face + 0.0002, z0)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    K.extrude(mb, [(-0.0158, -0.0108), (0.0158, -0.0108), (0.0158, 0.0108), (-0.0158, 0.0108)], 0.0008, mat="item_screen",
              uv_rect=(0.0, 0.0, 1.0, 1.0))
    mb.pop()
    # corner bolts (hex) on the face, side buttons, status lens
    for sx in (1, -1):
        for sz in (1, -1):
            mb.push(Matrix.Translation((sx * 0.0215, face - 0.0002, z0 + sz * 0.0172)) @ Matrix.Rotation(math.radians(90), 4, "X"))
            K.lathe(mb, [(0.0027, 0.0), (0.0027, 0.0016), (0.0019, 0.0021)], segments=6, mat="item_steel_dark", cap_bottom=False,
                    cap_top=True, angle0=0.3)
            mb.pop()
    for k, zz in enumerate((0.008, -0.004)):
        K.box(mb, (0.0024, 0.007, 0.0055), (0.0268, dy, z0 + zz), mat="item_rubber", bevel=0.0008)
    mb.push(Matrix.Translation((-0.012, face - 0.0005, z0 + 0.0182)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    K.lathe(mb, [(0.0016, 0.0), (0.0016, 0.0006), (0.0010, 0.0009)], segments=8, mat="item_plastic_red", cap_bottom=False, cap_top=True)
    mb.pop()
    # strap loop around the wrist (closed), lug brackets and the bolted closure plate
    loop = []
    n = 40
    cy = 0.0215
    for i in range(n):
        a = 2 * math.pi * i / n
        loop.append(Vector((math.cos(a) * 0.0335, cy + math.sin(a) * 0.0285, z0)))
    K.tube(mb, loop, (0.0148, 0.0019), profile=K.rect_profile(1, 1, 0.25), mat="item_rubber", closed=True, up=Vector((0, 0, 1)))
    for sx in (1, -1):
        K.box(mb, (0.008, 0.009, 0.03), (sx * 0.0285, dy + 0.0045, z0), mat="item_steel_dark", bevel=0.0012)
    K.box(mb, (0.022, 0.0042, 0.026), (0, cy + 0.0303, z0), mat="item_steel_dark", bevel=0.0012)
    for sx in (1, -1):
        mb.push(Matrix.Translation((sx * 0.0068, cy + 0.0322, z0)) @ Matrix.Rotation(math.radians(-90), 4, "X"))
        K.lathe(mb, [(0.0024, 0.0), (0.0024, 0.0014), (0.0017, 0.0019)], segments=6, mat="item_steel_tool", cap_bottom=False, cap_top=True)
        mb.pop()
    return [mb.build("tether", sharp_deg=40)], []


def repair_kit(p):
    seed = int(p["seed"])
    mb = K.MB()
    # soft canvas pouch: pinched-end pillow along X
    n = 12
    pts = [Vector((-0.095 + 0.19 * i / (n - 1), 0, 0.03)) for i in range(n)]
    rad = []
    for i in range(n):
        t = i / (n - 1)
        f = max(0.3, math.sin(math.pi * t) ** 0.16)
        rad.append((0.052 * (0.82 + 0.18 * f), 0.028 * (0.45 + 0.55 * f)))
    noise.seed_set(seed)
    K.tube(mb, pts, rad, profile=_superellipse(16, 3.4), mat="item_canvas_olive", up=Vector((0, 1, 0)),
           radius_fn=lambda i, t: 1.0 + 0.03 * math.sin(i * 1.7 + seed))
    # zip along the top ridge
    zp = [Vector((-0.085 + 0.17 * i / 8, 0.0, 0.0575)) for i in range(9)]
    K.tube(mb, zp, (0.0028, 0.0011), profile=K.rect_profile(1, 1, 0.3), mat="item_steel_dark")
    K.box(mb, (0.006, 0.010, 0.002), (0.05, -0.006, 0.0585), mat="item_steel_tool", bevel=0.0006)
    # strap with buckle around the pouch at x = 0.035
    loop = []
    for i in range(28):
        a = 2 * math.pi * i / 28
        c, s = math.cos(a), math.sin(a)
        loop.append(Vector((0.035, math.copysign(abs(c) ** (2 / 2.6), c) * 0.0535, 0.03 + math.copysign(abs(s) ** (2 / 2.6), s) * 0.0295)))
    K.tube(mb, loop, (0.0125, 0.0012), profile=K.rect_profile(1, 1, 0.2), mat="item_webbing", closed=True, up=Vector((1, 0, 0)))
    K.box(mb, (0.03, 0.006, 0.022), (0.035, -0.054, 0.031), mat="item_steel_dark", bevel=0.001)
    # half roll of duct tape lying beside the pouch
    mb.push(Matrix.Translation((-0.04, 0.105, 0.0)))
    K.lathe(mb, [(0.0300, 0.0), (0.0405, 0.0), (0.0405, 0.0475), (0.0300, 0.0475)], segments=24, mat="item_duct_tape",
            cap_bottom=False, cap_top=False)
    K.lathe(mb, [(0.0300, 0.0475), (0.0300, 0.0)], segments=24, mat="item_cardboard", cap_bottom=False, cap_top=False)
    mb.pop()
    # coil of wire tucked under the strap
    P.coil(mb, (0.06, 0.012, 0.052), 0.018, 3.5, cord=0.0009, mat="item_copper", per_turn=20, seed=seed, sides=4)
    obj = mb.build("repair_kit", sharp_deg=50)
    # pliers lying beside the pouch
    pl = K.MB()
    for side in (1, -1):
        hp = K.bezier((0.0, 0.0, 0.0), (-0.04, side * 0.008, 0.0), (-0.08, side * 0.016, 0.0), (-0.115, side * 0.024, 0.0), 8)
        K.tube(pl, hp, (0.0045, 0.0032), profile=_superellipse(10, 3.0), mat="item_steel_dark")
        K.tube(pl, hp[3:], (0.0068, 0.0055), profile=_superellipse(12, 2.6), mat="item_plastic_red")
        jaw = [Vector((0.0, side * 0.0015, 0.0)), Vector((0.025, side * 0.0012, 0.0)), Vector((0.048, side * 0.0006, 0.0))]
        K.tube(pl, jaw, [(0.0028, 0.0045), (0.0022, 0.0035), (0.0012, 0.0016)], profile=_superellipse(10, 2.4), mat="item_steel_dark")
    pl.push(Matrix.Translation((0, 0, -0.004)))
    K.lathe(pl, [(0.0055, 0.0), (0.0055, 0.008)], segments=12, mat="item_steel_tool")
    pl.pop()
    pliers = pl.build("pliers", sharp_deg=45)
    pliers.data.transform(Matrix.Translation((0.03, -0.085, 0.0068)) @ Matrix.Rotation(math.radians(-8), 4, "Z"))
    return [obj, pliers], []


def can_chime(p):
    seed = int(p["seed"])
    mb = K.MB()
    R, H = 0.0382, 0.111
    places = [(Matrix.Translation((-0.045, -0.01, R)) @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Rotation(0.4, 4, "Z") @
               Matrix.Translation((0, 0, -H / 2))),
              (Matrix.Translation((0.05, 0.02, R)) @ Matrix.Rotation(math.radians(-78), 4, "Y") @ Matrix.Rotation(1.9, 4, "Z") @
               Matrix.Translation((0, 0, -H / 2))),
              Matrix.Translation((0.005, 0.075, 0.0)) @ Matrix.Rotation(0.7, 4, "Z")]
    bottoms = []
    for i, m in enumerate(places):
        mb.push(m)
        P.can(mb, R, H, label=None, seed=seed + i, state="open", dent=0.0, segments=14, beads=False, simple=True)
        mb.pop()
        bottoms.append(m @ Vector((0, 0, 0.0)))
    # cord threaded through the punched bottoms, plus a loose coil
    a, b, c = bottoms
    cord = 0.0024
    path = K.bezier(a + Vector((0, 0, 0.004)), a + Vector((0.0, -0.06, 0.03)), b + Vector((-0.02, -0.07, 0.03)), b, 12)
    K.tube(mb, path, cord, sides=5, mat="item_cordage", u_tile=1.0, v_scale=1.0 / (2 * math.pi * cord) / 3)
    path2 = K.bezier(b, b + Vector((0.0, 0.06, 0.05)), c + Vector((0.03, 0.0, 0.06)), c + Vector((0, 0, 0.003)), 12)
    K.tube(mb, path2, cord, sides=5, mat="item_cordage", u_tile=1.0, v_scale=1.0 / (2 * math.pi * cord) / 3)
    P.coil(mb, (-0.06, 0.07, 0.0), 0.032, 3.2, cord=cord, seed=seed, mat="item_cordage")
    return [mb.build("can_chime", sharp_deg=50)], []


# kind -> (builder, viewmodel?, ground rotation, settle degrees)
BUILDERS = {
    "revolver": (revolver, True, Matrix.Rotation(math.radians(90), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "Y"), 30.0),
    "flashlight": (flashlight, True, Matrix.Rotation(math.radians(90), 4, "Z"), 20.0),
    "lighter": (lighter, True, Matrix.Rotation(math.radians(90), 4, "Z"), 20.0),
    "ammo_38": (ammo_38, False, None, None),
    "tether": (tether, False, None, 25.0),
    "repair_kit": (repair_kit, False, None, None),
    "can_chime": (can_chime, False, None, None),
}


def build(params: dict, outputs: list[str]) -> None:
    fn, vm, ground, settle = BUILDERS[params["kind"]]
    out = fn(params)
    parts, sockets = out[0], out[1]
    separate = out[2] if len(out) > 2 else ()
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]), viewmodel=vm,
              ground_rot=ground, sockets=sockets, separate=separate, settle_deg=settle,
              wear_deg=float(params.get("wear_deg", 30.0)))
