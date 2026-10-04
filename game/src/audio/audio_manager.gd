extends Node
## Audio manager (autoload `Audio`). Builds the bus layout from data/config/audio.json, resolves
## sound ids to generated files (res://assets/generated/audio/<id>[_NN].wav) with random variant
## selection, and plays 2D/3D one-shots with occlusion-aware 3D players (see Sound3D).
## Ambient beds and reverb zones are handled by AmbienceDirector / ReverbZone in the world.

const AUDIO_ROOT: String = "res://assets/generated/audio"

## sound id -> Array[AudioStream] (variants)
var _cache: Dictionary = {}
var _pool_2d: Array[AudioStreamPlayer] = []
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_rng.randomize()
	_build_buses()
	for i: int in 12:
		var p := AudioStreamPlayer.new()
		p.bus = &"UI"
		add_child(p)
		_pool_2d.append(p)


func _build_buses() -> void:
	var cfg: Dictionary = Content.config(&"audio")
	for b: Dictionary in cfg.get("buses", []):
		var name: String = str(b.get("name", ""))
		if name == "" or AudioServer.get_bus_index(name) >= 0:
			continue
		AudioServer.add_bus()
		var idx: int = AudioServer.bus_count - 1
		AudioServer.set_bus_name(idx, name)
		AudioServer.set_bus_send(idx, StringName(str(b.get("send", "Master"))))
		AudioServer.set_bus_volume_db(idx, float(b.get("volume_db", 0.0)))
		for fx: Dictionary in b.get("effects", []):
			var effect: AudioEffect = _make_effect(fx)
			if effect != null:
				AudioServer.add_bus_effect(idx, effect)


static func _make_effect(fx: Dictionary) -> AudioEffect:
	match str(fx.get("type", "")):
		"reverb":
			var r := AudioEffectReverb.new()
			r.room_size = float(fx.get("room_size", 0.6))
			r.damping = float(fx.get("damping", 0.5))
			r.wet = float(fx.get("wet", 0.3))
			r.dry = float(fx.get("dry", 1.0))
			r.predelay_msec = float(fx.get("predelay_ms", 40.0))
			return r
		"lowpass":
			var lp := AudioEffectLowPassFilter.new()
			lp.cutoff_hz = float(fx.get("cutoff_hz", 2000.0))
			return lp
		"limiter":
			var lim := AudioEffectHardLimiter.new()
			lim.ceiling_db = float(fx.get("ceiling_db", -0.5))
			return lim
		"compressor":
			var c := AudioEffectCompressor.new()
			c.threshold = float(fx.get("threshold_db", -12.0))
			c.ratio = float(fx.get("ratio", 4.0))
			return c
	return null


## Returns a random variant stream for a sound id ("sfx/axe_chop_wood"), or null.
func stream(sound_id: StringName) -> AudioStream:
	var variants: Array = _variants(sound_id)
	if variants.is_empty():
		return null
	return variants[_rng.randi() % variants.size()]


func _variants(sound_id: StringName) -> Array:
	if _cache.has(sound_id):
		return _cache[sound_id]
	var out: Array = []
	var base: String = AUDIO_ROOT.path_join(String(sound_id))
	if ResourceLoader.exists(base + ".wav"):
		out.append(load(base + ".wav"))
	for i: int in range(1, 17):
		var p: String = "%s_%02d.wav" % [base, i]
		if not ResourceLoader.exists(p):
			break
		out.append(load(p))
	_cache[sound_id] = out
	return out


func play_2d(sound_id: StringName, volume_db: float = 0.0, bus: StringName = &"UI", pitch: float = 1.0) -> void:
	var s: AudioStream = stream(sound_id)
	if s == null:
		return
	for p: AudioStreamPlayer in _pool_2d:
		if not p.playing:
			p.stream = s
			p.volume_db = volume_db
			p.bus = bus
			p.pitch_scale = pitch
			p.play()
			return


## Fire-and-forget positional sound. Returns the player (auto-freed when done) or null.
func play_3d(sound_id: StringName, pos: Vector3, opts: Dictionary = {}) -> Node3D:
	var s: AudioStream = stream(sound_id)
	var parent: Node = get_tree().current_scene
	if s == null or parent == null:
		return null
	var p := Sound3D.new()
	p.stream = s
	p.bus = StringName(str(opts.get("bus", "SFX")))
	p.volume_db = float(opts.get("volume_db", 0.0))
	p.unit_size = float(opts.get("unit_size", 6.0))
	p.max_distance = float(opts.get("max_distance", 90.0))
	p.pitch_scale = float(opts.get("pitch", 1.0)) * _rng.randf_range(0.94, 1.06)
	p.occlusion = bool(opts.get("occlusion", true))
	p.one_shot = true
	parent.add_child(p)
	p.global_position = pos
	p.play()
	return p
