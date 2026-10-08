class_name FieldManual
extends Control
## The Remand Program Field Manual (guidebook, B): a dog-eared printed booklet issued with the
## tether. Blueprints to lay out (shelter, crafting, defence, walls), your Record (level, XP,
## gamestage; spend points on attributes and perks), notes you have read, and the program's
## survival pages. Choosing "Lay it out" hands the blueprint to the building placement ghost and
## closes the book; points are spent through the progression.* commands.

const PAPER := Color(0.86, 0.82, 0.71)
const INK := Color(0.15, 0.12, 0.09)
const INK_DIM := UiStyle.INK_DIM
const TIPS: Array[Array] = [
	["The Remand Program", "You signed the waiver. You are inside the Cordon to find out what the Bloom did to Hollowmere and whether anyone is left. The canister drop is your only resupply. Your tether keeps time, vitals and the Hum forecast."],
	["Hollowed", "By day they are slow and half blind. After dark they see without light and they run. Anything you carry that glows tells them where you are. Crouch, keep your lights off, and let the wind carry your scent away from them."],
	["The Hum", "Every few nights the ground hums and the Hollowed answer from every side. They remember what killed them last time and where your walls held. Build where you can see them coming. Spikes slow them; logs make them work; nothing stops them forever."],
	["Shelter", "A lean-to and a bough bed mark your place in the world: sleep there to rest, save, and wake there if the worst happens. Fire keeps you warm and dries you — but within twenty metres of it you stand in its light, and the Hollowed see you from much farther off."],
	["Building with logs", "Fell trees with an axe; carry two logs (three once you learn Timberwright). Lay a blueprint from this manual and fill its ghost, or set logs freely: they notch onto each other (R turns the log, V stands it up or pitches it for a roof). A log needs something under it or beside it — what nothing holds up, falls."],
	["Gardens and rain", "A garden bed grows what you plant in it: seed packets and seed potatoes turn up in kitchen drawers and feed bins, and wild huckleberries and yarrow give seed of their own. Plants grow only while the soil is wet: rain soaks it, a bottle or a bucket of water tops it up (hold [X] on the bed to water it). Dry soil wilts them and kills them in a day or two; frost hurts the tender ones; nothing grows in winter, and summer is best. A rain catcher fills under open sky whenever it rains: fill bottles and buckets from it, or drink. Rain water is murky, so boil what you bottle."],
	["Traps and power", "The Hollowed walk their own way to your walls, so put something in it. A spike pit holds whatever falls in, slows it and stakes it while it climbs out; the stakes dull with use, so mend them with a hammer. A deadfall drops its log on the first thing under it; lift it again by hand. A tripwire bell rings when something walks through and tells you from where, but everything near hears it too. A generator runs on gas cans from car trunks and garages: fuel it, start it, and with a wire spool in your pack hold [X] on it, then on a light or a sentry, to wire them (a spool runs ten metres, fourteen at most between two pieces). Work lights shine while they have power; a motion floodlight lights up and warns you when something moves; a nail sentry shoots what comes in range while it has power and nails. A generator is loud and warm: the longer it runs, the more of them come to see what is making the noise."],
	["Hammer", "A claw hammer repairs what the Hollowed break (sticks for a log, sticks and nails for a reinforced one, a quarter of its cost for anything else), and reinforces logs once they are whole (cordage and nails)."],
	["Waystation 9", "The Program's relay post on Route 9, south by the river. Its guards shoot any Hollowed that come inside the wire, and nothing rises there. The quartermaster buys what you carry and sells what the drones bring, for Program scrip. The board posts contracts: clear a building and search its stores, bring back a cache the survey teams left, or hold a relay cache while it uploads. Report back to be paid; standing with the post opens better stock and harder work."],
	["The Ashen", "Tribes of the high timber, painted in lichen-ash so the Hollowed can't smell them. They burn their dead and kill outsiders who might carry the Bloom. First they watch: a still figure on a ridge, gone when you look again. Let a scout get away and the camp learns where you sleep. Anger them enough and they come at dusk, with drums: raiders who break what is in their way. Hold a torch up at them and keep your fires burning; fire in an outsider's hand frightens them, and a band that loses its nerve runs. They never come on a Hum night. At home in their camps they fight to the last."],
	["Ezra Vane", "A convict from two drops before yours, a lineman before the Program got him. He is holed up in his line truck by the power line, out in the timber, with a broken leg: bring him a first aid kit or painkillers and he walks with you. Talk to him (E) to give orders: follow, stay here, guard here, gather, fetch, give me what you carry, store at base; [H] whistles him to follow or to stay. Look at the spot or the thing first: he gathers round what you last looked at (wood, stone or fibre, into his own pack: twelve slots and two logs on his shoulder) and fetches it. His trees count half for your XP and directives. Following, he fights whatever comes at you or at him, and carries a lantern at night (his light, not yours: it doesn't give you away). Guarding, he holds the ground round his spot. If he goes down, get to him with a bandage or a first aid kit and hold E: he bleeds out in three minutes, and then he's gone till the next dawn, when he limps back to your bed. Under one-life rules he doesn't come back."],
	["Your record", "Everything you survive teaches you something: Hollowed put down, places searched, logs set, things made, buildings cleared, a Hum lived through. Each level is a point to spend in the Record — on an attribute, or on a perk once its attribute is high enough. The Cordon notices too: the longer you last and the more you learn, the worse the Hollowed that come for you, and the better what you find."],
]
## Attribute display order (the data is sorted by id).
const ATTR_ORDER: PackedStringArray = ["sinew", "grit", "keen", "quiet", "wits"]
## Perk/attribute effect keys -> [format, scale] for the Record tab.
const EFFECT_TEXT: Dictionary = {
	"melee_damage_mult": ["%+.0f%% melee damage", 100.0], "blunt_damage_mult": ["%+.0f%% blunt damage", 100.0],
	"ranged_damage_mult": ["%+.0f%% firearm damage", 100.0], "ranged_spread_mult": ["%+.0f%% firearm sway", 100.0],
	"chop_damage_mult": ["%+.0f%% chopping", 100.0],
	"carry_bulk": ["%+.0f pack space", 1.0], "log_carry": ["%+.0f log on the shoulder", 1.0],
	"max_health": ["%+.0f max health", 1.0], "stamina_regen_mult": ["%+.0f%% stamina recovery", 100.0],
	"damage_resist": ["%+.0f%% damage resisted", 100.0], "bleed_resist": ["%+.0f%% bleeding resisted", 100.0],
	"food_poison_resist": ["%+.0f%% food poisoning resisted", 100.0], "loot_quality_bonus": ["%+.2f loot quality", 1.0],
	"search_speed_mult": ["%+.0f%% search speed", 100.0], "sleeper_sense_range": ["sense sleepers within %.0f m", 1.0],
	"noise_mult": ["%+.0f%% noise", 100.0], "move_speed_mult": ["%+.0f%% move speed", 100.0],
	"visibility_mult": ["%+.0f%% seen in the dark", 100.0], "sprint_cost_mult": ["%+.0f%% sprint cost", 100.0],
	"craft_quality": ["%+.1f crafted quality", 1.0], "structure_hp_mult": ["%+.0f%% structure toughness", 100.0],
	"stagger_bonus": ["%+.1f stagger (blunt)", 1.0], "heal_mult": ["%+.0f%% healing", 100.0],
}

var _open: bool = false
var _tabs: HBoxContainer
var _list: VBoxContainer
var _detail: RichTextLabel
var _action: Button
var _tab: String = "build"
var _selected: Variant = null


func _ready() -> void:
	# In the tree already: plain set_anchors_preset() would keep the 0x0 rect (offsets follow).
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	# The paper theme (ADR-0063): disabled entries stay in dim ink, never Godot's white.
	theme = UiStyle.paper_theme()
	mouse_filter = Control.MOUSE_FILTER_STOP
	visible = false
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.5)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var book := PanelContainer.new()
	book.anchor_left = 0.14
	book.anchor_right = 0.86
	book.anchor_top = 0.08
	book.anchor_bottom = 0.92
	var sb := StyleBoxTexture.new()
	var tex_path: String = "res://assets/generated/textures/ui_paper_page.png"
	if ResourceLoader.exists(tex_path):
		sb.texture = load(tex_path)
		sb.content_margin_left = 40
		sb.content_margin_right = 40
		sb.content_margin_top = 30
		sb.content_margin_bottom = 30
		book.add_theme_stylebox_override(&"panel", sb)
	else:
		var flat := StyleBoxFlat.new()
		flat.bg_color = PAPER
		flat.content_margin_left = 40
		flat.content_margin_right = 40
		flat.content_margin_top = 30
		flat.content_margin_bottom = 30
		flat.shadow_size = 12
		flat.shadow_color = Color(0, 0, 0, 0.5)
		book.add_theme_stylebox_override(&"panel", flat)
	add_child(book)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 12)
	book.add_child(v)
	var title := UiStyle.label("REMAND PROGRAM — FIELD MANUAL  (rev. 3)", &"HeadingLabel")
	v.add_child(title)
	_tabs = HBoxContainer.new()
	_tabs.add_theme_constant_override(&"separation", 4)
	v.add_child(_tabs)
	var group := ButtonGroup.new()
	for t: Array in [["build", "Blueprints"], ["journal", "Journal"], ["record", "Record"], ["notes", "Notes found"], ["tips", "Survival"]]:
		var b := Button.new()
		b.text = t[1]
		b.name = "Tab_" + str(t[0])
		b.toggle_mode = true
		b.button_group = group
		b.focus_mode = Control.FOCUS_NONE
		b.theme_type_variation = &"ListButton"
		b.add_theme_font_size_override(&"font_size", 19)
		b.pressed.connect(_set_tab.bind(str(t[0])))
		_tabs.add_child(b)
	var h := HBoxContainer.new()
	h.size_flags_vertical = Control.SIZE_EXPAND_FILL
	h.add_theme_constant_override(&"separation", 24)
	v.add_child(h)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(380, 0)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	h.add_child(scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_list)
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(right)
	_detail = RichTextLabel.new()
	_detail.bbcode_enabled = true
	_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_detail.add_theme_color_override(&"default_color", INK)
	_detail.add_theme_font_size_override(&"normal_font_size", 18)
	_detail.add_theme_font_override(&"bold_font", UiStyle.bold_font())
	right.add_child(_detail)
	_action = Button.new()
	_action.text = "Lay it out"
	_action.theme_type_variation = &"PrimaryButton"
	_action.custom_minimum_size = Vector2(240, 44)
	_action.pressed.connect(_on_action)
	right.add_child(_action)
	Events.ui_modal_closed.connect(func(id: StringName) -> void:
		if id == &"field_manual" and _open:
			_open = false
			visible = false)
	Events.player_progressed.connect(func(_pid: StringName) -> void:
		if _open and _tab == "record":
			_refresh())
	# The tutorial backend's signal (hub contract); connected only once it exists.
	if Events.has_signal(&"tutorial_changed"):
		Events.connect(&"tutorial_changed", func() -> void:
			if _open and _tab == "journal":
				_refresh())


func _set_tab(t: String) -> void:
	_tab = t
	var b: Button = _tabs.get_node_or_null("Tab_" + t) as Button
	if b != null:
		b.set_pressed_no_signal(true)
	_selected = null
	_refresh()


func open(tab: String = "build") -> void:
	_tab = tab
	var tb: Button = _tabs.get_node_or_null("Tab_" + tab) as Button
	if tb != null:
		tb.set_pressed_no_signal(true)
	_open = true
	visible = true
	_selected = null
	_refresh()
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"push_modal"):
		ui.call(&"push_modal", &"field_manual")
	Audio.play_2d(&"ui/page_turn", -6.0)


func close() -> void:
	if not _open:
		return
	_open = false
	visible = false
	var ui: Node = get_parent()
	if ui != null and ui.has_method(&"pop_modal"):
		ui.call(&"pop_modal", &"field_manual")


func is_open() -> bool:
	return _open


func show_note(note_id: StringName) -> void:
	open("notes")
	_select(Content.get_def(&"note", note_id))


func _unhandled_key_input(event: InputEvent) -> void:
	if _open and (event.is_action_pressed(&"guidebook") or event.is_action_pressed(&"cancel")):
		close()
		get_viewport().set_input_as_handled()


func _refresh() -> void:
	for c: Node in _list.get_children():
		c.queue_free()
	_detail.text = ""
	_action.visible = false
	var p: PlayerState = Game.local_player()
	match _tab:
		"build":
			var by_cat: Dictionary = {}
			for bp: BlueprintDef in Content.all(&"blueprint"):
				if not by_cat.has(bp.category):
					by_cat[bp.category] = []
				(by_cat[bp.category] as Array).append(bp)
			for cat: String in ["survival", "shelter", "crafting", "storage", "farming", "defense", "power", "walls", "floors"]:
				if not by_cat.has(cat):
					continue
				_header(cat.capitalize())
				for bp: BlueprintDef in by_cat[cat]:
					var known: bool = p != null and p.progression.knows_blueprint(bp)
					_entry(bp.display_name if known else "%s  (schematic needed)" % bp.display_name, bp, known)
		"notes":
			if p == null or p.read_notes.is_empty():
				_header("Nothing yet. People leave notes. Read them.")
			for nid: Variant in (p.read_notes.keys() if p != null else []):
				var n: NoteDef = Content.get_def(&"note", StringName(str(nid))) as NoteDef
				if n != null:
					_entry(n.title, n, true)
		"record":
			_record_list(p)
		"tips":
			for t: Array in TIPS:
				_entry(t[0], t, true)
		"journal":
			_journal_list()
	if _selected != null:
		_select(_selected)
	elif _tab == "record":
		_select("record")
	elif _tab == "journal":
		_select("journal")


func _header(text: String) -> void:
	var l := Label.new()
	l.text = text.to_upper()
	l.add_theme_color_override(&"font_color", INK_DIM)
	l.add_theme_font_size_override(&"font_size", 14)
	_list.add_child(l)


func _entry(text: String, payload: Variant, enabled: bool) -> void:
	var b := Button.new()
	b.text = "  " + text
	b.flat = true
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.theme_type_variation = &"ListButton"
	b.add_theme_color_override(&"font_color", INK if enabled else INK_DIM)
	b.add_theme_font_size_override(&"font_size", 18)
	b.pressed.connect(_select.bind(payload))
	_list.add_child(b)


func _select(payload: Variant) -> void:
	_selected = payload
	_action.visible = false
	_action.disabled = false
	if payload is BlueprintDef:
		var bp: BlueprintDef = payload
		var p: PlayerState = Game.local_player()
		var cost: Dictionary = bp.total_cost(Content)
		var lines: PackedStringArray = []
		for k: Variant in cost.keys():
			var d: ItemDef = Content.item(StringName(str(k)))
			var have: int = p.inventory.count_of(StringName(str(k))) if p != null else 0
			lines.append("  %s %d  [color=#%s](carrying %d)[/color]" % [d.display_name if d != null else str(k), int(cost[k]), "3a5a2a" if have >= int(cost[k]) else "7a3a22", have])
		var known: bool = p != null and p.progression.knows_blueprint(bp)
		_detail.text = "[b][font_size=22]%s[/font_size][/b]\n\n%s\n\n[b]Materials[/b]\n%s\n\n%s" % [bp.display_name, bp.description,
			"\n".join(lines), "Place the ghost, then bring the materials to it." if bp.mode == "assembly" else "Place the ghost, then carry logs into each slot."]
		if not known:
			_detail.text += "\n\n[i]You need the schematic for this.[/i]"
		_action.text = "Lay it out"
		_action.visible = known
	elif payload is NoteDef:
		var n: NoteDef = payload
		_detail.text = "[b][font_size=22]%s[/font_size][/b]\n[i]%s[/i]\n\n%s" % [n.title, n.author, n.body]
	elif payload is Array:
		_detail.text = "[b][font_size=22]%s[/font_size][/b]\n\n%s" % [payload[0], payload[1]]
	elif payload is AttributeDef:
		_attribute_detail(payload as AttributeDef)
	elif payload is PerkDef:
		_perk_detail(payload as PerkDef)
	elif payload is String and payload == "record":
		_record_detail()
	elif payload is String and payload == "journal":
		_journal_detail({})
	elif payload is Dictionary and (payload as Dictionary).has("journal"):
		_journal_detail(payload)


func _on_action() -> void:
	if _tab == "journal":
		var t: Object = tutorial()
		if t != null:
			Game.execute(&"tutorial.set_enabled", {"enabled": not bool(t.call(&"is_enabled"))})
			_refresh()
		return
	if _selected is AttributeDef:
		Game.execute(&"progression.raise_attribute", {"attribute": String((_selected as AttributeDef).id)})
		return
	if _selected is PerkDef:
		Game.execute(&"progression.buy_perk", {"perk": String((_selected as PerkDef).id)})
		return
	if _selected is BlueprintDef:
		var building: Node = Game.world.get(&"building") if Game.world != null else null
		if building != null and bool(building.call(&"begin_placement", (_selected as BlueprintDef).id)):
			close()
			Events.player_status_message.emit("Place the %s — [%s] place · [%s] rotate · [%s] cancel" % [(_selected as BlueprintDef).display_name,
				PlayerInteraction.key_label(&"attack"), PlayerInteraction.key_label(&"rotate_piece"), PlayerInteraction.key_label(&"cancel")], &"info")


# --- Journal tab (the first days' tutorial, hub contract) ------------------------------------------

## The world's TutorialTracker (world.tutorial), or null in a world without one.
static func tutorial() -> Object:
	var w: Node = Game.world
	if w == null or w.get(&"tutorial") == null:
		return null
	return w.get(&"tutorial")


## A step's body with its key placeholders named ({action:interact} -> E), the prompts' way.
static func render_body(t: Object, text: String) -> String:
	return str(t.call(&"render_body", text)) if t != null and t.has_method(&"render_body") else text


func _journal_list() -> void:
	var t: Object = tutorial()
	if t == null:
		_header("No journal in this world.")
		return
	var on: bool = bool(t.call(&"is_enabled"))
	_header("The first days" if on else "The first days (guidance off)")
	for st: Dictionary in (t.call(&"steps") as Array):
		var done: bool = bool(st.get("done", false))
		var current: bool = bool(st.get("current", false))
		var mark: String = "✓ " if done else ("> " if current else "· ")
		var label: String = mark + str(st.get("title", ""))
		if current and int(st.get("count", 1)) > 1:
			label += "  (%d / %d)" % [int(st.get("progress", 0)), int(st.get("count", 1))]
		var payload: Dictionary = st.duplicate()
		payload["journal"] = true
		_entry(label, payload, not done)
		if current:
			var b: Button = _list.get_child(_list.get_child_count() - 1) as Button
			b.add_theme_color_override(&"font_color", UiStyle.INK_MISSING)
	var d: Dictionary = t.call(&"distress") as Dictionary
	if bool(d.get("received", false)):
		_header("On the tether")
		_entry("A distress call", {"journal": true, "distress": true}, true)


func _journal_detail(st: Dictionary) -> void:
	var t: Object = tutorial()
	_action.visible = t != null
	_action.text = "Turn guidance off" if t != null and bool(t.call(&"is_enabled")) else "Turn guidance on"
	if t == null:
		_detail.text = ""
		return
	if bool(st.get("distress", false)):
		var d: Dictionary = t.call(&"distress") as Dictionary
		_detail.text = "[b][font_size=22]A distress call[/font_size][/b]\n[i]%s[/i]\n\n%s" % [distress_bearing(d.get("position", Vector3.ZERO)), str(d.get("text", ""))]
		return
	if st.is_empty():
		for s2: Dictionary in (t.call(&"steps") as Array):
			if bool(s2.get("current", false)):
				st = s2
		if st.is_empty():
			_detail.text = "[b][font_size=22]The first days[/font_size][/b]\n\nEvery step is done. The rest is yours."
			return
	var state: String = "Done." if bool(st.get("done", false)) else ("%d / %d" % [int(st.get("progress", 0)), int(st.get("count", 1))])
	_detail.text = "[b][font_size=22]%s[/font_size][/b]   [color=%s]%s[/color]\n\n%s" % [str(st.get("title", "")), UiStyle.hex(UiStyle.INK_DIM),
		state, render_body(t, str(st.get("body", "")))]


## Where a point is from the player, in words: "north-west, 420 m".
static func distress_bearing(at: Vector3) -> String:
	var w: Node = Game.world
	if w == null or w.get(&"player") == null:
		return ""
	return bearing_words((w.player as Node3D).global_position, at)


const COMPASS: PackedStringArray = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


## Compass words and distance from `from` to `to` (-Z is north, +X east).
static func bearing_words(from: Vector3, to: Vector3) -> String:
	var d := Vector2(to.x - from.x, to.z - from.z)
	if d.length() < 15.0:
		return "here"
	var ang: float = fposmod(atan2(d.x, -d.y), TAU)
	var i: int = int(round(ang / (TAU / 8.0))) % 8
	var m: float = d.length()
	return "%s, %s" % [COMPASS[i], ("%d m" % int(round(m / 10.0) * 10)) if m < 1000.0 else ("%.1f km" % (m / 1000.0))]


# --- Record tab ---------------------------------------------------------------------------------

func _attributes() -> Array[AttributeDef]:
	var out: Array[AttributeDef] = []
	for id: String in ATTR_ORDER:
		var a: AttributeDef = Content.get_def(&"attribute", StringName(id)) as AttributeDef
		if a != null:
			out.append(a)
	for a: AttributeDef in Content.all(&"attribute"):
		if not out.has(a):
			out.append(a)
	return out


func _perks_of(attr: StringName) -> Array[PerkDef]:
	var out: Array[PerkDef] = []
	for pk: PerkDef in Content.all(&"perk"):
		if pk.attribute == attr:
			out.append(pk)
	out.sort_custom(func(a: PerkDef, b: PerkDef) -> bool:
		var la: int = int(a.ranks[0]["attr_level"])
		var lb: int = int(b.ranks[0]["attr_level"])
		return la < lb if la != lb else String(a.id) < String(b.id))
	return out


func _record_list(p: PlayerState) -> void:
	if p == null:
		return
	var pr: Progression = p.progression
	_entry("Level %d  ·  %d point%s to spend" % [pr.level, pr.skill_points, "" if pr.skill_points == 1 else "s"], "record", true)
	for a: AttributeDef in _attributes():
		_header("%s  %d / %d" % [a.display_name, pr.attr_level(a.id), a.max_level])
		_entry("%s%s (train)" % ["› " if pr.can_raise_attribute(a.id) else "", a.display_name], a, pr.attr_level(a.id) < a.max_level)
		for pk: PerkDef in _perks_of(a.id):
			var rank: int = pr.perk_rank(pk.id)
			_entry("%s%s  %d/%d" % ["› " if pr.can_buy_perk(pk.id) else "", pk.display_name, rank, pk.max_rank()], pk, rank > 0 or pr.can_buy_perk(pk.id))


## "+3% melee damage, +2 pack space" for an effects dictionary (each value x `times`).
static func effects_text(effects: Dictionary, times: float = 1.0) -> String:
	var parts: PackedStringArray = []
	for k: String in effects:
		var v: float = float(effects[k]) * times
		if EFFECT_TEXT.has(k):
			var f: Array = EFFECT_TEXT[k]
			parts.append(str(f[0]) % (v * float(f[1])))
		else:
			parts.append("%s %+.2f" % [k.replace("_", " "), v])
	return ", ".join(parts)


func _record_detail() -> void:
	var p: PlayerState = Game.local_player()
	var s: GameSession = Game.session
	if p == null or s == null:
		return
	var pr: Progression = p.progression
	var st: Dictionary = s.stats
	var gs: int = s.gamestage(p)
	var lines: PackedStringArray = [
		"[b][font_size=22]%s[/font_size][/b]" % p.display_name,
		"Level [b]%d[/b]    XP %d / %d" % [pr.level, pr.xp, pr.xp_to_next()],
		"Points to spend: [b]%d[/b]" % pr.skill_points,
		"",
		"Gamestage [b]%d[/b]  [color=#6a5a48](level + days survived × %.1f)[/color]" % [gs, s.rules.num("gamestage_days_weight")],
		"[color=#6a5a48]The higher it is, the worse what hunts you — and the better what you find.[/color]",
		"",
		"Days survived: %d" % s.days_survived(),
		"Hollowed put down: %d" % int(st.get("zombies_killed", 0)),
		"Buildings cleared: %d" % int(st.get("pois_cleared", 0)),
		"Hums survived: %d" % int(st.get("hums_survived", 0)),
		"Trees felled: %d" % int(st.get("trees_felled", 0)),
		"",
		"[color=#6a5a48]Experience comes from everything you live through: kills (Seeded and Bloomed pay more), searching, building, crafting, clearing buildings and, above all, the Hum. Attributes raise passive strengths and open perks; perks need their attribute at the level shown.[/color]",
	]
	lines.append_array(_directive_lines(p.directives))
	_detail.text = "\n".join(lines)


## The open chapter of Program directives: done ones ticked, open ones with progress and reward.
func _directive_lines(dr: Directives) -> PackedStringArray:
	var out: PackedStringArray = ["", "[b]Program directives[/b]  —  %s" % ("all complete" if dr.all_done() else Directives.chapter_name(dr.chapter))]
	if dr.all_done():
		return out
	for d: DirectiveDef in Directives.chapter_defs(dr.chapter):
		if dr.done.has(d.id):
			out.append("[color=#3a5a2a]  ✓ %s[/color]" % dr.label(d))
			continue
		if dr.spent.has(d.id):
			out.append("[color=#8a7a6a]  – %s  (no such building in this world)[/color]" % d.display_name)
			continue
		var reward: PackedStringArray = []
		if d.reward_xp > 0:
			reward.append("%d XP" % d.reward_xp)
		for k: Variant in d.reward_items.keys():
			var idef: ItemDef = Content.item(StringName(str(k)))
			reward.append("%d %s" % [int(d.reward_items[k]), idef.display_name if idef != null else str(k)])
		out.append("  • %s  %s  [color=#6a5a48](%s)[/color]" % [dr.label(d), d.goal_text(dr.count_of(d.id)), ", ".join(reward)])
	return out


func _attribute_detail(a: AttributeDef) -> void:
	var p: PlayerState = Game.local_player()
	if p == null:
		return
	var pr: Progression = p.progression
	var lvl: int = pr.attr_level(a.id)
	var lines: PackedStringArray = [
		"[b][font_size=22]%s[/font_size][/b]   level %d / %d" % [a.display_name, lvl, a.max_level],
		a.description, "",
		"Each level: %s" % effects_text(a.per_level),
	]
	if lvl > 1:
		lines.append("Now: %s" % effects_text(a.per_level, float(lvl - 1)))
	var perks: PackedStringArray = []
	for pk: PerkDef in _perks_of(a.id):
		perks.append(pk.display_name)
	if not perks.is_empty():
		lines.append("\nPerks: %s" % ", ".join(perks))
	var why: String = pr.attribute_block_reason(a.id)
	if lvl < a.max_level:
		lines.append("\nTraining to %d costs %d point%s (you have %d)." % [lvl + 1, pr.attribute_cost(a.id), "" if pr.attribute_cost(a.id) == 1 else "s", pr.skill_points])
	_detail.text = "\n".join(lines)
	_action.text = "Train %s" % a.display_name if why == "" else "Train %s — %s" % [a.display_name, why]
	_action.disabled = why != ""
	_action.visible = lvl < a.max_level


func _perk_detail(pk: PerkDef) -> void:
	var p: PlayerState = Game.local_player()
	if p == null:
		return
	var pr: Progression = p.progression
	var rank: int = pr.perk_rank(pk.id)
	var attr: AttributeDef = Content.get_def(&"attribute", pk.attribute) as AttributeDef
	var an: String = attr.display_name if attr != null else String(pk.attribute)
	var lines: PackedStringArray = [
		"[b][font_size=22]%s[/font_size][/b]   rank %d / %d   [color=#6a5a48](%s)[/color]" % [pk.display_name, rank, pk.max_rank(), an],
		pk.description, "",
	]
	for i: int in pk.max_rank():
		var rk: Dictionary = pk.ranks[i]
		var text: String = str(rk.get("text", ""))
		if text == "":
			text = effects_text(rk["effects"])
		var unlocks: Array = rk.get("unlocks", [])
		if not unlocks.is_empty():
			var names: PackedStringArray = []
			for u: Variant in unlocks:
				var bp: BlueprintDef = Content.get_def(&"blueprint", StringName(str(u))) as BlueprintDef
				var rc: RecipeDef = Content.recipe(StringName(str(u)))
				names.append(bp.display_name if bp != null else (Content.item(rc.result).display_name if rc != null and Content.item(rc.result) != null else str(u)))
			text += "; learn %s" % ", ".join(names)
		var col: String = "3a5a2a" if i < rank else ("2a2015" if pr.attr_level(pk.attribute) >= int(rk["attr_level"]) else "8a7a6a")
		lines.append("[color=#%s]Rank %d  (%s %d)  —  %s%s[/color]" % [col, i + 1, an, int(rk["attr_level"]), text, "   ✓" if i < rank else ""])
	_detail.text = "\n".join(lines)
	var why: String = pr.perk_block_reason(pk.id)
	_action.text = "Learn rank %d" % (rank + 1) if why == "" else "Learn rank %d — %s" % [rank + 1, why]
	_action.disabled = why != ""
	_action.visible = rank < pk.max_rank()
