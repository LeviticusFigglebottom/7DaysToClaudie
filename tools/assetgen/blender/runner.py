"""Executed INSIDE Blender: blender --background --factory-startup --python runner.py -- job.json

Runs each task's generator module (tools/assetgen/blender/generators/<module>.py), which must
define build(params: dict, outputs: list[str]) -> None. The scene is reset between tasks so
generators never see each other's data. Results are written to job["result_path"].
"""
import importlib
import json
import pathlib
import sys
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    job = json.loads(pathlib.Path(argv[0]).read_text())
    results = {}
    for task in job["tasks"]:
        try:
            reset_scene()
            mod = importlib.import_module("generators." + task["module"])
            mod.build(task["params"], task["outputs"])
            missing = [o for o in task["outputs"] if not pathlib.Path(o).exists()]
            results[task["name"]] = "ok" if not missing else "missing outputs: %s" % missing
        except Exception:  # noqa: BLE001 - report every failure back to the orchestrator
            results[task["name"]] = traceback.format_exc()
            print(results[task["name"]], file=sys.stderr)
        print("[blender-runner] %s: %s" % (task["name"], "ok" if results[task["name"]] == "ok" else "FAILED"))
    pathlib.Path(job["result_path"]).write_text(json.dumps(results))
    return 0 if all(v == "ok" for v in results.values()) else 1


if __name__ == "__main__":
    code = main()
    sys.exit(code)
