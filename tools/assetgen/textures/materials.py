"""Texture tasks + the material library task.

1. One task per registered texture (textures/gen/*.py).
2. "materials:library" writes game/assets/generated/materials/<id>.tres for every entry in
   game/data/materials/materials.json (ShaderMaterials bound to generated textures). Models name
   their materials M_<id>; the Godot post-import script swaps in these .tres files.
"""
from __future__ import annotations

import json
import pathlib

from ..core.godot_import import uid_for_res_path
from ..core.paths import ROOT, ASSETGEN, DATA, GAME, gen_path
from ..core.registry import Task
from . import registry

MATERIALS_DIR = DATA / "materials"
SHADER_DIR = "res://assets/shaders"


def _run_texture(task: Task) -> None:
    defs = registry.load_all()
    d = defs[task.params["texture"]]
    base = gen_path(f"textures/{d.name}")
    base.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(d.params)
    if d.kind == "array":
        kwargs["slices"] = d.slices
    d.fn(task.params["size"], task.params["seed"], base, **kwargs)


def _texture_tasks() -> list[Task]:
    out = []
    for name, d in sorted(registry.load_all().items()):
        outs, imports = registry.outputs_for(d)
        sources = [d.module_file, ASSETGEN / "textures" / "texlib.py", ASSETGEN / "textures" / "registry.py"]
        sources += [ROOT / s for s in d.sources]
        params = {"texture": name, "size": d.size, "seed": d.seed, "kind": d.kind, "extra": d.params, "slices": d.slices}
        out.append(Task(name=f"tex:{name}", group="textures", outputs=outs, sources=sources, params=params,
                        fn=_run_texture, imports=imports))
    return out


# --- Material library ----------------------------------------------------------------------------

def _tex_res(name: str) -> str:
    return f"res://assets/generated/textures/{name}.png"


def _write_material(mat_id: str, spec: dict, out_path: pathlib.Path, available: set[str]) -> None:
    shader = spec.get("shader", "std_surface")
    ext: list[tuple[str, str, str]] = []  # (type, path, uid or "")
    ext.append(("Shader", f"{SHADER_DIR}/{shader}.gdshader", ""))
    params: list[str] = []
    tex_set = spec.get("textures")
    slots = {}
    if tex_set:
        slots.update({"albedo_tex": f"{tex_set}_albedo", "normal_tex": f"{tex_set}_normal", "orm_tex": f"{tex_set}_orm"})
    for slot, tex_name in spec.get("maps", {}).items():
        slots[slot] = tex_name
    for layer, tex in spec.get("layers", {}).items():
        slots[f"{layer}_albedo_tex"] = f"{tex}_albedo"
        slots[f"{layer}_normal_tex"] = f"{tex}_normal"
        slots[f"{layer}_orm_tex"] = f"{tex}_orm"
    for slot, tex_name in sorted(slots.items()):
        if tex_name not in available:
            continue  # texture not produced by any task (yet): shader default is used
        path = _tex_res(tex_name)
        ext.append(("Texture2D", path, uid_for_res_path(path)))
        params.append(f'shader_parameter/{slot} = ExtResource("{len(ext)}")')
    for k, v in sorted(spec.get("params", {}).items()):
        params.append(f"shader_parameter/{k} = {_gd_value(v)}")
    uid = uid_for_res_path(f"res://assets/generated/materials/{mat_id}.tres")
    lines = [f'[gd_resource type="ShaderMaterial" load_steps={len(ext) + 1} format=3 uid="{uid}"]', ""]
    for i, (typ, path, tuid) in enumerate(ext, start=1):
        u = f' uid="{tuid}"' if tuid else ""
        lines.append(f'[ext_resource type="{typ}"{u} path="{path}" id="{i}"]')
    lines += ["", "[resource]", f'resource_name = "{mat_id}"']
    if "render_priority" in spec:
        lines.append(f"render_priority = {int(spec['render_priority'])}")
    lines.append('shader = ExtResource("1")')
    lines += params
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


def _gd_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(float(v)) if isinstance(v, float) else str(v)
    if isinstance(v, str) and v.startswith("#"):
        h = v.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + ([int(h[6:8], 16) / 255] if len(h) == 8 else [1.0])
        return "Color(%s)" % ", ".join(f"{x:.4f}" for x in c)
    if isinstance(v, list):
        if len(v) == 2:
            return "Vector2(%s)" % ", ".join(str(float(x)) for x in v)
        if len(v) == 3:
            return "Vector3(%s)" % ", ".join(str(float(x)) for x in v)
        if len(v) == 4:
            return "Color(%s)" % ", ".join(str(float(x)) for x in v)
    return json.dumps(v)


def _load_specs() -> dict:
    """Merges every game/data/materials/*.json (one file per asset family; ids must be unique)."""
    merged: dict = {}
    for f in sorted(MATERIALS_DIR.glob("*.json")):
        for mid, m in json.loads(f.read_text()).get("materials", {}).items():
            if mid in merged:
                raise ValueError(f"material id {mid} defined twice ({f.name})")
            merged[mid] = m
    return merged


def _run_materials(task: Task) -> None:
    specs = _load_specs()
    available = set(task.params["available"])
    for mat_id, m in sorted(specs.items()):
        _write_material(mat_id, m, gen_path(f"materials/{mat_id}.tres"), available)


def _material_task(texture_tasks: list[Task]) -> list[Task]:
    specs = _load_specs()
    if not specs:
        return []
    outs = [f"materials/{mid}.tres" for mid in sorted(specs)]
    # Bind only textures some task declares (order-independent, no filesystem checks).
    available = sorted({pathlib.PurePosixPath(o).stem for t in texture_tasks for o in t.outputs})
    params = {"available": available}
    return [Task(name="materials:library", group="materials", outputs=outs,
                 sources=sorted(MATERIALS_DIR.glob("*.json")) + [pathlib.Path(__file__)], params=params, fn=_run_materials,
                 imports={o: {"type": "none"} for o in outs})]


def tasks() -> list[Task]:
    tex = _texture_tasks()
    return tex + _material_task(tex)
