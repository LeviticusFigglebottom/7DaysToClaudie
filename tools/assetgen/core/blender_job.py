"""Runs batches of Blender tasks: one Blender process per batch (amortizes ~1-2 s startup)."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

from .paths import BLENDER_SCRIPTS, ROOT, gen_path
from .registry import Task


def find_blender(explicit: str | None) -> str:
    if explicit:
        return explicit
    local = ROOT / ".tools" / "blender" / "blender"
    if local.exists():
        return str(local)
    return "blender"


def run_batch(blender: str, tasks: list[Task], log_dir: pathlib.Path) -> dict[str, str]:
    """Returns {task_name: "ok" | error message}."""
    job = {
        "tasks": [
            {"name": t.name, "module": t.blender, "params": t.params, "outputs": [str(gen_path(o)) for o in t.outputs]}
            for t in tasks
        ]
    }
    for t in tasks:
        for o in t.outputs:
            gen_path(o).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hm_blender_") as tmp:
        job_path = pathlib.Path(tmp) / "job.json"
        result_path = pathlib.Path(tmp) / "result.json"
        job["result_path"] = str(result_path)
        job_path.write_text(json.dumps(job))
        cmd = [blender, "--background", "--factory-startup", "-noaudio", "--python-exit-code", "1",
               "--python", str(BLENDER_SCRIPTS / "runner.py"), "--", str(job_path)]
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"blender_{tasks[0].blender}_{abs(hash(tasks[0].name)) % 100000}.log"
        with open(log_file, "w") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
        results: dict[str, str] = {}
        if result_path.exists():
            results = json.loads(result_path.read_text())
        for t in tasks:
            if t.name not in results:
                results[t.name] = f"blender exited {proc.returncode} before finishing (see {log_file})"
        return results
