"""Forest encounter props (ADR-0054): a camp cooler, a ladder stand, a pop-up ground blind, a logging
truck run off its track, a broken-down ATV, a survivor's cache under a tarp, a Bloom-grown deer kill, a
lashed grave cross and a Cordon recovery marker. Catalog: blender_catalogs/props_encounters.py; content
defs: game/data/props/encounters.json (sizes there match the builds here).

Conventions (docs/ASSET_PIPELINE.md): metres, origin at the bottom centre, front towards Blender -Y
(Godot +Z). The ladder stand's back (+Y) leans on a trunk: the encounter places its origin at the trunk's
surface. Worn variants are weathered and damaged, never gory."""
from __future__ import annotations

import math

from mathutils import Vector

from lib import props_ext_kit as K
from lib import props_ext_parts as P
from lib import props_wild_parts as W


# ============================================================================================
# Camp cooler
# ============================================================================================

def enc_camp_cooler(ctx: K.Ctx) -> None:
    """Two-tone plastic cooler: red tub, white lid, swing handle, side grips, a drain plug. Worn:
    sun-faded and scuffed, the lid ajar."""
    L, Dp, H = 0.6, 0.38, 0.3
    tub = K.box("tub", (L, Dp, H), center=(0, 0, H / 2), bevel=0.03, bevel_segs=2, cuts=(3, 2, 2))
    ctx.add(tub, "plastic_red", uv_scale=1.5, smooth=40, patches=0.3)
    lid = K.box("lid", (L + 0.02, Dp + 0.02, 0.06), center=(0, 0, 0.03), bevel=0.02, bevel_segs=2)
    if ctx.worn:
        K.place(lid, (0, Dp / 2, H), rot=(-14, 0, 0))
        K.place(lid, (0, -Dp / 2 * 0.0, 0.0))
    else:
        K.place(lid, (0, 0, H))
    ctx.add(lid, "plastic_white", uv_scale=1.5, smooth=40, patches=0.4)
    handle = K.tube("handle", [(-L / 2 - 0.01, 0, H * 0.75), (-L / 2 - 0.03, 0, H + 0.12), (L / 2 + 0.03, 0, H + 0.12),
                               (L / 2 + 0.01, 0, H * 0.75)], 0.009, segs=6)
    ctx.add(handle, "plastic_white", uv_scale=1.0, smooth=50)
    for s in (-1, 1):
        ctx.add(K.box(f"grip{s}", (0.02, 0.12, 0.03), center=(s * (L / 2 + 0.005), 0, H * 0.6), bevel=0.006), "plastic_white")
    ctx.add(K.cyl("plug", 0.015, 0.02, segs=8, axis="Y", center=(L * 0.3, -Dp / 2 - 0.008, 0.04)), "plastic_black")
    ctx.col_box((-L / 2, -Dp / 2, 0), (L / 2, Dp / 2, H + 0.08))


# ============================================================================================
# Ladder stand
# ============================================================================================

def enc_ladder_stand(ctx: K.Ctx) -> None:
    """Steel ladder stand strapped to a trunk behind it (+Y): two ladder rails from the foot 1.35 m out
    to a platform 4.1 m up against the trunk, rungs, a mesh seat with a padded back, a shooting rail,
    a brace bar and ratchet straps round the trunk. Worn: rusted, a strap hanging loose, the cushion
    rotted."""
    paint = "paint_olive"
    top_z, foot_y = 4.1, -1.35
    for sx in (-1, 1):
        W.rod(ctx, f"rail{sx}", (sx * 0.22, foot_y, 0.0), (sx * 0.22, -0.08, top_z), 0.022, paint, segs=8)
    n = 13
    for k in range(1, n):
        t = k / n
        y = foot_y + (-0.08 - foot_y) * t
        W.rod(ctx, f"rung{k}", (-0.22, y, top_z * t), (0.22, y, top_z * t), 0.014, paint, segs=6)
    # Platform frame and grating.
    plat = K.box("platform", (0.62, 0.62, 0.04), center=(0, -0.33, top_z + 0.02), cuts=(4, 4, 0))
    ctx.add(plat, paint, uv_scale=2.0)
    seat = K.box("seat", (0.5, 0.36, 0.05), center=(0, -0.22, top_z + 0.45), bevel=0.01)
    ctx.add(seat, "canvas_olive" if ctx.clean else "canvas_khaki", uv_scale=2.0, smooth=40)
    back = K.box("back", (0.46, 0.06, 0.42), center=(0, -0.02, top_z + 0.72), bevel=0.02)
    ctx.add(back, "canvas_olive" if ctx.clean else "canvas_khaki", uv_scale=2.0, smooth=40)
    for sx in (-1, 1):
        W.rod(ctx, f"seatpost{sx}", (sx * 0.24, -0.3, top_z + 0.04), (sx * 0.24, -0.25, top_z + 0.45), 0.014, paint, segs=6)
        W.rod(ctx, f"railpost{sx}", (sx * 0.3, -0.62, top_z + 0.04), (sx * 0.3, -0.62, top_z + 0.78), 0.014, paint, segs=6)
    W.rod(ctx, "shooting_rail", (-0.3, -0.62, top_z + 0.78), (0.3, -0.62, top_z + 0.78), 0.016, "rubber_black", segs=8)
    # Brace bar from the ladder's middle back to the trunk.
    W.rod(ctx, "brace", (0.0, (foot_y - 0.08) / 2, top_z / 2), (0.0, 0.02, top_z * 0.55), 0.016, paint, segs=6)
    # Straps round the trunk: arcs into +Y (the trunk's radius is unknown: ~0.3 m reads right).
    for k, z in enumerate((top_z + 0.2, top_z * 0.55)):
        pts = [(math.sin(a) * 0.3, 0.3 - math.cos(a) * 0.3, z) for a in [math.pi * (-0.55 + 1.1 * i / 8) for i in range(9)]]
        if ctx.worn and k == 0:
            pts = pts[:5] + [(pts[4][0] + 0.02, pts[4][1] - 0.05, z - 0.4)]
        ctx.add(K.tube(f"strap{k}", pts, 0.012, segs=4, flat=(1.0, 0.25)), "item_webbing_black", uv_scale=4.0)


# ============================================================================================
# Ground blind
# ============================================================================================

def enc_ground_blind(ctx: K.Ctx) -> None:
    """Pop-up hub blind: five-sided canvas walls bowed out between the hub poles, a dark shooting window
    on each face (half unzipped flaps), guy lines and stakes. Worn: faded, one hub caved in, a flap
    torn loose."""
    r = ctx.rnd("blind")
    rings = []
    sides = 5
    for zi, (z, rad) in enumerate(((0.0, 0.95), (0.6, 1.0), (1.2, 0.9), (1.7, 0.6), (1.75, 0.05))):
        ring = []
        for i in range(sides * 4):
            a = math.tau * i / (sides * 4) + math.pi / 2
            bow = 1.0 + 0.06 * math.cos(math.pi * ((i % 4) / 4.0 - 0.5) * 2) * (1 if zi in (1, 2) else 0)
            rr = rad * bow
            if ctx.worn and zi == 2 and 2 <= i <= 6:
                rr *= 0.8
            ring.append((math.cos(a) * rr, math.sin(a) * rr, z))
        rings.append(ring)
    shell = K.loft("shell", rings, cap_start=False, cap_end=True)
    K.solidify(shell, 0.01)
    K.crumple(shell, 0.01 if ctx.clean else 0.025, scale=3.0, seed=r.randint(0, 999))
    ctx.add(shell, "wild_canvas_green" if ctx.clean else "canvas_olive", uv_scale=1.2, smooth=40, patches=0.5)
    for i in range(sides):
        a = math.tau * (i + 0.5) / sides + math.pi / 2
        c = Vector((math.cos(a) * 0.97, math.sin(a) * 0.97, 1.05))
        win = K.box(f"win{i}", (0.5, 0.02, 0.28), center=(0, 0, 0))
        K.orient(win, Vector((-math.sin(a), math.cos(a), 0)), Vector((math.cos(a), math.sin(a), 0)), c)
        ctx.add(win, "paint_black", uv_scale=1.0, wear=0.0, ao=False)
    for i in range(sides):
        a = math.tau * i / sides + math.pi / 2
        top = (math.cos(a) * 0.9, math.sin(a) * 0.9, 1.2)
        stake = (math.cos(a) * 1.7, math.sin(a) * 1.7, 0.0)
        ctx.add(K.tube(f"guy{i}", [top, stake], 0.004, segs=4), "item_cordage", uv_scale=4.0)
        ctx.add(K.cyl(f"stake{i}", 0.008, 0.2, segs=6, center=(stake[0], stake[1], 0.05)), "metal_galvanized")
    ctx.col_box((-0.9, -0.9, 0), (0.9, 0.9, 1.75))


# ============================================================================================
# Logging truck
# ============================================================================================

def _wheel(ctx, name, x, y, r_out=0.55, width=0.32, flat=False):
    t = P.tyre(name, r_out, r_out * 0.55, width)
    if flat:
        P.flatten_tyre(t, 0.0, r_out, amount=0.4)
    K.place(t, (x, y, r_out))
    ctx.add(t, "tyre_rubber", uv="cyl", uv_axis=0, smooth=40, patches=0.2)
    rim = P.steel_rim(name + "_rim", r_out * 0.55, width * 0.9)
    K.place(rim, (x, y, r_out))
    ctx.add(rim, "car_rust" if ctx.worn else "paint_white", uv_scale=2.0, smooth=40)


def enc_logging_truck_wreck(ctx: K.Ctx) -> None:
    """A conventional log truck 9.6 m long, front towards -Y: hood and cab, frame rails, tandem drive
    axles, three bunks with stakes and a few bark-on logs chained on. Worn: rusted out, the hood up,
    tyres flat, the load half spilled."""
    paint = "car_paint_red" if ctx.clean else "car_burnt"
    L = 9.6
    y0 = -L / 2
    # Frame rails.
    for sx in (-1, 1):
        ctx.add(K.box(f"rail{sx}", (0.18, L - 0.4, 0.28), center=(sx * 0.45, 0.2, 0.95)), "paint_black", uv_scale=2.0)
    # Hood, cab, bumper, stack.
    hood = K.box("hood", (2.0, 1.7, 1.0), center=(0, y0 + 1.15, 1.6), bevel=0.06, cuts=(2, 2, 1))
    if ctx.worn:
        K.place(hood, rot=(-8, 0, 0))
        K.dent(hood, (0.6, y0 + 0.4, 2.0), 0.4, 0.08)
    ctx.add(hood, paint, uv_scale=1.5, smooth=30, patches=0.7)
    cab = K.box("cab", (2.3, 1.9, 1.7), center=(0, y0 + 2.9, 2.0), bevel=0.06, cuts=(2, 2, 2))
    ctx.add(cab, paint, uv_scale=1.5, smooth=30, patches=0.7)
    ctx.add(K.box("windshield", (2.0, 0.04, 0.7), center=(0, y0 + 1.94, 2.45)), "window_grime", wear=0.0)
    ctx.add(K.box("bumper", (2.4, 0.25, 0.3), center=(0, y0 + 0.2, 0.75), bevel=0.03), "chrome_pitted" if ctx.clean else "car_rust")
    W.rod(ctx, "stack", (1.05, y0 + 3.7, 1.2), (1.05, y0 + 3.7, 4.0), 0.07, "chrome_pitted" if ctx.clean else "car_rust", segs=10)
    # Wheels: steer axle and tandem drive.
    _wheel(ctx, "wfl", -1.05, y0 + 1.2)
    _wheel(ctx, "wfr", 1.05, y0 + 1.2, flat=ctx.worn)
    for k, y in enumerate((1.7, 3.1)):
        for sx in (-1, 1):
            _wheel(ctx, f"wd{k}{sx}", sx * 1.0, y, flat=ctx.worn and k == 1 and sx < 0)
    # Bunks and stakes.
    for k, y in enumerate((-0.6, 1.6, 3.8)):
        ctx.add(K.box(f"bunk{k}", (2.5, 0.2, 0.18), center=(0, y, 1.25)), "paint_black", uv_scale=2.0)
        for sx in (-1, 1):
            if ctx.worn and k == 2 and sx > 0:
                continue
            W.rod(ctx, f"stake{k}{sx}", (sx * 1.18, y, 1.3), (sx * 1.18, y, 2.6), 0.05, "paint_black", segs=8)
    # Logs along Y on the bunks.
    n_logs = 5 if ctx.clean else 2
    for k in range(n_logs):
        x = -0.75 + (k % 3) * 0.75
        z = 1.65 + (k // 3) * 0.6
        W.add_log(ctx, f"log{k}", 6.6, 0.3, ctx.seed + k, at=(x, 1.6, z), rot=(0, 0, 90))
    # Chain over the load.
    ctx.add(K.tube("chain", [(-1.2, 1.6, 1.3), (-0.9, 1.6, 2.6), (0.9, 1.6, 2.6), (1.2, 1.6, 1.3)], 0.015, segs=4),
            "car_rust", uv_scale=4.0)
    ctx.col_box((-1.3, -L / 2, 0), (1.3, L / 2, 3.2))


# ============================================================================================
# ATV
# ============================================================================================

def enc_atv_wreck(ctx: K.Ctx) -> None:
    """A red quad bike, front towards -Y: frame, front and rear fenders, seat, fuel tank, handlebars,
    racks front and back with a black box strapped to the rear one, four fat tyres. Worn: faded and
    muddy, a front tyre flat, the handlebars twisted."""
    paint = "plastic_red"
    L = 2.0
    for k, y in enumerate((-0.62, 0.62)):
        for sx in (-1, 1):
            t = P.tyre(f"t{k}{sx}", 0.3, 0.17, 0.24)
            if ctx.worn and k == 0 and sx > 0:
                P.flatten_tyre(t, 0.0, 0.3, amount=0.5)
            K.place(t, (sx * 0.47, y, 0.3))
            ctx.add(t, "tyre_rubber", uv="cyl", uv_axis=0, smooth=40)
    ctx.add(K.box("frame", (0.36, 1.5, 0.12), center=(0, 0, 0.38)), "paint_black", uv_scale=2.0)
    for k, y in enumerate((-0.62, 0.62)):
        f = K.box(f"fender{k}", (1.18, 0.62, 0.08), center=(0, y, 0.66), bevel=0.03, cuts=(3, 2, 0))
        K.bend(f, 0, 0.12)
        ctx.add(f, paint, uv_scale=2.0, smooth=35, patches=0.6)
    ctx.add(K.blob("tank", 0.5, subdiv=2, scale=(0.32, 0.4, 0.2), center=(0, -0.2, 0.72)), paint, uv_scale=2.0, smooth=50)
    ctx.add(K.box("seat", (0.34, 0.75, 0.12), center=(0, 0.2, 0.86), bevel=0.04, bevel_segs=2), "leather_dark", smooth=45)
    tw = 12 if ctx.worn else 0
    bar = K.tube("bars", [(-0.4, -0.55, 1.02), (-0.15, -0.5, 1.0), (0.15, -0.5, 1.0), (0.4, -0.55, 1.02)], 0.014, segs=6)
    K.place(bar, rot=(0, 0, tw))
    ctx.add(bar, "paint_black", smooth=40)
    W.rod(ctx, "column", (0, -0.4, 0.6), (0, -0.5, 1.0), 0.022, "paint_black", segs=6)
    for k, (y, z) in enumerate(((-0.75, 0.78), (0.72, 0.8))):
        for sx in (-1, 1):
            W.rod(ctx, f"rack{k}{sx}", (sx * 0.3, y - 0.2, z), (sx * 0.3, y + 0.2, z), 0.012, "paint_black", segs=5)
    box = K.box("box", (0.5, 0.36, 0.3), center=(0, 0.75, 0.97), bevel=0.02)
    ctx.add(box, "plastic_black", uv_scale=2.0, smooth=40)
    ctx.add(K.box("strap", (0.52, 0.04, 0.33), center=(0, 0.75, 0.97)), "item_webbing_black")
    ctx.col_box((-0.6, -L / 2, 0), (0.6, L / 2, 1.12))


# ============================================================================================
# Survivor's cache
# ============================================================================================

def enc_tarp_cache(ctx: K.Ctx) -> None:
    """Crates and water jugs under a blue tarp pegged down at the corners, the edges weighted with river
    stones, a rope over the top. Worn: the tarp faded and torn back off one corner."""
    r = ctx.rnd("cache")
    crates = [((-0.35, 0.1), (0.55, 0.45, 0.42)), ((0.3, 0.15), (0.5, 0.4, 0.5)), ((0.0, -0.3), (0.45, 0.35, 0.3))]
    for k, ((x, y), (sx, sy, sz)) in enumerate(crates):
        ctx.add(K.box(f"crate{k}", (sx, sy, sz), center=(x, y, sz / 2), bevel=0.01, cuts=(2, 1, 1)), "wood_weathered", uv_scale=1.5)
    for k in range(2):
        jug = K.cyl(f"jug{k}", 0.1, 0.3, segs=12, center=(0.55 - k * 0.22, -0.35, 0.15), bevel=0.02)
        ctx.add(jug, "plastic_blue" if k == 0 else "plastic_white", uv="cyl", smooth=40)

    def height(x, y):
        h = 0.0
        for (cx, cy), (sx, sy, sz) in crates:
            dx = max(0.0, abs(x - cx) - sx / 2)
            dy = max(0.0, abs(y - cy) - sy / 2)
            d = math.hypot(dx, dy)
            h = max(h, (sz + 0.03) * max(0.0, 1.0 - d / 0.35))
        return h
    tarp = K.grid("tarp", 1.6, 1.2, 20, 16)
    K.uv_planar(tarp, 2, scale=1.0)

    def drape(co):
        z = height(co.x, co.y)
        if ctx.worn and co.x > 0.45 and co.y > 0.25:
            z += 0.25 * (co.x - 0.45)
        return Vector((co.x, co.y, z + 0.005))
    K.map_verts(tarp, drape)
    K.crumple(tarp, 0.015, scale=5.0, seed=r.randint(0, 999))
    K.solidify(tarp, 0.004)
    ctx.add(tarp, "tarp_blue", uv=None, smooth=40, patches=0.5)
    for k in range(9):
        a = math.tau * k / 9 + r.uniform(-0.2, 0.2)
        c = (math.cos(a) * 0.82, math.sin(a) * 0.6, 0.04)
        ctx.add(K.chunk(f"stone{k}", r.uniform(0.09, 0.15), r, flat=0.6), "stone_river", at=(c, (0, 0, r.uniform(0, 90))))
    ctx.add(K.tube("rope", [(-0.8, 0.0, 0.0), (-0.3, 0.0, 0.48), (0.3, 0.05, 0.55), (0.8, 0.0, 0.0)], 0.008, segs=5),
            "item_cordage", uv_scale=4.0)
    ctx.col_box((-0.8, -0.6, 0), (0.8, 0.6, 0.6))


# ============================================================================================
# Bloom-grown kill
# ============================================================================================

def enc_bloom_kill(ctx: K.Ctx) -> None:
    """A deer dead on its side along Y, head towards -Y, legs out towards +X: the Bloom's white felt
    grown through the coat in sheets and patches, pale caps fruiting from the flank and the neck, ribs
    showing where the felt has eaten through. Worn: further gone, more felt, more bone."""
    r = ctx.rnd("kill")
    body = K.blob("body", 0.5, subdiv=3, scale=(0.5, 0.95, 0.42), center=(0, 0.1, 0.24), rough=0.08, seed=ctx.seed)
    K.cut_plane(body, (0, 0, 0.005), (0, 0, -1), keep="above", fill=True)
    ctx.add(body, "fur_deer", uv_scale=1.5, smooth=50, patches=0.2)
    neck = K.tube("neck", [(0.05, -0.38, 0.22), (0.12, -0.62, 0.2), (0.22, -0.78, 0.14)], [0.14, 0.11, 0.09], segs=10)
    ctx.add(neck, "fur_deer", smooth=50)
    head = K.blob("head", 0.5, subdiv=2, scale=(0.18, 0.3, 0.16), center=(0.28, -0.9, 0.13), seed=ctx.seed + 1)
    ctx.add(head, "fur_deer", smooth=50)
    for k, (y, ang) in enumerate(((-0.28, 0.1), (-0.18, -0.2), (0.4, 0.15), (0.5, -0.25))):
        a = (0.3, y, 0.2)
        b = (0.3 + 0.55 * math.cos(ang), y + 0.55 * math.sin(ang), 0.06)
        ctx.add(W.rod_obj(f"leg{k}", a, b, 0.045, segs=6, r2=0.025), "fur_deer", smooth=45)
        ctx.add(K.blob(f"hoof{k}", 0.03, subdiv=1, center=b), "hoof")
    n_ribs = 3 if ctx.clean else 6
    for k in range(n_ribs):
        y = -0.15 + k * 0.08
        ctx.add(K.tube(f"rib{k}", [(-0.25, y, 0.08), (-0.3, y, 0.28), (-0.15, y, 0.42)], 0.012, segs=5), "corpse_bone", smooth=40)
    for k in range(7 if ctx.clean else 12):
        c = (r.uniform(-0.3, 0.3), r.uniform(-0.6, 0.7), r.uniform(0.25, 0.42))
        felt = K.blob(f"felt{k}", r.uniform(0.08, 0.16), subdiv=2, scale=(1.0, 1.4, 0.35), center=c, rough=0.4, seed=r.randint(0, 999))
        ctx.add(felt, "bloom_felt", smooth=50, patches=0.0, ao=True)
    for k in range(9 if ctx.clean else 14):
        x, y = r.uniform(-0.25, 0.25), r.uniform(-0.7, 0.6)
        h = r.uniform(0.04, 0.09)
        z = 0.3 + 0.1 * math.cos(y)
        stem = K.cyl(f"stem{k}", 0.006, h, segs=6, center=(x, y, z + h / 2))
        ctx.add(stem, "bloom_caps", uv="cyl", smooth=40)
        cap = K.lathe(f"cap{k}", [(0.0, 0.012), (0.018, 0.01), (0.026, 0.0), (0.0, 0.0)], segs=10)
        K.place(cap, (x, y, z + h))
        ctx.add(cap, "bloom_caps", smooth=50)
    ctx.col_box((-0.45, -1.0, 0), (0.45, 0.7, 0.55))


# ============================================================================================
# Grave cross
# ============================================================================================

def enc_grave_cross(ctx: K.Ctx) -> None:
    """Two crooked branches lashed with cord, the upright driven into the ground, a name burnt into the
    crosspiece. Worn: leaning, the lashing frayed."""
    lean = 0.0 if ctx.clean else 9.0
    up = W.pole(ctx, "upright", [(0, 0, -0.1), (0.01, 0.0, 0.6), (0.0, 0.0, 1.25)], 0.035, "wild_log_bark", r_end=0.028,
                seed=ctx.seed, wobble=0.015)
    arm = W.pole(ctx, "arm", [(-0.3, -0.03, 0.92), (0.0, -0.04, 0.93), (0.3, -0.03, 0.9)], 0.028, "wild_log_bark",
                 r_end=0.024, seed=ctx.seed + 1, wobble=0.012)
    plate = K.box("name", (0.22, 0.008, 0.05), center=(0.05, -0.07, 0.92))
    ctx.add(plate, "wood_charred", uv_scale=4.0)
    pts = [(math.cos(a) * 0.05, -0.04 + math.sin(a) * 0.05, 0.9 + 0.012 * i) for i, a in enumerate([k * 0.9 for k in range(9)])]
    ctx.add(K.tube("lash", pts, 0.005, segs=4), "item_cordage", uv_scale=6.0)
    if lean:
        for o in ctx.parts:
            K.place(o, rot=(lean, 0, 0))


# ============================================================================================
# Cordon marker
# ============================================================================================

def enc_cordon_marker(ctx: K.Ctx) -> None:
    """An orange survey stake with a laminated white placard and a streamer of hazard tape. Worn: the
    placard curled and grimy, the tape torn short."""
    ctx.add(K.box("stake", (0.04, 0.04, 1.35), center=(0, 0, 0.6), cuts=(0, 0, 3)), "paint_orange_wood", uv_scale=2.0)
    card = K.box("placard", (0.3, 0.008, 0.22), center=(0, -0.026, 1.05), cuts=(3, 0, 2))
    if ctx.worn:
        K.bend(card, 0, 0.04)
    ctx.add(card, "paper_trash", uv_scale=3.0, patches=0.5)
    n = 6 if ctx.clean else 3
    pts = [(0.02 + 0.08 * i, 0.03 * math.sin(i * 1.3), 1.22 - 0.05 * i) for i in range(n)]
    ctx.add(K.tube("tape", pts, 0.02, segs=4, flat=(1.0, 0.1)), "plastic_yellow", uv_scale=3.0)


BUILDERS = {
    "enc_camp_cooler": enc_camp_cooler,
    "enc_ladder_stand": enc_ladder_stand,
    "enc_ground_blind": enc_ground_blind,
    "enc_logging_truck_wreck": enc_logging_truck_wreck,
    "enc_atv_wreck": enc_atv_wreck,
    "enc_tarp_cache": enc_tarp_cache,
    "enc_bloom_kill": enc_bloom_kill,
    "enc_grave_cross": enc_grave_cross,
    "enc_cordon_marker": enc_cordon_marker,
}


def build(params: dict, outputs: list[str]) -> None:
    K.run(params, outputs, BUILDERS)
