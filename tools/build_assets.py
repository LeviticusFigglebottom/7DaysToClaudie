#!/usr/bin/env python3
"""Regenerates every procedural asset of the game from source scripts (ADR-0002).

  python tools/build_assets.py                     incremental build of everything
  python tools/build_assets.py --only textures     only some groups (comma separated)
  python tools/build_assets.py --match bark        only tasks whose name contains a substring
  python tools/build_assets.py --force             ignore the manifest, rebuild selected tasks
  python tools/build_assets.py --list              list tasks and whether they are up to date
  python tools/build_assets.py --check-determinism rebuild selected tasks into a scratch dir and
                                                   compare sha256 with the manifest
  python tools/build_assets.py --clean             delete game/assets/generated
  python tools/build_assets.py --adopt             record current input hashes for selected tasks
                                                   whose outputs exist unchanged (no rebuild); only
                                                   after a pipeline change that alters hashes but
                                                   not outputs

Outputs go to game/assets/generated/ (gitignored) together with Godot .import sidecars that pin
deterministic UIDs and import settings. Run from the repo root or anywhere (paths are absolute).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from assetgen.core import godot_import, manifest  # noqa: E402
from assetgen.core.blender_job import find_blender, run_batch  # noqa: E402
from assetgen.core.hashing import hash_inputs  # noqa: E402
from assetgen.core.paths import GEN_ROOT, ROOT, gen_path  # noqa: E402
from assetgen.core.registry import Task  # noqa: E402

BLENDER_BATCH = 6


def _write_imports(task: Task) -> None:
    for rel in task.outputs:
        path = gen_path(rel)
        cfg = dict(task.imports.get(rel, {}))
        kind = cfg.pop("type", None)
        ext = path.suffix.lower()
        if kind == "none":
            continue
        if kind == "texture_array":
            godot_import.texture_array(path, **cfg)
        elif kind == "texture" or (kind is None and ext == ".png"):
            godot_import.texture(path, **cfg)
        elif kind == "wav" or (kind is None and ext == ".wav"):
            godot_import.wav(path, **cfg)
        elif kind == "scene" or (kind is None and ext in (".glb", ".gltf")):
            # Vegetation ships hand-made LODs (and alpha cards that auto-LOD would collapse).
            if rel.startswith(("models/trees/", "models/plants/")):
                cfg.setdefault("lods", False)
            godot_import.scene(path, **cfg)


def _run_python_task(task: Task) -> str:
    try:
        for o in task.outputs:
            gen_path(o).parent.mkdir(parents=True, exist_ok=True)
        assert task.fn is not None
        task.fn(task)
        missing = [o for o in task.outputs if not gen_path(o).exists()]
        return "ok" if not missing else f"missing outputs: {missing}"
    except Exception:  # noqa: BLE001
        return traceback.format_exc()


def _select(tasks: list[Task], only: str | None, match: str | None) -> list[Task]:
    out = tasks
    if only:
        groups = {g.strip() for g in only.split(",")}
        out = [t for t in out if t.group in groups]
    if match:
        out = [t for t in out if match in t.name]
    return out


def build(tasks: list[Task], *, force: bool, jobs: int, blender: str, quiet: bool = False) -> int:
    data = manifest.load()
    todo: list[tuple[Task, str]] = []
    for t in tasks:
        h = hash_inputs(t.sources, t.params)
        if force or not manifest.is_current(data, t.name, h, t.outputs):
            todo.append((t, h))
    if not todo:
        if not quiet:
            print(f"[assets] all {len(tasks)} selected tasks up to date")
        return 0
    print(f"[assets] building {len(todo)} of {len(tasks)} tasks with {jobs} jobs ...")
    start = time.time()
    failures: dict[str, str] = {}
    done = 0
    py = [(t, h) for t, h in todo if t.fn is not None]
    bl = [(t, h) for t, h in todo if t.blender is not None]
    hashes = {t.name: h for t, h in todo}
    last_save = [time.time()]

    def finish(task: Task, result: str) -> None:
        nonlocal done
        done += 1
        if result == "ok":
            _write_imports(task)
            manifest.record(data, task.name, hashes[task.name], task.outputs)
            print(f"  [{done}/{len(todo)}] ok   {task.name}")
        else:
            failures[task.name] = result
            print(f"  [{done}/{len(todo)}] FAIL {task.name}\n{result}")

    with cf.ProcessPoolExecutor(max_workers=jobs) as pool, cf.ThreadPoolExecutor(max_workers=max(1, jobs // 2)) as bpool:
        futures: dict[cf.Future, object] = {}
        for t, _ in py:
            futures[pool.submit(_run_python_task, t)] = t
        # Batch Blender tasks per generator module.
        by_module: dict[str, list[Task]] = {}
        for t, _ in bl:
            by_module.setdefault(t.blender or "", []).append(t)
        log_dir = ROOT / "build" / "logs"
        for mod, ts in sorted(by_module.items()):
            for i in range(0, len(ts), BLENDER_BATCH):
                batch = ts[i:i + BLENDER_BATCH]
                futures[bpool.submit(run_batch, blender, batch, log_dir)] = batch
        for fut in cf.as_completed(futures):
            owner = futures[fut]
            try:
                res = fut.result()
            except Exception:  # noqa: BLE001
                res = traceback.format_exc()
            if isinstance(owner, list):
                for t in owner:
                    finish(t, res.get(t.name, "no result") if isinstance(res, dict) else str(res))
            else:
                finish(owner, res)  # type: ignore[arg-type]
            # Save often so an interrupted build keeps what it finished.
            if time.time() - last_save[0] > 5.0:
                manifest.save(data)
                last_save[0] = time.time()
    manifest.save(data)
    print(f"[assets] {len(todo) - len(failures)} built, {len(failures)} failed in {time.time() - start:.1f}s")
    from assetgen.core.registry import LOAD_ERRORS
    for e in LOAD_ERRORS:
        print(f"[assets] FAIL module did not load (its assets were skipped): {e}")
    return 1 if failures or LOAD_ERRORS else 0


def check_determinism(tasks: list[Task], jobs: int, blender: str) -> int:
    ref = manifest.load()["tasks"]
    with tempfile.TemporaryDirectory(prefix="hm_det_") as tmp:
        env = dict(os.environ, HM_GEN_ROOT=tmp)
        names = ",".join(t.name for t in tasks)
        cmd = [sys.executable, __file__, "--force", "--names", names, "--jobs", str(jobs), "--blender", blender]
        if subprocess.run(cmd, env=env).returncode != 0:
            print("[determinism] rebuild failed")
            return 1
        import json
        fresh = json.loads((pathlib.Path(tmp) / "manifest.json").read_text())["tasks"]
    bad = 0
    for t in tasks:
        a = ref.get(t.name, {}).get("outputs", {})
        b = fresh.get(t.name, {}).get("outputs", {})
        for o in t.outputs:
            if a.get(o) != b.get(o):
                bad += 1
                print(f"[determinism] MISMATCH {t.name}: {o}")
    print(f"[determinism] {len(tasks)} tasks checked, {bad} mismatching outputs")
    return 1 if bad else 0


def adopt(tasks: list) -> int:
    """Re-keys the manifest to the current input hashes without rebuilding. Only tasks whose
    outputs all exist and still match the sha256 recorded at their last build are adopted."""
    from assetgen.core.hashing import file_sha256
    from assetgen.core.paths import gen_path
    data = manifest.load()
    adopted = skipped = 0
    for t in tasks:
        entry = data["tasks"].get(t.name)
        h = hash_inputs(t.sources, t.params)
        if entry is None or entry.get("hash") == h:
            continue
        recorded: dict = entry.get("outputs", {})
        if all(gen_path(o).exists() and recorded.get(o) == file_sha256(gen_path(o)) for o in t.outputs):
            entry["hash"] = h
            manifest.mark(data, t.name)
            adopted += 1
        else:
            skipped += 1
    manifest.save(data)
    print(f"[assets] adopted {adopted} task hashes, {skipped} left to rebuild")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated groups")
    ap.add_argument("--match", help="substring of task names")
    ap.add_argument("--names", help=argparse.SUPPRESS)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--check-determinism", action="store_true")
    ap.add_argument("--adopt", action="store_true")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--blender", default=None)
    args = ap.parse_args()

    if args.clean:
        shutil.rmtree(GEN_ROOT, ignore_errors=True)
        print(f"[assets] removed {GEN_ROOT}")
        return 0
    from assetgen.catalog import all_tasks
    tasks = all_tasks()
    if args.names:
        wanted = set(args.names.split(","))
        tasks = [t for t in tasks if t.name in wanted]
    tasks = _select(tasks, args.only, args.match)
    blender = find_blender(args.blender)
    if args.list:
        data = manifest.load()
        for t in tasks:
            cur = manifest.is_current(data, t.name, hash_inputs(t.sources, t.params), t.outputs)
            print(f"{'ok  ' if cur else 'todo'} {t.group:10s} {t.name}  -> {', '.join(t.outputs[:3])}{' ...' if len(t.outputs) > 3 else ''}")
        print(f"{len(tasks)} tasks")
        return 0
    if args.check_determinism:
        return check_determinism(tasks, args.jobs, blender)
    if args.adopt:
        return adopt(tasks)
    return build(tasks, force=args.force, jobs=args.jobs, blender=blender)


if __name__ == "__main__":
    sys.exit(main())
