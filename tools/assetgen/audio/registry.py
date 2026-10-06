"""Sound generator registry.

Sound modules live in audio/sounds/*.py and register with @sound(...):

    @sound("sfx/axe_chop_wood", variants=6, seed=101)
    def axe_chop_wood(seed: int, variant: int, sr: int) -> np.ndarray:   # float32 mono [-1, 1]
        ...

The orchestrator writes <id>.wav (variants=1) or <id>_01.wav ... <id>_NN.wav, normalized and
faded by dsp.finish(). Loops (loop=True) are imported with forward looping and must be seamless
(use dsp.make_loop()). Stereo: return shape (N, 2).

A module that imports helpers from another sound module declares it, so editing the helpers
rebuilds its sounds: `@sound(..., sources=["ambience.py"])` (paths relative to the module's folder).
"""
from __future__ import annotations

import importlib
import inspect
import pathlib
import pkgutil
import sys
import traceback
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class SoundDef:
    sound_id: str
    fn: Callable
    module_file: pathlib.Path
    variants: int = 1
    seed: int = 1
    loop: bool = False
    sample_rate: int = 44100
    peak_db: float = -1.0
    params: dict = field(default_factory=dict)
    # Extra input files (helper modules it imports), hashed with module_file.
    sources: list = field(default_factory=list)


REGISTRY: dict[str, SoundDef] = {}
_LOADED = False


def sound(sound_id: str, *, variants: int = 1, seed: int = 1, loop: bool = False, sample_rate: int = 44100,
          peak_db: float = -1.0, sources: list[str] | None = None, **params):
    def deco(fn: Callable) -> Callable:
        if sound_id in REGISTRY:
            raise ValueError(f"sound {sound_id} registered twice")
        module_file = pathlib.Path(inspect.getfile(fn))
        extra = [module_file.parent / s for s in (sources or [])]
        for e in extra:
            if not e.is_file():
                raise ValueError(f"sound {sound_id}: source {e} not found")
        REGISTRY[sound_id] = SoundDef(sound_id, fn, module_file, variants, seed, loop,
                                      sample_rate, peak_db, params, extra)
        return fn
    return deco


def load_all() -> dict[str, SoundDef]:
    global _LOADED
    if _LOADED:
        return REGISTRY
    from . import sounds
    for m in sorted(pkgutil.iter_modules(sounds.__path__), key=lambda m: m.name):
        try:
            importlib.import_module(f"{sounds.__name__}.{m.name}")
        except Exception:  # noqa: BLE001
            from ..core.registry import LOAD_ERRORS
            LOAD_ERRORS.append(f"audio/{m.name}: {traceback.format_exc().strip().splitlines()[-1]}")
            print(f"[audio] ERROR: skipping audio/sounds/{m.name}.py:\n{traceback.format_exc()}", file=sys.stderr)
    _LOADED = True
    return REGISTRY


def outputs_for(d: SoundDef) -> list[str]:
    if d.variants <= 1:
        return [f"audio/{d.sound_id}.wav"]
    return [f"audio/{d.sound_id}_{i:02d}.wav" for i in range(1, d.variants + 1)]
