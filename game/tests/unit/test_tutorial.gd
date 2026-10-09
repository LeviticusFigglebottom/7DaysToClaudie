extends GutTest
## The first-days tutorial (ADR-0062): its content validates and quotes the real recipes, steps
## advance on their events (any order, the current one the first not done) and pay a little XP,
## turning it off stops it, the distress call comes once after the delay (not in the Hum) with the
## camp's position and is skipped when Ezra is already with you, keys render as the prompts do,
## and the state round-trips through a save (an old save without it is settled by its day).

const CAMP := Vector3(120.0, 14.0, -310.0)

var _prev: GameSession
var _tracker: TutorialTracker


func before_each() -> void:
	_prev = Game.session
	Game.session = GameSession.create_new({"seed": 7, "game_mode": "slice"})
	_tracker = TutorialTracker.new()
	_tracker.camp_source = func() -> Vector3: return CAMP
	add_child_autofree(_tracker)


func after_each() -> void:
	Game.unregister_command(&"tutorial.set_enabled")
	Game.session = _prev


func _p() -> PlayerState:
	return Game.local_player()


## {item: count} with String keys and int counts (JSON numbers parse as floats).
func _n(d: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for k: Variant in d.keys():
		out[String(k)] = int(d[k])
	return out


## Feeds every step's event until it is done, in order.
func _do_all() -> void:
	for d: TutorialStepDef in TutorialProgress.step_defs():
		_tracker.record(d.event, StringName(d.targets[0]) if not d.targets.is_empty() else &"", d.count)


func test_content_validates_and_is_ordered() -> void:
	for e: String in Content.errors():
		assert_false(e.contains("tutorial"), e)
	var defs: Array[TutorialStepDef] = TutorialProgress.step_defs()
	assert_between(defs.size(), 7, 9, "seven to nine steps")
	var orders: Dictionary = {}
	for d: TutorialStepDef in defs:
		assert_false(orders.has(d.order), "%s: unique order" % d.id)
		orders[d.order] = true
		assert_ne(d.display_name, "", "%s has a title" % d.id)
		assert_true(TutorialStepDef.EVENTS.has(d.event))
	# The bodies quote the real recipes and blueprints.
	var axe: RecipeDef = Content.recipe(&"stone_axe")
	assert_eq(_n(axe.ingredients), {"stick": 1, "stone": 1, "cordage": 1}, "the stone axe card's recipe")
	assert_eq(_n(Content.recipe(&"cordage").ingredients), {"plant_fiber": 3})
	assert_eq(_n(Content.recipe(&"cloth_bandage").ingredients), {"cloth": 2})
	assert_eq(_n(Content.recipe(&"boil_water").ingredients), {"water_bottle_dirty": 1})
	assert_eq(_n((Content.get_def(&"blueprint", &"campfire") as BlueprintDef).cost), {"stone": 6, "stick": 4})
	assert_eq(_n((Content.get_def(&"blueprint", &"lean_to") as BlueprintDef).cost), {"stick": 10, "leaf_bundle": 6, "cordage": 2})
	assert_eq(_n((Content.get_def(&"blueprint", &"bough_bed") as BlueprintDef).cost), {"leaf_bundle": 6, "stick": 4})
	assert_eq(int(Content.config(&"player")["start_kit"].get("cloth", 0)), 2, "the bandage card says 2 cloth were issued")
	assert_not_null(Content.get_def(&"companion", StringName(str(TutorialTracker.cfg()["companion"]))), "the call's companion exists")
	var ezra: Variant = Content.get_def(&"companion", StringName(str(TutorialTracker.cfg()["companion"])))
	if ezra != null:
		assert_true((ezra.get(&"recruit_items") as Array).has("cloth_bandage"), "the bandage card's bandage recruits him (ADR-0062)")
	assert_true(_p().progression.has_xp_source(str(TutorialTracker.cfg()["xp_source"])), "the XP source is in progression.json")


func test_bad_placeholders_and_targets_are_errors() -> void:
	var d := TutorialStepDef.new()
	var errs: PackedStringArray = d.parse({"id": "x", "title": "X", "body": "Press {key:no_such_action}.", "event": "craft",
		"targets": ["no_such_item"], "count": 1, "colour": "red"}, &"tutorial_step", "test.json")
	assert_true(Array(errs).any(func(e: String) -> bool: return e.contains("colour")), "unknown fields are errors")
	var out: PackedStringArray = []
	d._validate(Content, out)
	assert_true(Array(out).any(func(e: String) -> bool: return e.contains("no_such_action")), "an unknown key action is an error")
	assert_true(Array(out).any(func(e: String) -> bool: return e.contains("no_such_item")), "an unknown target is an error")


func test_render_body_uses_the_prompt_key_names() -> void:
	var text: String = TutorialTracker.render_body("Hold {key:interact} on it, {key:attack} to swing. No keys: {key}.")
	assert_eq(text, "Hold [%s] on it, [%s] to swing. No keys: {key}." % [PlayerInteraction.key_label(&"interact"),
		PlayerInteraction.key_label(&"attack")])
	for d: TutorialStepDef in TutorialProgress.step_defs():
		assert_false(TutorialTracker.render_body(d.body).contains("{key:"), "%s renders every key" % d.id)
		assert_false(TutorialTracker.render_body(d.body).contains("[?]"), "%s names bound actions" % d.id)


func test_steps_advance_on_their_events() -> void:
	var steps: Array[Dictionary] = _tracker.steps()
	assert_eq(steps[0]["id"], &"gather_basics")
	assert_true(steps[0]["current"])
	for k: String in ["id", "title", "body", "done", "current", "progress", "count"]:
		assert_true(steps[0].has(k), "steps() has %s" % k)
	watch_signals(Events)
	_tracker.record("gather", &"cloth", 5)
	assert_eq(_tracker.steps()[0]["progress"], 0, "cloth is not what the first card asks for")
	_tracker.record("gather", &"plant_fiber", 3)
	_tracker.record("gather", &"stick", 2)
	assert_eq(_tracker.steps()[0]["progress"], 5)
	assert_signal_emitted(Events, "tutorial_changed")
	var xp: int = _p().progression.xp
	_tracker.record("gather", &"stone", 4)
	steps = _tracker.steps()
	assert_true(steps[0]["done"])
	assert_eq(steps[0]["progress"], 6, "progress is capped at the count")
	assert_true(steps[1]["current"], "the axe is next")
	assert_gt(_p().progression.xp, xp, "a finished step pays a little XP")
	# Any order: the fire built early stays built; the current card is still the axe.
	_tracker.record("build", &"campfire")
	steps = _tracker.steps()
	assert_true(steps[3]["done"] and not steps[3]["current"])
	assert_true(steps[1]["current"])
	_tracker.record("craft", &"cordage")
	assert_false(_tracker.steps()[1]["done"], "cordage is not the axe")
	_tracker.record("craft", &"stone_axe")
	assert_true(_tracker.steps()[1]["done"])
	assert_true(_tracker.steps()[2]["current"], "felling is next")
	# The bough bed reports its structure.
	_tracker.record("build", &"bedroll")
	assert_true(_tracker.steps()[6]["done"], "a bough bed is a shelter")


func test_live_events_reach_it() -> void:
	_tracker.setup_world(null)
	Events.item_picked_up.emit(_p().id, &"stick", 6)
	assert_true(_tracker.steps()[0]["done"], "a pickup counts")
	Events.item_crafted.emit(&"companion:ezra", &"stone_axe", &"stone_axe", 1)
	assert_false(_tracker.steps()[1]["done"], "someone else's craft does not")
	Events.item_crafted.emit(_p().id, &"stone_axe", &"stone_axe", 1)
	assert_true(_tracker.steps()[1]["done"])
	Events.tree_felled.emit(&"t1", Vector3.ZERO, &"companion:ezra")
	assert_false(_tracker.steps()[2]["done"], "Ezra's tree is not yours")
	Events.tree_felled.emit(&"t2", Vector3.ZERO, _p().id)
	assert_true(_tracker.steps()[2]["done"])
	Events.player_slept.emit(_p().id, 8.0)
	assert_true(_tracker.steps()[7]["done"])


func test_disable_stops_it() -> void:
	_tracker.setup_world(null)
	assert_true(_tracker.is_enabled(), "on by default")
	var r: Dictionary = Game.execute(&"tutorial.set_enabled", {"enabled": false})
	assert_true(r["ok"])
	assert_false(_tracker.is_enabled())
	_tracker.record("gather", &"stick", 6)
	assert_eq(_tracker.steps()[0]["progress"], 0, "nothing counts while it is off")
	_do_all()
	_tracker.tick()
	assert_false(_tracker.distress()["received"], "no call while it is off")
	assert_true(Game.execute(&"tutorial.set_enabled", {"enabled": true})["ok"])
	_tracker.record("gather", &"stick", 6)
	assert_true(_tracker.steps()[0]["done"], "back on, it resumes")
	# The world setting off: nothing, and it can't be turned on.
	Game.session.rules.values["tutorial"] = false
	assert_false(_tracker.is_enabled())
	assert_false(Game.execute(&"tutorial.set_enabled", {"enabled": true})["ok"])
	assert_false(Game.execute(&"tutorial.set_enabled", {})["ok"], "enabled is required")


func test_distress_fires_once_with_the_camp_position() -> void:
	var clock: WorldClock = Game.session.clock
	clock.set_time(2, 9.0)
	watch_signals(Events)
	_do_all()
	assert_false(_tracker.distress()["received"])
	_tracker.tick()
	assert_signal_not_emitted(Events, "tutorial_distress", "not before the delay")
	clock.total_minutes += float(TutorialTracker.cfg()["delay_minutes"]) + 1.0
	_tracker.tick()
	assert_signal_emit_count(Events, "tutorial_distress", 1)
	assert_eq(get_signal_parameters(Events, "tutorial_distress"), [&"ezra", CAMP])
	var d: Dictionary = _tracker.distress()
	assert_true(d["received"])
	assert_eq(d["companion_id"], &"ezra")
	assert_eq(d["position"], CAMP)
	assert_true(str(d["text"]).contains("first aid kit") and str(d["text"]).contains("painkillers"), "he says what he needs")
	_tracker.tick()
	_tracker.record("sleep")
	assert_signal_emit_count(Events, "tutorial_distress", 1, "once")


func test_distress_waits_out_the_hum() -> void:
	var clock: WorldClock = Game.session.clock
	var hum: int = clock.next_horde_day(1)
	clock.set_time(hum, 21.0)
	watch_signals(Events)
	_do_all()
	clock.set_time(hum, 23.0)
	assert_true(clock.is_horde_active())
	_tracker.tick()
	assert_signal_not_emitted(Events, "tutorial_distress", "not during the Hum")
	clock.set_time(hum + 1, 8.0)
	_tracker.tick()
	assert_signal_emit_count(Events, "tutorial_distress", 1, "after it")


func test_distress_skipped_when_recruited_or_no_camp() -> void:
	Game.session.world.companion["recruited"] = true
	watch_signals(Events)
	_do_all()
	Game.session.clock.total_minutes += 600.0
	_tracker.tick()
	assert_signal_not_emitted(Events, "tutorial_distress")
	var d: Dictionary = _tracker.distress()
	assert_true(d["received"], "marked received")
	assert_eq(d["text"], "", "but no call was heard")
	# Recruited between the last step and the call: skipped too.
	Game.session = GameSession.create_new({"seed": 8, "game_mode": "slice"})
	_do_all()
	Game.session.world.companion["recruited"] = true
	Game.session.clock.total_minutes += 600.0
	_tracker.tick()
	assert_signal_not_emitted(Events, "tutorial_distress")
	assert_true(_tracker.distress()["received"])
	# A world without his camp.
	Game.session = GameSession.create_new({"seed": 9, "game_mode": "slice"})
	_tracker.camp_source = func() -> Vector3: return Vector3.INF
	_do_all()
	assert_true(_tracker.distress()["received"], "no camp: nothing to point at")


func test_save_round_trip_and_old_saves() -> void:
	_tracker.record("gather", &"stick", 4)
	_tracker.record("craft", &"stone_axe")
	_p().tutorial.enabled = false
	var back := PlayerState.new()
	back.from_dict(_p().to_dict())
	assert_false(back.tutorial.legacy)
	assert_eq(back.tutorial.count_of(&"gather_basics"), 4)
	assert_true(back.tutorial.done.has(&"stone_axe"))
	assert_false(back.tutorial.enabled, "the player's switch is saved")
	_p().tutorial.enabled = true
	_do_all()
	back.from_dict(_p().to_dict())
	assert_eq(back.tutorial.distress_due, _p().tutorial.distress_due, "a call still to come is saved")
	assert_gt(back.tutorial.distress_due, 0.0)
	# An old save (no "tutorial" key): done past day 2, else it starts now.
	var old: Dictionary = _p().to_dict()
	old.erase("tutorial")
	var ps := PlayerState.new()
	ps.from_dict(old)
	assert_true(ps.tutorial.legacy)
	Game.session.clock.set_time(5, 10.0)
	_tracker.settle_load(ps)
	assert_true(ps.tutorial.all_done() and ps.tutorial.distress_received, "day 5: done, no call")
	ps.from_dict(old)
	Game.session.clock.set_time(2, 10.0)
	_tracker.settle_load(ps)
	assert_false(ps.tutorial.legacy)
	assert_eq(ps.tutorial.current().id, &"gather_basics", "day 2: it starts")


func test_recruit_counts_for_find_lineman_in_any_chapter() -> void:
	var dr := Directives.new()
	assert_eq(dr.chapter, 1)
	assert_eq(dr.record("recruit", &"ezra_camp").size(), 1, "Ezra found on day 1 still counts")
	assert_true(dr.done.has(&"find_lineman"))
	assert_eq(dr.chapter, 1, "and opens no chapter early")


## One deed that finishes a journal step and a Program directive says one line (first-hour audit
## #10): the journal step carries the directive's reward, whichever tracker hears the deed first;
## with the tutorial off the directive says its own line.
func test_a_directive_done_with_a_step_rides_on_its_journal_line() -> void:
	var ws := GDScript.new()
	ws.source_code = "extends Node\nvar directives: Node\nvar tutorial: Node\n"
	assert_eq(ws.reload(), OK)
	var w: Node = ws.new()
	add_child_autofree(w)
	var dt := DirectiveTracker.new()
	add_child_autofree(dt)
	w.set(&"directives", dt)
	w.set(&"tutorial", _tracker)
	dt.world = w
	dt._announced = 1
	_tracker.world = w
	var said: Array[String] = []
	var on_msg := func(text: String, _k: StringName) -> void: said.append(text)
	Events.player_status_message.connect(on_msg)
	# The directives hear it first (GameWorld wires them first).
	dt.record("craft", &"stone_axe")
	_tracker.record("craft", &"stone_axe")
	await get_tree().process_frame
	assert_eq(_tracker.steps()[1]["reward"], "+40 XP", "the axe's journal line carries the directive's XP")
	assert_eq(said, [] as Array[String], "and the directive says no line of its own")
	# The tutorial hears it first.
	_tracker.record("build", &"campfire")
	dt.record("build", &"campfire")
	await get_tree().process_frame
	assert_eq(_tracker.steps()[3]["reward"], "+60 XP, and a Bottle of Boiled Water")
	assert_eq(said, [] as Array[String])
	# A directive the step doesn't share: its own line.
	for i: int in 3:
		dt.record("fell_tree")
	await get_tree().process_frame
	assert_eq(said, ["Directive complete: Fell three trees.  +60 XP, and a Program Ration Bar"] as Array[String])
	# Tutorial off: nothing folds.
	said.clear()
	_p().tutorial.enabled = false
	_tracker.record("build", &"lean_to")
	dt.record("build", &"lean_to")
	await get_tree().process_frame
	assert_eq(said, ["Directive complete: Raise a lean-to.  +80 XP, and 2 Cordage"] as Array[String])
	Events.player_status_message.disconnect(on_msg)


func test_reward_text_reads_as_one_reward() -> void:
	assert_eq(DirectiveTracker.reward_text(60, ["a Bottle of Boiled Water"] as Array[String]), "+60 XP, and a Bottle of Boiled Water")
	assert_eq(DirectiveTracker.reward_text(40, [] as Array[String]), "+40 XP")
	assert_eq(DirectiveTracker.reward_text(200, ["2 Wire Spool", "a Gas Can"] as Array[String]), "+200 XP, and 2 Wire Spool and a Gas Can")
	assert_eq(DirectiveTracker.reward_text(0, ["a Repair Kit"] as Array[String]), "a Repair Kit", "a level goal pays no XP")
	assert_eq(DirectiveTracker.item_phrase(1, "Antifungal Tablets"), "1 Antifungal Tablets", "a plural name keeps its count")
	assert_eq(DirectiveTracker.item_phrase(1, "Empty Can"), "an Empty Can")
