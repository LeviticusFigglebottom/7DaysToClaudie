class_name AmbienceDirector
extends Node
## Ambient soundscape (the "ambience" world module): picks a bed from where you are and when —
## forest by day or night, the town, the lake shore or river, a house interior — and cross-fades
## between them; layers rain and strong wind from the weather (muffled indoors), the Hum's drone
## on horde nights, and short music cues (discovery, the Hum, dawn after it, death). The listener's
## surroundings also choose the reverb bus every 3D sound plays through (interior / cave / open).

const FADE: float = 2.5
const CHECK: float = 0.75

var world: Node
var _beds: Dictionary = {}
var _want: Dictionary = {}
var _t: float = 0.0


func setup_world(w: Node) -> void:
	world = w
	Events.horde_night_ended.connect(func(_d: int, _r: Dictionary) -> void: Audio.play_2d(&"music/dawn_relief", -4.0, &"Music"))
	Events.player_died.connect(func(_id: StringName, _c: String) -> void: Audio.play_2d(&"music/death", -2.0, &"Music"))
	Events.poi_discovered.connect(_on_poi_discovered)


func _layer(id: StringName) -> AudioStreamPlayer:
	if _beds.has(id):
		return _beds[id]
	var p := AudioStreamPlayer.new()
	p.bus = &"Music" if String(id).begins_with("music/") else &"Ambience"
	p.stream = Audio.stream(id)
	p.volume_db = -60.0
	if p.stream is AudioStreamWAV:
		var wav: AudioStreamWAV = (p.stream as AudioStreamWAV).duplicate()
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wav.loop_begin = 0
		wav.loop_end = int(wav.get_length() * wav.mix_rate)
		p.stream = wav
	add_child(p)
	if p.stream != null:
		p.play(randf() * maxf(0.0, p.stream.get_length() - 1.0))
	_beds[id] = p
	return p


func _process(delta: float) -> void:
	if world == null or world.get(&"player") == null or world.player == null:
		return
	_t -= delta
	if _t <= 0.0:
		_t = CHECK
		_choose()
	for id: StringName in _want:
		var p: AudioStreamPlayer = _layer(id)
		var target: float = float(_want[id])
		p.volume_db = move_toward(p.volume_db, target, delta * 60.0 / FADE)
	for id2: StringName in _beds:
		if not _want.has(id2):
			var q: AudioStreamPlayer = _beds[id2]
			q.volume_db = move_toward(q.volume_db, -60.0, delta * 60.0 / FADE)


func _choose() -> void:
	var p: Vector3 = (world.player as Node3D).global_position
	var clock: WorldClock = Game.session.clock
	var wp: Dictionary = Game.session.weather.params()
	var pois: Node = world.get(&"pois")
	var building: Node = world.get(&"building")
	var indoors: bool = pois != null and bool(pois.call(&"is_indoors", p))
	var sheltered: bool = indoors or (building != null and bool(building.call(&"is_sheltered", p)))
	_want = {}
	# Base bed.
	# Beds follow the light, not the rule clock: winter dusk comes before night_start_hour.
	var dark: bool = clock.sun_elevation_deg() < -3.0
	var bed: StringName = &"amb/forest_night" if dark else &"amb/forest_day"
	var rt: RegionTerrain = (world.get(&"terrain") as TerrainManager).region_terrain_at(p.x, p.z)
	var biome: String = rt.biome_at(p.x, p.z) if rt != null else ""
	if biome == "town":
		bed = &"amb/town" if not dark else &"amb/forest_night"
	elif biome != "":
		# A biome with beds of its own plays them (ADR-0041: amb/burn_*, amb/fen_*; the others fall
		# back to the forest's, as before).
		var bd: BiomeDef = Content.get_def(&"biome", StringName(biome)) as BiomeDef
		if bd != null and bd.ambience != "":
			var own := StringName("amb/%s_%s" % [bd.ambience, "night" if dark else "day"])
			if own != bed and Audio.stream(own) != null:
				bed = own
	var water: String = _water_near(p)
	if water != "" and not indoors:
		_want[&"amb/river" if water == "river" else &"amb/lake_shore"] = -8.0
	if indoors:
		_want[&"amb/interior_house"] = -6.0
		_want[bed] = -22.0
	else:
		_want[bed] = -6.0
	# Weather.
	var rain: float = float(wp.get("rain", 0.0))
	if rain > 0.05:
		var rid: StringName = &"amb/rain_heavy" if rain > 0.6 else &"amb/rain_light"
		_want[rid] = (-4.0 if not sheltered else -16.0) + (rain - 1.0) * 10.0
	if float(wp.get("wind", 0.0)) > 0.65:
		_want[&"amb/wind_strong"] = -8.0 if not sheltered else -20.0
	# The Hum.
	if clock.is_horde_active():
		_want[&"amb/the_hum"] = -2.0
		_want[&"music/dread_drone"] = -10.0
	elif clock.hours_until_horde() < 1.0:
		_want[&"amb/the_hum"] = -18.0 + (1.0 - clock.hours_until_horde()) * 12.0
	# Reverb of everything around you follows where you stand.
	Audio.set(&"sfx_bus", &"ReverbInterior" if indoors else &"SFX")


func _water_near(p: Vector3) -> String:
	var wsys: Node = world.get(&"water")
	if wsys == null or not wsys.has_method(&"depth_at"):
		return ""
	for o: Vector3 in [Vector3.ZERO, Vector3(14, 0, 0), Vector3(-14, 0, 0), Vector3(0, 0, 14), Vector3(0, 0, -14), Vector3(26, 0, 0), Vector3(-26, 0, 0), Vector3(0, 0, 26), Vector3(0, 0, -26)]:
		var q: Vector3 = p + o
		q.y = world.call(&"height_at", q.x, q.z)
		if float(wsys.call(&"depth_at", q)) > 0.3:
			return str(wsys.call(&"kind_at", q)) if wsys.has_method(&"kind_at") else "lake"
	return ""


## The discovery sting plays once per building per run (the visited flag is saved; a session-only
## list replayed it after every load).
func _on_poi_discovered(_id: StringName) -> void:
	Audio.play_2d(&"music/discovery", -8.0, &"Music")
