"""Developer helper: build one generator task and render a preview PNG (no export side effects
beyond the given outputs).

  blender -b --factory-startup --python tools/assetgen/blender/dev_preview.py -- \
      <module> '<params-json>' <out.png> [output.glb ...]

Imports generators.<module>, calls build(params, outputs) with temp outputs, then renders every
mesh in the scene with lib.preview (Cycles CPU)."""
import importlib
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402

from lib.preview import render_preview  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
module, params, out_png = argv[0], json.loads(argv[1]), argv[2]
outs = argv[3:]
bpy.ops.wm.read_factory_settings(use_empty=True)
mod = importlib.import_module("generators." + module)
tmp = tempfile.mkdtemp(prefix="hm_prev_")
if not outs:
    outs = [str(pathlib.Path(tmp) / f"out_{i}.glb") for i in range(int(params.get("_outputs", 1)))]
mod.build(params, outs)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.name.endswith("colonly") and not o.hide_render]
render_preview(objs, out_png, samples=int(params.get("_samples", 24)))
print("PREVIEW_WRITTEN", out_png)
