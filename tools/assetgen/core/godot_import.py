"""Writes Godot .import sidecars for generated assets.

Why: (1) deterministic resource UIDs (derived from the res:// path) so scenes referencing generated
assets never churn between machines or rebuilds; (2) correct import settings (VRAM compression,
normal maps, audio loops, glTF post-import script) without opening the editor.
Godot fills in all remaining parameters on first import and keeps the UID we wrote.
"""
from __future__ import annotations

import pathlib

from .hashing import fnv1a64
from .paths import res_path

# Godot ResourceUID text alphabet: 'a'..'y' (25) then '0'..'8' (9) -> base 34.
_CHAR_COUNT = 25
_BASE = 34


def uid_for_res_path(res: str) -> str:
    n = fnv1a64("uid:" + res) & 0x7FFFFFFFFFFFFFFF
    out = ""
    while True:
        c = n % _BASE
        out = (chr(ord("a") + c) if c < _CHAR_COUNT else chr(ord("0") + c - _CHAR_COUNT)) + out
        n //= _BASE
        if n == 0:
            break
    return "uid://" + out


def _write(path: pathlib.Path, importer: str, rtype: str, params: dict) -> None:
    res = res_path(path)
    lines = ["[remap]", "", f'importer="{importer}"', f'type="{rtype}"', f'uid="{uid_for_res_path(res)}"', "", "[params]", ""]
    for k, v in params.items():
        lines.append(f"{k}={_fmt(v)}")
    pathlib.Path(str(path) + ".import").write_text("\n".join(lines) + "\n")


def _fmt(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v if v.startswith("{") else f'"{v}"'
    return str(v)


def texture(path: pathlib.Path, *, kind: str = "albedo", mipmaps: bool = True, size_limit: int = 0) -> None:
    """kind: albedo | normal | data (roughness/AO, linear) | mask (up to four unrelated linear channels:
    BC7, because S3TC blends RGB channels within a block) | ui (no compression, no mips)."""
    if kind == "ui":
        params = {"compress/mode": 0, "mipmaps/generate": False}
    else:
        params = {
            "compress/mode": 2,  # VRAM compressed (BPTC/S3TC on desktop)
            "compress/high_quality": kind in ("normal", "mask"),
            "compress/normal_map": 1 if kind == "normal" else 2,  # 2 = disabled
            "mipmaps/generate": mipmaps,
            "process/size_limit": size_limit,
            "detect_3d/compress_to": 0,
        }
    _write(path, "texture", "CompressedTexture2D", params)


def texture_array(path: pathlib.Path, slices: int, *, kind: str = "albedo") -> None:
    """Vertical strip of `slices` equal tiles -> Texture2DArray."""
    params = {
        "compress/mode": 2,
        "compress/high_quality": kind == "normal",
        "compress/channel_pack": 0,
        "mipmaps/generate": True,
        "slices/horizontal": 1,
        "slices/vertical": slices,
    }
    _write(path, "2d_array_texture", "CompressedTexture2DArray", params)


def wav(path: pathlib.Path, *, loop: bool = False, compress: str = "qoa") -> None:
    params = {
        "edit/loop_mode": 2 if loop else 0,  # 2 = forward loop
        "edit/trim": False,
        "edit/normalize": False,
        "compress/mode": {"none": 0, "adpcm": 1, "qoa": 2}[compress],
    }
    _write(path, "wav", "AudioStreamWAV", params)


def scene(path: pathlib.Path, *, lods: bool = True, shadow_meshes: bool = True, animation: bool = False,
          post_import: str = "res://src/tools/import/generated_scene_post_import.gd") -> None:
    params = {
        "nodes/root_type": "",
        "nodes/root_name": "",
        "nodes/apply_root_scale": True,
        "nodes/root_scale": 1.0,
        "meshes/ensure_tangents": True,
        "meshes/generate_lods": lods,
        "meshes/create_shadow_meshes": shadow_meshes,
        "meshes/light_baking": 1,
        "skins/use_named_skins": True,
        "animation/import": animation,
        "animation/fps": 30,
        "import_script/path": post_import,
        "gltf/naming_version": 2,
        "gltf/embedded_image_handling": 1,
    }
    _write(path, "scene", "PackedScene", params)
