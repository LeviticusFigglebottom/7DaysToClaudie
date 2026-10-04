"""Blender model tasks. Each generator module under blender/generators exposes its own
`TASKS(spec_helper)` description via a sibling catalog in blender_catalogs/."""
from __future__ import annotations

import importlib
import pkgutil

from .core.registry import Task


def tasks() -> list[Task]:
    out: list[Task] = []
    from . import blender_catalogs
    import sys
    import traceback
    for mod in sorted(pkgutil.iter_modules(blender_catalogs.__path__), key=lambda m: m.name):
        try:
            m = importlib.import_module(f"{blender_catalogs.__name__}.{mod.name}")
            out += m.tasks()
        except Exception:  # noqa: BLE001
            print(f"[models] WARNING: skipping blender_catalogs/{mod.name}.py:\n{traceback.format_exc()}", file=sys.stderr)
    return out
