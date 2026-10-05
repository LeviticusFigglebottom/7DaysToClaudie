class_name PopulationDef
extends ContentDef
## Who the Hollowed were before the Bloom, by place (ADR-0028): per enemy type, the bodies a
## building, a sleeper's post or a region dresses its Hollowed in, weighted. A building names one
## with PoiDef `population` (a sleeper entry may name its own), a region with `population` in its
## region.json; EnemyVisual asks PopulationDef.pick() when it builds a body.
##
## A body is a character model id ("characters/<id>", tools/assetgen/blender_catalogs/
## characters.py). Every body shares the Hollowed skeleton, so any body can play any enemy type.
## "*" lists the bodies for enemy types the population does not name. `mix` is the share of its
## Hollowed that wear the population's bodies; the rest keep their type's own (a visitor among the
## patients). Picks are deterministic per Hollowed: the same sleeper wears the same clothes on
## every visit and every machine.

## Enemy id (or "*") -> {body id: weight}.
var bodies: Dictionary = {}
var mix: float = 1.0


func _fields() -> PackedStringArray:
	return ["bodies", "mix"]


func _parse(r: DefReader) -> void:
	mix = clampf(r.num("mix", 1.0), 0.0, 1.0)
	var raw: Dictionary = r.dict("bodies")
	bodies = {}
	for k: Variant in raw.keys():
		var table: Variant = raw[k]
		if not table is Dictionary or (table as Dictionary).is_empty():
			r.err("bodies.%s must be a non-empty object {body id: weight}" % k)
			continue
		var clean: Dictionary = {}
		for b: Variant in (table as Dictionary).keys():
			var w: Variant = table[b]
			if not (w is float or w is int) or float(w) <= 0.0:
				r.err("bodies.%s.%s: weight must be a number > 0" % [k, b])
				continue
			if not str(b).begins_with("characters/"):
				r.err("bodies.%s: body '%s' must be a character model id (characters/<id>)" % [k, b])
				continue
			clean[str(b)] = float(w)
		bodies[str(k)] = clean
	if bodies.is_empty():
		r.err("a population needs bodies")


func _validate(db: Node, out: PackedStringArray) -> void:
	for k: String in bodies:
		if k != "*" and not db.has_def(&"enemy", StringName(k)):
			out.append("%s: enemy '%s' unknown" % [ctx(), k])


## The bodies (id -> weight) this population dresses `enemy_id` in; {} = the type keeps its own.
func bodies_for(enemy_id: StringName) -> Dictionary:
	return bodies.get(String(enemy_id), bodies.get("*", {}))


## Every body id the population can put on any Hollowed (asset checks, tests).
func all_bodies() -> PackedStringArray:
	var out: PackedStringArray = []
	for k: String in bodies:
		for b: String in bodies[k]:
			if not out.has(b):
				out.append(b)
	out.sort()
	return out


## The body for one Hollowed of type `enemy_id`, keyed by something stable for it (its entity id):
## one of the population's bodies, or "" to keep the type's own pick (outside `mix`, or the
## population has nothing for that type).
func pick(enemy_id: StringName, key: String) -> String:
	var table: Dictionary = bodies_for(enemy_id)
	if table.is_empty():
		return ""
	var rng := RandomNumberGenerator.new()
	rng.seed = Ids.hash64("look:%s:%s" % [id, key])
	if rng.randf() >= mix:
		return ""
	# Sorted, so the pick never depends on the order the JSON was read in.
	var ids: Array = table.keys()
	ids.sort()
	var total: float = 0.0
	for b: String in ids:
		total += float(table[b])
	var x: float = rng.randf() * total
	for b: String in ids:
		x -= float(table[b])
		if x < 0.0:
			return b
	return str(ids.back())
