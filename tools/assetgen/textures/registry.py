"""Texture generator registry.

Generators live in textures/gen/*.py and register with @texture(...):

    @texture("rock_granite", size=1024, seed=11, kind="pbr")
    def rock_granite(size, seed, out):        # out: base path (no suffix), e.g. .../textures/rock_granite
        ... texlib.save_pbr_set(out, albedo, height, rough)

kind:
  "pbr"     -> outputs <name>_albedo.png, <name>_normal.png, <name>_orm.png
  "albedo"  -> <name>_albedo.png only (e.g. decals without normals)
  "rgba"    -> <name>_albedo.png with alpha (foliage cards also get _normal/_orm when kind="pbr_alpha")
  "pbr_alpha" -> albedo with alpha + normal + orm
  "single"  -> exactly <name>.png (masks, LUTs, UI); import kind from `import_kind`
  "array"   -> <name>.png vertical strip of `slices` tiles (Texture2DArray), import as array
"""
from __future__ import annotations

import importlib
import pathlib
import pkgutil
from dataclasses import dataclass, field
from typing import Callable

HERE = pathlib.Path(__file__).resolve().parent


@dataclass
class TexDef:
    name: str
    fn: Callable
    module_file: pathlib.Path
    size: int = 1024
    seed: int = 1
    kind: str = "pbr"
    import_kind: str = "albedo"
    slices: int = 1
    params: dict = field(default_factory=dict)
    #: Extra input files (repo-relative) whose content changes must rebuild this texture,
    #: e.g. data/materials/terrain_layers.json for the terrain arrays.
    sources: list = field(default_factory=list)


REGISTRY: dict[str, TexDef] = {}


def texture(name: str, *, size: int = 1024, seed: int = 1, kind: str = "pbr", import_kind: str = "albedo",
            slices: int = 1, sources: list[str] | None = None, **params):
    def deco(fn: Callable) -> Callable:
        if name in REGISTRY:
            raise ValueError(f"texture {name} registered twice")
        import inspect
        REGISTRY[name] = TexDef(name, fn, pathlib.Path(inspect.getfile(fn)), size, seed, kind, import_kind, slices, params,
                                list(sources or []))
        return fn
    return deco


_LOADED = False


def load_all() -> dict[str, TexDef]:
    """Imports every textures/gen module. A broken module is reported and skipped so one family's
    work-in-progress never blocks the others."""
    global _LOADED
    if _LOADED:
        return REGISTRY
    from . import gen
    import sys
    import traceback
    for m in sorted(pkgutil.iter_modules(gen.__path__), key=lambda m: m.name):
        try:
            importlib.import_module(f"{gen.__name__}.{m.name}")
        except Exception:  # noqa: BLE001
            from ..core.registry import LOAD_ERRORS
            LOAD_ERRORS.append(f"textures/{m.name}: {traceback.format_exc().strip().splitlines()[-1]}")
            print(f"[textures] ERROR: skipping textures/gen/{m.name}.py:\n{traceback.format_exc()}", file=sys.stderr)
    _LOADED = True
    return REGISTRY


def outputs_for(d: TexDef) -> tuple[list[str], dict[str, dict]]:
    base = f"textures/{d.name}"
    if d.kind in ("pbr", "pbr_alpha"):
        outs = [f"{base}_albedo.png", f"{base}_normal.png", f"{base}_orm.png"]
        imports = {outs[0]: {"type": "texture", "kind": "albedo"}, outs[1]: {"type": "texture", "kind": "normal"},
                   outs[2]: {"type": "texture", "kind": "data"}}
    elif d.kind in ("albedo", "rgba"):
        outs = [f"{base}_albedo.png"]
        imports = {outs[0]: {"type": "texture", "kind": "albedo"}}
    elif d.kind == "array":
        outs = [f"{base}.png"]
        imports = {outs[0]: {"type": "texture_array", "slices": d.slices, "kind": d.import_kind}}
    else:
        outs = [f"{base}.png"]
        imports = {outs[0]: {"type": "texture", "kind": d.import_kind}}
    return outs, imports
