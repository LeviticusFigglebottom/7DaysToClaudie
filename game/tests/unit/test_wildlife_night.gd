extends GutTest
## Deer and hares by the sky's light (docs/AI_TUNING.md, "Wildlife at night"): since GameWorld
## feeds Stimuli.ambient_light (733dd80) a person in the dark shows less, so the old extra night
## cut (sight x 0.45) made a deer blind past ~15 m. Each species now keeps senses.dark_sight of its
## sight in pitch dark: a walking person is still seen and run from at the flight distance on a
## moonless night, crouching gets you closer, the wind carries your scent as far as by day, and the
## animals hear your footsteps. test_probe prints the whole matrix (the tables in the doc).

## name -> [light on the player, as GameWorld feeds it]: noon, dusk, a moonlit and a moonless night.
const LIGHTS: Dictionary = {"day": 1.0, "dusk": 0.35, "moon": 0.15, "dark": 0.05}
const WALK: float = 3.4
const CROUCH: float = 1.7


func _def(id: StringName) -> WildlifeDef:
	return Content.get_def(&"wildlife", id) as WildlifeDef


## What an animal at the origin makes of the player `dist` m off down +Z, walking or crouch-walking
## toward it, in `light`; wind: 0 calm, 1 blowing from the player to the animal, -1 the other way.
## The same pipeline as WildlifeManager.senses_context + Animal._think (sight, scent, footsteps).
func _threat(d: WildlifeDef, dist: float, light: float, crouched: bool, wind: int) -> WildlifeBrain.Threat:
	var st := Stimuli.new()
	var lit: float = clampf(st.detection_range(1.0, 1.0, crouched, CROUCH if crouched else WALK, false, 0.0, 1.0), 0.05, 1.25)
	st.free()
	var vis: float = WildlifeBrain.visibility(d, lit, light)
	var t: WildlifeBrain.Threat = WildlifeBrain.person_threat(d, Vector3.ZERO, Vector3(0, 0, dist), vis, crouched,
		Vector2(0, -1) * float(wind), 0.6 if wind != 0 else 0.0)
	var step: WildlifeBrain.Threat = WildlifeBrain.sound_threat(d, 2.0 if crouched else 6.0, dist)
	return maxi(t, step) as WildlifeBrain.Threat


func test_a_deer_still_sees_a_walking_man_on_a_moonless_night() -> void:
	var d: WildlifeDef = _def(&"white_tailed_deer")
	assert_eq(_threat(d, 30.0, LIGHTS["dark"], false, 0), WildlifeBrain.Threat.FLEE, "inside its flight distance it bolts")
	assert_eq(_threat(d, 30.0, LIGHTS["moon"], false, 0), WildlifeBrain.Threat.FLEE)
	assert_eq(_threat(d, 80.0, LIGHTS["dark"], false, 0), WildlifeBrain.Threat.NONE, "80 m off in the dark: unseen")
	assert_eq(_threat(d, 20.0, LIGHTS["day"], false, 0), WildlifeBrain.Threat.FLEE, "by day as before")
	assert_eq(_threat(d, 50.0, LIGHTS["day"], false, 0), WildlifeBrain.Threat.ALERT)


func test_at_dusk_a_deer_looks_up_from_far_off() -> void:
	var d: WildlifeDef = _def(&"white_tailed_deer")
	assert_eq(_threat(d, 45.0, LIGHTS["dusk"], false, 0), WildlifeBrain.Threat.ALERT, "dusk is its hour: it sees you at 45 m")
	assert_eq(_threat(d, 25.0, LIGHTS["dusk"], true, 0), WildlifeBrain.Threat.NONE, "crouched at 25 m it doesn't")


func test_crouching_in_the_dark_gets_you_closer() -> void:
	var d: WildlifeDef = _def(&"white_tailed_deer")
	assert_ne(_threat(d, 20.0, LIGHTS["dark"], true, 0), WildlifeBrain.Threat.FLEE, "a crouched stalker at 20 m")
	assert_eq(_threat(d, 12.0, LIGHTS["dark"], true, 0), WildlifeBrain.Threat.FLEE, "but not to 12 m")


func test_the_wind_works_the_same_by_night() -> void:
	var d: WildlifeDef = _def(&"white_tailed_deer")
	assert_eq(_threat(d, 80.0, LIGHTS["dark"], true, 1), WildlifeBrain.Threat.FLEE, "downwind it smells you at 80 m")
	assert_eq(_threat(d, 40.0, LIGHTS["dark"], true, -1), WildlifeBrain.Threat.NONE, "upwind and crouched you get within 40 m")


func test_a_hare_sits_tight_then_goes() -> void:
	var h: WildlifeDef = _def(&"snowshoe_hare")
	assert_eq(_threat(h, 8.0, LIGHTS["dark"], false, 0), WildlifeBrain.Threat.FLEE, "walked up on at night it bolts")
	assert_eq(_threat(h, 14.0, LIGHTS["dark"], false, 0), WildlifeBrain.Threat.ALERT, "it has seen you at 14 m")
	assert_ne(_threat(h, 6.0, LIGHTS["dark"], true, 0), WildlifeBrain.Threat.FLEE, "crouched, you get to 6 m")


func test_footsteps_are_heard() -> void:
	var d: WildlifeDef = _def(&"white_tailed_deer")
	assert_eq(WildlifeBrain.sound_threat(d, 6.0, 7.0), WildlifeBrain.Threat.ALERT, "a walking tread at 7 m")
	assert_eq(WildlifeBrain.sound_threat(d, 2.0, 7.0), WildlifeBrain.Threat.NONE, "a crouched one isn't")
	var h: WildlifeDef = _def(&"snowshoe_hare")
	assert_eq(WildlifeBrain.sound_threat(h, 14.0, 12.0), WildlifeBrain.Threat.FLEE, "a sprint sends a hare off")


func test_a_carried_light_shows_whatever_the_dark() -> void:
	var d: WildlifeDef = _def(&"white_tailed_deer")
	assert_almost_eq(WildlifeBrain.visibility(d, 1.25, 0.0, true), 1.25, 0.001)
	assert_lt(WildlifeBrain.visibility(d, 1.0, 0.05), 0.5, "the dark costs it")
	assert_gt(WildlifeBrain.visibility(d, 1.0, 0.05), WildlifeBrain.visibility(_def(&"crow"), 1.0, 0.05), "deer see better at night than the default eye")


## The measurement in docs/AI_TUNING.md: threat at 20/40/80 m (F flee, A alert, - nothing), and the
## player walking (3.4 m/s) or crouch-walking (1.7 m/s) straight at the animal from 120 m: where it
## first looks up, where it bolts and after how long (one think per 0.25 s, as Animal does).
func test_probe() -> void:
	var out: PackedStringArray = ["| animal | light | stance | wind | 20 / 40 / 80 m | looks up at | bolts at |", "|---|---|---|---|---|---|---|"]
	for id: StringName in [&"white_tailed_deer", &"snowshoe_hare"]:
		var d: WildlifeDef = _def(id)
		for lk: String in LIGHTS:
			for crouched: bool in [false, true]:
				for wind: int in [0, -1, 1]:
					var cells: PackedStringArray = []
					for dist: float in [20.0, 40.0, 80.0]:
						cells.append(["-", "A", "F"][_threat(d, dist, LIGHTS[lk], crouched, wind)])
					var first_a: float = -1.0
					var first_f: float = -1.0
					var dd: float = 120.0
					var t: float = 0.0
					while dd > 1.0 and first_f < 0.0:
						var th: WildlifeBrain.Threat = _threat(d, dd, LIGHTS[lk], crouched, wind)
						if th != WildlifeBrain.Threat.NONE and first_a < 0.0:
							first_a = dd
						if th == WildlifeBrain.Threat.FLEE:
							first_f = dd
						else:
							dd -= (CROUCH if crouched else WALK) * 0.25
							t += 0.25
					var wl: String = "calm" if wind == 0 else ("downwind" if wind > 0 else "upwind")
					out.append("| %s | %s | %s | %s | %s | %s | %s |" % [id, lk, "crouch" if crouched else "walk", wl, " ".join(cells),
						"%.0f m" % first_a if first_a > 0.0 else "-", ("%.0f m (%.1f s)" % [first_f, t]) if first_f > 0.0 else "-"])
	gut.p("\n".join(out))
	assert_eq(out.size(), 2 + 2 * 4 * 2 * 3)
