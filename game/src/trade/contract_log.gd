class_name ContractLog
extends RefCounted
## One player's standing with the Program's traders (ADR-0039): reputation per trader, the
## contracts they hold and the board offers they have already taken. Saved with the PlayerState.

## Contract states: working on it, done and waiting to be turned in.
const ACTIVE: String = "active"
const READY: String = "ready"

## trader id -> reputation points
var rep: Dictionary = {}
## [{id, def, giver, target, name, pos: [3], tier, state, day, (clear) looted, (fetch) placed,
##   picked, (defend) spot: [3]}]
var active: Array = []
## offer id -> day taken (offer ids repeat each day; older days are dropped)
var taken: Dictionary = {}
## contracts turned in, by def id
var done: Dictionary = {}
## Contracts that ran out of time this run (the first few are spared their standing cost:
## config/contracts.json spared_lapses).
var lapsed: int = 0


func reputation(trader_id: StringName) -> int:
	return int(rep.get(String(trader_id), 0))


func add_rep(trader_id: StringName, n: int) -> void:
	rep[String(trader_id)] = maxi(0, reputation(trader_id) + n)


func get_contract(cid: String) -> Dictionary:
	for c: Variant in active:
		if str((c as Dictionary).get("id", "")) == cid:
			return c
	return {}


func remove(cid: String) -> void:
	for i: int in active.size():
		if str((active[i] as Dictionary).get("id", "")) == cid:
			active.remove_at(i)
			return


func count_for(trader_id: StringName) -> int:
	var n: int = 0
	for c: Variant in active:
		if str((c as Dictionary).get("giver", "")) == String(trader_id):
			n += 1
	return n


## Building ids the player is already sent to (the board deals them nothing there).
func busy_targets() -> Dictionary:
	var out: Dictionary = {}
	for c: Variant in active:
		out[str((c as Dictionary).get("target", ""))] = true
	return out


func has_taken(offer_id: String, day: int) -> bool:
	return int(taken.get(offer_id, -1)) == day


func mark_taken(offer_id: String, day: int) -> void:
	for k: Variant in taken.keys():
		if int(taken[k]) < day:
			taken.erase(k)
	taken[offer_id] = day


func total_done() -> int:
	var n: int = 0
	for k: Variant in done.keys():
		n += int(done[k])
	return n


func to_dict() -> Dictionary:
	return {"rep": rep.duplicate(), "active": active.duplicate(true), "taken": taken.duplicate(), "done": done.duplicate(), "lapsed": lapsed}


func from_dict(d: Dictionary) -> void:
	rep = (d.get("rep", {}) as Dictionary).duplicate()
	active = (d.get("active", []) as Array).duplicate(true)
	taken = (d.get("taken", {}) as Dictionary).duplicate()
	done = (d.get("done", {}) as Dictionary).duplicate()
	lapsed = int(d.get("lapsed", 0))
	# A defence is never saved half-held: it starts again from the beginning.
	for c: Variant in active:
		(c as Dictionary).erase("running")
