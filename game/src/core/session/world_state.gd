class_name WorldState
extends RefCounted
## Authoritative ledger of everything the player changed in the world (serializable).
## The world is regenerated deterministically from its seed + region data; only *differences*
## are stored here, keyed by deterministic ids (ADR-0003, ADR-0005).

## piece id -> {def, pos:[3], rot:[4] (quat xyzw), hp, hp_mult?, grounded, links:{id: rel}, owner}
var structures: Dictionary = {}
## blueprint instance id -> {def, pos:[3], rot:[4], delivered:{item:n}, placed:[piece index]}
var blueprints: Dictionary = {}
## container id -> {opened: bool, items: [stack dicts] | null (= not rolled yet),
##                   rolled_day: int, gen: int (loot respawns re-roll with gen + 1)}
var containers: Dictionary = {}
## poi instance id -> {visited, cleared, dead: [sleeper ids], broken: [piece ids], doors: {id: state}, traps: {id: state}}
var pois: Dictionary = {}
## chunk key -> {tree index (String): {state: "stump", day}}
var trees: Dictionary = {}
## dropped item / loose log entities: id -> {kind: "item"|"log", stack?, pos:[3], rot:[4]}
var loose: Dictionary = {}
## chunk key -> PackedByteArray (terrain height deltas / volume densities), saved as chunks/<key>.bin
var chunk_blobs: Dictionary = {}
## Story / tutorial flags (also last_drop_day for SupplyDrops).
var flags: Dictionary = {}
## Remand supply drops still in the world: drop id -> {pos:[3], day, tier}.
var drops: Dictionary = {}


func container_state(id: StringName) -> Dictionary:
	return containers.get(String(id), {})


func set_container_items(id: StringName, inv: Inventory, opened: bool = true, rolled_day: int = -1, gen: int = -1) -> void:
	var items: Array = []
	for s: ItemStack in inv.stacks:
		items.append(s.to_dict())
	var prev: Dictionary = containers.get(String(id), {})
	containers[String(id)] = {"opened": opened, "items": items,
		"rolled_day": rolled_day if rolled_day >= 0 else int(prev.get("rolled_day", 0)),
		"gen": gen if gen >= 0 else int(prev.get("gen", 0))}


func poi_state(id: StringName) -> Dictionary:
	var key: String = String(id)
	if not pois.has(key):
		pois[key] = {"visited": false, "cleared": false, "dead": [], "broken": [], "doors": {}, "traps": {}}
	return pois[key]


func tree_state(chunk_key: String, index: int) -> Dictionary:
	return (trees.get(chunk_key, {}) as Dictionary).get(str(index), {})


func set_tree_state(chunk_key: String, index: int, state: Dictionary) -> void:
	if not trees.has(chunk_key):
		trees[chunk_key] = {}
	trees[chunk_key][str(index)] = state


func to_dict() -> Dictionary:
	return {
		"structures": structures, "blueprints": blueprints, "containers": containers, "pois": pois,
		"trees": trees, "loose": loose, "flags": flags, "drops": drops, "chunk_keys": chunk_blobs.keys(),
	}


## Blobs are attached separately by SaveSystem.
func from_dict(d: Dictionary) -> void:
	structures = d.get("structures", {})
	blueprints = d.get("blueprints", {})
	containers = d.get("containers", {})
	pois = d.get("pois", {})
	trees = d.get("trees", {})
	loose = d.get("loose", {})
	flags = d.get("flags", {})
	drops = d.get("drops", {})
