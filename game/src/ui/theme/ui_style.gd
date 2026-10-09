class_name UiStyle
extends RefCounted
## The game's one UI style (ADR-0063): Program paperwork on a field kit. Two surfaces share one
## palette and one set of fonts:
## * **paper** (field manual, crafting sheet, trader ledger, item tags): dark ink on aged paper;
## * **kit** (main menu, New Game, options, pause, loading): paper-coloured type on dark oiled
##   canvas, with rust as the one accent.
## Every screen takes its Theme from here instead of building StyleBoxes and colours of its own.
## Disabled controls get explicit colours on both themes: Godot's default draws them near-white,
## which made uncraftable recipes unreadable on the paper flap (player report 4, item 7).

const PAPER := Color(0.86, 0.82, 0.71)
const PAPER_DARK := Color(0.76, 0.71, 0.6)
const INK := Color(0.15, 0.12, 0.09)
## Secondary ink: still >= 4.5:1 against PAPER (WCAG AA for body text).
const INK_DIM := Color(0.36, 0.31, 0.26)
## What you lack: red-brown ink, readable on paper and distinct from INK by hue, not only value.
const INK_MISSING := Color(0.6, 0.13, 0.08)
## What you have: a dark green ink.
const INK_OK := Color(0.13, 0.36, 0.16)
const RUST := Color(0.66, 0.29, 0.13)
const RUST_BRIGHT := Color(0.86, 0.45, 0.22)
const KIT_BG := Color(0.065, 0.07, 0.068, 0.96)
const KIT_PANEL := Color(0.1, 0.105, 0.1, 0.97)
const KIT_LINE := Color(0.3, 0.29, 0.25)
const KIT_TEXT := Color(0.88, 0.85, 0.76)
const KIT_TEXT_DIM := Color(0.6, 0.6, 0.55)

const HEADING_FONT: String = "res://assets/fonts/SpecialElite-Regular.ttf"
const BODY_FONT: String = "res://assets/fonts/IBMPlexMono-Regular.ttf"
const BODY_BOLD_FONT: String = "res://assets/fonts/IBMPlexMono-Bold.ttf"
const HAND_FONT: String = "res://assets/fonts/Caveat-Variable.ttf"

## Base size of body text at a UI scale of 1 (1080p).
const BODY_SIZE: int = 18
## The UI scales with the window above 1080 lines (ADR-0063): the layout was drawn for 1080p.
const BASE_HEIGHT: float = 1080.0
const SCALES: PackedFloat32Array = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

static var _kit: Theme = null
static var _paper: Theme = null
static var _fonts: Dictionary = {}


static func font(path: String) -> Font:
	if not _fonts.has(path):
		_fonts[path] = load(path) if ResourceLoader.exists(path) else ThemeDB.fallback_font
	return _fonts[path]


static func heading_font() -> Font:
	return font(HEADING_FONT)


static func body_font() -> Font:
	return font(BODY_FONT)


static func bold_font() -> Font:
	return font(BODY_BOLD_FONT)


static func hand_font() -> Font:
	return font(HAND_FONT)


# --- Scale ------------------------------------------------------------------------------------

## The UI scale for a window `height` lines tall: 1 at 1080p and below (the layout fits 720p as
## drawn), growing with the height above it in quarter steps, so 1440p is 1.25 and 4K is 2.
static func auto_scale(height: int) -> float:
	if height <= int(BASE_HEIGHT):
		return 1.0
	return clampf(floorf(float(height) / BASE_HEIGHT * 4.0) / 4.0, 1.0, 2.0)


## The scale the setting asks for: 0 (auto) follows the window, any other value is fixed.
static func resolve_scale(setting: float, height: int) -> float:
	return auto_scale(height) if setting <= 0.0 else clampf(setting, SCALES[0], SCALES[SCALES.size() - 1])


## Applies the UI scale to a window's 2D content. The stretch mode stays disabled, so 3D renders
## at the window's resolution and only the canvas is scaled.
static func apply_scale(win: Window, setting: float) -> void:
	if win == null:
		return
	win.content_scale_factor = resolve_scale(setting, win.size.y)


# --- Themes -----------------------------------------------------------------------------------

## Dark canvas: menus, options, pause, the loading screen.
static func kit_theme() -> Theme:
	if _kit == null:
		_kit = _build(false)
	return _kit


## Aged paper: the field manual, the crafting sheet, the trader, item tags.
static func paper_theme() -> Theme:
	if _paper == null:
		_paper = _build(true)
	return _paper


static func _build(paper: bool) -> Theme:
	var t := Theme.new()
	t.default_font = body_font()
	t.default_font_size = BODY_SIZE
	var fg: Color = INK if paper else KIT_TEXT
	var dim: Color = INK_DIM if paper else KIT_TEXT_DIM
	var hover: Color = INK_MISSING if paper else RUST_BRIGHT
	var bg: Color = PAPER if paper else KIT_PANEL
	var line: Color = Color(INK, 0.45) if paper else KIT_LINE

	t.set_stylebox(&"panel", &"PanelContainer", panel_box(paper))
	t.set_stylebox(&"panel", &"Panel", panel_box(paper))
	for type: StringName in [&"Label", &"RichTextLabel"]:
		t.set_color(&"font_color" if type == &"Label" else &"default_color", type, fg)
	t.set_color(&"font_shadow_color", &"Label", Color(0, 0, 0, 0))

	# Buttons: a ruled box on paper, a canvas tab in the kit. Disabled is dim ink, never white.
	var normal := _box(Color(bg.lightened(0.04), 0.0 if paper else 0.85), line, 1, 6)
	var hovered := _box(Color(PAPER_DARK, 0.55) if paper else Color(0.16, 0.15, 0.13, 0.95), hover, 1, 6)
	var pressed := _box(Color(PAPER_DARK, 0.8) if paper else Color(0.2, 0.12, 0.08, 0.95), hover, 2, 6)
	var disabled := _box(Color(bg, 0.0), Color(line, 0.25), 1, 6)
	var focus := _box(Color(0, 0, 0, 0), hover, 1, 6)
	for type: StringName in [&"Button", &"OptionButton", &"CheckBox", &"CheckButton"]:
		t.set_stylebox(&"normal", type, normal)
		t.set_stylebox(&"hover", type, hovered)
		t.set_stylebox(&"pressed", type, pressed)
		t.set_stylebox(&"hover_pressed", type, pressed)
		t.set_stylebox(&"disabled", type, disabled)
		t.set_stylebox(&"focus", type, focus)
		t.set_color(&"font_color", type, fg)
		t.set_color(&"font_hover_color", type, hover)
		t.set_color(&"font_pressed_color", type, hover)
		t.set_color(&"font_hover_pressed_color", type, hover)
		t.set_color(&"font_focus_color", type, fg)
		t.set_color(&"font_disabled_color", type, dim)
		t.set_color(&"icon_disabled_color", type, Color(dim, 0.6))
	# Check boxes: drawn here, so an unchecked box shows on both surfaces (Godot's is dark grey).
	for type5: StringName in [&"CheckBox", &"CheckButton"]:
		t.set_icon(&"unchecked", type5, check_icon(false, fg))
		t.set_icon(&"checked", type5, check_icon(true, fg))
		t.set_icon(&"unchecked_disabled", type5, check_icon(false, dim))
		t.set_icon(&"checked_disabled", type5, check_icon(true, dim))
	# CheckBox / CheckButton draw no frame of their own.
	for type2: StringName in [&"CheckBox", &"CheckButton"]:
		t.set_stylebox(&"normal", type2, _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4))
		t.set_stylebox(&"hover", type2, _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4))
		t.set_stylebox(&"pressed", type2, _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4))
		t.set_stylebox(&"hover_pressed", type2, _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4))

	# Inputs.
	var field := _box(Color(PAPER_DARK, 0.35) if paper else Color(0.04, 0.045, 0.045, 0.95), line, 1, 6)
	for type3: StringName in [&"LineEdit", &"SpinBox", &"TextEdit"]:
		t.set_stylebox(&"normal", type3, field)
		t.set_stylebox(&"focus", type3, _box(Color(0, 0, 0, 0), hover, 1, 6))
		t.set_color(&"font_color", type3, fg)
		t.set_color(&"font_placeholder_color", type3, dim)
		t.set_color(&"caret_color", type3, hover)
		# Read-only (a disabled count): dim ink on no fill, never pale on grey.
		t.set_stylebox(&"read_only", type3, _box(Color(0, 0, 0, 0), Color(line, 0.35), 1, 6))
		t.set_color(&"font_uneditable_color", type3, dim)
		t.set_color(&"selection_color", type3, Color(hover, 0.35))

	# Sliders and bars.
	var groove := _box(Color(line, 0.6), Color(0, 0, 0, 0), 0, 0)
	groove.content_margin_top = 3
	groove.content_margin_bottom = 3
	t.set_stylebox(&"slider", &"HSlider", groove)
	t.set_stylebox(&"grabber_area", &"HSlider", _box(Color(hover, 0.85), Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox(&"grabber_area_highlight", &"HSlider", _box(hover, Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox(&"background", &"ProgressBar", _box(Color(line, 0.5), Color(0, 0, 0, 0), 0, 0))
	t.set_stylebox(&"fill", &"ProgressBar", _box(RUST if paper else RUST_BRIGHT, Color(0, 0, 0, 0), 0, 0))
	t.set_color(&"font_color", &"ProgressBar", fg)

	# Tabs.
	t.set_stylebox(&"panel", &"TabContainer", _box(Color(0, 0, 0, 0), line, 1, 10))
	t.set_stylebox(&"tab_selected", &"TabContainer", _tab(bg.lightened(0.05) if not paper else PAPER_DARK, hover))
	t.set_stylebox(&"tab_unselected", &"TabContainer", _tab(Color(0, 0, 0, 0), Color(0, 0, 0, 0)))
	t.set_stylebox(&"tab_hovered", &"TabContainer", _tab(Color(line, 0.3), Color(0, 0, 0, 0)))
	t.set_color(&"font_selected_color", &"TabContainer", fg)
	t.set_color(&"font_unselected_color", &"TabContainer", dim)
	t.set_color(&"font_hovered_color", &"TabContainer", hover)
	t.set_stylebox(&"tab_selected", &"TabBar", _tab(bg.lightened(0.05) if not paper else PAPER_DARK, hover))
	t.set_stylebox(&"tab_unselected", &"TabBar", _tab(Color(0, 0, 0, 0), Color(0, 0, 0, 0)))
	t.set_stylebox(&"tab_hovered", &"TabBar", _tab(Color(line, 0.3), Color(0, 0, 0, 0)))
	t.set_color(&"font_selected_color", &"TabBar", fg)
	t.set_color(&"font_unselected_color", &"TabBar", dim)
	t.set_color(&"font_hovered_color", &"TabBar", hover)

	# Scroll bars: a thin ink rule.
	for type4: StringName in [&"VScrollBar", &"HScrollBar"]:
		t.set_stylebox(&"scroll", type4, _box(Color(line, 0.25), Color(0, 0, 0, 0), 0, 3))
		t.set_stylebox(&"grabber", type4, _box(Color(dim, 0.7), Color(0, 0, 0, 0), 0, 3))
		t.set_stylebox(&"grabber_highlight", type4, _box(hover, Color(0, 0, 0, 0), 0, 3))
		t.set_stylebox(&"grabber_pressed", type4, _box(hover, Color(0, 0, 0, 0), 0, 3))

	# Popups (OptionButton lists, tooltips) are always readable dark-on-paper.
	t.set_stylebox(&"panel", &"PopupMenu", panel_box(true))
	t.set_color(&"font_color", &"PopupMenu", INK)
	t.set_color(&"font_hover_color", &"PopupMenu", INK_MISSING)
	t.set_color(&"font_disabled_color", &"PopupMenu", INK_DIM)
	t.set_stylebox(&"hover", &"PopupMenu", _box(Color(PAPER_DARK, 0.8), Color(0, 0, 0, 0), 0, 4))
	t.set_stylebox(&"panel", &"TooltipPanel", panel_box(true))
	t.set_color(&"font_color", &"TooltipLabel", INK)
	t.set_font_size(&"font_size", &"TooltipLabel", BODY_SIZE - 2)

	# Named variations: headings in the typewriter face, notes in the margin hand.
	t.add_type(&"HeadingLabel")
	t.set_type_variation(&"HeadingLabel", &"Label")
	t.set_font(&"font", &"HeadingLabel", heading_font())
	t.set_font_size(&"font_size", &"HeadingLabel", 30)
	t.set_color(&"font_color", &"HeadingLabel", fg)
	t.add_type(&"SubheadingLabel")
	t.set_type_variation(&"SubheadingLabel", &"Label")
	t.set_font(&"font", &"SubheadingLabel", heading_font())
	t.set_font_size(&"font_size", &"SubheadingLabel", 21)
	t.set_color(&"font_color", &"SubheadingLabel", INK_MISSING if paper else RUST_BRIGHT)
	t.add_type(&"DimLabel")
	t.set_type_variation(&"DimLabel", &"Label")
	t.set_font_size(&"font_size", &"DimLabel", BODY_SIZE - 3)
	t.set_color(&"font_color", &"DimLabel", dim)
	t.add_type(&"HandLabel")
	t.set_type_variation(&"HandLabel", &"Label")
	t.set_font(&"font", &"HandLabel", hand_font())
	t.set_font_size(&"font_size", &"HandLabel", 26)
	t.set_color(&"font_color", &"HandLabel", Color(0.17, 0.22, 0.42) if paper else KIT_TEXT_DIM)
	# A flat list entry (recipes, manual entries): no frame until hovered or chosen.
	t.add_type(&"ListButton")
	t.set_type_variation(&"ListButton", &"Button")
	var flat := _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 4)
	flat.content_margin_left = 8
	t.set_stylebox(&"normal", &"ListButton", flat)
	t.set_stylebox(&"disabled", &"ListButton", flat)
	var lh := _box(Color(PAPER_DARK, 0.6) if paper else Color(0.17, 0.16, 0.14, 0.9), Color(0, 0, 0, 0), 0, 4)
	lh.content_margin_left = 8
	t.set_stylebox(&"hover", &"ListButton", lh)
	var lp := _box(Color(PAPER_DARK, 0.95) if paper else Color(0.22, 0.14, 0.09, 0.95), Color(0, 0, 0, 0), 0, 4)
	lp.content_margin_left = 8
	lp.border_width_left = 3
	lp.border_color = hover
	t.set_stylebox(&"pressed", &"ListButton", lp)
	t.set_stylebox(&"hover_pressed", &"ListButton", lp)
	# The one call to action on a screen (Start, Make): rust with paper type.
	t.add_type(&"PrimaryButton")
	t.set_type_variation(&"PrimaryButton", &"Button")
	t.set_font(&"font", &"PrimaryButton", heading_font())
	t.set_font_size(&"font_size", &"PrimaryButton", 22)
	t.set_stylebox(&"normal", &"PrimaryButton", _box(RUST, RUST.darkened(0.3), 1, 8))
	t.set_stylebox(&"hover", &"PrimaryButton", _box(RUST.lightened(0.12), RUST_BRIGHT, 1, 8))
	t.set_stylebox(&"pressed", &"PrimaryButton", _box(RUST.darkened(0.15), RUST_BRIGHT, 2, 8))
	t.set_stylebox(&"hover_pressed", &"PrimaryButton", _box(RUST.darkened(0.15), RUST_BRIGHT, 2, 8))
	t.set_stylebox(&"disabled", &"PrimaryButton", _box(Color(0, 0, 0, 0), Color(dim, 0.5), 1, 8))
	for c: StringName in [&"font_color", &"font_hover_color", &"font_pressed_color", &"font_hover_pressed_color", &"font_focus_color"]:
		t.set_color(c, &"PrimaryButton", PAPER.lightened(0.3))
	t.set_color(&"font_disabled_color", &"PrimaryButton", dim)
	# The menu's big entries.
	t.add_type(&"MenuEntry")
	t.set_type_variation(&"MenuEntry", &"Button")
	t.set_font(&"font", &"MenuEntry", heading_font())
	t.set_font_size(&"font_size", &"MenuEntry", 24)
	var mb := _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 6)
	mb.content_margin_left = 18
	t.set_stylebox(&"normal", &"MenuEntry", mb)
	t.set_stylebox(&"disabled", &"MenuEntry", mb)
	t.set_stylebox(&"focus", &"MenuEntry", _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0, 6))
	var mh := _box(Color(0.0, 0.0, 0.0, 0.35), Color(0, 0, 0, 0), 0, 6)
	mh.content_margin_left = 18
	mh.border_width_left = 3
	mh.border_color = RUST_BRIGHT
	t.set_stylebox(&"hover", &"MenuEntry", mh)
	t.set_stylebox(&"pressed", &"MenuEntry", mh)
	t.set_stylebox(&"hover_pressed", &"MenuEntry", mh)
	return t


## A panel's frame: paper with an ink rule and a soft drop shadow, or dark canvas with a rust rule.
static func panel_box(paper: bool) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = PAPER if paper else KIT_PANEL
	sb.border_color = Color(INK, 0.5) if paper else KIT_LINE
	sb.set_border_width_all(1)
	if not paper:
		sb.border_width_top = 3
		sb.border_color = KIT_LINE
	sb.set_corner_radius_all(2)
	sb.set_content_margin_all(20)
	sb.shadow_color = Color(0, 0, 0, 0.45)
	sb.shadow_size = 12
	sb.shadow_offset = Vector2(0, 4)
	return sb


## A 20 px check box icon: an inked square, with a tick when checked.
static func check_icon(checked: bool, c: Color) -> ImageTexture:
	var n: int = 20
	var img := Image.create(n, n, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for i: int in n:
		for w: int in 2:
			img.set_pixel(i, w, c)
			img.set_pixel(i, n - 1 - w, c)
			img.set_pixel(w, i, c)
			img.set_pixel(n - 1 - w, i, c)
	if checked:
		# A tick from (5, 10) down to (8, 14), then up to (15, 5), three pixels thick.
		for k: int in 40:
			var t: float = float(k) / 39.0
			var p: Vector2 = Vector2(4.5, 10.0).lerp(Vector2(8.0, 14.5), t * 2.0) if t < 0.5 else Vector2(8.0, 14.5).lerp(Vector2(15.5, 4.5), (t - 0.5) * 2.0)
			for dx: int in range(-1, 2):
				for dy: int in range(-1, 1):
					var x: int = clampi(int(p.x) + dx, 0, n - 1)
					var y: int = clampi(int(p.y) + dy, 0, n - 1)
					img.set_pixel(x, y, c)
	return ImageTexture.create_from_image(img)


static func _box(bg: Color, border: Color, width: int, margin: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(width)
	sb.set_corner_radius_all(2)
	sb.content_margin_left = margin + 4
	sb.content_margin_right = margin + 4
	sb.content_margin_top = margin
	sb.content_margin_bottom = margin
	return sb


static func _tab(bg: Color, accent: Color) -> StyleBoxFlat:
	var sb := _box(bg, Color(0, 0, 0, 0), 0, 6)
	sb.border_width_bottom = 2
	sb.border_color = accent
	sb.content_margin_left = 14
	sb.content_margin_right = 14
	return sb


# --- Small builders shared by every screen ----------------------------------------------------

static func label(text: String, variation: StringName = &"") -> Label:
	var l := Label.new()
	l.text = text
	if variation != &"":
		l.theme_type_variation = variation
	return l


## Colour as a BBCode hex for RichTextLabel text.
static func hex(c: Color) -> String:
	return "#" + c.to_html(false)


## A UI or music sound's level in dB (data/config/audio.json `ui_levels`), `fallback` when unset.
static func level(key: String, fallback: float) -> float:
	var db: Object = ContentDB.instance
	if db == null:
		return fallback
	return float((db.call(&"config", &"audio").get("ui_levels", {}) as Dictionary).get(key, fallback))
