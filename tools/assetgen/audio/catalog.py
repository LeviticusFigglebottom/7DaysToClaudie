"""Audio tasks: one task per registered sound id (all its variants)."""
from __future__ import annotations

from ..core.paths import ASSETGEN, gen_path
from ..core.registry import Task
from . import registry


def _run_sound(task: Task) -> None:
    from . import dsp
    d = registry.load_all()[task.params["sound"]]
    for i, rel in enumerate(task.outputs):
        sig = d.fn(d.seed * 1000 + i, i, d.sample_rate, **d.params)
        dsp.write_wav(gen_path(rel), dsp.finish(sig, d.sample_rate, peak_db=d.peak_db, loop=d.loop), d.sample_rate)


def tasks() -> list[Task]:
    out: list[Task] = []
    defs = registry.load_all()
    dsp_file = ASSETGEN / "audio" / "dsp.py"
    for sid, d in sorted(defs.items()):
        outs = registry.outputs_for(d)
        out.append(Task(name=f"snd:{sid}", group="audio", outputs=outs,
                        sources=[d.module_file, dsp_file, ASSETGEN / "audio" / "registry.py", *d.sources],
                        params={"sound": sid, "variants": d.variants, "seed": d.seed, "loop": d.loop, "sr": d.sample_rate, "extra": d.params},
                        fn=_run_sound, imports={o: {"type": "wav", "loop": d.loop} for o in outs}))
    return out
