"""POI kit window glass pieces (docs/POI_KIT.md): sash frames (M_kit_trim) + panes (M_glass) that fill the
CLEAR opening of wall_1m_window / wall_2m_window. Origin = bottom centre of the clear opening on the wall
centre plane: the builder places it at (0, 0, sill) relative to the wall (sill 0.90 / 0.85).

params: size ("window_1m" | "window_2m"), name, seed, broken (bool)
  window_1m: 2-over-2 double-hung (upper sash on the outer track), sash lock on the meeting rail.
  window_2m: twin fixed units with transom lites around a centre mullion.
  broken:    jagged shards left in the sashes (some lites fully out), sashes intact.
The intact piece has a thin box collision; the broken one none (the builder decides passability).
Pane UV0 spans each lite 0..1 so the glass texture's edge grime follows the frame.
"""
from __future__ import annotations

from lib import common
from lib.kit_dims import OPENINGS, sash_layout
from lib.kit_geo import KitMesh, bake_colors, collision_box, export_glb
from lib.kit_parts import glass_pane, glass_shards


def build(params: dict, outputs: list[str]) -> None:
    name = params.get("name", "window_glass")
    size = params.get("size", "window_1m")
    seed = int(params.get("seed", 1))
    broken = bool(params.get("broken", False))
    rng = common.rng(seed)
    lay = sash_layout(size)
    km = KitMesh(name)
    for x0, x1, z0, z1, y0, y1 in lay["frames"]:
        km.part(rng.uniform(0.35, 0.65))
        grain = "z" if (z1 - z0) > (x1 - x0) else "x"
        km.box((x0, y0, z0), (x1, y1, z1), "kit_trim", side="y", grain=grain)
    km.part(0.5)
    for x, z, y in lay["locks"]:
        km.box((x - 0.03, y, z - 0.012), (x + 0.03, y + 0.008, z + 0.006), "metal_steel", side="y")
        km.box((x - 0.012, y + 0.008, z - 0.006), (x + 0.012, y + 0.018, z + 0.004), "metal_steel", side="y")
    tuck = 0.01
    for x0, x1, z0, z1, yc in lay["lites"]:
        km.part(rng.uniform(0.3, 0.7))
        if broken:
            if rng.random() < 0.22:
                continue  # lite completely knocked out
            glass_shards(km, x0, x1, z0, z1, rng, yc=yc, uv_rect=(x0, x1, z0, z1), tuck=tuck)
        else:
            glass_pane(km, x0 - tuck, x1 + tuck, z0 - tuck, z1 + tuck, yc, uv_rect=(x0, x1, z0, z1))
    obj = km.build()
    bake_colors(obj, ground_z=None, samples=12, distance=0.12, strength=0.6, seed=seed)
    out = [obj]
    if not broken:
        w, h, _ = OPENINGS[size]
        out.append(collision_box(f"{name}_col0", (-w / 2, -0.02, 0.0), (w / 2, 0.02, h)))
    export_glb(outputs[0], out)
