"""Blender model tasks. Each generator module under blender/generators exposes its own
`TASKS(spec_helper)` description via a sibling catalog in blender_catalogs/."""
from __future__ import annotations

import importlib
import pkgutil

from .core.registry import Task


def tasks() -> list[Task]:
    out: list[Task] = []
    from . import blender_catalogs
    for mod in sorted(pkgutil.iter_modules(blender_catalogs.__path__), key=lambda m: m.name):
        m = importlib.import_module(f"{blender_catalogs.__name__}.{mod.name}")
        out += m.tasks()
    return out
