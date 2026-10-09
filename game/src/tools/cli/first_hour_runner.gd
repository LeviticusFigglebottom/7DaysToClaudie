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
		if l2.is_visible_in_tree() and l2.text.strip_edges() != "" and l2.text.length() < 400:
			shown.append(l2.text.replace("\n", " / "))
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
	w.terrain.update_streaming(p.global_position, true)
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
	game = get_node("/root/Game")
	Events.player_status_message.connect(func(text: String, kind: StringName) -> void: _msgs.append("[%s] %s" % [kind, text]))
	game.call(&"start_new_game", {"game_mode": "survival", "seed": 4471, "skip_intro": true, "slot": "qa_first_hour"})
	await frames(3)
	ui = (game.world as Node).get(&"ui") as GameUI if game.get(&"world") != null else null
	await seconds(2.0)
	if ui != null:
		await snap("loading_new_game")
	if not await wait_until(func() -> bool: return game.get(&"world") != null and bool(game.world.is_ready), 900.0):
		note("the world never became ready")
		_finish()
		return
	w = game.world
	p = w.player
	ui = w.ui
	await seconds(3.0)
	await snap("wake")
	var ps: PlayerState = p.state
	if OS.get_cmdline_user_args().has("--week-only"):
		# Straight to the week (rendered frames of it without the hour's 48 minutes): the
		# journal finished and Ezra recruited by command.
		ps.tutorial.finish_all()
		ps.inventory.add_item(&"cloth_bandage", 1)
		var camp: Vector3 = w.tutorial.camp_position()
		p.global_position = camp + Vector3(2, 0.5, 2)
		w.terrain.update_streaming(p.global_position, true)
		await seconds(3.0)
		ex(&"companion.recruit", {})
		await seconds(1.0)
		p.global_position = w.drop_site() + Vector3(0, 0.5, 0)
		w.terrain.update_streaming(p.global_position, true)
		await seconds(3.0)
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
	var bb: Dictionary = ex(&"build.place_blueprint", {"blueprint": "bough_bed", "pos": [bed_at.x, bed_at.y, bed_at.z], "yaw": 0.0})
	if bb.has("site"):
		ex(&"build.deliver", {"site": bb["site"]})
	await face(bed_at + Vector3.UP * 0.2, 1.8)
	await snap("bed_aim")
	Game.session.clock.set_time(1, 20.5)
	await use()
	await seconds(1.0)
	await snap("sleeping")
	await wait_until(func() -> bool: return not w.sleeping, 60.0)
	await seconds(1.0)
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
	await snap("continued")
	if OS.get_cmdline_user_args().has("--through") and OS.get_cmdline_user_args().has("hum"):
		await _week()
	_finish()


# --- The first week (--through hum) --------------------------------------------------------------

## Day 2 to the morning after the first Hum: building, the trader, Ezra's orders, hunting, a cave,
## the supply drop, levelling, the Hum's warnings, the night and the morning after.
func _week() -> void:
	var ps: PlayerState = p.state
	Settings.sound_captions = true
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
		w.terrain.update_streaming(p.global_position, true)
		await seconds(3.0)
		look(mouth + Vector3.UP * 1.0)
		await frames(6)
		await snap("w_cave_mouth")
		if cp.spine.size() > 0:
			var deep: Vector3 = cp.spine[cp.spine.size() - 1]
			deep.y = cp.floor_y[cp.floor_y.size() - 1] + 0.1
			p.global_position = deep
			look(mouth + Vector3.UP * 1.5)
			await seconds(2.0)
			await snap("w_cave_inside")

	# --- The supply drop ---------------------------------------------------------------------------------
	var drops: SupplyDrops = w.get(&"supply_drops") as SupplyDrops
	if drops != null:
		p.global_position = base + Vector3(0, 0.5, 4)
		w.terrain.update_streaming(p.global_position, true)
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
	w.terrain.update_streaming(p.global_position, true)
	# The night before, outside with no fire, the cold kills (finding: the first run froze); the
	# audit wants the Hum's screens, so the player is kept alive from here.
	note("health %.0f, warmth %s before the night" % [ps.stats.health, str(ps.stats.get(&"body_temp")) if ps.stats.get(&"body_temp") != null else "?"])
	p.god_mode = true
	var hum_day: int = Game.session.clock.next_horde_day(Game.session.clock.day())
	note("first Hum on day %d (now day %d)" % [hum_day, Game.session.clock.day()])
	# Through the day before and the day itself on the clock, as play would: the warnings fire as
	# their hours pass (setting the time jumps over them).
	Game.session.clock.set_time(hum_day - 1, 18.0)
	var marks: Dictionary = {}
	while Game.session.clock.day() < hum_day or Game.session.clock.hour_f() < 21.9:
		w.clock_driver.advance(30.0)
		await frames(2)
		var tag: String = "w_hum_d%d_%02d" % [Game.session.clock.day() - hum_day, Game.session.clock.hour()]
		if not _msgs.is_empty() and not marks.has(tag):
			marks[tag] = true
			await snap(tag)
	w.clock_driver.advance(20.0)
	await seconds(3.0)
	await snap("w_hum_start")
	var ai: AIDirector = w.ai
	await wait_until(func() -> bool: return ai.hum.members.size() > 0, 30.0)
	await seconds(6.0)
	note("Hum members: %d" % ai.hum.members.size())
	await snap("w_hum_night")
	for id: StringName in ai.hum.members.keys().slice(0, 4):
		var e: Enemy = ai.hum.members[id]["node"]
		if is_instance_valid(e) and e.is_alive():
			var k := DamageInfo.make(999.0, &"blunt", &"melee", ps.id)
			k.hit_pos = e.global_position + Vector3.UP
			e.take_damage(k)
	await seconds(2.0)
	await snap("w_hum_kills")
	p.god_mode = true
	Game.session.clock.set_time(hum_day + 1, 3.9)
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


func _finish() -> void:
	var f := FileAccess.open(ProjectSettings.globalize_path(_out).path_join("first_hour.txt"), FileAccess.WRITE)
	if f != null:
		f.store_string("\n".join(_log) + "\n")
		f.close()
	SaveSystem.delete_slot("qa_first_hour")
	print("[first_hour] done, %d steps, %.0fs" % [_n, (Time.get_ticks_msec() - _t0) / 1000.0])
	get_tree().quit(0)
