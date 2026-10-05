"""Route-cue props (ADR-0022): what makes a POI's entry window read from the street. RouteCues
(game/src/poi/route_cues.gd) puts them on windows that are route entries.

  cue_curtain        torn floral curtain on a 1 m window (0.7 x 1.1 opening, sill 0.9): a pinch-
                     pleated panel still hanging on the left, the right panel torn half off its
                     rings and dragged out over the sill so it hangs down the outside wall
  cue_curtain_wide   the same on a 2 m window (1.6 x 1.2, sill 0.85): two panels left hanging
                     either side, the middle one out over the sill

Conventions: metres; origin = the window's centre on the wall's centre plane at the storey's floor
(z = 0); front = Blender -Y (Godot +Z) = OUTSIDE, so the rod and the hanging panels are on +Y (the
room) and the torn panel crosses the sill to -Y. The wall is 0.16 thick (faces at y = +/-0.08), as
PoiBuilder.WALL_T. No collision: a curtain stops nobody. Faded upholstery_floral (cue_curtain),
zinc rod and brackets (lock_zinc, from the traps family).
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

from lib import export
from lib import props_ext_kit as K

K.materials.PREVIEW_COLORS.update({"cue_curtain": (0.78, 0.74, 0.64)})

WALL = 0.08  # half the wall thickness: the room face is +WALL, the street face -WALL
CLOTH = 0.0035


def _rod(ctx: K.Ctx, x0: float, x1: float, z: float) -> None:
    """Zinc curtain rod on two L brackets screwed into the wall above the opening, ball finials."""
    y = WALL + 0.055
    parts = [K.cyl(ctx.uid("rod"), 0.0085, x1 - x0, segs=10, axis="X", center=((x0 + x1) / 2, y, z))]
    for x in (x0 + 0.05, x1 - 0.05):
        parts.append(K.box(ctx.uid("plate"), (0.03, 0.004, 0.05), center=(x, WALL + 0.002, z + 0.01), bevel=0.0015))
        parts.append(K.box(ctx.uid("arm"), (0.012, 0.055, 0.012), center=(x, WALL + 0.03, z), bevel=0.002))
    for x in (x0, x1):
        parts.append(K.blob(ctx.uid("finial"), 0.016, subdiv=1, center=(x, y, z)))
    ctx.add(K.merge_parts(parts, ctx.uid("rodset")), "lock_zinc", uv="box", uv_scale=1.0, smooth=40, edge=0.8, patches=0.5)


def _rings(ctx: K.Ctx, xs: list[float], z: float) -> None:
    y = WALL + 0.055
    rings = []
    for x in xs:
        pts = [Vector((x, y + 0.016 * math.cos(a), z + 0.016 * math.sin(a))) for a in [i * math.pi / 5 for i in range(10)]]
        rings.append(K.tube(ctx.uid("ring"), pts, 0.0022, segs=5, closed=True))
    if rings:
        ctx.add(K.merge_parts(rings, ctx.uid("rings")), "lock_zinc", uv="box", uv_scale=1.0, smooth=40)


def _ragged(r: random.Random, n: int, depth: float) -> list[float]:
    """Smooth random tear depths for n+1 columns (a hem torn in a few long rips)."""
    knots = [r.uniform(0.0, depth) for _ in range(5)]
    out = []
    for i in range(n + 1):
        t = i / n * 4
        k = min(3, int(t))
        f = t - k
        out.append(knots[k] * (1 - f) + knots[k + 1] * f + r.uniform(-0.012, 0.012))
    return out


def _hanging_panel(ctx: K.Ctx, key: str, x0: float, x1: float, z_top: float, z_hem: float, *, pleats: float = 0.11,
                   draw: float = 0.0, tear: float = 0.18) -> None:
    """A gathered panel hanging from the rod: pinch pleats at the head relaxing into soft folds,
    swinging `draw` metres toward the window at the hem, the hem torn ragged."""
    r = ctx.rnd(key)
    w, h = x1 - x0, z_top - z_hem
    nx, ny = max(8, int(w / 0.034)), max(12, int(h / 0.07))
    g = K.grid(ctx.uid(key), w, h, nx, ny, center=((x0 + x1) / 2, (z_top + z_hem) / 2, 0.0))
    K.uv_sheet(g, scale=1.0)
    ph = r.uniform(0, math.tau)
    tears = _ragged(r, nx, tear)

    def shape(co: Vector) -> Vector:
        u = (co.x - x0) / w
        v = (z_top - co.y) / h  # 0 at the rod, 1 at the hem
        amp = 0.022 * (1.0 - 0.45 * v)
        fold = amp * math.sin(u * w / pleats * math.tau + ph + 0.6 * v)
        y = WALL + 0.055 + 0.012 + fold + 0.035 * v * v
        return Vector((co.x + draw * v * v * (0.5 - u + 0.5), y, co.y))

    K.map_verts(g, shape)
    cut = lambda c, n: c.z < z_hem + tears[min(nx, max(0, int(round((c.x - x0) / w * nx))))]  # noqa: E731
    K.delete_faces(g, cut)
    K.solidify(g, CLOTH, offset=0.0, even=False)
    ctx.add(g, "cue_curtain", uv=None, smooth=50, wear=1.2, edge=0.4, patches=0.8)


def _blown_panel(ctx: K.Ctx, key: str, x0: float, x1: float, z_top: float, sill: float, *, out_drop: float = 0.5) -> None:
    """The panel torn from the right-hand rings and dragged out of the window: it falls inside to
    the sill, runs over it and hangs down the street face of the wall, its end in tatters."""
    r = ctx.rnd(key)
    d_in = z_top - (sill + 0.03)
    d_sill = 2 * WALL + 0.07
    length = d_in + d_sill + out_drop
    w = x1 - x0
    nx, nv = max(8, int(w / 0.034)), max(26, int(length / 0.06))
    g = K.grid(ctx.uid(key), w, length, nx, nv, center=((x0 + x1) / 2, length / 2, 0.0))
    K.uv_sheet(g, scale=1.0)
    ph = r.uniform(0, math.tau)
    tears = _ragged(r, nx, 0.22)

    def centre(t: float) -> tuple[float, float]:
        """(y, z) of the cloth's centre line at arc length t."""
        if t <= d_in:
            v = t / d_in
            # Bellies into the room on the way down, drawn back to the sill's inner lip.
            return (WALL + 0.055 + 0.07 * math.sin(math.pi * v) - (0.055 - 0.012) * v, z_top - t)
        if t <= d_in + d_sill:
            v = (t - d_in) / d_sill
            return (WALL + 0.012 - v * (2 * WALL + 0.04), sill + 0.028 + 0.012 * math.sin(math.pi * v))
        v = (t - d_in - d_sill) / out_drop
        return (-WALL - 0.03 - 0.02 * v, sill + 0.02 - (t - d_in - d_sill))

    def shape(co: Vector) -> Vector:
        u = (co.x - x0) / w
        t = co.y
        y, z = centre(t)
        v = t / length
        # The top is still on the rod across its left part only: the right edge was ripped down,
        # so the free corner hangs lower and the cloth narrows toward the window.
        narrow = 0.25 * v
        x = x0 + w * (narrow * 0.5 + u * (1.0 - narrow))
        if t < 0.25:
            z -= (u ** 2) * 0.22 * (1.0 - t / 0.25)
        fold = 0.02 * math.sin(u * w / 0.1 * math.tau + ph + 4.0 * v) * (1.0 - 0.5 * v)
        if t <= d_in:
            y += fold
        elif t <= d_in + d_sill:
            z += abs(fold) * 0.6
        else:
            y -= abs(fold) * 0.8
        return Vector((x, y, z))

    K.map_verts(g, shape)
    K.delete_faces(g, lambda c, n: c.z < sill + 0.02 - out_drop + tears[min(nx, max(0, int(round((c.x - x0) / w * nx))))]
                   and c.y < -WALL)
    K.solidify(g, CLOTH, offset=0.0, even=False)
    ctx.add(g, "cue_curtain", uv=None, smooth=50, wear=1.4, edge=0.4, patches=0.9)


def cue_curtain(ctx: K.Ctx) -> None:
    w, h, sill = 0.7, 1.1, 0.9
    ctx.ground_clamp = False
    z_rod = sill + h + 0.09
    x0, x1 = -w / 2 - 0.14, w / 2 + 0.14
    _rod(ctx, x0, x1, z_rod)
    _rings(ctx, [x0 + 0.04 + i * 0.045 for i in range(8)] + [x1 - 0.05, x1 - 0.1], z_rod)
    _hanging_panel(ctx, "left", x0 + 0.02, -0.06, z_rod - 0.02, sill - 0.2, draw=0.06)
    _blown_panel(ctx, "out", -0.02, w / 2 - 0.05, z_rod - 0.03, sill, out_drop=0.55)


def cue_curtain_wide(ctx: K.Ctx) -> None:
    w, h, sill = 1.6, 1.2, 0.85
    ctx.ground_clamp = False
    z_rod = sill + h + 0.09
    x0, x1 = -w / 2 - 0.16, w / 2 + 0.16
    _rod(ctx, x0, x1, z_rod)
    _rings(ctx, [x0 + 0.04 + i * 0.045 for i in range(9)] + [x1 - 0.04 - i * 0.045 for i in range(6)], z_rod)
    _hanging_panel(ctx, "left", x0 + 0.02, -0.42, z_rod - 0.02, sill - 0.22, draw=0.1)
    _hanging_panel(ctx, "right", 0.55, x1 - 0.02, z_rod - 0.02, sill - 0.12, draw=-0.08, tear=0.24)
    _blown_panel(ctx, "out", -0.36, 0.45, z_rod - 0.03, sill, out_drop=0.62)


BUILDERS = {
    "cue_curtain": cue_curtain,
    "cue_curtain_wide": cue_curtain_wide,
}


def build(params: dict, outputs: list[str]) -> None:
    """One GLB per condition (props_ext_kit.run without the floor clamp and floor AO: the curtain
    hangs in a window, high off any floor)."""
    prop = params["prop"]
    fn = BUILDERS[prop]
    conds = params.get("conditions", ["clean"])
    if len(conds) != len(outputs):
        raise ValueError(f"{prop}: {len(conds)} conditions but {len(outputs)} outputs")
    for cond, out in zip(conds, outputs):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ctx = K.Ctx(params, cond)
        fn(ctx)
        name = prop if cond == "clean" else f"{prop}_{cond}"
        obj = K.finalize(ctx, name, ao_samples=int(params.get("ao_samples", 20)), ao_dist=float(params.get("ao_dist", 0.25)),
                         ao_strength=float(params.get("ao_strength", 1.0)), ground_ao=False)
        K.report(name, obj, ctx.cols)
        export.export_glb(out, [obj] + ctx.cols)
