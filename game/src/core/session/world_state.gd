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
## poi instance id -> {visited, cleared, dead: [sleeper ids], broken: [piece ids], doors: {id: state},
##   traps: {trap id: "triggered" (can chime) | "sprung" | "disarmed"}, hp: {piece id: hp},
##   triggers: {trigger id: true} (fired ambush triggers, ADR-0018),
##   keys: 2 = pieces keyed by authored ids (TD-031); 1 = a pre-v3 save still keyed by list
##   position, which PoiInstance re-keys when the building is next built}
var pois: Dictionary = {}

## Current POI piece-key format (see `pois`).
const POI_KEYS: int = 2
## How this world dresses its buildings (ADR-0030, PoiDressing): 2 = per run (alternatives, wear,
## scatter and decals follow the world seed); 1 = legacy (saves from before save v5: the authored
## defaults and the instance-id scatter they were played with). A POI state may pin its picks
## ("picks": {group: option}) the first time the building is built.
var poi_dressing: int = 2
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
## Fungal mounds where Hum survivors rooted at dawn (BloomMounds, ADR-0025): mound id ->
## {pos:[3], yaw, model, day (game day, fractional, when it rooted), harvested: bool}.
var mounds: Dictionary = {}
## Trader posts (ADR-0039): trader id (or post id for a `stock_per_post` def, TD-146) ->
## {period: restock period rolled, stock: {item: {count, rep_tier}}}.
var traders: Dictionary = {}
## The Ashen (ADR-0048): {hostility, level, last_raid_day, base_marked, camps: {building id: {dead, alerted}}}.
## Loads empty from older saves (no version bump).
var ashen: Dictionary = {}
## Gardens and rain catchers (ADR-0049), by the piece id of their structure:
## bed -> {kind: "bed", water: soil moisture, plots: [{} (empty) | {crop, grown: days, health, dead?}]};
## catcher -> {kind: "catcher", water: units}. Loads empty from saves before it (no version bump).
var farms: Dictionary = {}
## Bloom nests (ADR-0055, BloomNests), by placement id: {burned: bool, hp: fire damage left,
## seeded_dead: [{i: guard slot, at: game minutes it died}], burned_at: game minutes}. Loads empty
## from saves before it (no version bump).
var nests: Dictionary = {}
## Base traps and electricity (ADR-0052): {traps: {piece id: {armed: bool}}, power: {piece id:
## {on: bool, fuel: generator hours, ammo: sentry nails}}, wires: [[piece id, piece id, spools]]}.
## Loads empty from saves before it (no version bump).
var base_tech: Dictionary = {}
## Forest encounters (ADR-0054), by site id ("enc:<cell>"), only once something changed there:
## {visited: bool, dead: [sleeper ids], taken: [pickup ids]}. Their containers live in
## `containers` ("enc:<cell>:<prop key>"). Loads empty from saves before it (no version bump).
var encounters: Dictionary = {}


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
		pois[key] = {"visited": false, "cleared": false, "dead": [], "broken": [], "doors": {}, "traps": {}, "triggers": {},
			"keys": POI_KEYS}
	var st: Dictionary = pois[key]
	# States saved before the dungeon mechanics have no trigger ledger yet.
	if not st.has("triggers"):
		st["triggers"] = {}
	if not st.has("traps"):
		st["traps"] = {}
	return st


## Moves a container's saved state to a new id (POI re-keying, TD-031). No-op when there is
## nothing under the old id or the new id is already taken.
func rekey_container(old_id: String, new_id: String) -> void:
	if old_id == new_id or not containers.has(old_id) or containers.has(new_id):
		return
	containers[new_id] = containers[old_id]
	containers.erase(old_id)


func tree_state(chunk_key: String, index: int) -> Dictionary:
	return (trees.get(chunk_key, {}) as Dictionary).get(str(index), {})


func set_tree_state(chunk_key: String, index: int, state: Dictionary) -> void:
	if not trees.has(chunk_key):
		trees[chunk_key] = {}
	trees[chunk_key][str(index)] = state


func to_dict() -> Dictionary:
	return {
		"structures": structures, "blueprints": blueprints, "containers": containers, "pois": pois,
		"trees": trees, "loose": loose, "flags": flags, "drops": drops, "mounds": mounds, "traders": traders, "ashen": ashen, "farms": farms, "nests": nests, "base_tech": base_tech, "encounters": encounters, "chunk_keys": chunk_blobs.keys(),
		"poi_dressing": poi_dressing,
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
	mounds = d.get("mounds", {})
	traders = d.get("traders", {})
	ashen = d.get("ashen", {})
	farms = d.get("farms", {})
	nests = d.get("nests", {})
	base_tech = d.get("base_tech", {})
	encounters = d.get("encounters", {})
	# A world saved without the key predates per-run dressing (the v4 -> v5 migration sets it too).
	poi_dressing = int(d.get("poi_dressing", 1))
