class_name MenuBackdrop
extends Control
## The main menu's backdrop (player report 4, item 3; ADR-0063, ADR-0065): the valley of Larch
## Hollow at dusk, as pictures rendered offline from the real main map (`make stills`, MenuFlight)
## that the menu drifts across slowly, one dissolving into the next, like a camera panning.
##
## It used to be built and drawn live: the region's terrain, water and some thousands of trees in
## a SubViewport. The packaged build's menu froze on the owner's machine as soon as it was used
## (Build #94), and a software renderer froze the same way for minutes. Pictures cost nothing to
## draw on any machine, load off the main thread, and never touch the scene.
##
## "Menu backdrop" in Options picks moving (the drift), still (the first picture) or off. Without
## the generated assets (or headless) the menu stays plain.

const DIR: String = "res://assets/generated/stills/"
const COUNT: int = 5
## Seconds each picture shows (fade in to fade out), and the dissolve between two.
const HOLD: float = 17.0
const DISSOLVE: float = 3.5
## How far a picture is zoomed (its start and end), and how far it drifts (a share of the screen).
const ZOOM: Vector2 = Vector2(1.08, 1.16)
const DRIFT: float = 0.03
const FADE_IN: float = 2.0

## "moving" | "still" | "off" (Settings.menu_backdrop).
var mode: String = "moving"

var _paths: PackedStringArray = []
var _textures: Array[Texture2D] = []
## The two pictures on screen (the one showing and the next, dissolving in), which picture shows,
## and seconds into it.
var _a: TextureRect
var _b: TextureRect
var _index: int = 0
var _t: float = 0.0
var _started: bool = false
var _fade_t: float = 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip_contents = true
	modulate.a = 0.0
	set_process(false)
	if mode == "off" or DisplayServer.get_name() == "headless":
		return
	_paths = picture_paths(DIR, COUNT if mode == "moving" else 1)
	if _paths.is_empty():
		Log.info("menu", "backdrop: no generated pictures; the menu stays plain")
		return
	for p: String in _paths:
		ResourceLoader.load_threaded_request(p, "Texture2D")
	_a = _picture()
	_b = _picture()
	set_process(true)


## The pictures that exist of `count` (DIR/menu_<i>.png), in order.
static func picture_paths(dir: String, count: int) -> PackedStringArray:
	var out: PackedStringArray = []
	for i: int in count:
		var p: String = dir.path_join("menu_%d.png" % i)
		if ResourceLoader.exists(p):
			out.append(p)
	return out


func _picture() -> TextureRect:
	var r := TextureRect.new()
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	r.modulate.a = 0.0
	add_child(r)
	r.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	return r


func _process(delta: float) -> void:
	if not _started:
		# Every picture loads on a worker; the first shows as soon as it is in.
		if not _collect():
			return
		_started = true
		_show(_a, 0)
		_a.modulate.a = 1.0
	_fade_t = minf(_fade_t + delta, FADE_IN)
	modulate.a = _fade_t / FADE_IN
	if mode != "moving" or _textures.size() < 2:
		_pose(_a, 0, 0.5)
		if _fade_t >= FADE_IN:
			set_process(false)
		return
	_t += delta
	_pose(_a, _index, _t / HOLD)
	if _t >= HOLD - DISSOLVE:
		var next: int = (_index + 1) % _textures.size()
		if _b.texture != _textures[next]:
			_show(_b, next)
		var k: float = clampf((_t - (HOLD - DISSOLVE)) / DISSOLVE, 0.0, 1.0)
		var alphas: Vector2 = dissolve_alphas(k)
		_a.modulate.a = alphas.x
		_b.modulate.a = alphas.y
		_pose(_b, next, (_t - (HOLD - DISSOLVE)) / HOLD)
		if k >= 1.0:
			var old: TextureRect = _a
			_a = _b
			_b = old
			_a.modulate.a = 1.0
			_b.modulate.a = 0.0
			_index = next
			_t = DISSOLVE


## Takes the pictures that have loaded; true once all of them are in (failed ones are dropped).
func _collect() -> bool:
	var pending: bool = false
	for p: String in _paths:
		match ResourceLoader.load_threaded_get_status(p):
			ResourceLoader.THREAD_LOAD_IN_PROGRESS:
				pending = true
	if pending:
		return false
	for p2: String in _paths:
		var tex: Texture2D = ResourceLoader.load_threaded_get(p2) as Texture2D
		if tex != null:
			_textures.append(tex)
	if _textures.is_empty():
		set_process(false)
		return false
	return true


func _show(r: TextureRect, i: int) -> void:
	r.texture = _textures[i]
	r.move_to_front()


## Picture `i`'s pan at `k` (0..1 of its time): a slow zoom and a drift whose direction alternates
## from picture to picture.
func _pose(r: TextureRect, i: int, k: float) -> void:
	var e: float = clampf(k, 0.0, 1.0)
	r.pivot_offset = r.size * 0.5
	r.scale = Vector2.ONE * pan_zoom(i, e)
	r.position = pan_drift(i, e) * r.size


## How strongly the outgoing (x) and incoming (y) pictures show at `k` (0..1) of a dissolve: a dip
## through the dusk behind them, not an even crossfade. Every picture frames the river down the
## middle, and two of them at half strength showed two riverbeds at once, which reads as a
## rendering fault. Here each is about a quarter strength halfway, so the frame dims toward
## dusk (not to black: that blinked every 13 s) and the old one is mostly gone as the new one rises.
static func dissolve_alphas(k: float) -> Vector2:
	return Vector2(1.0 - smoothstep(0.0, 0.75, k), smoothstep(0.25, 1.0, k))


## The zoom of picture `i` at `k`: in on even pictures, out on odd ones.
static func pan_zoom(i: int, k: float) -> float:
	return lerpf(ZOOM.x, ZOOM.y, k) if i % 2 == 0 else lerpf(ZOOM.y, ZOOM.x, k)


## The drift of picture `i` at `k`, as a share of the screen: sideways, alternating left and right,
## always inside what the zoom leaves spare (never showing an edge).
static func pan_drift(i: int, k: float) -> Vector2:
	var dir: float = 1.0 if i % 2 == 0 else -1.0
	return Vector2(dir * DRIFT * (k - 0.5) * 2.0, -0.008 * (k - 0.5))
