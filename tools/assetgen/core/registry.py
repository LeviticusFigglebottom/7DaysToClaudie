"""Asset task model. Every generated file belongs to exactly one Task."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Callable

from .paths import ASSETGEN


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


def blender_sources(module: str) -> list[pathlib.Path]:
    """Source files for a Blender generator: the module + every shared bpy lib file + runner."""
    base = ASSETGEN / "blender"
    files = [base / "runner.py", base / "generators" / f"{module}.py"]
    files += sorted((base / "lib").glob("*.py"))
    return files
