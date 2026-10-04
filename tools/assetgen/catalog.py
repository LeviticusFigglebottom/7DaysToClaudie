"""Collects every asset Task from the generator packages. Add new packages here."""
from __future__ import annotations

from .core.registry import Task


def all_tasks() -> list[Task]:
    from .audio import catalog as audio
    from .docs import catalog as docs
    from .textures import catalog as textures
    from . import models_catalog

    tasks: list[Task] = []
    tasks += textures.tasks()
    tasks += audio.tasks()
    tasks += models_catalog.tasks()
    tasks += docs.tasks()
    names: set[str] = set()
    outs: dict[str, str] = {}
    for t in tasks:
        if t.name in names:
            raise ValueError(f"duplicate task name {t.name}")
        names.add(t.name)
        for o in t.outputs:
            if o in outs:
                raise ValueError(f"output {o} produced by both {outs[o]} and {t.name}")
            outs[o] = t.name
    return tasks
