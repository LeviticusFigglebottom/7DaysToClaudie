class_name SoundCaptions
extends RefCounted
## Captions for the big sounds the player hears but may not see (mid-game audit G4): wolves howling,
## the Hollowed calling, a Rammer's rush, the Ashen's war cries, Ezra calling from afar. The game's
## sources call `say`; it rate-limits per group (one howl caption per pack per `every` s), leaves out
## a sound right beside the player (seen, not just heard) and emits Events.sound_caption, which
## GameUI shows (with its bearing) only when captions are on. Text is lowercase, no brackets.

## Nearer than this (m) the source is in plain sight: no caption.
const NEAR: float = 8.0

## Group key -> when it was last captioned (s, ticks clock).
static var _last: Dictionary = {}


## Captions `text` at `at` unless the group `key` was captioned within `every` s or the player is
## within NEAR m of it.
static func say(key: String, text: String, at: Vector3, every: float = 10.0) -> void:
	if not Events.has_signal(&"sound_caption"):
		return
	var now: float = Time.get_ticks_msec() / 1000.0
	if now - float(_last.get(key, -1000.0)) < every:
		return
	var p: Node3D = Game.world.get(&"player") as Node3D if Game.world != null else null
	if p != null and p.global_position.distance_to(at) < NEAR:
		return
	_last[key] = now
	Events.emit_signal(&"sound_caption", text, at)


## The group key of a sound by where it is: the Hollowed calling in one 40 m cell count once.
static func cell_key(prefix: String, at: Vector3) -> String:
	return "%s:%d:%d" % [prefix, floori(at.x / 40.0), floori(at.z / 40.0)]
