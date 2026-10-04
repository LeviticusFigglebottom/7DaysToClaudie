"""Audio tasks (procedural DSP synthesis). See docs/ASSET_PIPELINE.md#audio."""
from __future__ import annotations

from ..core.registry import Task


def tasks() -> list[Task]:
    out: list[Task] = []
    try:
        from . import sounds
        out += sounds.tasks()
    except ImportError:
        pass
    return out
