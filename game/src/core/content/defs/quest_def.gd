class_name QuestDef
extends ContentDef
## A Waystation contract or story quest (ADR-0039). Contracts (`clear`, `fetch`, `defend`) are
## templates: the trader's board deals them out by the day and the world seed, and each offer
## picks its own building from `target` (tier band, distance band from the post). Story quests
## (`story`, `kill`, `deliver`) are data for now; their objectives name their targets.

var quest_type: String = "clear"
var tier: int = 1
## [{type: "clear_poi"|"fetch"|"defend"|"kill"|"deliver", target: id, count: n}] (story quests)
var objectives: Array = []
## {item_id: count, "scrip": n, "reputation": n, "xp": n}
var rewards: Dictionary = {}
var giver: String = "waystation"
var requires: PackedStringArray = []
## Contracts: the building a board offer picks: {tier: [lo, hi], distance: [min, max] metres from
## the post, kind: "any" | "authored" | "generated", fresh: bool (default true: never a building
## the player has visited or cleared)}.
var target: Dictionary = {}
## Reputation tier with the giver needed before the board offers it.
var rep_tier: int = 0
## How often the board deals it relative to the others it may offer.
var weight: float = 1.0
## Defend: seconds to hold, number of waves, Hollowed per wave [lo, hi] and the enemy table.
var duration: float = 150.0
var waves: int = 4
var wave_size: Array = [2, 3]
var enemies: Dictionary = {"hollow": 3}
## Defend: extra Hollowed per wave per gamestage point (TD-142).
var wave_growth: float = 0.04
## Fetch: the item the Program left in the building (placed when the player gets near).
var item: String = "program_cache"
## Fetch: false when the building already holds `item` (a tier-5 site's guaranteed payoff, TD-179):
## nothing is set down, and the contract is ready while the player carries one.
var place: bool = true
## Offered until the player has turned it in once (a unique building's one-off job).
var once: bool = false
## Contracts (TD-146): days an accepted contract has before it fails at dawn (0 = never). Only a
## contract still open fails; one done and waiting to be reported does not.
var expires_days: int = 3
## Reputation with the giver lost when the contract fails (expires) or is abandoned.
var fail_rep: int = 10
var abandon_rep: int = 5
## Briefing on the board (`{building}` and `{distance}` are filled in).
var briefing: String = ""

const CONTRACT_TYPES: PackedStringArray = ["clear", "fetch", "defend"]


func _fields() -> PackedStringArray:
	return ["type", "tier", "objectives", "rewards", "giver", "requires", "target", "rep_tier", "weight",
		"duration", "waves", "wave_size", "enemies", "wave_growth", "item", "place", "once", "briefing",
		"expires_days", "fail_rep", "abandon_rep"]


func _parse(r: DefReader) -> void:
	quest_type = r.enum_str("type", ["clear", "fetch", "defend", "kill", "deliver", "story"], "clear")
	tier = r.integer("tier", 1)
	objectives = r.arr("objectives")
	rewards = r.dict("rewards")
	giver = r.str_field("giver", "waystation")
	requires = r.strings("requires")
	target = r.dict("target")
	rep_tier = r.integer("rep_tier", 0)
	weight = r.num("weight", 1.0)
	duration = r.num("duration", 150.0)
	waves = maxi(1, r.integer("waves", 4))
	if r.has("wave_size"):
		wave_size = r.arr("wave_size")
	if r.has("enemies"):
		enemies = r.dict("enemies")
	wave_growth = maxf(0.0, r.num("wave_growth", 0.04))
	item = r.str_field("item", "program_cache")
	place = r.boolean("place", true)
	once = r.boolean("once", false)
	briefing = r.str_field("briefing", "")
	expires_days = r.integer("expires_days", 3)
	fail_rep = r.integer("fail_rep", 10)
	abandon_rep = r.integer("abandon_rep", 5)


func _validate(db: Node, out: PackedStringArray) -> void:
	for k: Variant in rewards.keys():
		if not str(k) in ["scrip", "reputation", "xp"] and not db.has_def(&"item", StringName(str(k))):
			out.append("%s: reward item '%s' unknown" % [ctx(), k])
	if not is_contract():
		return
	if expires_days < 0 or fail_rep < 0 or abandon_rep < 0:
		out.append("%s: expires_days, fail_rep and abandon_rep can't be negative" % ctx())
	if not db.has_def(&"trader", StringName(giver)):
		out.append("%s: giver '%s' is not a trader" % [ctx(), giver])
	if quest_type == "fetch" and not db.has_def(&"item", StringName(item)):
		out.append("%s: fetch item '%s' unknown" % [ctx(), item])
	if not place and quest_type != "fetch":
		out.append("%s: only a fetch contract can leave its item in place" % ctx())
	if quest_type == "defend":
		for e: Variant in enemies.keys():
			if not db.has_def(&"enemy", StringName(str(e))):
				out.append("%s: defend enemy '%s' unknown" % [ctx(), e])
	var d: Array = target.get("distance", [0, 0])
	if d.size() != 2 or float(d[1]) <= float(d[0]):
		out.append("%s: target.distance must be [min, max] metres" % ctx())


## A board contract (dealt by a trader) rather than a story quest.
func is_contract() -> bool:
	return quest_type in CONTRACT_TYPES


## Whether the board skips buildings the player has visited or cleared.
func fresh_only() -> bool:
	return bool(target.get("fresh", true))


func tier_band() -> Vector2i:
	var t: Array = target.get("tier", [tier, tier])
	return Vector2i(int(t[0]), int(t[t.size() - 1]))


func distance_band() -> Vector2:
	var d: Array = target.get("distance", [100.0, 900.0])
	return Vector2(float(d[0]), float(d[1]))
