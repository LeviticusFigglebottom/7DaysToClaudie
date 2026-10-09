"""Developer helper (ADR-0060): the first-person arms posed and rendered from the player's camera in
Blender alone, in a minute or two instead of a full asset build and a Godot import. For iterating
on the hold poses (viewmodel.json), the solver (lib/char_fp.py) and the hand mesh.

  .tools/blender/blender -b --factory-startup -noaudio --python tools/assetgen/blender/fp_dev_render.py -- \\
      <out_dir> <shot>[,<shot>...] [h=0.0014] [samples=16] [size=960x540] [crop=x0,y0,x1,y1] [cache=arms.blend]

A shot is `action` (an idle, frame 0) or `action@frame`, e.g. fp_empty,fp_lighter,fp_chop@12. Items
are stand-ins (a lighter body, a handle cylinder) placed on the socket the way ViewModelHolds
places the real model; the real look is fp_preview.gd's (Godot) once assets are built."""
from __future__ import annotations

import math
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402
from mathutils import Euler, Matrix  # noqa: E402

from lib import char_fp as F  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = pathlib.Path(argv[0])
shots = [s for s in argv[1].split(",") if s]
opts = dict(a.split("=", 1) for a in argv[2:])
h = float(opts.get("h", 0.0014))
samples = int(opts.get("samples", 16))
w, ht = (int(x) for x in opts.get("size", "960x540").split("x"))
out_dir.mkdir(parents=True, exist_ok=True)

wanted = {s.split("@")[0] for s in shots}
params = {"name": "fp_arms", "seed": 808, "height": 1.78, "h": h}
# The meshed, skinned arms are cached (cache=<file.blend>, rebuilt when missing): a pose change
# only re-bakes its actions, in seconds.
cache = pathlib.Path(opts["cache"]) if "cache" in opts else None
if cache is not None and cache.exists():
    bpy.ops.wm.open_mainfile(filepath=str(cache))
else:
    _all = F.fp_actions
    F.fp_actions = lambda cfg: _all(cfg)[:1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from generators import character_fp_arms as G  # noqa: E402
    G.build(params, [str(out_dir / "_arms.glb")])
    F.fp_actions = _all
    if cache is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(cache))
scene = bpy.context.scene
arm = next(o for o in scene.objects if o.type == "ARMATURE")
if arm.animation_data is None:
    arm.animation_data_create()
cfg = F.load_config()
from lib import char_anim  # noqa: E402
sk = F.FPSkeleton(F.fp_joints(params), params, bones=F.FP_BONES)
rig = F.FPRig(sk)
solver = F.PoseSolver(rig, cfg.get("wrist"))
print(f"FPDEV loaded in {time.process_time():.0f} s cpu")
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
for name, n, loop, frames in F.fp_actions(cfg):
    if name not in wanted:
        continue
    solver.reset()
    char_anim.write_action(arm, sk, name, [rig.evaluate(solver.solve(hands)) for hands in frames])
    print(f"FPDEV {name}: turned R{solver.clamped.get('R', 0):.0f} L{solver.clamped.get('L', 0):.0f} deg, "
          f"moved R{solver.moved.get('R', 0) * 100:.0f} L{solver.moved.get('L', 0) * 100:.0f} cm")

print(f"FPDEV baked in {time.process_time():.0f} s cpu")
# Materials: skin, sleeve, nails, tether, plain enough to judge shape and silhouette.
COLS = {"fp_skin": (0.62, 0.42, 0.33, 1), "fp_sleeve": (0.55, 0.28, 0.08, 1), "fp_nail": (0.75, 0.6, 0.55, 1)}
for m in bpy.data.materials:
    m.use_nodes = True
    bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        continue
    for ln in list(m.node_tree.links):
        if ln.to_node == bsdf:
            m.node_tree.links.remove(ln)
    col = COLS.get(m.name.split(".")[0].removeprefix("M_"), (0.12, 0.12, 0.13, 1))
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = 0.55
    if m.name.removeprefix("M_").startswith("fp_skin"):
        bsdf.inputs["Subsurface Weight"].default_value = 0.25
        bsdf.inputs["Subsurface Radius"].default_value = (0.01, 0.004, 0.002)


def _stand_in(hold: dict, sd: str):
    """A stand-in item on the hand's socket: the lighter's body, or a 3.4 cm handle."""
    sock = bpy.data.objects.get(f"socket_hand.{sd}")
    item = hold.get("item", {})
    lighter = hold.get("_doc", "").lower().startswith("lighter")
    if lighter:
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        o = bpy.context.object
        o.scale = (0.0246, 0.0118, 0.082)   # Godot socket X (knuckles), Z, Y (handle) -> Blender x, -y?, z
        o.location = (0.0, 0.0, 0.041 - 0.033)
    else:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.017, depth=0.30)
        o = bpy.context.object
    mat = bpy.data.materials.new("standin")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.7, 0.08, 0.05, 1) if lighter else (0.35, 0.25, 0.15, 1)
    o.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=True, scale=True)
    # The socket's axes (Blender): x knuckles, z the handle; Godot's socket +Y is Blender's +z.
    # The hold's item rot (Godot YXZ Euler, socket space) turns the item in the fist.
    r = [math.radians(float(a)) for a in item.get("rot", [0, 0, 0])]
    p = item.get("pos", [0, 0, 0])
    g2s = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))   # Godot socket (x, y, z) -> Blender socket (x, z, -y)
    rg = Euler((r[0], r[1], r[2]), "YXZ").to_matrix()
    rb = g2s @ rg @ g2s.inverted()
    o.matrix_world = sock.matrix_world @ Matrix.Translation(g2s @ __import__("mathutils").Vector(p)) @ rb.to_4x4()
    o.parent = sock
    o.matrix_parent_inverse = sock.matrix_world.inverted()
    return o


cam_data = bpy.data.cameras.new("cam")
cam_data.sensor_fit = "VERTICAL"
cam_data.angle = math.radians(float(cfg.get("fov", 58.0)))
cam_data.clip_start = 0.01
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.rotation_euler = (math.radians(90), 0.0, math.radians(180))   # looking -Y, up +Z
scene.camera = cam
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(150))
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.55, 0.7, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
scene.world = world
scene.render.engine = "CYCLES"
scene.cycles.samples = samples
scene.cycles.device = "CPU"
scene.render.resolution_x, scene.render.resolution_y = w, ht
scene.render.film_transparent = False
if "crop" in opts:
    # crop=x0,y0,x1,y1 in fractions of the frame from the top left: a close-up at full resolution.
    x0, y0, x1, y1 = (float(v) for v in opts["crop"].split(","))
    scene.render.use_border = scene.render.use_crop_to_border = True
    scene.render.border_min_x, scene.render.border_max_x = x0, x1
    scene.render.border_min_y, scene.render.border_max_y = 1.0 - y1, 1.0 - y0

for shot in shots:
    name, _, fr = shot.partition("@")
    act = bpy.data.actions.get(name)
    if act is None:
        print("FPDEV missing action", name)
        continue
    arm.animation_data.action = act
    scene.frame_set(int(fr or 0))
    cls = name[3:]
    hold = None
    for group in ("attacks", "uses"):
        a = cfg.get(group, {}).get(cls)
        if a:
            hold = cfg["holds"][a["hold"]]
    if hold is None:
        hold = cfg["holds"].get(cls.replace("_guard", "").replace("_tether", ""), {})
    items = []
    if hold.get("item") is not None or hold.get("_doc", "").lower().startswith("lighter"):
        items.append(_stand_in(hold, str(hold.get("hand", "R"))))
    bpy.context.view_layer.update()
    scene.render.filepath = str(out_dir / f"{name}{'_' + fr if fr else ''}.png")
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"FPDEV wrote {scene.render.filepath} in {time.time() - t0:.0f} s")
    for o in items:
        bpy.data.objects.remove(o, do_unlink=True)
