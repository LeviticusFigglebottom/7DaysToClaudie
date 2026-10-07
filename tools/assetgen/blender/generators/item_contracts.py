"""Contract items (ADR-0039): the sealed Remand Program field cache a fetch contract sets down in a building
(TD-141). Origin bottom centre, lying flat on its feet, handle and latches on the front (-Y in Blender = +Z
in Godot). params: kind, name, seed.

The Program mark and the serial plate are cells of the Waystation 9 print atlas (ws_print, PRINT_RECTS in
textures/gen/waystation.py): the stencilled roundel the waystation's crates carry and its riveted asset
plate, so the case reads as the post's own kit."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

from lib import item_kit as K

ATLAS_PX = 2048.0
# Mirrors textures/gen/waystation.py PRINT_RECTS (x0, y0, x1, y1, pixels, y down) - change both together.
ATLAS = {"emblem": (960, 512, 1216, 768), "plate": (768, 1152, 1024, 1280)}

SHELL = "item_plastic_olive"
TRIM = "item_plastic_black"


def _uv(name: str, inset: float = 2.0) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = ATLAS[name]
    return ((x0 + inset) / ATLAS_PX, 1.0 - (y1 - inset) / ATLAS_PX, (x1 - inset) / ATLAS_PX, 1.0 - (y0 + inset) / ATLAS_PX)


def _rounded(w: float, h: float, r: float, n: int = 2) -> list[tuple[float, float]]:
    """Rounded rectangle w x h (centred, CCW) with corner radius r."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def _slab(mb: K.MB, w: float, d: float, z0: float, z1: float, r: float, mat: str, chamfer: float = 0.0, side_mat=None) -> None:
    mb.push(Matrix.Translation((0, 0, (z0 + z1) / 2)))
    K.extrude(mb, _rounded(w, d, r), z1 - z0, mat=mat, side_mat=side_mat, chamfer=chamfer, uv_scale=2.0)
    mb.pop()


def program_cache(p):
    """A ruggedized polymer hard case, 0.45 x 0.32 x 0.18 m: an olive body and lid on a black gasket,
    rubber feet, two hinge knuckles at the back, a folding grip between two draw latches at the front, the Program roundel stencilled on the lid beside the asset plate, and an amber tamper seal on a
    wire through the right-hand latch."""
    mb = K.MB()
    W, D = 0.45, 0.32
    seam = 0.105
    top = 0.172
    # Body: a slightly narrower foot band, then the shell up to the seam.
    _slab(mb, W - 0.012, D - 0.012, 0.006, 0.022, 0.03, SHELL, chamfer=0.004)
    _slab(mb, W, D, 0.018, seam, 0.034, SHELL, chamfer=0.005)
    # Gasket line, inset, black.
    _slab(mb, W - 0.008, D - 0.008, seam - 0.002, seam + 0.006, 0.03, TRIM)
    # Lid, flush with the body, stepped up to a raised field on top.
    _slab(mb, W, D, seam + 0.004, top - 0.008, 0.034, SHELL, chamfer=0.005)
    _slab(mb, W - 0.02, D - 0.02, top - 0.012, top, 0.026, SHELL, chamfer=0.004)
    # Stacking ribs across the lid field.
    for x in (-0.19, 0.19):
        K.box(mb, (0.018, D - 0.05, 0.006), (x, 0.0, top + 0.003), mat=SHELL, bevel=0.002)
    # A moulded reinforcing rib along each long side of the body (chamfered, so it doesn't scuff white).
    for sy in (-1, 1):
        K.box(mb, (W - 0.09, 0.012, 0.012), (0.0, sy * (D / 2 + 0.003), 0.06), mat=SHELL, bevel=0.004)
    # Rubber feet.
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.box(mb, (0.05, 0.035, 0.008), (sx * 0.17, sy * 0.115, 0.004), mat="item_rubber")
    # Hinge knuckles along the back seam.
    for x in (-0.13, 0.13):
        K.box(mb, (0.07, 0.016, 0.03), (x, D / 2 + 0.006, seam + 0.002), mat=TRIM)
        mb.push(Matrix.Translation((x, D / 2 + 0.012, seam + 0.002)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
        K.lathe(mb, [(0.0, -0.04), (0.005, -0.04), (0.005, 0.04), (0.0, 0.04)], segments=6, mat="item_steel_dark")
        mb.pop()
    fy = -D / 2
    # Draw latches straddling the seam: a black lever over a steel catch, hasp for a padlock.
    for x in (-0.145, 0.145):
        K.box(mb, (0.052, 0.012, 0.024), (x, fy - 0.004, seam + 0.02), mat=TRIM)
        K.box(mb, (0.046, 0.016, 0.062), (x, fy - 0.010, seam - 0.012), mat=TRIM, bevel=0.004)
        K.box(mb, (0.03, 0.004, 0.02), (x, fy - 0.019, seam - 0.024), mat="item_steel_dark")
        K.box(mb, (0.012, 0.012, 0.02), (x + 0.032, fy - 0.006, seam - 0.012), mat=TRIM)
    # Folding grip: two pivot bosses on the body and a moulded bar, hanging slightly forward.
    for x in (-0.075, 0.075):
        K.box(mb, (0.022, 0.02, 0.03), (x, fy - 0.008, seam - 0.018), mat=TRIM)
    grip = [Vector((-0.075, fy - 0.012, seam - 0.02)), Vector((-0.07, fy - 0.03, seam - 0.045)),
            Vector((-0.045, fy - 0.038, seam - 0.056)), Vector((0.045, fy - 0.038, seam - 0.056)),
            Vector((0.07, fy - 0.03, seam - 0.045)), Vector((0.075, fy - 0.012, seam - 0.02))]
    K.tube(mb, grip, (0.009, 0.007), sides=8, mat=TRIM, up=Vector((0, -1, 0)))
    # Program roundel (stencilled) and the riveted asset plate on the lid field.
    mb.push(Matrix.Translation((-0.085, 0.0, top + 0.0007)))
    K.extrude(mb, [(-0.07, -0.07), (0.07, -0.07), (0.07, 0.07), (-0.07, 0.07)], 0.0014, mat="ws_print", side_mat=SHELL,
              uv_rect=_uv("emblem"))
    mb.pop()
    mb.push(Matrix.Translation((0.095, -0.06, top + 0.0007)))
    K.extrude(mb, [(-0.06, -0.03), (0.06, -0.03), (0.06, 0.03), (-0.06, 0.03)], 0.0014, mat="ws_print", side_mat="item_steel_dark",
              uv_rect=_uv("plate"))
    mb.pop()
    # Amber tamper seal: a wire through the right latch's hasp and a numbered tag hanging off it.
    hx, hy, hz = 0.177, fy - 0.006, seam - 0.012
    wire = [Vector((hx, hy + 0.004, hz)), Vector((hx + 0.008, hy - 0.006, hz - 0.006)), Vector((hx + 0.012, hy - 0.012, hz - 0.02)),
            Vector((hx + 0.014, hy - 0.016, hz - 0.034))]
    K.tube(mb, wire, 0.0012, sides=4, mat="item_steel_bright")
    mb.push(Matrix.Translation((hx + 0.014, hy - 0.017, hz - 0.05)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    tag = [(-0.012, -0.017), (0.012, -0.017), (0.012, 0.011), (0.0, 0.018), (-0.012, 0.011)]
    K.extrude(mb, tag, 0.0016, mat="item_plastic_amber", side_mat="item_plastic_amber")
    mb.pop()
    # Scuffing only on the hard edges: the 45-degree shell chamfers would otherwise all wear to bare
    # (white) plastic and the case reads as chipped paint.
    return [mb.build(p["name"], sharp_deg=35)], {"settle": None, "wear_deg": 55.0}


BUILDERS = {"program_cache": program_cache}


def build(params: dict, outputs: list[str]) -> None:
    parts, opts = BUILDERS[params["kind"]](params)
    K.publish(outputs, name=params.get("name", params["kind"]), parts=parts, seed=int(params["seed"]),
              settle_deg=opts.get("settle", 20.0), wear_deg=opts.get("wear_deg", 30.0))
