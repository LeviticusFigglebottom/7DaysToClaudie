class_name TutorialTracker
extends Node
## The optional first-days tutorial (ADR-0062): a GameWorld module (`world.tutorial`) that feeds
## gameplay events into the local player's TutorialProgress, pays each finished step a little XP,
## and, once every step is done, puts a distress call from the companion (Ezra, ADR-0058) on the
## tether a short in-game delay later, pointing at his camp. The journal tab, HUD nudge and map
## marker read it through steps() and distress() and redraw on Events.tutorial_changed.
##
## Off when the world setting `tutorial` is off or the player turned it off (tutorial.set_enabled):
## nothing is tracked and no call comes; Ezra is still found as before (the find_lineman directive).
## Steps count in any order; the current one is the first not done (TutorialProgress).

const COMMANDS: Array[StringName] = [&"tutorial.set_enabled"]
const TICK: float = 1.0
## `{key:interact}` -> "[E]" (the key the action is bound to now).
static var _key_re: RegEx = null

var world: Node
var _tick: float = 0.0
## Tests stand in the camp: () -> Vector3 (Vector3.INF: this world has no camp).
var camp_source: Callable = Callable()
## Steps finished in frame `_finished_frame`: [{id, event, target}] (fold_reward matches them).
var _finished_now: Array[Dictionary] = []
var _finished_frame: int = -1
## Step id -> the reward of the Program directive the same deed completed ("+40 XP"): one deed,
## one line (first-hour audit #10). Not saved: it is for the line said when the step is done.
var _rewards: Dictionary = {}


func setup_world(w: Node) -> void:
	world = w
	for c: StringName in COMMANDS:
		Game.register_command(c, Callable(self, "_cmd_" + String(c).replace(".", "_")))
	var local := func(pid: StringName) -> bool: return Game.session != null and pid == Game.session.local_player_id
	Events.item_picked_up.connect(func(owner: StringName, item_id: StringName, n: int) -> void:
		if local.call(owner):
			record("gather", item_id, n))
	Events.item_crafted.connect(func(owner: StringName, _r: StringName, item_id: StringName, _n: int) -> void:
		if local.call(owner):
			record("craft", item_id))
	# An assembly blueprint reports its structure (bough_bed -> bedroll), a log one its blueprint.
	Events.blueprint_completed.connect(func(_site: StringName, def_id: StringName) -> void: record("build", def_id))
	# Only the player's own trees: Ezra's count half for the directives, nothing here.
	Events.tree_felled.connect(func(_id: StringName, _pos: Vector3, by: StringName) -> void:
		if CompanionDef.share_for(by) >= 1.0:
			record("fell_tree"))
	Events.structure_placed.connect(func(_id: StringName, def_id: StringName, _pos: Vector3) -> void:
		if def_id == BuildingManager.LOG_DEF:
			record("place_log"))
	Events.player_slept.connect(func(pid: StringName, _h: float) -> void:
		if local.call(pid):
			record("sleep"))
	Events.container_looted.connect(func(pid: StringName, _c: StringName, _tier: int) -> void:
		if local.call(pid):
			record("loot"))
	Events.poi_entered.connect(func(id: StringName) -> void: record("enter_poi", _poi_def(id)))
	Events.note_found.connect(func(_n: StringName) -> void: record("read_note"))
	Events.enemy_killed.connect(func(_eid: StringName, enemy_id: StringName, _pos: Vector3, killer: Dictionary) -> void:
		if local.call(StringName(str(killer.get("source", "")))):
			record("kill", enemy_id))
	Events.companion_recruited.connect(_on_recruited)
	var p: PlayerState = Game.local_player()
	if p != null:
		settle_load(p)


func _exit_tree() -> void:
	for c: StringName in COMMANDS:
		Game.unregister_command(c)


static func cfg() -> Dictionary:
	return Content.config(&"tutorial")


## A loaded player: a save from before the tutorial counts it done past the first days, else it
## starts now; a tutorial finished without its call (steps added since) schedules it.
func settle_load(p: PlayerState) -> void:
	var t: TutorialProgress = p.tutorial
	if t.legacy:
		t.legacy = false
		if Game.session != null and Game.session.clock.day() > int(cfg().get("old_save_done_after_day", 2)):
			t.finish_all()
	if is_enabled() and t.all_done():
		_schedule_distress(t)


## The world setting and the player's own switch.
func is_enabled() -> bool:
	var p: PlayerState = Game.local_player()
	return p != null and GameRules.current().flag("tutorial") and p.tutorial.enabled


## Every step, by order: {id, title, body (raw: render_body() shows its keys), done, current (the
## first not done), progress (capped at count), count, reward (what the Program directive done by
## the same deed paid, "+40 XP" or "", for the step's done line: that directive says no line of
## its own)}.
func steps() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var p: PlayerState = Game.local_player()
	if p == null:
		return out
	var t: TutorialProgress = p.tutorial
	var cur: TutorialStepDef = t.current()
	for d: TutorialStepDef in TutorialProgress.step_defs():
		out.append({"id": d.id, "title": d.display_name, "body": d.body, "done": t.done.has(d.id),
			"current": cur != null and cur.id == d.id, "progress": mini(t.count_of(d.id), d.count), "count": d.count,
			"reward": str(_rewards.get(d.id, ""))})
	return out


## The call: {received, companion_id, position (his camp; Vector3.ZERO when the world has none),
## text}. `received` is also true when it was skipped (he was already with you or dead, or no
## camp): then `text` is "" (no call was heard).
func distress() -> Dictionary:
	var p: PlayerState = Game.local_player()
	var received: bool = p != null and p.tutorial.distress_received
	var at: Vector3 = camp_position()
	var heard: bool = received and p.tutorial.distress_heard
	return {"received": received, "companion_id": companion_id(), "position": at if at != Vector3.INF else Vector3.ZERO,
		"text": str(cfg().get("distress_text", "")) if heard else ""}


## A body's `{key:<action>}` placeholders as the keys they are bound to now ("[E]"), through the
## interaction prompts' PlayerInteraction.key_label (TD-119), so a rebound key reads right.
static func render_body(text: String) -> String:
	if _key_re == null:
		_key_re = RegEx.create_from_string(TutorialStepDef.KEY_PATTERN)
	var out: String = ""
	var at: int = 0
	for m: RegExMatch in _key_re.search_all(text):
		out += text.substr(at, m.get_start() - at) + "[%s]" % PlayerInteraction.key_label(StringName(m.get_string(1)))
		at = m.get_end()
	return out + text.substr(at)


func companion_id() -> StringName:
	return StringName(str(cfg().get("companion", "ezra")))


# --- Progress ------------------------------------------------------------------------------------

## Feeds one gameplay event (nothing while the tutorial is off).
func record(event: String, target: StringName = &"", amount: int = 1) -> void:
	if not is_enabled():
		return
	var p: PlayerState = Game.local_player()
	var t: TutorialProgress = p.tutorial
	var before: Dictionary = t.progress.duplicate()
	var finished: Array[TutorialStepDef] = t.record(event, target, amount)
	var src: String = str(cfg().get("xp_source", "tutorial_step"))
	var frame: int = Engine.get_process_frames()
	if frame != _finished_frame:
		_finished_frame = frame
		_finished_now.clear()
	for d: TutorialStepDef in finished:
		if p.progression.has_xp_source(src):
			p.progression.award(src)
		Log.info(&"tutorial", "step done: %s" % d.id)
		_finished_now.append({"id": d.id, "event": event, "target": target})
		# A directive the same deed paid just now (the directives heard it first): its reward
		# rides on this step's journal line instead of a line of its own.
		var directives: Node = world.get(&"directives") if world != null else null
		if directives != null and directives.has_method(&"claim_reward"):
			var reward: String = directives.call(&"claim_reward", event, target)
			if reward != "":
				_rewards[d.id] = reward
	if not finished.is_empty() and t.all_done():
		_schedule_distress(t)
	if t.progress != before:
		Events.tutorial_changed.emit()


## A directive's reward ("+40 XP") for the journal step that `event` on `target` finished this
## frame (DirectiveTracker, when it heard the deed after us): true when a step took it, and the
## directive then says no line of its own.
func fold_reward(event: String, target: StringName, reward: String) -> bool:
	if _finished_frame != Engine.get_process_frames():
		return false
	for f: Dictionary in _finished_now:
		if str(f["event"]) == event and StringName(f["target"]) == target:
			if reward != "":
				_rewards[StringName(f["id"])] = reward
				Events.tutorial_changed.emit()
			return true
	return false


func _on_recruited(cid: StringName) -> void:
	var cd: CompanionDef = Content.get_def(&"companion", cid) as CompanionDef
	record("recruit", StringName(str(cd.camp.get("poi", ""))) if cd != null else &"")
	# A call still to come is moot now.
	var p: PlayerState = Game.local_player()
	if p != null and cid == companion_id() and not p.tutorial.distress_received:
		_skip(p.tutorial)


## Due a short game-time delay from now; skipped when he can't need finding.
func _schedule_distress(t: TutorialProgress) -> void:
	if t.distress_received or t.distress_due >= 0.0 or Game.session == null:
		return
	if not _companion_waiting() or camp_position() == Vector3.INF:
		_skip(t)
		return
	t.distress_due = Game.session.clock.total_minutes + float(cfg().get("delay_minutes", 45.0))
	Events.tutorial_changed.emit()


func _skip(t: TutorialProgress) -> void:
	t.distress_received = true
	t.distress_heard = false
	t.distress_due = -1.0
	Events.tutorial_changed.emit()


## Not recruited, not dead: still at his camp to be found.
func _companion_waiting() -> bool:
	if Game.session == null or Content.get_def(&"companion", companion_id()) == null:
		return false
	var s: Dictionary = Game.session.world.companion
	return not bool(s.get("recruited", false)) and not bool(s.get("dead", false))


# --- The call ------------------------------------------------------------------------------------

func _process(delta: float) -> void:
	_tick += delta
	if _tick < TICK:
		return
	_tick = 0.0
	tick()


## Delivers a due call: never while the Hum is on, while the player sleeps or before the world is
## ready (it waits for the next tick that allows it). Tests call it directly.
func tick() -> void:
	var p: PlayerState = Game.local_player()
	if p == null or not is_enabled():
		return
	var t: TutorialProgress = p.tutorial
	if t.distress_received or t.distress_due < 0.0:
		return
	if not _companion_waiting():
		_skip(t)
		return
	var clock: WorldClock = Game.session.clock
	if clock.total_minutes < t.distress_due or clock.is_horde_active():
		return
	if world != null and (bool(world.get(&"sleeping")) or (world.get(&"is_ready") != null and not bool(world.get(&"is_ready")))):
		return
	var at: Vector3 = camp_position()
	if at == Vector3.INF:
		_skip(t)
		return
	t.distress_received = true
	t.distress_heard = true
	t.distress_due = -1.0
	Log.info(&"tutorial", "distress call from %s at %s" % [companion_id(), at])
	Events.tutorial_distress.emit(companion_id(), at)
	Events.tutorial_changed.emit()


## His camp: where CompanionDirector seats him, else the camp building's own position (a streamed
## world lists a building before it is built); Vector3.INF when this world has no camp.
func camp_position() -> Vector3:
	if camp_source.is_valid():
		return camp_source.call()
	var cd: CompanionDef = Content.get_def(&"companion", companion_id()) as CompanionDef
	if cd == null or world == null:
		return Vector3.INF
	var director: Node = world.get(&"companion")
	if director != null and director.has_method(&"camp_spot") and director.get(&"cdef") == cd:
		var spot: Dictionary = director.call(&"camp_spot")
		if not spot.is_empty():
			return spot["pos"]
	var pois: Node = world.get(&"pois")
	if pois == null or not pois.has_method(&"all_buildings"):
		return Vector3.INF
	var poi: String = str(cd.camp.get("poi", ""))
	for b: Variant in pois.call(&"all_buildings"):
		if str((b as Dictionary).get("def", "")) == poi:
			var at: Vector3 = (b as Dictionary).get("pos", Vector3.ZERO)
			if world.has_method(&"height_at"):
				at.y = float(world.call(&"height_at", at.x, at.z))
			return at
	return Vector3.INF


func _poi_def(instance_id: StringName) -> StringName:
	var pois: Node = world.get(&"pois") if world != null else null
	if pois == null:
		return &""
	var inst: PoiInstance = (pois.get(&"instances") as Dictionary).get(instance_id)
	return inst.layout.def.id if inst != null and inst.layout != null else &""


# --- Commands (ADR-0003) -----------------------------------------------------------------------------

## {enabled: bool, player?} -> {ok, enabled}. Turning it back on resumes where it stood (what was
## done while it was off does not count); it can't be turned on in a world whose setting is off.
func _cmd_tutorial_set_enabled(args: Dictionary) -> Dictionary:
	var p: PlayerState = Game.session.players.get(StringName(str(args.get("player", Game.session.local_player_id)))) if Game.session != null else null
	if p == null:
		return {"ok": false, "error": "no player"}
	if not args.has("enabled"):
		return {"ok": false, "error": "enabled missing"}
	var on: bool = bool(args["enabled"])
	if on and not GameRules.current().flag("tutorial"):
		return {"ok": false, "error": "the tutorial is off in this world's settings"}
	if p.tutorial.enabled != on:
		p.tutorial.enabled = on
		if on and p.tutorial.all_done():
			_schedule_distress(p.tutorial)
		Events.tutorial_changed.emit()
	return {"ok": true, "enabled": on}
