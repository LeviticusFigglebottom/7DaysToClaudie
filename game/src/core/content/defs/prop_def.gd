class_name PropDef
extends ContentDef
## A set-dressing prop (furniture, appliances, clutter, vehicles, debris).

## Model ids for condition variants: {"clean": id, "worn": id, "destroyed": id}
var variants: Dictionary = {}
## "box" | "convex" | "mesh" | "none"
var collision: String = "box"
## "static" | "rigid" | "carry"
var physics: String = "static"
var hp: float = 0.0
var size: Vector3 = Vector3.ONE
## Container def id if this prop is lootable.
var container: StringName = &""
## {color, energy, range, flicker, offset:[x,y,z]} for light-emitting props.
var light: Dictionary = {}
var blocks_sight: bool = true
var wall_mounted: bool = false
## Room tags this prop suits (kitchen, bedroom, bathroom, living, office, store, garage, basement,
## diner, hallway, exterior, any). PoiBuilder.ROOM_TAGS maps POI room types onto these.
var rooms: PackedStringArray = []


func _fields() -> PackedStringArray:
	return ["variants", "collision", "physics", "hp", "size", "container", "light", "blocks_sight", "wall_mounted", "rooms"]


func _parse(r: DefReader) -> void:
	variants = r.dict("variants")
	collision = r.enum_str("collision", ["box", "convex", "mesh", "none"], "box")
	physics = r.enum_str("physics", ["static", "rigid", "carry"], "static")
	hp = r.num("hp", 0.0)
	size = r.vec3("size", Vector3.ONE)
	container = r.sname("container")
	light = r.dict("light")
	blocks_sight = r.boolean("blocks_sight", true)
	wall_mounted = r.boolean("wall_mounted", false)
	rooms = r.strings("rooms")
	if variants.is_empty():
		r.err("prop needs variants {clean|worn|destroyed: model}")


func _validate(db: Node, out: PackedStringArray) -> void:
	if container != &"" and not db.has_def(&"container", container):
		out.append("%s: container '%s' unknown" % [ctx(), container])


func model_for(condition: String) -> String:
	if variants.has(condition):
		return str(variants[condition])
	for c: String in ["worn", "clean", "destroyed"]:
		if variants.has(c):
			return str(variants[c])
	return ""
