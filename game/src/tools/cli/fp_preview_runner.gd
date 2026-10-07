extends Node
## fp_preview.gd's work: a clearing with a sun (or a moonlit night), a camera with the player's
## ViewModel, and one PNG per shot: an item in its hold pose, frozen partway through an action,
## guarding, reading the tether, or burning at night. Shots and options are documented in
## fp_preview.gd.

const SHOTS: Array[Dictionary] = [
	{"name": "axe_idle", "item": "stone_axe"},
	{"name": "axe_windup", "item": "stone_axe", "action": "fp_chop", "frame": 10},
	{"name": "axe_impact", "item": "stone_axe", "action": "fp_chop", "frame": 12},
	{"name": "axe_guard", "item": "stone_axe", "guard": true},
	{"name": "hatchet_idle", "item": "hatchet"},
	{"name": "machete_idle", "item": "machete"},
	{"name": "knife_idle", "item": "kitchen_knife"},
	{"name": "hammer_idle", "item": "claw_hammer"},
	{"name": "spear_idle", "item": "crude_spear"},
	{"name": "spear_stab", "item": "crude_spear", "action": "fp_stab", "frame": 9},
	{"name": "club_idle", "item": "stone_club"},
	{"name": "club_bash", "item": "stone_club", "action": "fp_bash", "frame": 16},
	{"name": "pipe_idle", "item": "steel_pipe"},
	{"name": "machete_slash", "item": "machete", "action": "fp_slash", "frame": 9},
	{"name": "shovel_idle", "item": "shovel"},
	{"name": "shovel_dig", "item": "shovel", "action": "fp_dig", "frame": 12},
	{"name": "punch", "item": "", "action": "fp_punch", "frame": 7},
	{"name": "revolver_idle", "item": "revolver"},
	{"name": "revolver_fire", "item": "revolver", "action": "fp_fire_pistol", "frame": 2},
	{"name": "revolver_reload_open", "item": "revolver", "action": "fp_reload_pistol", "frame": 16},
	{"name": "revolver_reload_eject", "item": "revolver", "action": "fp_reload_pistol", "frame": 22},
	{"name": "revolver_reload_load", "item": "revolver", "action": "fp_reload_pistol", "frame": 40},
	{"name": "revolver_reload_close", "item": "revolver", "action": "fp_reload_pistol", "frame": 64},
	{"name": "revolver_inspect_right", "item": "revolver", "action": "fp_inspect_pistol", "frame": 24},
	{"name": "revolver_inspect_left", "item": "revolver", "action": "fp_inspect_pistol", "frame": 52},
	{"name": "torch_day", "item": "torch", "lit": true},
	{"name": "torch_night", "item": "torch", "lit": true, "night": true},
	{"name": "flashlight_idle", "item": "flashlight"},
	{"name": "lighter_idle", "item": "lighter", "lit": true},
	{"name": "torch_swing", "item": "torch", "lit": true, "action": "fp_torch", "frame": 10},
	# Shot while the view swings round (turn: rad/s of yaw, at 30 fps for 8 frames): the flames
	# must stay on the item, not trail behind it.
	{"name": "torch_turn", "item": "torch", "lit": true, "night": true, "turn": 3.0},
	{"name": "lighter_turn", "item": "lighter", "lit": true, "night": true, "turn": 3.0},
	{"name": "tether_raised", "item": "stone_axe", "tether": true},
	{"name": "food_idle", "item": "canned_beans"},
	{"name": "food_eat", "item": "canned_beans", "action": "fp_eat", "frame": 15},
	{"name": "bottle_idle", "item": "water_bottle_clean"},
	{"name": "bottle_drink", "item": "water_bottle_clean", "action": "fp_drink", "frame": 30},
	# The bow (ADR-0057): at the ready with an arrow nocked, mid-draw, at full draw, just loosed.
	{"name": "bow_idle", "item": "hunting_bow"},
	{"name": "bow_draw_mid", "item": "hunting_bow", "action": "fp_draw_bow", "frame": 12},
	{"name": "bow_full_draw", "item": "hunting_bow", "action": "fp_bow_drawn", "frame": 0},
	{"name": "bow_release", "item": "hunting_bow", "action": "fp_release_bow", "frame": 4, "nocked": false},
	{"name": "held_stone", "item": "stone"},
	{"name": "stone_throw", "item": "stone", "action": "fp_throw_stone", "frame": 12},
	{"name": "stone_windup", "item": "stone", "action": "fp_throw_stone", "frame": 9},
	{"name": "stone_release", "item": "stone", "action": "fp_throw_stone", "frame": 14},
	{"name": "molotov_idle", "item": "molotov"},
	{"name": "molotov_lighting", "item": "molotov", "action": "fp_light_molotov", "frame": 13},
	{"name": "molotov_lit", "item": "molotov", "lit": true},
	{"name": "molotov_lit_night", "item": "molotov", "lit": true, "night": true},
	{"name": "molotov_windup", "item": "molotov", "lit": true, "action": "fp_throw_molotov", "frame": 10},
	{"name": "molotov_throw", "item": "molotov", "lit": true, "action": "fp_throw_molotov", "frame": 13},
	{"name": "ground_fire_dusk", "item": "", "ground_fire": "molotov", "night": true},
	{"name": "bandage_apply", "item": "cloth_bandage", "action": "fp_apply", "frame": 20},
	{"name": "empty_hands", "item": ""},
	{"name": "empty_guard", "item": "", "guard": true},
	{"name": "carry_log", "item": "", "base": "fp_carry_log"},
	{"name": "blueprint", "item": "stone_axe", "base": "fp_blueprint"},
	# Strike phases either side of the contact frames above (TD-172): windup, follow-through.
	{"name": "machete_slash_windup", "item": "machete", "action": "fp_slash", "frame": 6},
	{"name": "machete_slash_follow", "item": "machete", "action": "fp_slash", "frame": 12},
	{"name": "club_bash_windup", "item": "stone_club", "action": "fp_bash", "frame": 13},
	{"name": "club_bash_follow", "item": "stone_club", "action": "fp_bash", "frame": 20},
	{"name": "shovel_dig_windup", "item": "shovel", "action": "fp_dig", "frame": 8},
	{"name": "shovel_dig_follow", "item": "shovel", "action": "fp_dig", "frame": 15},
	{"name": "food_eat_lift", "item": "canned_beans", "action": "fp_eat", "frame": 8},
	# The skin lit only by the flame in hand (falloff over the hand, light through the fingers).
	{"name": "lighter_night", "item": "lighter", "lit": true, "night": true},
	# Utility items and bare hands: the other phases of their uses and strikes, and the inspects.
	{"name": "lighter_light", "item": "lighter", "action": "fp_light", "frame": 11},
	{"name": "flashlight_jab", "item": "flashlight", "action": "fp_jab", "frame": 7},
	{"name": "torch_swing_windup", "item": "torch", "lit": true, "action": "fp_torch", "frame": 6},
	{"name": "punch_windup", "item": "", "action": "fp_punch", "frame": 4},
	{"name": "stone_throw_windup", "item": "stone", "action": "fp_throw", "frame": 10},
	{"name": "stone_throw_release", "item": "stone", "action": "fp_throw", "frame": 15},
	{"name": "bandage_idle", "item": "cloth_bandage"},
	{"name": "chime_idle", "item": "can_chime"},
	{"name": "chime_place", "item": "can_chime", "action": "fp_place", "frame": 12},
	{"name": "bottle_drink_lift", "item": "water_bottle_clean", "action": "fp_drink", "frame": 12},
	{"name": "stone_throw_follow", "item": "stone", "action": "fp_throw", "frame": 18},
	{"name": "bandage_apply_over", "item": "cloth_bandage", "action": "fp_apply", "frame": 10},
	{"name": "bandage_apply_far", "item": "cloth_bandage", "action": "fp_apply", "frame": 17},
	{"name": "lighter_inspect_a", "item": "lighter", "action": "fp_inspect_lighter", "frame": 30},
	{"name": "lighter_inspect_b", "item": "lighter", "action": "fp_inspect_lighter", "frame": 46},
	{"name": "torch_inspect", "item": "torch", "lit": true, "action": "fp_inspect_light_left", "frame": 34},
	{"name": "flashlight_inspect_a", "item": "flashlight", "action": "fp_inspect_flashlight", "frame": 34},
	{"name": "flashlight_inspect_b", "item": "flashlight", "action": "fp_inspect_flashlight", "frame": 50},
	{"name": "stone_inspect", "item": "stone", "action": "fp_inspect_held", "frame": 30},
	{"name": "food_inspect_a", "item": "canned_beans", "action": "fp_inspect_food", "frame": 16},
	{"name": "food_inspect_b", "item": "canned_beans", "action": "fp_inspect_food", "frame": 48},
	{"name": "bottle_inspect", "item": "water_bottle_clean", "action": "fp_inspect_bottle", "frame": 16},
	# Spear and shovel: thrust windup, dig pry, guards, tether, inspects (turned one way, the other).
	{"name": "spear_stab_windup", "item": "crude_spear", "action": "fp_stab", "frame": 5},
	{"name": "spear_guard", "item": "crude_spear", "guard": true},
	{"name": "spear_inspect_a", "item": "crude_spear", "action": "fp_inspect_spear", "frame": 30},
	{"name": "spear_inspect_b", "item": "crude_spear", "action": "fp_inspect_spear", "frame": 46},
	{"name": "shovel_dig_pry", "item": "shovel", "action": "fp_dig", "frame": 17},
	{"name": "shovel_guard", "item": "shovel", "guard": true},
	{"name": "shovel_tether", "item": "shovel", "tether": true},
	{"name": "shovel_inspect_a", "item": "shovel", "action": "fp_inspect_two_hand", "frame": 30},
	{"name": "shovel_inspect_b", "item": "shovel", "action": "fp_inspect_two_hand", "frame": 46},
	# One-handed tools, knives and clubs: the chop's follow-through, the knife's own hold and
	# slice, the pipe's blow, and each class's inspect (key Y) at its look and its turn.
	{"name": "axe_follow", "item": "stone_axe", "action": "fp_chop", "frame": 15},
	{"name": "hatchet_impact", "item": "hatchet", "action": "fp_chop", "frame": 12},
	{"name": "knife_guard", "item": "kitchen_knife", "guard": true},
	{"name": "knife_slice_windup", "item": "kitchen_knife", "action": "fp_slice", "frame": 3},
	{"name": "knife_slice", "item": "kitchen_knife", "action": "fp_slice", "frame": 6},
	{"name": "club_guard", "item": "stone_club", "guard": true},
	{"name": "pipe_bash", "item": "steel_pipe", "action": "fp_bash", "frame": 16},
	{"name": "axe_inspect", "item": "stone_axe", "action": "fp_inspect_one_hand", "frame": 20},
	{"name": "hatchet_inspect_turn", "item": "hatchet", "action": "fp_inspect_one_hand", "frame": 40},
	{"name": "club_inspect", "item": "stone_club", "action": "fp_inspect_club", "frame": 24},
	{"name": "pipe_inspect_turn", "item": "steel_pipe", "action": "fp_inspect_club", "frame": 44},
	{"name": "knife_inspect", "item": "kitchen_knife", "action": "fp_inspect_knife", "frame": 20},
	{"name": "knife_inspect_turn", "item": "kitchen_knife", "action": "fp_inspect_knife", "frame": 40},
	# Climbing (ADR-0057): hand over hand on a ladder's rails (each hand mid-reach, both gripping),
	# the grab-on, the let-go, and on a rope; the rails/rope stand where Player hangs the climber.
	{"name": "climb_ladder_a", "item": "", "action": "fp_climb_cycle", "frame": 21, "rails": "ladder"},
	{"name": "climb_ladder_b", "item": "", "action": "fp_climb_cycle", "frame": 51, "rails": "ladder"},
	{"name": "climb_ladder_grip", "item": "", "action": "fp_climb_cycle", "frame": 36, "rails": "ladder"},
	{"name": "climb_grab", "item": "", "action": "fp_climb_grab", "frame": 6, "rails": "ladder"},
	{"name": "climb_release", "item": "", "action": "fp_climb_release", "frame": 5, "rails": "ladder"},
	{"name": "climb_rope_a", "item": "", "action": "fp_climb_rope_cycle", "frame": 21, "rails": "rope"},
	{"name": "climb_rope_b", "item": "", "action": "fp_climb_rope_cycle", "frame": 51, "rails": "rope"},
	{"name": "climb_rope_grab", "item": "", "action": "fp_climb_rope_grab", "frame": 6, "rails": "rope"},
	{"name": "hunting_stand", "item": "climbing_rope", "rails": "structures/hunting_stand"},
	# Hunting rifle (ADR-0057): the ready, the kick, the bolt cycle, a round going in, the inspect;
	# aim (0..1): raised toward the sights, the scope picture once up; the revolver's iron sights.
	{"name": "rifle_idle", "item": "hunting_rifle"},
	{"name": "rifle_fire", "item": "hunting_rifle", "action": "fp_fire_rifle", "frame": 2},
	{"name": "rifle_bolt_up", "item": "hunting_rifle", "action": "fp_fire_rifle", "frame": 15},
	{"name": "rifle_bolt_back", "item": "hunting_rifle", "action": "fp_fire_rifle", "frame": 21},
	{"name": "rifle_reload_open", "item": "hunting_rifle", "action": "fp_reload_rifle_open", "frame": 12},
	{"name": "rifle_reload_round", "item": "hunting_rifle", "action": "fp_reload_rifle", "frame": 16},
	{"name": "rifle_inspect_a", "item": "hunting_rifle", "action": "fp_inspect_rifle", "frame": 32},
	{"name": "rifle_inspect_b", "item": "hunting_rifle", "action": "fp_inspect_rifle", "frame": 62},
	{"name": "rifle_aim_half", "item": "hunting_rifle", "aim": 0.6},
	{"name": "rifle_aimed", "item": "hunting_rifle", "aim": 1.0},
	{"name": "revolver_aimed", "item": "revolver", "aim": 1.0},
]

var _out: String = "res://../build/fp_preview"
var _only: PackedStringArray = []
var _size := Vector2i(1280, 720)
var _cam: Camera3D
## The camera's parent, turned by the turn shots.
var _head: Node3D
var _vm: ViewModel
var _sun: DirectionalLight3D
var _env: Environment
var _torch_light: OmniLight3D
## The climbing shots' ladder or rope in front of the camera (null when none is shown).
var _rails: Node3D = null
var _scope: ScopeOverlay = null


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	for i: int in args.size():
		match args[i]:
			"--out":
				_out = args[i + 1]
			"--only":
				_only = args[i + 1].split(",")
			"--size":
				var p: PackedStringArray = args[i + 1].split("x")
				_size = Vector2i(int(p[0]), int(p[1]))
	DirAccess.make_dir_recursive_absolute(_out)
	get_window().size = _size
	_run.call_deferred()


func _wait(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame


func _scene() -> void:
	var world := Node3D.new()
	add_child(world)
	_env = Environment.new()
	_env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.30, 0.42, 0.58)
	sm.sky_horizon_color = Color(0.66, 0.68, 0.66)
	sm.ground_horizon_color = Color(0.36, 0.33, 0.28)
	sm.ground_bottom_color = Color(0.12, 0.1, 0.08)
	sky.sky_material = sm
	_env.sky = sky
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	_env.ambient_light_energy = 0.7
	_env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	_env.glow_enabled = true
	_env.glow_intensity = 0.35
	_env.ssao_enabled = true
	_env.ssao_radius = 1.4
	_env.ssao_intensity = 2.2
	var we := WorldEnvironment.new()
	we.environment = _env
	world.add_child(we)
	_sun = DirectionalLight3D.new()
	_sun.shadow_enabled = true
	_sun.light_energy = 1.4
	_sun.rotation_degrees = Vector3(-48.0, -35.0, 0.0)
	world.add_child(_sun)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(80, 80)
	ground.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.30, 0.22, 0.14)
	gm.roughness = 1.0
	ground.material_override = gm
	world.add_child(ground)
	# A few trees and a boulder in front for depth and something to lean against.
	for t: Array in [["trees/grey_fir_a", Vector3(-3.0, 0, -7.0), 0.0], ["trees/paper_birch_a", Vector3(2.5, 0, -9.0), 1.0],
			["trees/grey_fir_c", Vector3(6.0, 0, -15.0), 2.0], ["trees/hollow_larch_a", Vector3(-7.5, 0, -14.0), 0.5],
			["rocks/boulder_a", Vector3(1.2, 0, -4.5), 0.3]]:
		var path: String = "res://assets/generated/models/%s.glb" % t[0]
		if ResourceLoader.exists(path):
			var n: Node3D = (load(path) as PackedScene).instantiate() as Node3D
			world.add_child(n)
			n.position = t[1]
			n.rotation.y = float(t[2])
	_cam = Camera3D.new()
	_cam.fov = 75.0
	_cam.near = 0.04
	_cam.far = 400.0
	_head = Node3D.new()
	world.add_child(_head)
	_head.position = Vector3(0, 1.65, 0)
	_head.add_child(_cam)
	_cam.make_current()
	_vm = (load("res://src/player/viewmodel.gd") as GDScript).new() as ViewModel
	_vm.name = "ViewModel"
	_cam.add_child(_vm)
	# The tether UI on the wrist screen, beside the viewmodel as GameUI puts it. With no session it
	# shows only its layout and caption: enough to see the screen read upright when raised.
	var tether := Tether.new()
	tether.name = "Tether"
	_cam.add_child(tether)
	_torch_light = OmniLight3D.new()
	_torch_light.light_color = Color(1.0, 0.6, 0.29)
	_torch_light.omni_range = 13.0
	_torch_light.light_energy = 2.4
	_torch_light.shadow_enabled = true
	_torch_light.visible = false
	world.add_child(_torch_light)


func _run() -> void:
	_scene()
	await _wait(0.5)
	for shot: Dictionary in SHOTS:
		if not _only.is_empty() and not _only.has(str(shot["name"])):
			continue
		await _shoot(shot)
	print("FP_PREVIEW done")
	get_tree().quit(0)


## A shot's aim (0..1): the camera's zoom, the arms raised toward the sights, the scope picture.
func _aim_shot(shot: Dictionary) -> void:
	var a: float = float(shot.get("aim", 0.0))
	var pa := PlayerAim.new()
	pa.update(0.0, a > 0.0, StringName(str(shot.get("item", ""))))
	pa.progress = a
	_cam.fov = pa.fov(75.0)
	_vm.set_aim(pa.amount(), 1.0 - pa.sway_mult(), pa.scoped())
	if _scope == null:
		_scope = ScopeOverlay.new()
		add_child(_scope)
	_scope.visible = pa.scoped()
	pa.free()


func _shoot(shot: Dictionary) -> void:
	var night: bool = bool(shot.get("night", false))
	_sun.visible = not night
	_env.ambient_light_energy = 0.06 if night else 0.7
	_env.background_energy_multiplier = 0.04 if night else 1.0
	_vm.release_action()
	_vm.set_guard(false)
	_vm.set_tether_raised(false)
	_vm.tether.t = 0.0
	_vm.tether.state = TetherRaise.State.LOWERED
	_vm.qa_base = StringName(str(shot.get("base", "")))
	_vm.show_item(StringName(str(shot.get("item", ""))))
	_show_rails(str(shot.get("rails", "")))
	_vm.motion.equip = 1.0
	_aim_shot(shot)
	if bool(shot.get("guard", false)):
		_vm.set_guard(true)
	if bool(shot.get("tether", false)):
		_vm.set_tether_raised(true)
	var rig: BowRig = BowRig.of(_vm.held_item())
	if rig != null:
		rig.nocked = bool(shot.get("nocked", true))
	var lit: bool = bool(shot.get("lit", false))
	_vm.set_lit(lit)
	await _wait(0.6)
	if shot.has("action"):
		if not _vm.freeze_action(StringName(str(shot["action"])), float(shot.get("frame", 0)) / 30.0):
			print("FP_PREVIEW warning: no action %s" % shot["action"])
	_torch_light.visible = lit and night
	# A molotov's ground fire burning a few metres ahead (ADR-0057), to see its flames, smoke and light.
	var fire: GroundFire = null
	if shot.has("ground_fire"):
		fire = GroundFire.spawn(self, Vector3(-0.6, 0.0, -4.0), StringName(str(shot["ground_fire"])))
	# The held item's own light, as PlayerEquipment makes it (a lighter is far dimmer than a torch).
	var idef: ItemDef = Content.item(StringName(str(shot.get("item", "")))) if lit else null
	if idef != null and idef.equip.has("light"):
		var l: Dictionary = idef.equip["light"]
		_torch_light.light_color = Color.html(str(l.get("color", "#ffb46b")))
		_torch_light.light_energy = float(l.get("energy", 1.0))
		_torch_light.omni_range = float(l.get("range", 8.0))
	await _wait(1.2)
	var anchor: Node3D = _vm.light_anchor()
	if anchor != null:
		_torch_light.global_position = anchor.global_position + Vector3.UP * 0.08
	await _wait(0.4)
	# Turn the head (the viewmodel drives the camera's own rotation): a few frames of steady yaw.
	var turn: float = float(shot.get("turn", 0.0))
	if turn != 0.0:
		for i: int in 8:
			await get_tree().process_frame
			_head.rotation.y += turn / 30.0
	var img: Image = get_viewport().get_texture().get_image()
	var path: String = _out.path_join("%s.png" % shot["name"])
	img.save_png(path)
	print("FP_PREVIEW %s" % path)
	if fire != null:
		fire.queue_free()
	_head.rotation.y = 0.0


## A ladder (the kit's, else rails and rungs of its own) or a climbing rope where Player hangs a
## climber (0.42 m out from the ladder's foot): the rails ~0.3 m ahead of the eye.
func _show_rails(kind: String) -> void:
	if _rails != null:
		_rails.queue_free()
		_rails = null
	if kind == "":
		return
	_rails = Node3D.new()
	_head.get_parent().add_child(_rails)
	var foot := Vector3(0.0, 0.0, -0.42)
	if kind.begins_with("structures/"):
		# A model check: the piece 4.5 m ahead, its front toward the camera.
		var mi2 := MeshInstance3D.new()
		mi2.mesh = ModelLibrary.mesh(kind)
		mi2.position = Vector3(0.6, 0.0, -4.5)
		mi2.rotation.y = 0.5
		_rails.add_child(mi2)
		return
	if kind == "rope":
		_rails.add_child(ClimbMount.rope_visual(foot + Vector3(0, 0, 0.12), foot + Vector3(0, 3.2, 0.12)))
		return
	var kit: Mesh = ModelLibrary.generated_mesh("kit/ladder_3m")
	if kit != null:
		var mi := MeshInstance3D.new()
		mi.mesh = kit
		mi.position = foot
		_rails.add_child(mi)
		return
	_rails.add_child(ClimbMount.ladder_stand_in(foot, Vector3.BACK, 3.0))
