class_name ItemCard
extends PanelContainer
## A paper tag describing one item (TD-014's item tooltips): name and quality, what kind of
## thing it is, its numbers (damage, food, fuel...), wear, bulk and worth, the description, and
## what the mouse buttons do with it here. Shown by the salvage roll next to the hovered item.

const CONSUME_LABELS: Dictionary = {
	"fullness": "Food", "hydration": "Water", "health": "Health", "stamina": "Stamina",
	"warmth": "Warmth", "infection": "Infection", "bleeding": "Bleeding",
}

var _name: Label
var _kind: Label
var _body: RichTextLabel
var _actions: Label


func _init() -> void:
	theme = UiStyle.paper_theme()
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(380, 0)
	var sb: StyleBoxFlat = UiStyle.panel_box(true)
	sb.set_content_margin_all(14)
	add_theme_stylebox_override(&"panel", sb)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 4)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(v)
	_name = UiStyle.label("", &"SubheadingLabel")
	v.add_child(_name)
	_kind = UiStyle.label("", &"DimLabel")
	v.add_child(_kind)
	_body = RichTextLabel.new()
	_body.bbcode_enabled = true
	_body.fit_content = true
	_body.scroll_active = false
	_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_body.add_theme_font_override(&"bold_font", UiStyle.bold_font())
	_body.add_theme_font_size_override(&"normal_font_size", UiStyle.BODY_SIZE - 2)
	_body.add_theme_font_size_override(&"bold_font_size", UiStyle.BODY_SIZE - 2)
	v.add_child(_body)
	_actions = UiStyle.label("", &"DimLabel")
	_actions.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_actions)


## Fills the card for a stack; `actions` is the line of key hints ("[LMB] equip   [RMB] drop").
func show_stack(s: ItemStack, actions: String) -> void:
	var d: ItemDef = s.def()
	if d == null:
		return
	_name.text = d.display_name + ((" ×%d" % s.count) if s.count > 1 else "")
	var kind: String = d.category.capitalize()
	if s.quality > 0:
		kind += "  ·  %s (Q%d)" % [ItemStack.quality_name(s.quality), s.quality]
		_name.add_theme_color_override(&"font_color", ItemStack.quality_color(s.quality).darkened(0.35))
	else:
		_name.remove_theme_color_override(&"font_color")
	_kind.text = kind
	_body.text = body_bbcode(s)
	_actions.text = actions
	_actions.visible = actions != ""
	reset_size()


## The card's text: stats, wear, bulk/worth and the description.
static func body_bbcode(s: ItemStack) -> String:
	var d: ItemDef = s.def()
	var lines: PackedStringArray = []
	var stats: PackedStringArray = stat_lines(d, s.quality)
	if not stats.is_empty():
		lines.append("   ".join(stats))
	if d.durability > 0.0:
		var full: float = d.durability * ItemStack.quality_durability_mult(s.quality)
		var pct: int = int(round(100.0 * s.durability / maxf(1.0, full)))
		var c: Color = UiStyle.INK_OK if pct > 50 else (UiStyle.INK if pct > 20 else UiStyle.INK_MISSING)
		lines.append("Condition [color=%s]%d%%[/color]" % [UiStyle.hex(c), pct])
	var bulk: String = "Bulk %.1f" % (d.bulk * s.count) if s.count > 1 else "Bulk %.1f" % d.bulk
	if s.count > 1:
		bulk += " (%.2f each)" % d.bulk
	if d.value > 0:
		bulk += "   ·   Worth %d scrip" % d.value
	lines.append("[color=%s]%s[/color]" % [UiStyle.hex(UiStyle.INK_DIM), bulk])
	if d.description != "":
		lines.append(d.description)
	return "\n".join(lines)


## The numbers worth knowing about an item, short: "Damage 24 slash", "Food +30", "Burns 2 min".
static func stat_lines(d: ItemDef, quality: int) -> PackedStringArray:
	var out: PackedStringArray = []
	if d == null:
		return out
	var e: Dictionary = d.equip
	if e.has("damage"):
		var dmg: float = float(e["damage"]) * (ItemStack.quality_damage_mult(quality) if quality > 0 else 1.0)
		out.append("Damage %d%s" % [roundi(dmg), (" " + str(e["damage_type"])) if e.has("damage_type") else ""])
	if e.has("reach"):
		out.append("Reach %.1f m" % float(e["reach"]))
	if e.has("range"):
		out.append("Range %d m" % int(e["range"]))
	if e.has("mag_size"):
		out.append("Holds %d" % int(e["mag_size"]))
	var tools: Array = e.get("tools", [])
	if not tools.is_empty():
		out.append("Works as: %s" % ", ".join(PackedStringArray(tools.map(func(t: Variant) -> String: return str(t)))))
	for k: String in CONSUME_LABELS:
		if d.consume.has(k):
			var v: float = float(d.consume[k])
			out.append("%s %s%s" % [CONSUME_LABELS[k], "+" if v > 0 else "", str(snappedf(v, 0.1)).trim_suffix(".0")])
	if d.fuel > 0.0:
		out.append("Burns %s" % (("%d s" % int(d.fuel)) if d.fuel < 120.0 else ("%d min" % int(d.fuel / 60.0))))
	return out
