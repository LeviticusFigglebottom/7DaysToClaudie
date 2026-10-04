"""Texture tasks (numpy procedural PBR textures). See docs/ASSET_PIPELINE.md#textures."""
from __future__ import annotations

from ..core.registry import Task


def tasks() -> list[Task]:
    out: list[Task] = []
    try:
        from . import materials
        out += materials.tasks()
    except ImportError:
        pass
    return out
