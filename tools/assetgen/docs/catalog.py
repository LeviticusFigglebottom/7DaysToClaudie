"""Documentation images generated from data (e.g. the main-map region sketch)."""
from __future__ import annotations

from ..core.registry import Task


def tasks() -> list[Task]:
    out: list[Task] = []
    try:
        from . import map_sketch
        out += map_sketch.tasks()
    except ImportError:
        pass
    return out
