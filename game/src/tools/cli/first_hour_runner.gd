extends Node
## Runner for first_hour.gd (the first-hour UX audit): one new game on the main map, then the
## first hour of play step by step, each step a captured frame and a dump of every word on screen
## (status messages since the last step, the interaction prompt and hint, the tutorial card, the
## loading line). Not a test: it never fails, it records. Rendered (xvfb + lavapipe) it writes
## <out>/<nn>_<step>.png; headless it writes the text only.
##   make first-hour   ->  build/first_hour/{*.png, first_hour.txt}

var _out: String = "res://../build/first_hour"
var _n: int = 0
var _log: PackedStringArray = []
var _msgs: PackedStringArray = []
var _t0: int = 0
var game: Node
var w: GameWorld
var p: Player
var ui: GameUI


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.find("--out") >= 0 and args.find("--out") + 1 < args.size():
		_out = args[args.find("--out") + 1]
	_t0 = Time.get_ticks_msec()
	_run.call_deferred()


func frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


## The value after `key` on the command line (after `--`), else `default`.
func _arg(key: String, default: String) -> String:
	var a: PackedStringArray = OS.get_cmdline_user_args()
	var i: int = a.find(key)
	return a[i + 1] if i >= 0 and i + 1 < a.size() else default


func seconds(s: float) -> void:
	var end: int = Time.get_ticks_msec() + int(s * 1000.0)
	while Time.get_ticks_msec() < end:
		await get_tree().process_frame


func wait_until(cond: Callable, timeout_s: float) -> bool:
	var end: int = Time.get_ticks_msec() + int(timeout_s * 1000.0)
	while Time.get_ticks_msec() < end:
		if cond.call():
			return true
		await get_tree().process_frame
	return false


func note(text: String) -> void:
	_log.append("    note: " + text)
	print("[first_hour] note  " + text)


## A step: a frame (rendered runs) and everything the screen says now.
func snap(step: String) -> void:
	await frames(4)
	var name_: String = "%02d_%s" % [_n, step]
	_n += 1
	var lines: PackedStringArray = ["## %s  (t=%.0fs, day %d %s)" % [name_, (Time.get_ticks_msec() - _t0) / 1000.0,
		Game.session.clock.day() if Game.session != null else 0, Game.session.clock.time_string() if Game.session != null and Game.session.clock.has_method(&"time_string") else ""]]
	for m: String in _msgs:
		lines.append("    message: " + m)
	_msgs.clear()
	for f: Array in [["prompt", &"_prompt"], ["hint", &"_tool_hint"], ["loading", &"_loading_label"]]:
		var l: Label = ui.get(f[1]) as Label if ui != null else null
		if l != null and l.is_visible_in_tree() and l.text != "":
			lines.append("    %s: %s" % [f[0], l.text.replace("\n", " / ")])
	var shown: PackedStringArray = []
	for n: Node in ui.find_children("*", "Label", true, false) if ui != null else []:
		var l2 := n as Label
		# A long one (the distress call, ~450 characters) is shortened, not dropped: dropping it
		# once made the call look like it never reached the screen.
		if l2.is_visible_in_tree() and l2.text.strip_edges() != "":
			var tx: String = l2.text.replace("\n", " / ")
			shown.append(tx if tx.length() < 400 else tx.left(240) + " …")
	for n: Node in ui.find_children("*", "RichTextLabel", true, false) if ui != null else []:
		var r := n as RichTextLabel
		if r.is_visible_in_tree() and r.get_parsed_text().strip_edges() != "":
			shown.append(r.get_parsed_text().replace("\n", " / ").left(600))
	lines.append("    on screen: " + "  |  ".join(shown))
	_log.append("\n".join(lines))
	print("\n".join(lines))
	if DisplayServer.get_name() != "headless":
		var img: Image = get_viewport().get_texture().get_image()
		img.save_png(ProjectSettings.globalize_path(_out).path_join(name_ + ".png"))


## Stands `dist` m from `at` (on the side toward `from`) and looks at it; the interaction ray then
## finds what a player aiming there would.
func face(at: Vector3, dist: float = 1.8, from: Vector3 = Vector3.INF) -> void:
	var dir := Vector3(1, 0, 0.3) if from == Vector3.INF else Vector3(from.x - at.x, 0.0, from.z - at.z)
	dir = dir.normalized() if dir.length() > 0.01 else Vector3(1, 0, 0)
	var stand: Vector3 = at + dir * dist
	stand.y = w.height_at(stand.x, stand.z)
	p.global_position = stand + Vector3.UP * 0.05
	p.velocity = Vector3.ZERO
	await _stream(p.global_position)
	look(at)
	await frames(6)
	look(at)
	await frames(6)


func look(at: Vector3) -> void:
	var eye: Vector3 = p.global_position + Vector3.UP * 1.65
	var to: Vector3 = at - eye
	p.rotation.y = atan2(-to.x, -to.z)
	var pitch: float = atan2(to.y, Vector2(to.x, to.z).length())
	p.set(&"_pitch", pitch)
	(p.get(&"head") as Node3D).rotation.x = pitch


func nearest_species(veg: VegetationManager, pos: Vector3, species: String, max_d: float) -> Array:
	var best: Array = []
	var best_d: float = max_d
	var data: Dictionary = veg.get(&"_data")
	for key: Vector2i in data:
		for layer: String in VegetationScatter.ORDER:
			for inst: VegetationScatter.Instance in (data[key] as Dictionary).get(layer, []):
				if String(inst.species) != species or bool(veg.call(&"_is_removed", key, inst.index)):
					continue
				var d: float = inst.pos.distance_to(pos)
				if d < best_d:
					best_d = d
					best = [key, inst]
	return best


func use() -> bool:
	await frames(2)
	var t: Object = p.interaction.target
	if t != null and is_instance_valid(t) and t.has_method(&"interact"):
		t.call(&"interact", p)
		await frames(6)
		return true
	return false


func ex(cmd: StringName, args: Dictionary) -> Dictionary:
	var r: Dictionary = Game.execute(cmd, args)
	if not bool(r.get("ok", false)):
		note("%s failed: %s" % [cmd, r.get("error", r)])
	return r


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out))
	# --no-3d: frames of the screens and words over black. Software Vulkan drawing the real
	# assets' forest starves the game's own threads (26 s frames on Build 102's pack); without
	# the 3D the run takes minutes and still shows every card, prompt and line.
	if OS.get_cmdline_user_args().has("--no-3d"):
		get_viewport().disable_3d = true
	game = get_node("/root/Game")
	Events.player_status_message.connect(func(text: String, kind: StringName) -> void: _msgs.append("[%s] %s" % [kind, text]))
	var opts: Dictionary = {"game_mode": "survival", "seed": 4471, "skip_intro": true, "slot": "qa_first_hour"}
	# `--world random --world-seed N [--world-set k=v]`: a random world, read as the game reads it.
	var ra: PackedStringArray = OS.get_cmdline_user_args()
	if ra.find("--world") >= 0 and ra.find("--world") + 1 < ra.size() and ra[ra.find("--world") + 1] == "random":
		opts["world_gen"] = (load("res://src/app/main.gd") as GDScript).call(&"world_gen_from_args", ra, 7)
		opts["stream"] = not ra.has("--no-stream")
	game.call(&"start_new_game", opts)
	await frames(3)
	ui = (game.world as Node).get(&"ui") as GameUI if game.get(&"world") != null else null
	await seconds(2.0)
	if ui != null:
		await snap("loading_new_game")
	# --load-wait <s>: a rendered run of an exported pack (real assets, software Vulkan) raises
	# its towns at about a second a frame and can need far longer than the default.
	var load_wait: float = float(_arg("--load-wait", "900"))
	if not await wait_until(func() -> bool: return game.get(&"world") != null and bool(game.world.is_ready), load_wait):
		note("the world never became ready")
		_finish()
		return
	w = game.world
	p = w.player
	ui = w.ui
	await seconds(3.0)
	await snap("wake")
	var ps: PlayerState = p.state
	if OS.get_cmdline_user_args().has("--week-only") or OS.get_cmdline_user_args().has("--mid-only") or OS.get_cmdline_user_args().has("--gaps"):
		# Straight to the week (rendered frames of it without the hour's 48 minutes): the
		# journal finished and Ezra recruited by command.
		ps.tutorial.finish_all()
		ps.inventory.add_item(&"cloth_bandage", 1)
		var camp: Vector3 = w.tutorial.camp_position()
		p.global_position = camp + Vector3(2, 0.5, 2)
		await _stream(p.global_position)
		await seconds(3.0)
		ex(&"companion.recruit", {})
		await seconds(1.0)
		p.global_position = w.drop_site() + Vector3(0, 0.5, 0)
		await _stream(p.global_position)
		await seconds(3.0)
		if OS.get_cmdline_user_args().has("--gaps"):
			await _gaps()
		elif OS.get_cmdline_user_args().has("--mid-only"):
			await _midgame()
		else:
			await _week()
		_finish()
		return
	note("start kit: " + ", ".join(ps.inventory.stacks.map(func(s: ItemStack) -> String: return "%s x%d" % [s.item_id, s.count])))

	# --- The tether and the first card -----------------------------------------------------------
	ui.call(&"_raise_wrist", true)
	await seconds(1.5)
	await snap("tether")
	ui.call(&"_raise_wrist", false)
	ui.manual.open("journal")
	await frames(4)
	await snap("journal")
	ui.manual.call(&"close") if ui.manual.has_method(&"close") else ui.close_top_screen()
	await frames(3)

	# --- Gathering ----------------------------------------------------------------------------------
	var veg: VegetationManager = w.vegetation
	await wait_until(func() -> bool: return veg.is_settled(1), 60.0)
	var spawn: Vector3 = p.global_position
	for sp: String in ["sword_fern", "fireweed", "deadfall_branches", "loose_stone", "huckleberry_bush", "forest_sorrel", "granite_boulder"]:
		var found: Array = nearest_species(veg, spawn, sp, 200.0)
		if found.is_empty():
			note("no %s within 200 m of the drop site" % sp)
			continue
		var inst: VegetationScatter.Instance = found[1]
		note("nearest %s: %.0f m from the drop" % [sp, inst.pos.distance_to(spawn)])
		await face(inst.pos + Vector3.UP * 0.15, 1.3 if sp != "granite_boulder" else 2.2)
		await snap("gather_%s_aim" % sp)
		if not await use():
			note("nothing to use aiming at %s" % sp)
		await snap("gather_%s_done" % sp)
	for kv: Array in [["plant_fiber", 6], ["stick", 4], ["stone", 3]]:
		if ps.inventory.count_of(StringName(kv[0])) < int(kv[1]):
			ps.inventory.add_item(StringName(kv[0]), int(kv[1]) - ps.inventory.count_of(StringName(kv[0])))

	# --- Crafting the axe ---------------------------------------------------------------------------
	ui.roll.open(&"inventory")
	await frames(6)
	await snap("roll_open")
	ex(&"inventory.craft", {"recipe": "cordage"})
	ex(&"inventory.craft", {"recipe": "stone_axe"})
	await frames(6)
	await snap("roll_axe_made")
	ui.close_top_screen()
	var slot: int = ps.toolbelt.find(&"stone_axe")
	note("the axe went to toolbelt slot %d" % slot)
	if slot < 0:
		ps.toolbelt[0] = &"stone_axe"
		slot = 0
	p.equipment.select_slot(slot)
	await frames(6)

	# --- Felling ------------------------------------------------------------------------------------
	var trees: Array = veg.nearest_instance(spawn, "tree", 150.0)
	if not trees.is_empty():
		var ti: VegetationScatter.Instance = trees[1]
		await face(ti.pos + Vector3.UP * 1.2, 1.5)
		await snap("tree_aim")
		await wait_until(func() -> bool: return veg.body_for(trees[0], ti) != null, 20.0)
		var swings: int = 0
		for i: int in 40:
			if int(Game.session.stats.get("trees_felled", 0)) >= 1:
				break
			look(ti.pos + Vector3.UP * 1.2)
			if i % 8 == 0:
				note("swing %d: hp %s, stamina %.0f, ray hits %s" % [i, str((veg.get(&"_tree_hp") as Dictionary).values()), ps.stats.stamina, str(p.interaction.target)])
			p.equipment.primary()
			swings += 1
			# A player's cadence: 0.9 s of physics ticks between presses (process frames ran
			# faster than the swing, so presses landed mid-swing and were dropped).
			for t: int in int(0.9 * Engine.physics_ticks_per_second):
				await get_tree().physics_frame
		note("felled after %d swings: %s (tree hp now %s, stamina %.0f)" % [swings, int(Game.session.stats.get("trees_felled", 0)) >= 1,
			str((veg.get(&"_tree_hp") as Dictionary).values()), ps.stats.stamina])
		# Swings that didn't fell it (finding 7): finish it as the smoke run does, so the
		# tutorial's chain (and the distress call after it) still runs.
		var body: Node = veg.body_for(trees[0], ti)
		for i: int in 20:
			if int(Game.session.stats.get("trees_felled", 0)) >= 1 or body == null or not is_instance_valid(body):
				break
			var info := DamageInfo.make(20.0, &"slash", &"melee", ps.id)
			info.tool_power = {"chop": 30.0, "wood": 30.0}
			info.hit_pos = ti.pos + Vector3.UP
			info.direction = Vector3(-1, 0, 0.2).normalized()
			info.collider = body
			veg.take_damage(info)
			await frames(2)
		await seconds(3.0)
		await snap("tree_felled")
		var logs: Array = get_tree().get_nodes_in_group(&"logs")
		if not logs.is_empty():
			await face((logs[0] as Node3D).global_position, 1.6)
			await snap("log_aim")
			await use()
			await snap("log_shouldered")
			p.state.inventory.remove(&"log", p.state.inventory.count_of(&"log"))
	else:
		note("no tree near the drop site")

	# --- The campfire -------------------------------------------------------------------------------
	ui.manual.open("build")
	await frames(6)
	await snap("manual_blueprints")
	ui.close_top_screen()
	var cpos: Vector3 = spawn + Vector3(3, 0, 3)
	cpos.y = w.height_at(cpos.x, cpos.z)
	await face(cpos + Vector3.UP * 0.2, 2.2)
	ps.inventory.add_item(&"stone", 6)
	ps.inventory.add_item(&"stick", 4)
	var bp: Dictionary = ex(&"build.place_blueprint", {"blueprint": "campfire", "pos": [cpos.x, cpos.y, cpos.z], "yaw": 0.0})
	await face(cpos + Vector3.UP * 0.2, 2.2)
	await snap("campfire_ghost_aim")
	await use()
	await snap("campfire_delivered")
	await face(cpos + Vector3.UP * 0.2, 1.8)
	await snap("campfire_unlit_aim")
	await use()
	await seconds(1.0)
	await snap("campfire_lit")
	var lit: bool = false
	for piece: StructurePiece in w.building.pieces_in_radius(cpos, 2.0):
		lit = lit or bool(piece.get(&"lit"))
	note("campfire lit by interacting: %s (blueprint %s)" % [lit, bp.get("ok", false)])

	# --- Water --------------------------------------------------------------------------------------
	ex(&"inventory.consume", {"item": "water_bottle_clean"})
	await snap("drank_issued_water")
	await face(Vector3(-262, 0.2, 1915), 14.0, Vector3(-240, 0, 1912))
	await seconds(1.0)
	# Walk in toward the pond until the ray offers the water, as a player would.
	for k: int in 14:
		if p.interaction.target is WaterSource:
			break
		p.global_position += (Vector3(-262, 0, 1915) - p.global_position).normalized() * Vector3(1, 0, 1)
		p.global_position.y = w.height_at(p.global_position.x, p.global_position.z) + 0.05
		look(Vector3(-262, w.height_at(-262, 1915), 1915))
		await frames(4)
	var ws: WaterSource = p.interaction.target as WaterSource
	if ws != null:
		note("water offered at %.1f m (bottles: %s)" % [p.global_position.distance_to(ws.point), WaterSource._can_fill(p)])
	await snap("pond_aim")
	var dirty0: int = ps.inventory.count_of(&"water_bottle_dirty")
	await use()
	note("pressing it filled %d bottle(s)" % (ps.inventory.count_of(&"water_bottle_dirty") - dirty0))
	await snap("pond_used")
	await face(cpos + Vector3.UP * 0.2, 1.8)
	await snap("campfire_aim_with_stream_water")
	ui.roll.open(&"station", &"campfire")
	await frames(6)
	await snap("campfire_station")
	ex(&"inventory.craft", {"recipe": "boil_water", "station": "campfire"})
	await frames(4)
	await snap("water_boiled")
	ui.close_top_screen()

	# --- Bandage, shelter, sleep ---------------------------------------------------------------------
	ex(&"inventory.craft", {"recipe": "cloth_bandage"})
	await snap("bandage")
	var left_b: Variant = ps.inventory.add_item(&"leaf_bundle", 6)
	note("6 bough bundles into the pack: %s left over, pack %.1f / %.0f" % [left_b, ps.inventory.bulk() if ps.inventory.has_method(&"bulk") else -1.0, ps.inventory.max_bulk])
	ps.inventory.add_item(&"stick", 4)
	var bed_at: Vector3 = spawn + Vector3(-3, 0, 4)
	bed_at.y = w.height_at(bed_at.x, bed_at.z)
	await face(bed_at + Vector3.UP * 0.2, 2.2)
	# --lean-to: the roofed shelter instead of the open bough bed, slept in from under its roof
	# (the cold line a player under a roof sees is its own: sheltered_text).
	var lean_to: bool = OS.get_cmdline_user_args().has("--lean-to")
	if lean_to:
		ps.inventory.add_item(&"stick", 10)
		ps.inventory.add_item(&"cordage", 2)
	var bb: Dictionary = ex(&"build.place_blueprint", {"blueprint": "lean_to" if lean_to else "bough_bed", "pos": [bed_at.x, bed_at.y, bed_at.z], "yaw": 0.0})
	if bb.has("site"):
		ex(&"build.deliver", {"site": bb["site"]})
	await face(bed_at + Vector3.UP * 0.2, 1.8)
	await snap("bed_aim")
	Game.session.clock.set_time(1, 20.5)
	await use()
	if lean_to:
		# Asleep under its roof (it's slept in from outside, where the ray finds it).
		p.global_position = bed_at + Vector3.UP * 0.1
		p.velocity = Vector3.ZERO
		await frames(4)
		var env: Dictionary = w.call(&"survival_env", p.global_position) if w.has_method(&"survival_env") else {}
		note("asleep under the lean-to: sheltered %s, sleeping %s" % [str(env.get("sheltered", "?")), str(w.sleeping)])
	await seconds(1.0)
	await snap("sleeping")
	await wait_until(func() -> bool: return not w.sleeping, 60.0)
	await seconds(1.0)
	if lean_to:
		var env2: Dictionary = w.call(&"survival_env", p.global_position) if w.has_method(&"survival_env") else {}
		note("awake: sheltered %s at %s (the lean-to at %s)" % [str(env2.get("sheltered", "?")), str(p.global_position.round()), str(bed_at.round())])
	await snap("woke")

	# --- The distress call ----------------------------------------------------------------------------
	for s: Dictionary in w.tutorial.steps():
		note("tutorial step %s done=%s" % [s.get("id", "?"), s.get("done", "?")])
	var t: TutorialProgress = ps.tutorial
	note("distress due at %.0f, clock %.0f (game minutes)" % [t.distress_due, Game.session.clock.total_minutes])
	if t.distress_due > 0.0:
		var h: float = Game.session.clock.hour_f() + (t.distress_due - Game.session.clock.total_minutes) / 60.0 + 0.1
		Game.session.clock.set_time(Game.session.clock.day(), h)
	await wait_until(func() -> bool: return t.distress_received, 10.0)
	note("distress received: %s" % t.distress_received)
	await seconds(1.0)
	await snap("distress")
	ui.call(&"_raise_wrist", true)
	await seconds(1.5)
	await snap("tether_after_distress")
	ui.call(&"_raise_wrist", false)

	# --- The Lift 3 wreck and Ezra --------------------------------------------------------------------
	var wreck: Variant = IntroPlayer.shot_target({"poi": "lift3_crash_site", "at": [397, 2315]})
	if wreck is Vector3:
		await face(wreck, 12.0)
		await seconds(2.0)
		await snap("wreck")
	var camp: Vector3 = w.tutorial.camp_position()
	note("Ezra's camp at %s, %.0f m from the drop" % [camp, camp.distance_to(spawn)])
	await face(camp + Vector3.UP * 0.8, 6.0)
	await seconds(2.0)
	var ezra: Node3D = w.companion.get(&"body") as Node3D
	if ezra != null:
		for k: int in 16:
			var d := Vector3(cos(k * TAU / 8.0), 0, sin(k * TAU / 8.0))
			await face(ezra.global_position + Vector3.UP * (0.9 if k < 8 else 0.5), 1.6, ezra.global_position + d)
			if p.interaction.target != null and p.interaction.prompt != "":
				break
		var tgt: Object = p.interaction.target
		note("aiming at Ezra the ray finds %s" % (str(tgt) if tgt != null else "nothing"))
		await snap("ezra_aim")
		await use()
		await frames(6)
		await snap("ezra_talk")
		ex(&"companion.recruit", {})
		await frames(6)
		await snap("ezra_recruited")
		var cs: Node = w.companion.get(&"screen") as Node
		note("Esc/B through GameUI closes Ezra's card: %s" % ui.close_top_screen())
		if cs != null and is_instance_valid(cs) and (cs as Control).visible:
			note("Ezra's card still open after close_top_screen (pad B dead end)")
			cs.call(&"close_screen")
	else:
		note("Ezra has no body at his camp")
		await snap("camp")

	# --- A house in Pell's Crossing ------------------------------------------------------------------
	var house: Node3D = null
	for id: Variant in (w.pois.get(&"instances") as Dictionary).keys():
		var n: Node3D = (w.pois.get(&"instances") as Dictionary)[id] as Node3D
		if n != null and String(id).begins_with("pell") and n.get(&"layout") != null and String((n.get(&"layout") as PoiLayout).def.id).contains("house"):
			house = n
			break
	if house != null:
		note("house: %s" % house.name)
		var props: Array = house.find_children("*", "Node3D", true, false).filter(func(n: Node) -> bool: return n is PoiPieces.LootProp)
		note("%d containers in it" % props.size())
		if not props.is_empty():
			var c: Node3D = props[0]
			for k: int in 4:
				var d := Vector3(cos(k * PI / 2.0), 0, sin(k * PI / 2.0))
				await face(c.global_position + Vector3.UP * 0.4, 1.2, c.global_position + d)
				p.global_position.y = c.global_position.y + 0.1
				look(c.global_position + Vector3.UP * 0.4)
				await frames(6)
				if p.interaction.target == c:
					break
			await snap("container_aim")
			await use()
			await frames(6)
			var cinv: Inventory = c.get(&"inventory") as Inventory
			note("container holds %s; roll mode %s, flap empty line %s" % [str(cinv.stacks.map(func(x: ItemStack) -> String: return "%s x%d" % [x.item_id, x.count])) if cinv != null else "no inventory",
				ui.roll.mode, (ui.roll.get(&"_flap_empty") as Label).visible])
			await snap("container_open")
			ui.close_top_screen()
	else:
		note("no Pell's Crossing house found")

	# --- A note, the map ----------------------------------------------------------------------------
	var note_id: StringName = &"lift3_kneeboard"
	ps.inventory.add_item(StringName("note_" + String(note_id)), 1) if Content.item(StringName("note_" + String(note_id))) != null else null
	ui.show_note(note_id)
	await frames(6)
	await snap("note")
	ui.close_top_screen()
	ui.world_map.open()
	await wait_until(func() -> bool: return int(ui.world_map.get(&"_task")) < 0, 30.0)
	await frames(6)
	await snap("map")
	ui.close_top_screen()

	# --- Death and respawn ----------------------------------------------------------------------------
	var hurt := DamageInfo.make(500.0, &"slash", &"melee", &"")
	hurt.hit_pos = p.global_position + Vector3.UP
	p.take_damage(hurt)
	await seconds(2.0)
	await snap("death")
	var btn: Button = ui.get(&"_death_button") as Button
	if btn != null and btn.visible:
		btn.pressed.emit()
	await seconds(3.0)
	_note_shelter("respawned")
	await snap("respawned")

	# --- Save and continue ---------------------------------------------------------------------------
	ui.toggle_pause()
	await frames(6)
	await snap("pause")
	ui.toggle_pause()
	Game.save_game("qa_first_hour")
	await frames(4)
	await snap("saved")
	var old: int = w.get_instance_id()
	Game.load_game("qa_first_hour")
	await seconds(2.0)
	ui = (game.world as Node).get(&"ui") as GameUI if game.get(&"world") != null else ui
	await snap("continue_loading")
	await wait_until(func() -> bool: return game.get(&"world") != null and is_instance_valid(game.world) and game.world.get_instance_id() != old and bool(game.world.is_ready), 900.0)
	w = game.world
	p = w.player
	ui = w.ui
	await seconds(3.0)
	_note_shelter("continued")
	await snap("continued")
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.has("--through") and (args.has("hum") or args.has("day21")):
		await _week()
	if args.has("--through") and args.has("day21"):
		await _midgame()
	_finish()


# --- The first week (--through hum) --------------------------------------------------------------

## Day 2 to the morning after the first Hum: building, the trader, Ezra's orders, hunting, a cave,
## the supply drop, levelling, the Hum's warnings, the night and the morning after.
func _week() -> void:
	var ps: PlayerState = p.state
	Settings.sound_captions = true
	# The driver teleports (into a cave, out of it): blows and falls would be its own doing, so
	# the player takes none this week. Cold, hunger and thirst still count.
	p.god_mode = true
	ps.inventory.add_item(&"log", 2)
	for kv: Array in [["stick", 20], ["stone", 12], ["plant_fiber", 12], ["leaf_bundle", 8], ["cordage", 4], ["nails", 20], ["claw_hammer", 1]]:
		if Content.item(StringName(kv[0])) != null:
			ps.inventory.add_item(StringName(kv[0]), int(kv[1]))
	var base: Vector3 = p.global_position + Vector3(6, 0, 0)
	base.y = w.height_at(base.x, base.z)

	# --- Building ---------------------------------------------------------------------------------
	await face(base + Vector3.UP * 0.5, 4.0)
	ui.manual.open("build")
	await frames(4)
	await snap("w_build_menu")
	ui.close_top_screen()
	var b: BuildingManager = w.building
	note("begin placement lean_to: %s" % b.begin_placement(&"lean_to"))
	await frames(10)
	await snap("w_ghost_lean_to")
	note("placement hint: '%s'" % b.placement_hint())
	b.handle_primary(p)
	await frames(6)
	await snap("w_lean_to_placed")
	b.cancel_placement()
	for site: Node in get_tree().get_nodes_in_group(&"blueprint_sites"):
		await face((site as Node3D).global_position + Vector3.UP * 0.5, 2.2)
		await snap("w_lean_to_site_aim")
		await use()
		await snap("w_lean_to_site_filled")
		break
	# Freeform logs: one on the ground, one carried to snap onto it.
	var lpos: Vector3 = base + Vector3(-2, 0, 3)
	await face(lpos, 2.5)
	ps.inventory.add_item(&"log", 2)
	note("place a carried log: %s" % b.try_place_carried(p))
	await frames(6)
	await snap("w_log_placed")
	note("second log (snaps onto the first): %s" % b.try_place_carried(p))
	await frames(6)
	await snap("w_log_snapped")
	# Damage one piece and look at it with the hammer out: the repair prompt.
	var pieces: Array = b.pieces.values()
	if not pieces.is_empty():
		var piece: StructurePiece = pieces[0]
		var hit := DamageInfo.make(40.0, &"blunt", &"melee", &"")
		hit.hit_pos = piece.global_position
		b.damage_piece(piece, hit)
		var hs: int = ps.toolbelt.find(&"claw_hammer")
		if hs < 0:
			ps.toolbelt[3] = &"claw_hammer"
			hs = 3
		p.equipment.select_slot(hs)
		await face(piece.global_position + Vector3.UP * 0.3, 2.0)
		await snap("w_repair_aim")
		await use()
		await snap("w_repaired")

	# --- The trader at Waystation 9 -------------------------------------------------------------------
	var tm: Node = w.get(&"traders")
	var posts: Dictionary = tm.get(&"posts") if tm != null else {}
	note("trader posts: %s" % str(posts.keys()))
	if not posts.is_empty():
		var post: Dictionary = posts[posts.keys()[0]]
		var td: TraderDef = post["def"]
		await face((post["pos"] as Vector3) + Vector3.UP * 1.2, 3.0)
		await seconds(1.0)
		await snap("w_trader_aim")
		ps.inventory.add_item(&"scrip", 200)
		ps.inventory.add_item(&"huckleberries", 4)
		tm.call(&"open_screen", str(post["id"]), "shop")
		await frames(6)
		await snap("w_trader_buy")
		var st: Dictionary = tm.call(&"stock_of", td.id, str(post["id"]))
		note("stock: %s" % str(st.keys().slice(0, 8)))
		if not st.is_empty():
			ex(&"trade.buy", {"trader": String(td.id), "item": str(st.keys()[0]), "count": 1})
		ex(&"trade.sell", {"trader": String(td.id), "item": "huckleberries", "count": 2})
		await frames(4)
		await snap("w_trader_after_trade")
		ui.close_top_screen()
		tm.call(&"open_screen", str(post["id"]), "board")
		await frames(6)
		await snap("w_trader_board")
		var offers: Array = tm.call(&"board_offers", ps, td)
		note("board offers: %d" % offers.size())
		if not offers.is_empty():
			ex(&"contract.accept", {"trader": String(td.id), "offer": str((offers[0] as Dictionary).get("id", ""))})
			await frames(4)
			await snap("w_contract_accepted")
		ui.close_top_screen()

	# --- Ezra's orders ----------------------------------------------------------------------------
	var cd: Node = w.companion
	var ezra: Node3D = cd.get(&"body") as Node3D
	if ezra != null:
		await face(ezra.global_position + Vector3.UP * 0.9, 2.0)
		await snap("w_ezra_aim")
		cd.call(&"open_card")
		await frames(6)
		await snap("w_ezra_card")
		ui.close_top_screen()
		for order: String in ["follow", "gather", "guard", "stay"]:
			ex(&"companion.order", {"order": order})
			await seconds(2.0)
			await snap("w_ezra_" + order)
	else:
		note("Ezra has no body after the Continue")

	# --- Hunting -------------------------------------------------------------------------------------
	ps.inventory.add_item(&"hunting_bow", 1)
	ps.inventory.add_item(&"arrow_stone", 10)
	ps.inventory.add_item(&"kitchen_knife", 1)
	var bslot: int = ps.toolbelt.find(&"hunting_bow")
	if bslot < 0:
		ps.toolbelt[4] = &"hunting_bow"
		bslot = 4
	p.equipment.select_slot(bslot)
	var wm: WildlifeManager = w.get(&"wildlife") as WildlifeManager
	var deer_def := Content.get_def(&"wildlife", &"white_tailed_deer") as WildlifeDef
	if wm != null and deer_def != null:
		var at: Vector3 = p.global_position + Vector3(0, 0, -14)
		var herd: Array = wm.spawn_band(deer_def, {"id": &"qa:first_week", "def": deer_def.id, "pos": Vector2(at.x, at.z), "count": 1, "seed": 7})
		if not herd.is_empty():
			var deer: Node3D = herd[0]
			look(deer.global_position + Vector3.UP * 0.8)
			await frames(6)
			await snap("w_bow_aim")
			p.equipment.primary()
			await seconds(1.5)
			await snap("w_bow_shot")
			if is_instance_valid(deer) and deer.has_method(&"take_damage"):
				var kill := DamageInfo.make(500.0, &"pierce", &"ranged", ps.id)
				kill.hit_pos = deer.global_position + Vector3.UP * 0.8
				deer.call(&"take_damage", kill)
			await seconds(2.0)
			if is_instance_valid(deer):
				await face(deer.global_position + Vector3.UP * 0.4, 1.6)
				note("butcher prompt at %.1f m from the carcass" % p.global_position.distance_to(deer.global_position))
				await snap("w_carcass_aim")
				await use()
				await seconds(1.0)
				await snap("w_butchered")
	else:
		note("no wildlife manager or deer def")

	# --- A cave ----------------------------------------------------------------------------------------
	var caves: Object = w.terrain.get(&"caves")
	var plans: Array = caves.get(&"plans") if caves != null else []
	note("caves planned: %d" % plans.size())
	if not plans.is_empty():
		var cp: CavePlan = plans[0]
		var mouth: Vector3 = cp.mouth.origin
		var outside: Vector3 = mouth + cp.mouth.basis.z * 8.0
		outside.y = w.height_at(outside.x, outside.z)
		p.global_position = outside + Vector3.UP * 0.1
		await _stream(p.global_position)
		await seconds(3.0)
		look(mouth + Vector3.UP * 1.0)
		await frames(6)
		await snap("w_cave_mouth")
		if cp.spine.size() > 0:
			var deep: Vector3 = cp.spine[cp.spine.size() - 1]
			deep.y = cp.floor_y[cp.floor_y.size() - 1] + 0.1
			p.global_position = deep
			await _stream(deep)
			look(mouth + Vector3.UP * 1.5)
			await seconds(2.0)
			await snap("w_cave_inside")

	# --- The supply drop ---------------------------------------------------------------------------------
	var drops: SupplyDrops = w.get(&"supply_drops") as SupplyDrops
	if drops != null:
		p.global_position = base + Vector3(0, 0.5, 4)
		await _stream(p.global_position)
		var did: StringName = drops.dispatch(Game.session.clock.day())
		note("supply drop dispatched: %s" % did)
		await seconds(3.0)
		await snap("w_drop_incoming")
		for d: SupplyDrops.Drop in drops.drops.values():
			for i: int in 30:
				if d.landed:
					break
				d._process(10.0)
				await frames(1)
			await frames(4)
			var crate: Node3D = d.get(&"crate") as Node3D
			note("drop landed: %s, crate %s" % [d.landed, crate != null])
			await face((crate.global_position if crate != null else d.global_position) + Vector3.UP * 0.5, 1.8)
			await snap("w_drop_landed_aim")
			await use()
			await snap("w_drop_opened")
			ui.close_top_screen()
			break

	# --- Levelling ------------------------------------------------------------------------------------------
	ps.progression.skill_points += 2
	ui.manual.open("record")
	await frames(6)
	await snap("w_record")
	ex(&"progression.raise_attribute", {"attribute": "sinew"})
	await frames(4)
	await snap("w_record_after_point")
	ui.close_top_screen()

	# --- The Hum ----------------------------------------------------------------------------------------------
	p.global_position = base + Vector3(0, 0.5, 3)
	await _stream(p.global_position)
	# The night before, outside with no fire, the cold kills (finding: the first run froze); the
	# audit wants the Hum's screens, so the player is kept alive from here.
	note("health %.0f, warmth %s before the night" % [ps.stats.health, str(ps.stats.get(&"body_temp")) if ps.stats.get(&"body_temp") != null else "?"])
	p.god_mode = true
	# Days were skipped, not lived: fed and watered as a player who lived them would be.
	ps.stats.hydration = 100.0
	ps.stats.fullness = 100.0
	ps.stats.health = ps.stats.max_health if ps.stats.get(&"max_health") != null else 100.0
	var hum_day: int = Game.session.clock.next_horde_day(Game.session.clock.day())
	note("first Hum on day %d (now day %d)" % [hum_day, Game.session.clock.day()])
	# Through the day before and the day itself on the clock, as play would: the warnings fire as
	# their hours pass (setting the time jumps over them).
	Game.session.clock.set_time(hum_day - 1, 18.0)
	var marks: Dictionary = {}
	while Game.session.clock.day() < hum_day or Game.session.clock.hour_f() < 21.9:
		w.clock_driver.advance(30.0)
		# A player drinks and eats through a day (a day without water kills: finding W18).
		ps.stats.hydration = maxf(ps.stats.hydration, 60.0)
		ps.stats.fullness = maxf(ps.stats.fullness, 60.0)
		await frames(2)
		var tag: String = "w_hum_d%d_%02d" % [Game.session.clock.day() - hum_day, Game.session.clock.hour()]
		if not _msgs.is_empty() and not marks.has(tag):
			marks[tag] = true
			await snap(tag)
	# And a fire, as a player should have by now: god mode stops blows, not the cold.
	ps.inventory.add_item(&"stone", 6)
	ps.inventory.add_item(&"stick", 8)
	var fire_at: Vector3 = p.global_position + Vector3(1.6, 0, 0)
	fire_at.y = w.height_at(fire_at.x, fire_at.z)
	var fb: Dictionary = ex(&"build.place_blueprint", {"blueprint": "campfire", "pos": [fire_at.x, fire_at.y, fire_at.z], "yaw": 0.0})
	if fb.has("site"):
		ex(&"build.deliver", {"site": fb["site"]})
	for piece: StructurePiece in w.building.pieces_in_radius(fire_at, 2.0):
		if piece.provides("light"):
			piece.set_lit(true)
			ps.inventory.add_item(&"stick", 6)
			for i: int in 6:
				ex(&"build.add_fuel", {"piece": String(piece.piece_id)})
	ps.stats.hydration = 100.0
	ps.stats.fullness = 100.0
	w.clock_driver.advance(20.0)
	await seconds(3.0)
	await snap("w_hum_start")
	var ai: AIDirector = w.ai
	await wait_until(func() -> bool: return ai.hum.members.size() > 0, 30.0)
	await seconds(4.0)
	await snap("w_hum_wave1")
	# The night on the clock, 15 minutes at a time: every wave comes (a jump to dawn skipped
	# waves 2-4), and the player puts down whatever reaches them.
	var seen: Dictionary = {}
	var shot: Dictionary = {}
	while ai.hum.active and not (Game.session.clock.day() > hum_day and Game.session.clock.hour_f() >= 4.5):
		w.clock_driver.advance(15.0)
		ps.stats.hydration = maxf(ps.stats.hydration, 60.0)
		ps.stats.fullness = maxf(ps.stats.fullness, 60.0)
		await seconds(1.0)
		for id: StringName in ai.hum.members.keys():
			seen[id] = true
			var e: Enemy = ai.hum.members[id]["node"]
			if is_instance_valid(e) and e.is_alive() and e.global_position.distance_to(p.global_position) < 12.0:
				var k := DamageInfo.make(999.0, &"blunt", &"melee", ps.id)
				k.hit_pos = e.global_position + Vector3.UP
				e.take_damage(k)
		var hour: int = Game.session.clock.hour()
		if not shot.has(hour) and (not _msgs.is_empty() or hour in [23, 1, 3]):
			shot[hour] = true
			await snap("w_hum_night_%02d" % hour)
	note("Hum night: %d Hollowed seen across its waves; player alive at dawn: %s (health %.0f)" % [seen.size(), ps.stats.alive, ps.stats.health])
	Game.session.clock.set_time(Game.session.clock.day(), maxf(Game.session.clock.hour_f(), 3.9))
	w.clock_driver.advance(12.0)
	await seconds(4.0)
	await snap("w_hum_dawn")
	Game.session.clock.set_time(hum_day + 1, 7.0)
	w.clock_driver.advance(5.0)
	await seconds(3.0)
	await snap("w_morning_after")
	ui.manual.open("record")
	await frames(6)
	await snap("w_morning_record")
	ui.close_top_screen()


# --- The mid game (--through day21) ---------------------------------------------------------------

## Keeps the player fed and watered over skipped days (the audit is about the screens, not the
## driver's diet) and keeps damage off them (god mode, stated in the audit).
func _sustain() -> void:
	var ps: PlayerState = p.state
	ps.stats.hydration = maxf(ps.stats.hydration, 70.0)
	ps.stats.fullness = maxf(ps.stats.fullness, 70.0)
	if ps.stats.has_method(&"revive") and not ps.stats.alive:
		note("the player was dead: revived to go on (%s)" % str(ps.stats.get(&"last_cause")))
		ps.stats.revive(100.0)


func _teleport(at: Vector3) -> void:
	at.y = w.height_at(at.x, at.z) + 0.3
	p.global_position = at
	p.velocity = Vector3.ZERO
	await _stream(at)
	await seconds(3.0)


## Where the player stands and whether survival_env counts it as under a roof (the cold line says
## "Light a fire" there, "Find shelter or a fire" in the open).
func _note_shelter(when: String) -> void:
	var env: Dictionary = w.call(&"survival_env", p.global_position) if w.has_method(&"survival_env") else {}
	note("%s: sheltered %s at %s" % [when, str(env.get("sheltered", "?")), str(p.global_position.round())])


## Streams the world in around a spot the player was just moved to and waits until the chunks
## around it have their meshes and collision: a frame taken before then shows streaming gaps that
## read like terrain bugs (World's W9 note).
func _stream(at: Vector3) -> void:
	w.terrain.update_streaming(at, true)
	if not await wait_until(func() -> bool: return w.terrain.is_ready_around(at, 1), 30.0):
		note("terrain not ready around %s after 30 s" % str(at.round()))


func _kill_near(at: Vector3, r: float) -> int:
	var n: int = 0
	for e: Node in get_tree().get_nodes_in_group(&"enemies"):
		var en := e as Enemy
		if en != null and is_instance_valid(en) and en.is_alive() and en.global_position.distance_to(at) < r:
			var k := DamageInfo.make(999.0, &"blunt", &"melee", p.state.id)
			k.hit_pos = en.global_position + Vector3.UP
			en.take_damage(k)
			n += 1
	return n


func _building(def_id: String) -> Dictionary:
	for b: Dictionary in w.pois.call(&"all_buildings"):
		if String(b.get("def", "")) == def_id:
			return b
	return {}


## Clears a building room by room as a player would: in at its door, each sleeper put down where
## it lies, until the POI calls itself cleared.
func _clear(def_id: String, tag: String) -> void:
	var b: Dictionary = _building(def_id)
	if b.is_empty():
		note("%s: no such building on this map" % def_id)
		return
	await _teleport(b["pos"] + Vector3(0, 0, 0))
	await wait_until(func() -> bool: return w.pois.instances.has(StringName(str(b["id"]))), 60.0)
	var inst: PoiInstance = w.pois.instances.get(StringName(str(b["id"])))
	if inst == null:
		note("%s: not built after 60 s" % def_id)
		return
	await seconds(3.0)
	look(inst.global_position + Vector3.UP * 1.5)
	await snap(tag + "_arrive")
	var total: int = inst.layout.sleepers.size()
	note("%s (tier %d): %d sleepers; spawned %s, bodies %d, enemies in group %d" % [inst.layout.def.display_name, inst.tier, total,
		inst.sleepers_spawned, (inst.get(&"_sleepers") as Dictionary).size(), get_tree().get_nodes_in_group(&"enemies").size()])
	for i: int in 30:
		if bool(inst.state.get("cleared", false)):
			break
		var live: Array = []
		for sid: Variant in (inst.get(&"_sleepers") as Dictionary).keys():
			var en: Enemy = inst.call(&"sleeper", str(sid)) as Enemy
			if en != null and is_instance_valid(en) and en.is_alive():
				live.append(en)
		if live.is_empty():
			# Sleepers rise only near the player: walk the building's levels.
			var cells: Array = inst.layout.sleepers
			if i < cells.size():
				var sp: Dictionary = cells[i]
				var lp: Vector3 = inst.global_transform * inst.layout.cell_center(int(sp.get("level", 0)), sp.get("cell", Vector2i.ZERO))
				p.global_position = lp + Vector3.UP * 0.3
				await _stream(lp)
			await seconds(2.0)
			continue
		var en: Enemy = live[0]
		await face(en.global_position + Vector3.UP * 1.2, 2.0)
		if i < 2:
			await snap("%s_fight_%d" % [tag, i])
		var kd := DamageInfo.make(999.0, &"blunt", &"melee", p.state.id)
		kd.hit_pos = en.global_position + Vector3.UP
		en.take_damage(kd)
		await seconds(1.0)
	note("%s cleared: %s (%d of %d dead)" % [def_id, inst.state.get("cleared", false), (inst.state.get("dead", []) as Array).size(), total])
	await snap(tag + "_cleared")


func _place(bp: String, at: Vector3) -> StringName:
	at.y = w.height_at(at.x, at.z)
	# Logs ride on the shoulder, two at a time: fetched again for each piece.
	p.state.inventory.add_item(&"log", maxi(0, 2 - p.state.inventory.count_of(&"log")))
	await face(at + Vector3.UP * 0.4, 2.4)
	var r: Dictionary = ex(&"build.place_blueprint", {"blueprint": bp, "pos": [at.x, at.y, at.z], "yaw": 0.0})
	if not r.has("site"):
		return &""
	var d: Dictionary = ex(&"build.deliver", {"site": r["site"]})
	await frames(4)
	if not bool(d.get("complete", false)):
		note("%s: not complete after delivering (%s); prompt: '%s'" % [bp, str(d), p.interaction.prompt])
	for piece: StructurePiece in w.building.pieces_in_radius(at, 2.5):
		if piece.def != null and String(piece.def.id).begins_with(bp):
			return piece.piece_id
	return &""


func _midgame() -> void:
	var ps: PlayerState = p.state
	p.god_mode = true
	Settings.sound_captions = true
	note("mid game from day %d (god mode on: the audit wants every screen, not a run's end)" % Game.session.clock.day())
	Game.session.clock.set_time(maxi(Game.session.clock.day(), 8), 8.0)
	_sustain()
	ps.inventory.max_bulk = maxf(ps.inventory.max_bulk, 400.0)
	ps.inventory.add_item(&"stone_axe", 1)
	for kv: Array in [["log", 2], ["stick", 40], ["stone", 30], ["nails", 80], ["plant_fiber", 20], ["cordage", 10], ["gas_can", 4],
			["copper_wire", 4], ["scrap_metal", 60], ["leaf_bundle", 12], ["torch", 2], ["seed_potato", 4], ["carrot_seeds", 4],
			["water_bottle_dirty", 2], ["claw_hammer", 1], ["planks", 20], ["cloth", 12], ["small_engine", 1], ["electrical_parts", 12],
			["light_bulb", 4], ["duct_tape", 4]]:
		if Content.item(StringName(kv[0])) != null:
			ps.inventory.add_item(StringName(kv[0]), int(kv[1]))
	ps.inventory.max_bulk = maxf(ps.inventory.max_bulk, 400.0)
	for bid: String in ["generator", "floodlight", "nail_sentry"]:
		ps.progression.known_blueprints[StringName(bid)] = true
	ps.progression.skill_points += 6

	# --- Perks and the Record -----------------------------------------------------------------------
	for attr: String in ["sinew", "wits"]:
		ex(&"progression.raise_attribute", {"attribute": attr})
	for perk: String in ["packhorse", "timberwright", "scavenger", "handy"]:
		ex(&"progression.buy_perk", {"perk": perk})
	ui.manual.open("record")
	await frames(6)
	await snap("m_record_perks")
	ui.close_top_screen()

	# --- A base: defences, power, a workbench, a garden -----------------------------------------------
	var base: Vector3 = w.drop_site() + Vector3(10, 0, 10)
	await _teleport(base)
	var pieces: Dictionary = {}
	var spots: Dictionary = {"workbench": Vector3(0, 0, -4), "spike_pit": Vector3(8, 0, 0), "deadfall": Vector3(-8, 0, 0), "tripwire_bell": Vector3(0, 0, 8),
		"generator": Vector3(4, 0, -6), "work_light": Vector3(6, 0, -3), "floodlight": Vector3(-5, 0, -5), "nail_sentry": Vector3(3, 0, 5),
		"garden_bed": Vector3(-4, 0, 5), "rain_catcher": Vector3(-7, 0, 4)}
	for bp: String in spots:
		pieces[bp] = await _place(bp, base + spots[bp])
		if String(pieces[bp]) != "":
			await snap("m_built_" + bp)
	note("base pieces: %s" % str(pieces))
	# Power: fuel, wire, switch on.
	if String(pieces.get("generator", "")) != "":
		var g: StringName = pieces["generator"]
		await face(base + spots["generator"] + Vector3.UP * 0.5, 2.0)
		await snap("m_generator_aim")
		ex(&"power.fuel", {"piece": String(g)})
		for to: String in ["work_light", "nail_sentry", "floodlight"]:
			if String(pieces.get(to, "")) != "":
				ex(&"power.wire", {"from": String(g), "to": String(pieces[to])})
		ex(&"power.toggle", {"piece": String(g)})
		if String(pieces.get("nail_sentry", "")) != "":
			await face(base + spots["nail_sentry"] + Vector3.UP * 0.6, 1.8)
			ex(&"power.load", {"piece": String(pieces["nail_sentry"])})
			await snap("m_sentry_loaded")
		await frames(6)
		await face(base + spots["work_light"] + Vector3.UP * 0.8, 2.2)
		await snap("m_power_on")
	# Workbench crafting.
	if String(pieces.get("workbench", "")) != "":
		await face(base + spots["workbench"] + Vector3.UP * 0.8, 1.8)
		await snap("m_workbench_aim")
		ui.roll.open(&"station", &"workbench")
		await frames(6)
		await snap("m_workbench_roll")
		for rec: String in ["bucket", "repair_kit", "saw_planks"]:
			ex(&"inventory.craft", {"recipe": rec, "station": "workbench"})
		await frames(4)
		await snap("m_workbench_crafted")
		ui.close_top_screen()
	# The garden and the rain.
	if String(pieces.get("garden_bed", "")) != "":
		var gb: String = String(pieces["garden_bed"])
		await face(base + spots["garden_bed"] + Vector3.UP * 0.3, 1.8)
		await snap("m_garden_aim")
		ex(&"farm.plant", {"piece": gb, "seed": "seed_potato"})
		ex(&"farm.plant", {"piece": gb, "seed": "carrot_seeds"})
		ex(&"farm.water", {"piece": gb})
		await frames(4)
		await snap("m_garden_planted")
		if Game.session.get(&"weather") != null and Game.session.weather.has_method(&"force"):
			Game.session.weather.force(&"rain")
		for h: int in 12:
			w.clock_driver.advance(60.0)
			_sustain()
			await frames(2)
		await face(base + spots["garden_bed"] + Vector3.UP * 0.3, 1.8)
		await snap("m_garden_after_rain")
		if String(pieces.get("rain_catcher", "")) != "":
			await face(base + spots["rain_catcher"] + Vector3.UP * 0.6, 1.8)
			await snap("m_rain_catcher_aim")
			ex(&"farm.draw_water", {"piece": String(pieces["rain_catcher"])})
			await snap("m_rain_catcher_drawn")

	# --- Ezra on errands ------------------------------------------------------------------------------
	var cd: Node = w.companion
	if cd != null and cd.get(&"body") != null:
		ex(&"companion.order", {"order": "gather", "kind": "wood"})
		for h: int in 6:
			w.clock_driver.advance(30.0)
			_sustain()
			await frames(10)
		await snap("m_ezra_gathered")
		ex(&"companion.store", {})
		await seconds(2.0)
		await snap("m_ezra_stored")
		ex(&"companion.order", {"order": "follow"})
	else:
		note("Ezra has no body here (not recruited in this run)")

	# --- The Ashen ------------------------------------------------------------------------------------
	var ash: Node = w.ashen
	if ash != null and bool(ash.call(&"enabled")):
		var scout: Node = ash.call(&"send_scout", p)
		await seconds(3.0)
		if scout != null and is_instance_valid(scout):
			look((scout as Node3D).global_position + Vector3.UP * 1.5)
			await frames(6)
		await snap("m_ashen_scout")
		_kill_near(p.global_position, 200.0)
		ash.call(&"debug_raid", 4)
		await seconds(4.0)
		await snap("m_ashen_raid")
		# A torch held up at them.
		ps.inventory.add_item(&"torch", 1)
		var ts: int = ps.toolbelt.find(&"torch")
		if ts < 0:
			ps.toolbelt[5] = &"torch"
			ts = 5
		p.equipment.select_slot(ts)
		await frames(6)
		if p.equipment.has_method(&"toggle_light"):
			p.equipment.toggle_light()
		for e: Node in get_tree().get_nodes_in_group(&"enemies"):
			if (e as Enemy) != null and (e as Enemy).def != null and String((e as Enemy).def.id).begins_with("ashen"):
				look((e as Node3D).global_position + Vector3.UP * 1.5)
				break
		await seconds(4.0)
		await snap("m_ashen_torch")
		_kill_near(p.global_position, 200.0)
		await seconds(3.0)
		await snap("m_ashen_after")
	else:
		note("the Ashen are off on these rules")

	# --- Contracts over several days --------------------------------------------------------------------
	var tm: Node = w.traders
	var post: Dictionary = (tm.get(&"posts") as Dictionary).values()[0] if tm != null and not (tm.get(&"posts") as Dictionary).is_empty() else {}
	if not post.is_empty():
		var td: TraderDef = post["def"]
		await _teleport(post["pos"] + Vector3(3, 0, 3))
		var offers: Array = tm.call(&"board_offers", ps, td)
		note("board offer keys: %s" % (str((offers[0] as Dictionary).keys()) if not offers.is_empty() else "none"))
		for o: Dictionary in offers:
			var qid: String = str(o.get("def", ""))
			note("offer: %s (%s) -> %s" % [o.get("name", "?"), qid, str(o.get("target", ""))])
			if qid.contains("clear") or qid.begins_with("fetch"):
				ex(&"contract.accept", {"trader": String(td.id), "offer": str(o.get("id", ""))})
		tm.call(&"open_screen", str(post["id"]), "board")
		await frames(6)
		await snap("m_contracts_taken")
		ui.close_top_screen()

	# --- Dungeons ---------------------------------------------------------------------------------------
	_sustain()
	await _clear("pell_crossing_school", "m_school")
	_sustain()
	await _clear("larch_hollow_sawmill", "m_sawmill")
	# The adit: its mouth and its buried levels.
	var adit: Dictionary = _building("corvane_larkspur_adit")
	if not adit.is_empty():
		await _teleport(adit["pos"] + Vector3(0, 0, 8))
		look(adit["pos"] + Vector3.UP * 2.0)
		await seconds(2.0)
		await snap("m_adit_mouth")
		var ai2: PoiInstance = w.pois.instances.get(StringName(str(adit["id"])))
		if ai2 != null:
			note("adit levels: %d, sleepers %d" % [ai2.layout.levels.size() if ai2.layout.get(&"levels") != null else -1, ai2.layout.sleepers.size()])
	# Turn in what's ready.
	if not post.is_empty():
		var td2: TraderDef = post["def"]
		for c: Variant in ps.contracts.active:
			var cdict: Dictionary = c
			if str(cdict.get("state", "")) == "ready":
				ex(&"contract.turn_in", {"trader": String(td2.id), "contract": str(cdict["id"]), "remote": true})
		await frames(4)
		await snap("m_contracts_after")

	# --- Hounds, wolves, a nest ------------------------------------------------------------------------
	await _teleport(base + Vector3(0, 0, 20))
	for i: int in 3:
		var at: Vector3 = p.global_position + Vector3(10 + i * 2, 0, -6)
		at.y = w.height_at(at.x, at.z)
		w.ai.spawn(&"hollow_hound", at, {"authored": true})
	await seconds(2.0)
	look(p.global_position + Vector3(11, 0.5, -6))
	await frames(6)
	await snap("m_hounds")
	_kill_near(p.global_position, 60.0)
	var wolf_at: Vector3 = p.global_position + Vector3(-12, 0, -8)
	wolf_at.y = w.height_at(wolf_at.x, wolf_at.z)
	var wolf: Node = w.ai.spawn(&"grey_wolf", wolf_at, {"authored": true})
	note("a grey wolf spawned: %s" % (wolf != null))
	await seconds(2.0)
	look(wolf_at + Vector3.UP * 0.6)
	await frames(6)
	await snap("m_wolf")
	_kill_near(p.global_position, 60.0)
	await _teleport(Vector3(268, 0, 1694) + Vector3(8, 0, 8))
	look(Vector3(268, w.height_at(268, 1694) + 1.0, 1694))
	await seconds(3.0)
	await snap("m_nest")

	# --- The second and third Hums --------------------------------------------------------------------
	for hum_day: int in [Game.session.clock.next_horde_day(maxi(Game.session.clock.day(), 8)), 0]:
		if hum_day == 0:
			hum_day = Game.session.clock.next_horde_day(Game.session.clock.day() + 1)
		await _teleport(base + Vector3(0, 0, 2))
		Game.session.clock.set_time(hum_day, 21.9)
		_sustain()
		w.clock_driver.advance(10.0)
		await seconds(2.0)
		var ai: AIDirector = w.ai
		await wait_until(func() -> bool: return ai.hum.active, 30.0)
		var at2: Vector3 = base + Vector3(14, 0, 0)
		at2.y = w.height_at(at2.x, at2.z)
		var ram: Node = ai.spawn(&"rammer", at2, {"authored": true, "target": base})
		note("Hum on day %d; a Rammer joins: %s" % [hum_day, ram != null])
		await seconds(3.0)
		await snap("m_hum%d_start" % hum_day)
		var seen: Dictionary = {}
		var shot_n: int = 0
		while ai.hum.active and Game.session.clock.day() <= hum_day + 1:
			w.clock_driver.advance(15.0)
			_sustain()
			await seconds(1.0)
			for id: StringName in ai.hum.members.keys():
				seen[id] = true
			if not _msgs.is_empty() and shot_n < 4:
				shot_n += 1
				await snap("m_hum%d_night_%02d" % [hum_day, Game.session.clock.hour()])
			_kill_near(p.global_position, 10.0)
		note("Hum %d: %d came" % [hum_day, seen.size()])
		# The morning: what's broken, a repair.
		var damaged: Array = []
		for pc: StructurePiece in w.building.pieces_in_radius(base, 20.0):
			if pc.hp < pc.max_hp() - 0.5:
				damaged.append(pc)
		note("after Hum %d: %d of %d pieces damaged" % [hum_day, damaged.size(), w.building.pieces_in_radius(base, 20.0).size()])
		if not damaged.is_empty():
			var hs: int = ps.toolbelt.find(&"claw_hammer")
			if hs < 0:
				ps.toolbelt[3] = &"claw_hammer"
				hs = 3
			p.equipment.select_slot(hs)
			await face((damaged[0] as Node3D).global_position + Vector3.UP * 0.4, 2.0)
			await snap("m_hum%d_repair_aim" % hum_day)
			for kv: Array in [["log", 2], ["stick", 10], ["cordage", 4], ["nails", 20], ["stone", 10]]:
				ps.inventory.add_item(StringName(kv[0]), int(kv[1]))
			ex(&"build.repair", {"piece": String((damaged[0] as StructurePiece).piece_id)})
		await seconds(3.0)
		await snap("m_hum%d_morning" % hum_day)


# --- The mid game's gaps (--gaps): routes walked, the adit inside, a wolf pack, a Murmur -------------

## Walks a building's intended route (its `route` cells, in order, on each one's level): at each
## point the screen's words are logged, every third point framed, and whatever the ray offers
## used (doors, keycard readers, hatches). Then its sleepers are put down (_clear).
func _walk_route(def_id: String, tag: String) -> void:
	var b: Dictionary = _building(def_id)
	if b.is_empty():
		note("%s: not in this world" % def_id)
		return
	await _teleport(b["pos"])
	await wait_until(func() -> bool: return w.pois.instances.has(StringName(str(b["id"]))), 90.0)
	var inst: PoiInstance = w.pois.instances.get(StringName(str(b["id"])))
	if inst == null:
		note("%s: not built after 90 s" % def_id)
		return
	var route: Array = inst.layout.route
	note("%s (%s, tier %d): %d route points, %d levels, %d sleepers" % [def_id, inst.layout.def.display_name, inst.tier, route.size(), inst.layout.levels.size(), inst.layout.sleepers.size()])
	for i: int in route.size():
		var r: Dictionary = route[i]
		var at: Array = r.get("at", [0, 0])
		var lv: int = int(r.get("level", 0))
		var here: Vector3 = inst.global_transform * inst.layout.cell_center(lv, Vector2i(int(at[0]), int(at[1])))
		var nxt: Vector3 = here + Vector3(0, 0, -2)
		if i + 1 < route.size():
			var at2: Array = (route[i + 1] as Dictionary).get("at", [0, 0])
			nxt = inst.global_transform * inst.layout.cell_center(int((route[i + 1] as Dictionary).get("level", 0)), Vector2i(int(at2[0]), int(at2[1])))
		p.global_position = here + Vector3.UP * 0.2
		p.velocity = Vector3.ZERO
		await _stream(here)
		look(nxt + Vector3.UP * 1.4)
		await seconds(1.0)
		look(nxt + Vector3.UP * 1.4)
		await frames(4)
		_log.append("    route %d/%d: %s" % [i + 1, route.size(), str(r.get("label", "")).left(140)])
		if i % 3 == 0 or i == route.size() - 1:
			await snap("%s_route_%02d" % [tag, i + 1])
		else:
			await snap("%s_r%02d" % [tag, i + 1])
		if p.interaction.target != null and p.interaction.prompt != "":
			await use()
		_kill_near(p.global_position, 6.0)
	await _clear(def_id, tag)


func _gaps() -> void:
	var ps: PlayerState = p.state
	p.god_mode = true
	_sustain()
	ps.inventory.max_bulk = maxf(ps.inventory.max_bulk, 400.0)
	for kv: Array in [["torch", 2], ["keycard_corvane", 1], ["lockpick", 6], ["crowbar", 1]]:
		if Content.item(StringName(kv[0])) != null:
			ps.inventory.add_item(StringName(kv[0]), int(kv[1]))
	var random: bool = Game.session.world_mode == &"random"
	note("gaps run on %s" % ("random world %s" % Game.session.world_id if random else "the main map"))
	if random:
		await _walk_route("corvane_field_lab", "g_lab")
		# A building from the world's pool in a random town (one the main map doesn't have).
		var main_ids: PackedStringArray = ["pell_crossing_school", "larch_hollow_sawmill", "corvane_larkspur_adit"]
		var picked: String = ""
		for bd: Dictionary in w.pois.call(&"all_buildings"):
			var did: String = String(bd.get("def", ""))
			if int(bd.get("tier", 0)) >= 2 and not main_ids.has(did) and did != "corvane_field_lab" and str(bd.get("kind", "")) != "trader":
				picked = did
				break
		note("pool building picked: %s" % picked)
		if picked != "":
			await _walk_route(picked, "g_pool")
	else:
		await _walk_route("corvane_larkspur_adit", "g_adit")
	# A wolf pack hunting the player.
	var wm: WildlifeManager = w.get(&"wildlife") as WildlifeManager
	var pack_def := Content.get_def(&"wildlife", &"grey_wolf_pack") as WildlifeDef
	if wm != null and wm.wolves != null and pack_def != null:
		await _teleport(p.global_position + Vector3(30, 0, 30))
		Game.session.clock.set_time(Game.session.clock.day(), 22.5)
		var at: Vector3 = p.global_position + Vector3(25, 0, -20)
		var pack: Variant = wm.wolves.spawn_plan(pack_def, {"id": &"qa:wolves", "def": pack_def.id, "pos": Vector2(at.x, at.z), "count": 4, "seed": 3})
		note("wolf pack spawned: %s" % (pack != null))
		for k: int in 6:
			await seconds(4.0)
			var nearest: Node3D = null
			for e: Node in get_tree().get_nodes_in_group(&"enemies"):
				var en2 := e as Enemy
				if en2 != null and en2.get(&"wolf") != null and en2.is_alive() and (nearest == null or en2.global_position.distance_to(p.global_position) < nearest.global_position.distance_to(p.global_position)):
					nearest = e as Node3D
			if nearest != null:
				look(nearest.global_position + Vector3.UP * 0.6)
				note("nearest wolf %.0f m" % nearest.global_position.distance_to(p.global_position))
			await snap("g_wolves_%d" % k)
		_kill_near(p.global_position, 80.0)
	else:
		note("no wolf pack def or manager")
	# A Murmur: crows flushed by the player follow them.
	var crow := Content.get_def(&"wildlife", &"crow") as WildlifeDef
	if wm != null and crow != null:
		Game.session.clock.set_time(Game.session.clock.day() + 1, 10.0)
		var c_at: Vector3 = p.global_position + Vector3(8, 0, -8)
		var flock: BirdFlock = wm.spawn_flock(crow, {"id": &"qa:crows", "def": crow.id, "pos": Vector2(c_at.x, c_at.z), "count": 8, "seed": 5})
		await seconds(2.0)
		if flock != null:
			flock.start_murmur(p.global_position)
			for k: int in 3:
				await _teleport(p.global_position + Vector3(12, 0, 0))
				look(p.global_position + Vector3(0, 8, -6))
				if flock != null and is_instance_valid(flock):
					flock.set(&"murmur_target", p.global_position)
				await seconds(3.0)
				await snap("g_murmur_%d" % k)
		else:
			note("no crow flock spawned")


func _finish() -> void:
	var f := FileAccess.open(ProjectSettings.globalize_path(_out).path_join("first_hour.txt"), FileAccess.WRITE)
	if f != null:
		f.store_string("\n".join(_log) + "\n")
		f.close()
	SaveSystem.delete_slot("qa_first_hour")
	print("[first_hour] done, %d steps, %.0fs" % [_n, (Time.get_ticks_msec() - _t0) / 1000.0])
	get_tree().quit(0)
