"""Asset task model. Every generated file belongs to exactly one Task."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Callable

from .paths import ASSETGEN


#: Catalog / generator modules that failed to import ("family/module: error"). Other families still
#: build, but the run reports these as failures and exits non-zero (no silently missing ids).
LOAD_ERRORS: list[str] = []


@dataclass
class Task:
    """One unit of generation.

    name:     unique id, "<group>:<thing>" (e.g. "tex:bark_grey_fir").
    group:    textures | audio | models | icons | docs | ... (used by --only).
    outputs:  paths relative to game/assets/generated.
    sources:  files whose *content* affects the outputs (the generator module, shared libs, data files).
    params:   JSON-serializable parameters (seeds, sizes, variant knobs). Part of the input hash.
    fn:       python callable(task) for in-process tasks.
    blender:  generator module name under tools/assetgen/blender/generators (Blender tasks, batched).
    imports:  per-output Godot import config: {"textures/x_n.png": {"type": "texture", "kind": "normal"}}.
    """

    name: str
    group: str
    outputs: list[str]
    sources: list[pathlib.Path] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    fn: Callable[["Task"], None] | None = None
    blender: str | None = None
    imports: dict[str, dict] = field(default_factory=dict)

    def out(self, i: int = 0) -> pathlib.Path:
        from .paths import gen_path
        return gen_path(self.outputs[i])


def _lib_imports(path: pathlib.Path, lib_dir: pathlib.Path) -> set[str]:
    """Names of the shared lib modules `path` imports, in any form: `from lib import a, b as c`,
    `from lib.a import x`, `import lib.a`, and (inside lib) `from . import a` / `from .a import x`."""
    import ast
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError):
        return set()
    in_lib = path.parent == lib_dir
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 0 and mod == "lib":
                found.update(a.name for a in node.names)
            elif node.level == 0 and mod.startswith("lib."):
                found.add(mod.split(".")[1])
            elif node.level == 1 and in_lib:
                if mod:
                    found.add(mod.split(".")[0])
                else:
                    found.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("lib."):
                    found.add(a.name.split(".")[1])
    return {m for m in found if (lib_dir / f"{m}.py").exists()}


def blender_sources(module: str) -> list[pathlib.Path]:
    """Source files for a Blender generator: the runner, the module and the shared bpy libs it
    imports, followed transitively. Editing one lib rebuilds only the families that use it
    (every lib used to count for every model: one tweak meant ~45 min of rebuilds, TD-020)."""
    base = ASSETGEN / "blender"
    lib_dir = base / "lib"
    roots = [base / "runner.py", base / "generators" / f"{module}.py"]
    seen: set[str] = set()
    todo: list[str] = []
    for r in roots:
        todo += sorted(_lib_imports(r, lib_dir))
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        todo += sorted(_lib_imports(lib_dir / f"{m}.py", lib_dir) - seen)
    files = roots + [lib_dir / "__init__.py"] + [lib_dir / f"{m}.py" for m in sorted(seen)]
    return [f for f in files if f.exists()]
