"""Writes game/data/materials/props_exterior.json (run with the venv python, not inside Blender):

    .tools/venv/bin/python tools/assetgen/blender/lib/props_ext_matgen.py

The JSON is the committed source of truth; this script only keeps the ~80 related entries
consistent (shared defaults per family, tints in one table). Re-run after editing the tables."""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = ROOT / "game" / "data" / "materials" / "props_exterior.json"

STD = "std_surface"
WHITE = "#ffffff"


def std(tex: str, uv: float = 1.0, **params) -> dict:
    m = {"shader": STD, "textures": tex, "params": {"uv_scale": float(uv), "vertex_ao_strength": 1.0}}
    layers = params.pop("layers", None)
    if layers:
        m["layers"] = layers
    for k, v in params.items():
        m["params"][k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    return m


def painted(tex: str, tint: str, wear: str = "car_rust", uv: float = 1.0, wear_uv: float = 1.2,
            wear_amount: float = 0.65, grime: float = 0.45, **kw) -> dict:
    return std(tex, uv, tint=tint, layers={"wear": wear}, wear_amount=wear_amount, wear_uv_scale=wear_uv,
               grime_amount=grime, grime_color="#29241d", **kw)


def glass(tex: str, uv: float, tint: str, opacity: float, **params) -> dict:
    """Transparent glass / clear plastic (std_glass: same slots as std_surface, plus opacity)."""
    m = std(tex, uv, tint=tint, opacity=opacity, **params)
    m["shader"] = "std_glass"
    return m


def glow(tint: str, translucency: float = 2.0, rough: float = 0.6) -> dict:
    """Light-source surfaces (flames, lamp globes): the foliage shader's BACKLIGHT term lets the
    prop's own OmniLight (PropDef.light) shine through them at night. std_surface has no emission."""
    return {"shader": "foliage", "params": {
        "tint": tint, "alpha_scissor": 0.0, "translucency": float(translucency), "roughness": float(rough),
        "spring_tint": WHITE, "summer_tint": WHITE, "autumn_tint": WHITE, "winter_tint": WHITE,
        "winter_leaf_loss": 0.0, "sway_height": 1000.0, "stiffness": 10.0, "flutter_strength": 0.0, "ao_strength": 0.0}}


MATS: dict[str, dict] = {}

# --- Vehicles ------------------------------------------------------------------------------------
CAR_TINTS = {"red": "#8a2b22", "blue": "#3c5674", "green": "#4b5f4a", "tan": "#b49a74", "white": "#d8d6cf",
             "brown": "#6e4b33", "maroon": "#5e2426"}
for k, t in CAR_TINTS.items():
    MATS[f"car_paint_{k}"] = painted("car_paint", t, uv=1.0, wear_uv=1.2, wear_amount=0.66, grime=0.5,
                                     roughness_mult=1.0)
MATS["car_rust"] = std("car_rust", 1.2, grime_amount=0.3, grime_color="#1c140e")
MATS["car_burnt"] = std("car_rust", 1.0, tint="#9a8a80", layers={"wear": "ash_burnt"}, wear_amount=0.5,
                        wear_uv_scale=1.0, grime_amount=0.55, grime_color="#0e0c0a")
MATS["underbody"] = std("car_rust", 1.5, tint="#5a4c42", grime_amount=0.6, grime_color="#14100c")
MATS["tyre_rubber"] = std("tyre_rubber", 2.5, grime_amount=0.3, grime_color="#141210")
MATS["chrome_pitted"] = std("chrome_pitted", 2.5, layers={"wear": "car_rust"}, wear_amount=0.55, wear_uv_scale=1.5,
                            grime_amount=0.35)
MATS["window_grime"] = std("window_grime", 1.0, grime_amount=0.3, grime_color="#4a463e")
MATS["plastic_black"] = std("plastic_molded", 2.0, tint="#2c2c2b", grime_amount=0.35, roughness_add=0.08)
MATS["car_upholstery"] = std("canvas_tarp", 4.0, tint="#6a5d50", layers={"wear": "plastic_molded"}, wear_amount=0.5,
                             wear_uv_scale=2.0, grime_amount=0.5)
MATS["lens_red"] = glass("plastic_molded", 2.0, "#8c1712", 0.75, roughness_mult=0.45, grime_amount=0.3)
MATS["lens_amber"] = glass("plastic_molded", 2.0, "#b8661c", 0.75, roughness_mult=0.45, grime_amount=0.3)
MATS["lens_clear"] = glass("plastic_molded", 2.0, "#b9bebc", 0.45, roughness_mult=0.35, grime_amount=0.35)

# --- Painted metal (generic street furniture / containers) ---------------------------------------
PAINT = {"red": "#8e2a21", "green": "#3f5a3f", "blue": "#35506e", "black": "#2a2a29", "white": "#d6d3ca",
         "grey": "#77797a", "olive": "#5a5a3c"}
for k, t in PAINT.items():
    MATS[f"paint_{k}"] = painted("car_paint", t, uv=1.0, wear_uv=1.4, wear_amount=0.68, grime=0.5,
                                 roughness_add=0.12)

# --- Wood ----------------------------------------------------------------------------------------
MATS["wood_weathered"] = std("wood_weathered", 1.0, layers={"moss": "moss"}, moss_amount=0.55, moss_uv_scale=1.5,
                             grime_amount=0.45, grime_color="#231d17")
MATS["wood_fresh"] = std("wood_weathered", 1.0, tint="#d9b98e", layers={"moss": "moss"}, moss_amount=0.35,
                         moss_uv_scale=1.5, grime_amount=0.4, grime_color="#2a2118")
MATS["wood_stained"] = std("wood_weathered", 1.0, tint="#a8805e", layers={"moss": "moss"}, moss_amount=0.5,
                           moss_uv_scale=1.5, grime_amount=0.45, grime_color="#231b14")
MATS["wood_creosote"] = std("wood_weathered", 1.0, tint="#6a4f3c", grime_amount=0.5, grime_color="#1b140f")
MATS["wood_charred"] = std("ash_burnt", 1.5, grime_amount=0.3, grime_color="#080707")
MATS["paint_white_wood"] = painted("car_paint", "#e3dfd4", wear="wood_weathered", uv=1.0, wear_uv=1.0,
                                   wear_amount=0.72, grime=0.5, roughness_add=0.25)
MATS["paint_orange_wood"] = painted("car_paint", "#c4612c", wear="wood_weathered", uv=1.0, wear_uv=1.0,
                                    wear_amount=0.7, grime=0.45, roughness_add=0.2)
MATS["plywood_marks"] = std("plywood_marks", 1.0, grime_amount=0.4, grime_color="#2a2219")
MATS["bark_firewood"] = std("ash_burnt", 3.0, tint="#b48c6a", grime_amount=0.35, grime_color="#1a130d",
                            layers={"moss": "moss"}, moss_amount=0.45, moss_uv_scale=2.0)
MATS["plaster_rubble"] = std("concrete_barrier", 2.0, tint="#e4dfd4", grime_amount=0.5, grime_color="#4a443a")
MATS["brick_rubble"] = std("concrete_barrier", 2.0, tint="#b0654c", grime_amount=0.5, grime_color="#2e211a")

# --- Metal, concrete, signs ----------------------------------------------------------------------
MATS["metal_galvanized"] = std("metal_galvanized", 2.0, layers={"wear": "car_rust"}, wear_amount=0.55,
                               wear_uv_scale=1.5, grime_amount=0.45)
MATS["chainlink"] = {"shader": "foliage", "textures": "chainlink", "params": {
    "alpha_scissor": 0.38, "translucency": 0.0, "roughness": 0.9, "normal_strength": 1.0, "ao_strength": 0.4,
    "spring_tint": WHITE, "summer_tint": WHITE, "autumn_tint": WHITE, "winter_tint": WHITE, "winter_leaf_loss": 0.0,
    "sway_height": 1000.0, "stiffness": 10.0, "flutter_strength": 0.0}}
MATS["concrete_barrier"] = std("concrete_barrier", 1.0, grime_amount=0.5, grime_color="#3a362e")
MATS["paint_red_sign"] = std("paint_red_sign", 1.0, grime_amount=0.3)

# --- Clutter -------------------------------------------------------------------------------------
MATS["cardboard"] = std("cardboard", 2.0, grime_amount=0.45, grime_color="#2e2418")
MATS["cardboard_wet"] = std("cardboard", 2.0, tint="#8d7c68", grime_amount=0.65, grime_color="#211a12",
                            roughness_add=0.04)
MATS["packing_tape"] = std("plastic_molded", 3.0, tint="#b48c55", roughness_mult=0.6)
MATS["plastic_bag_black"] = std("plastic_bag", 2.5, tint="#3a3a3d", grime_amount=0.3)
MATS["plastic_bag_green"] = std("plastic_bag", 2.5, tint="#5a7550", grime_amount=0.3)
PLASTIC = {"red": "#94342a", "white": "#d9d6cd", "orange": "#c6652a", "blue": "#3b5f86", "yellow": "#c9a332",
           "grey": "#8a8a86"}
for k, t in PLASTIC.items():
    MATS[f"plastic_{k}"] = std("plastic_molded", 2.0, tint=t, grime_amount=0.6, grime_color="#2b261e")
MATS["glass_green"] = glass("window_grime", 3.0, "#7fae86", 0.5, roughness_mult=0.6, grime_amount=0.3)
MATS["glass_brown"] = glass("window_grime", 3.0, "#b0743c", 0.55, roughness_mult=0.6, grime_amount=0.3)
MATS["glass_clear"] = glass("window_grime", 3.0, "#e2ece8", 0.3, roughness_mult=0.6, grime_amount=0.3)
MATS["can_alu"] = std("chrome_pitted", 3.0, tint="#c9cbcc", grime_amount=0.4)
MATS["can_red"] = painted("car_paint", "#9c2a22", wear="chrome_pitted", uv=3.0, wear_uv=3.0, wear_amount=0.6, grime=0.4)
MATS["can_blue"] = painted("car_paint", "#2f5486", wear="chrome_pitted", uv=3.0, wear_uv=3.0, wear_amount=0.6, grime=0.4)
MATS["can_green"] = painted("car_paint", "#3f6b3a", wear="chrome_pitted", uv=3.0, wear_uv=3.0, wear_amount=0.6, grime=0.4)
MATS["paper_trash"] = std("paper_trash", 1.0, grime_amount=0.4, grime_color="#3a3226")
MATS["paper_pages"] = std("plastic_molded", 3.0, tint="#d9d0ba", roughness_add=0.3, grime_amount=0.5)
BOOK = {"red": "#7a2a24", "blue": "#2f4664", "green": "#3c5a3c", "brown": "#6a4a30"}
for k, t in BOOK.items():
    MATS[f"book_{k}"] = std("canvas_tarp", 5.0, tint=t, grime_amount=0.45)
MATS["rubber_black"] = std("tyre_rubber", 4.0, grime_amount=0.3)

# --- Fabric --------------------------------------------------------------------------------------
CANVAS = {"olive": "#6a6d4c", "khaki": "#9c8b64", "navy": "#33405a", "grey": "#7e7a70", "denim": "#4a5f7d"}
for k, t in CANVAS.items():
    MATS[f"canvas_{k}"] = std("canvas_tarp", 5.0, tint=t, grime_amount=0.5, grime_color="#29241c")
MATS["tarp_blue"] = std("canvas_tarp", 0.7, tint="#3f6c9e", grime_amount=0.55, grime_color="#29241c",
                        roughness_mult=0.8)  # big sheets: low uv scale so the dirt mottling doesn't tile
MATS["flannel_red"] = std("plaid_flannel", 5.0, grime_amount=0.5, grime_color="#211c16")
MATS["flannel_bloody"] = std("plaid_flannel", 5.0, layers={"wear": "blood_dried"}, wear_amount=0.7, wear_uv_scale=2.5,
                             grime_amount=0.55, grime_color="#1d1712")
MATS["denim_bloody"] = std("canvas_tarp", 5.0, tint="#46597a", layers={"wear": "blood_dried"}, wear_amount=0.7,
                           wear_uv_scale=2.5, grime_amount=0.55, grime_color="#1d1712")
MATS["bandage_bloody"] = std("canvas_tarp", 8.0, tint="#dcd6c8", layers={"wear": "blood_dried"}, wear_amount=0.75,
                             wear_uv_scale=3.0, grime_amount=0.4)
MATS["nylon_navy"] = std("sleeping_bag_nylon", 2.0, tint="#2e3b5c", grime_amount=0.5, grime_color="#2a241c")
MATS["ext_mattress_ticking"] = std("ext_mattress_ticking", 2.0, grime_amount=0.55, grime_color="#3a3226")
MATS["foam_yellow"] = std("plastic_molded", 3.0, tint="#c9b26a", roughness_add=0.4, grime_amount=0.5)

# --- Story ---------------------------------------------------------------------------------------
MATS["corpse_skin"] = std("corpse", 2.0, tint="#a39380", grime_amount=0.6, grime_color="#1c1612", roughness_add=-0.05)
MATS["corpse_bone"] = std("concrete_barrier", 3.0, tint="#e2d6b8", grime_amount=0.6, grime_color="#3a2e20",
                          roughness_add=0.02)
MATS["corpse_hair"] = std("canvas_tarp", 12.0, tint="#3e3428", grime_amount=0.3)
MATS["blood_dried"] = std("blood_dried", 2.5, grime_amount=0.2)
MATS["ash_burnt"] = std("ash_burnt", 1.5, grime_amount=0.3, grime_color="#0a0909")
MATS["candle_wax"] = std("plastic_molded", 4.0, tint="#e7dcc0", roughness_add=0.15, grime_amount=0.4)
MATS["flame_glow"] = glow("#ffb04a", translucency=2.0, rough=0.9)
MATS["lamp_glow"] = glow("#efe6cf", translucency=1.6, rough=0.4)
MATS["leather_dark"] = std("plastic_molded", 2.5, tint="#4a3426", roughness_add=0.25, grime_amount=0.5)


def main() -> None:
    doc = {"_doc": "Exterior props family materials (tools/assetgen/blender/lib/props_ext_matgen.py keeps "
                   "this file consistent). Textures from tools/assetgen/textures/gen/props_exterior.py; "
                   "'moss' from rock.py. Vertex colour G drives the 'wear' layer (rust under paint, bare wood "
                   "under paint, dried blood on cloth); B drives moss on wood.",
           "materials": dict(sorted(MATS.items()))}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {OUT} ({len(MATS)} materials)")


if __name__ == "__main__":
    main()
