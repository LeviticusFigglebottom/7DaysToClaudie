extends Node
## Runner for wrist_audit.gd (player report 5: the hand twitched every other second with the wrist
## raised, and the tether couldn't be read while running). A new game on the main map, the tether
## raised the way T raises it, then:
##  * every movement state (idle, walk, sprint, crouch, crouch-walk, jump, swim, climb) and every
##    hold class, a frame each (rendered runs) -> <out>/<res>_<state>.png;
##  * --steady: per hold class, both hands sampled in the camera's space every frame for 5 s with
##    the wrist up; the largest single-frame turn against the median step (a periodic snap shows
##    as a spike). WRIST_STEADY lines; exits 1 if a hand jumps more than STEADY_MAX_DEG.
## Not a test of the game's rules: it records what a player sees.

const STEADY_MAX_DEG: float = 1.0
const MOVES: Array[String] = ["idle", "walk", "sprint", "crouch", "crouch_walk", "jump", "swim", "climb"]

var _out: String = "res://../build/wrist_audit"
var _tag: String = ""
var game: Node
var w: GameWorld
var p: Player
var ui: GameUI
var _fails: int = 0
## The QA ladder room, removed after the climb.
var _ladder_room: Node3D = null


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.find("--out") >= 0 and args.find("--out") + 1 < args.size():
		_out = args[args.find("--out") + 1]
	_tag = "%dx%d" % [get_viewport().get_visible_rect().size.x, get_viewport().get_visible_rect().size.y]
	_run.call_deferred()


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


## A frame of what the player sees: the world drawn again for it (see _cheap).
func _snap(name_: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	_cheap(false)
	await _frames(3)
	var img: Image = get_viewport().get_texture().get_image()
	_cheap(true)
	# Tagged by the frame's own pixels (the viewport's visible rect is the 1920x1080 stretch base).
	_tag = "%dx%d" % [img.get_width(), img.get_height()]
	img.save_png(ProjectSettings.globalize_path(_out).path_join("%s_%s.png" % [_tag, name_]))
	print("WRIST_AUDIT frame %s_%s" % [_tag, name_])


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out))
	game = get_node("/root/Game")
	var opts: Dictionary = {"game_mode": "survival", "seed": 4471, "skip_intro": true, "slot": "qa_wrist"}
	# A small random world of open meadow and lakes, no towns or places: software Vulkan takes ~30
	# min to raise the main map's towns and ~40 s to draw a frame of its forest; the wrist and its
	# screen draw the same either way. --main-map for the real one.
	if not OS.get_cmdline_user_args().has("--main-map"):
		# --towns: the default towns, whose buildings off the minimap once heaped up over the readouts.
		var towns: String = "town_density=%s" % ("2" if OS.get_cmdline_user_args().has("--towns") else "0")
		var wa := PackedStringArray(["--world-seed", "7", "--world-set", "size=2", "--world-set", towns,
			"--world-set", "wilderness=0", "--world-set", "lakes=many", "--world-set", "conifer=0", "--world-set", "birch=0",
			"--world-set", "burn=0", "--world-set", "fen=0"])
		opts["world_gen"] = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", wa, 7)
		opts["stream"] = true
	game.call(&"start_new_game", opts)
	# --load-wait <s>: under software Vulkan the drop site's town alone takes ~20 min to raise.
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var wait_s: float = float(args[args.find("--load-wait") + 1]) if args.find("--load-wait") >= 0 and args.find("--load-wait") + 1 < args.size() else 2400.0
	var end: int = Time.get_ticks_msec() + int(wait_s * 1000.0)
	while Time.get_ticks_msec() < end and not (game.get(&"world") != null and bool(game.world.is_ready)):
		await get_tree().process_frame
	if game.get(&"world") == null or not bool(game.world.is_ready):
		print("WRIST_AUDIT the world never became ready")
		get_tree().quit(1)
		return
	w = game.world
	p = w.player
	ui = w.ui
	p.god_mode = true
	p.state.tutorial.finish_all()
	_cheap(true)
	await _frames(15)
	if OS.get_cmdline_user_args().has("--steady"):
		await _steady_all()
	elif OS.get_cmdline_user_args().has("--markers"):
		await _markers()
	elif OS.get_cmdline_user_args().has("--hands"):
		await _hands()
	else:
		# --moves / --classes: one half of the run (both by default).
		var only_c: bool = OS.get_cmdline_user_args().has("--classes")
		var only_m: bool = OS.get_cmdline_user_args().has("--moves")
		if not only_c:
			await _moves()
		if not only_m:
			await _classes()
	print("WRIST_AUDIT done: %d failing" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Between frames only the arms are drawn, without the sun's shadows: the game steps the same
## (physics, animation, the tether), but software Vulkan drawing the world takes ~12 s a frame
## and the waits between frames ran to hours.
var _cam_mask: int = -1


func _cheap(on: bool) -> void:
	var cam: Camera3D = get_viewport().get_camera_3d()
	if cam == null or DisplayServer.get_name() == "headless":
		return
	if on:
		if _cam_mask < 0:
			_cam_mask = cam.cull_mask
		cam.cull_mask = FpMaterials.LAYER
	elif _cam_mask >= 0:
		cam.cull_mask = _cam_mask
	if w != null and w.env != null and w.env.sun != null:
		w.env.sun.shadow_enabled = not on


# --- The tether up, the way T raises it -------------------------------------------------------

func _raise(up: bool) -> void:
	ui.call(&"_ensure_tether")
	var t: Tether = ui.get(&"tether") as Tether
	if t != null and t.raised != up:
		t.toggle()
		ui.call(&"_raise_wrist", t.raised)
	await _frames(15)


func _hold(item: StringName) -> void:
	_release_all()
	var ps: PlayerState = p.state
	# The last one back out first: one of everything in turn filled the bag past its bulk, and an
	# item that didn't fit left the hands empty (the molotov and chime frames of the hands sheet).
	var last: StringName = ps.toolbelt[0]
	if last != &"" and last != item:
		ps.inventory.remove(last, ps.inventory.count_of(last))
	if item != &"":
		if ps.inventory.add_item(item, 1) > 0 and not ps.inventory.has(item):
			print("WRIST_AUDIT FAIL %s didn't fit in the bag" % item)
			_fails += 1
	ps.toolbelt[0] = item
	p.equipment.select_slot(0)
	await _frames(10)


## One item for every hold class the arms know (empty hands first).
func _class_items() -> Dictionary:
	var out: Dictionary = {&"empty": &""}
	var cfg: Dictionary = ViewModelHolds.config()
	for def: ItemDef in Content.all(&"item"):
		var cls: StringName = ViewModelHolds.hold_class(def, cfg)
		if cls != &"" and not out.has(cls):
			out[cls] = def.id
	return out


func _release_all() -> void:
	for a: StringName in [&"move_forward", &"sprint", &"crouch", &"jump"]:
		Input.action_release(a)


func _tap(action: StringName) -> void:
	Input.action_press(action)
	await _frames(2)
	Input.action_release(action)


# --- Movement states --------------------------------------------------------------------------

func _moves() -> void:
	var start: Vector3 = w.drop_site() + Vector3(4.0, 0.0, 4.0)
	for m: String in MOVES:
		await _hold(&"stone_axe")
		await _place_for(m, start)
		await _raise(true)
		match m:
			"walk":
				Input.action_press(&"move_forward")
				await _frames(20)
			"sprint":
				Input.action_press(&"move_forward")
				Input.action_press(&"sprint")
				await _frames(25)
			"crouch":
				await _tap(&"crouch")
				await _frames(15)
			"crouch_walk":
				await _tap(&"crouch")
				Input.action_press(&"move_forward")
				await _frames(20)
			"jump":
				Input.action_press(&"move_forward")
				await _frames(10)
				await _tap(&"jump")
				await _frames(5)
			"swim":
				Input.action_press(&"move_forward")
				await _frames(20)
			"climb":
				Input.action_press(&"move_forward")
				await _frames(45)
			_:
				await _frames(15)
		var vm: ViewModel = p.equipment.viewmodel
		print("WRIST_AUDIT move %s: raised %s reading %.2f sprinting %s crouching %s on_floor %s water %.2f climbing %s | rig %s m %s deg" % [m,
			vm != null and vm.tether_raised(), vm.tether.progress() if vm != null else 0.0, p.sprinting, p.crouching,
			p.is_on_floor(), p.in_water_depth, p.is_climbing(), vm.motion.rig_position() if vm != null else Vector3.ZERO,
			vm.motion.rig_rotation_deg() if vm != null else Vector3.ZERO])
		if m == "climb":
			# By design: both hands are on the rails (T says so; ADR-0051 climbing).
			print("WRIST_AUDIT move climb: the wrist is down on the ladder (both hands on the rails), as designed")
		elif vm == null or not vm.tether_raised():
			_fails += 1
			print("WRIST_AUDIT FAIL move %s: the wrist went down" % m)
		await _snap("move_" + m)
		_release_all()
		if p.is_climbing():
			# Jump lets go of the ladder (a teleport alone left the player holding it).
			await _tap(&"jump")
			await _frames(10)
		if _ladder_room != null:
			_ladder_room.queue_free()
			_ladder_room = null
		if p.crouching:
			await _tap(&"crouch")
		await _raise(false)


## Puts the player where the state can happen: open ground, a lake, the foot of a ladder.
func _place_for(m: String, start: Vector3) -> void:
	var at: Vector3 = start
	if m == "swim":
		at = _lake_spot(start)
	elif m == "climb":
		at = _ladder_foot(start + Vector3(0.0, 0.0, -14.0))
	at.y = maxf(at.y, w.height_at(at.x, at.z)) + 0.05
	p.global_position = at
	p.velocity = Vector3.ZERO
	p.rotation.y = 0.0
	await _frames(20)


func _lake_spot(near: Vector3) -> Vector3:
	var water: Node = w.water
	var best := Vector3.INF
	for l: Dictionary in (water.get(&"_lakes") as Array):
		var c: Vector2 = (l["bounds"] as Rect2).get_center()
		var lvl: float = float(l["level"])
		var at := Vector3(c.x, lvl - 1.0, c.y)
		if Geometry2D.is_point_in_polygon(c, l["poly"]) and lvl - w.height_at(c.x, c.y) > 2.0:
			if best == Vector3.INF or at.distance_to(near) < best.distance_to(near):
				best = at
	if best == Vector3.INF:
		print("WRIST_AUDIT no lake deep enough to swim in")
		return near
	return best


## A two-storey room with a ladder and hatch (as test_ladder_climb builds), its foot ahead of
## where the player is put (facing -Z).
func _ladder_foot(at: Vector3) -> Vector3:
	var raw: Dictionary = {"id": "qa_ladder", "name": "QA", "tier": 1, "footprint": [12, 12],
		"style": {"floor_height": 0.0},
		"levels": [{"level": 0, "plan": ["AAA", "AAA", "AAA"], "rooms": {"A": {}}},
			{"level": 1, "plan": ["BBB", "BBB", "BBB"], "rooms": {"B": {}}}],
		"openings": [{"id": "front", "at": [1, 2], "side": "S", "type": "door", "state": "open"}],
		"ladders": [{"level": 0, "at": [1, 0], "side": "N", "hatch": true}],
		"route": [{"at": [1, 4]}, {"at": [1, 1]}, {"at": [1, 1], "level": 1}]}
	var d := PoiDef.new()
	d.parse(raw, &"poi", "qa")
	var inst: PoiInstance = PoiBuilder.build(PoiLayout.compile(d), &"qa_ladder")
	w.add_child(inst)
	_ladder_room = inst
	at.y = w.height_at(at.x, at.z)
	inst.global_position = at
	var lad: Node3D = null
	for n: Node in get_tree().get_nodes_in_group(&"ladder"):
		if inst.is_ancestor_of(n):
			lad = n as Node3D
	if lad == null:
		print("WRIST_AUDIT no ladder built")
		return at
	# A metre in front of its foot, on the room's open (south) side of it.
	return lad.global_position + Vector3(0.0, 0.0, 1.0)


# --- Hold classes -----------------------------------------------------------------------------

func _classes() -> void:
	p.global_position = w.drop_site() + Vector3(4.0, 0.0, 4.0)
	p.global_position.y = w.height_at(p.global_position.x, p.global_position.z) + 0.05
	await _frames(15)
	var items: Dictionary = _class_items()
	for cls: StringName in items:
		await _hold(items[cls])
		await _raise(true)
		await _frames(10)
		var vm: ViewModel = p.equipment.viewmodel
		var up: bool = vm != null and vm.tether_raised()
		print("WRIST_AUDIT class %s (%s): raised %s" % [cls, items[cls], up])
		await _snap("class_%s" % cls)
		await _raise(false)


# --- Hands in every hold (player report 5, item 6) ---------------------------------------------

## fp_preview's shots worth judging the hands by, in the game's world and light (1080p, real
## materials): each hold class at rest and the moments its fingers do the most (a grip closing on a
## strike, a draw, a thumb on a lighter, the tether read). Climbing is left to its own audit.
const HAND_SHOTS: PackedStringArray = ["empty_hands", "empty_guard", "punch",
	"axe_idle", "axe_impact", "axe_guard", "axe_inspect", "hatchet_idle", "machete_idle", "machete_slash",
	"knife_idle", "knife_slice", "knife_inspect", "hammer_idle", "spear_idle", "spear_stab", "spear_guard",
	"club_idle", "club_bash", "pipe_idle", "shovel_idle", "shovel_dig",
	"revolver_idle", "revolver_fire", "revolver_reload_load", "rifle_idle", "rifle_bolt_up", "rifle_inspect_a",
	"torch_day", "torch_swing", "torch_inspect", "flashlight_idle", "flashlight_inspect_a",
	"lighter_idle", "lighter_light", "lighter_inspect_a", "tether_raised",
	"food_idle", "food_eat", "food_inspect_a", "bottle_idle", "bottle_drink", "bandage_idle", "bandage_apply",
	"bow_idle", "bow_draw_mid", "bow_full_draw", "held_stone", "stone_windup", "molotov_idle", "molotov_lighting",
	"carry_log", "blueprint", "chime_place"]


func _hands() -> void:
	p.global_position = w.drop_site() + Vector3(4.0, 0.0, 4.0)
	p.global_position.y = w.height_at(p.global_position.x, p.global_position.z) + 0.05
	await _frames(15)
	var by_name: Dictionary = {}
	for shot: Dictionary in (load("res://src/tools/cli/fp_preview_runner.gd") as GDScript).get_script_constant_map()["SHOTS"]:
		by_name[str(shot["name"])] = shot
	var only: PackedStringArray = []
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.find("--only") >= 0 and args.find("--only") + 1 < args.size():
		only = args[args.find("--only") + 1].split(",")
	for n: String in (only if not only.is_empty() else HAND_SHOTS):
		if not by_name.has(n):
			print("WRIST_AUDIT FAIL no fp_preview shot %s" % n)
			_fails += 1
			continue
		var shot: Dictionary = by_name[n]
		await _hold(StringName(str(shot.get("item", ""))))
		var vm: ViewModel = p.equipment.viewmodel
		vm.release_action()
		vm.set_guard(bool(shot.get("guard", false)))
		vm.qa_base = StringName(str(shot.get("base", "")))
		var rig: BowRig = BowRig.of(vm.held_item())
		if rig != null:
			rig.nocked = bool(shot.get("nocked", true))
		vm.set_lit(bool(shot.get("lit", false)))
		if bool(shot.get("tether", false)):
			await _raise(true)
		await _frames(20)
		if shot.has("action") and not vm.freeze_action(StringName(str(shot["action"])), float(shot.get("frame", 0)) / 30.0):
			print("WRIST_AUDIT FAIL no action %s" % shot["action"])
			_fails += 1
		# The other hand's item for a moment (the lighter lighting a molotov's rag), as ThrowHand shows it.
		if shot.has("offhand"):
			vm.show_offhand(StringName(str(shot["offhand"])), 999.0)
		await _frames(6)
		await _snap("hands_%s" % n)
		vm.release_action()
		vm.set_guard(false)
		vm.qa_base = &""
		if bool(shot.get("tether", false)):
			await _raise(false)


# --- Shelter markers (player report 5) ---------------------------------------------------------

## A lean-to and a bough bed built near the drop site, then the minimap on the raised wrist and the
## full map with the shelters' layer on and off.
func _markers() -> void:
	var base: Vector3 = w.drop_site() + Vector3(6.0, 0.0, 6.0)
	p.global_position = base + Vector3(0.0, w.height_at(base.x, base.z) - base.y + 0.05, 0.0)
	await _frames(15)
	# One of each layer, 60 m apart so their marks read apart on both maps (the bed beside the
	# lean-to); the garden bed's layer is off by default.
	var builds: Array = [["lean_to", Vector3(3.0, 0.0, -3.0)], ["bough_bed", Vector3(-3.0, 0.0, -2.0)],
		["workbench", Vector3(60.0, 0.0, 0.0)], ["storage_crate", Vector3(0.0, 0.0, 60.0)], ["garden_bed", Vector3(60.0, 0.0, 60.0)]]
	for b: Array in builds:
		var at: Vector3 = base + (b[1] as Vector3)
		at.y = w.height_at(at.x, at.z)
		p.global_position = at + Vector3(2.5, 0.05, 2.5)
		await _frames(5)
		for it: String in ["stick", "leaf_bundle", "cordage", "log", "nails", "wood_plank"]:
			p.state.inventory.add_item(StringName(it), 20)
		var r: Dictionary = Game.execute(&"build.place_blueprint", {"blueprint": b[0], "pos": [at.x, at.y, at.z], "yaw": 0.0})
		var d: Dictionary = Game.execute(&"build.deliver", {"site": r.get("site", "")}) if r.has("site") else r
		print("WRIST_AUDIT built %s: %s" % [b[0], str(d)])
		await _frames(10)
	var marks: Array[Dictionary] = MapMarkers.marks(MapMarkers.placed(), MapMarkers.layers())
	print("WRIST_AUDIT marks: %d (%s)" % [marks.size(), ", ".join(marks.map(func(m: Dictionary) -> String: return str(m["def"])))])
	if marks.size() < 4:
		_fails += 1
		print("WRIST_AUDIT FAIL the shelters, the workbench and the crate should be marked (the garden bed's layer is off)")
	# The logs left over from the builds go in the arms (carried), which keeps the tether down.
	p.state.inventory.remove(&"log", p.state.inventory.count_of(&"log"))
	# Walk off ~110 m so the marks don't sit under the player's arrow.
	var away: Vector3 = base + Vector3(130.0, 0.0, -50.0)
	p.global_position = Vector3(away.x, w.height_at(away.x, away.z) + 0.05, away.z)
	await _frames(15)
	await _raise(true)
	await _frames(20)
	await _snap("markers_minimap")
	await _raise(false)
	var map: Node = ui.get(&"world_map")
	map.call(&"open")
	await _frames(30)
	await _snap("markers_map_on")
	# Through the legend's own toggle, as the player turns it off (the box shows it too).
	var layer: Dictionary = MapMarkers.layers()[0]
	var was: Variant = Settings.map_layers.get(str(layer["id"]))
	var toggle: CheckButton = null
	for row: Node in (map.get(&"_legend") as Node).get_children():
		if row is HBoxContainer and ((row as HBoxContainer).get_child(1) as CheckButton).text == str(layer["label"]):
			toggle = (row as HBoxContainer).get_child(1) as CheckButton
	toggle.button_pressed = false
	await _frames(4)
	await _snap("markers_map_off")
	if was == null:
		Settings.map_layers.erase(str(layer["id"]))
	else:
		Settings.map_layers[str(layer["id"])] = was
	Settings.save()
	map.call(&"close")


# --- Steadiness -------------------------------------------------------------------------------

func _steady_all() -> void:
	var items: Dictionary = _class_items()
	for cls: StringName in items:
		await _hold(items[cls])
		await _raise(true)
		var vm: ViewModel = p.equipment.viewmodel
		if vm == null or not vm.tether_raised():
			print("WRIST_STEADY %s: no reading pose (the hold has none)" % cls)
			await _raise(false)
			continue
		await _frames(20)
		var r: Dictionary = await _steadiness(5.0)
		var bad: bool = r["max"] > STEADY_MAX_DEG
		_fails += 1 if bad else 0
		print("WRIST_STEADY %s (%s): largest frame step %.2f deg (%s, frame %d), median %.3f deg | %s" % [cls, items[cls],
			r["max"], r["hand"], r["at"], r["median"], "FAIL" if bad else "ok"])
		await _raise(false)


## Both hands' turn in the camera's space, frame to frame, over `seconds`.
func _steadiness(seconds: float) -> Dictionary:
	var cam: Camera3D = get_viewport().get_camera_3d()
	var sk: Skeleton3D = null
	var arms: Node3D = p.equipment.viewmodel.get(&"_arms") as Node3D
	for n: Node in arms.find_children("*", "Skeleton3D", true, false):
		sk = n as Skeleton3D
	var prev: Dictionary = {}
	var steps: Array[float] = []
	var out: Dictionary = {"max": 0.0, "hand": "", "at": 0, "median": 0.0}
	var n_frames: int = int(seconds * 60.0)
	for f: int in n_frames:
		await get_tree().process_frame
		for b: String in ["hand.L", "hand.R"]:
			var i: int = sk.find_bone(b)
			if i < 0:
				continue
			var basis: Basis = (cam.global_transform.affine_inverse() * sk.global_transform * sk.get_bone_global_pose(i)).basis.orthonormalized()
			if prev.has(b):
				var d: float = rad_to_deg(((prev[b] as Basis).inverse() * basis).get_rotation_quaternion().get_angle())
				steps.append(d)
				if d > float(out["max"]):
					out["max"] = d
					out["hand"] = b
					out["at"] = f
			prev[b] = basis
	steps.sort()
	out["median"] = steps[steps.size() / 2] if not steps.is_empty() else 0.0
	return out
