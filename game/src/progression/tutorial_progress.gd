class_name TutorialProgress
extends RefCounted
## A player's first-days tutorial (ADR-0062): which steps are done, counts toward the rest, whether
## the player turned it off, and the distress call it ends with. Steps count in any order (a player
## who builds the fire before the axe is not made to do it again); the journal's current step is the
## first by order not done. Serializable (PlayerState.tutorial); TutorialTracker feeds it.

## The player's own switch (the tutorial.set_enabled command); the world setting `tutorial` is
## checked on top of it by TutorialTracker.is_enabled().
var enabled: bool = true
## step id -> count so far
var progress: Dictionary = {}
## step id -> true
var done: Dictionary = {}
## Game minutes (WorldClock.total_minutes) when the distress call is due; -1: not scheduled.
var distress_due: float = -1.0
## The call came, or was skipped (the companion already with you, dead, or no camp).
var distress_received: bool = false
## The call was heard (false when it was skipped).
var distress_heard: bool = false
## Loaded from a save made before the tutorial existed (no "tutorial" key). Not saved: the tracker
## settles it on load (done past old_save_done_after_day, else a fresh start) and clears it.
var legacy: bool = false


## Every step, by order.
static func step_defs() -> Array[TutorialStepDef]:
	var out: Array[TutorialStepDef] = []
	for d: TutorialStepDef in Content.all(&"tutorial_step"):
		out.append(d)
	out.sort_custom(func(a: TutorialStepDef, b: TutorialStepDef) -> bool: return a.order < b.order if a.order != b.order else String(a.id) < String(b.id))
	return out


func count_of(id: StringName) -> int:
	return int(progress.get(id, 0))


## The first step by order not done (null when all are).
func current() -> TutorialStepDef:
	for d: TutorialStepDef in step_defs():
		if not done.has(d.id):
			return d
	return null


func all_done() -> bool:
	return current() == null


## Feeds one gameplay event; `amount` adds to the counts. Returns the steps it finished.
func record(event: String, target: StringName = &"", amount: int = 1) -> Array[TutorialStepDef]:
	var out: Array[TutorialStepDef] = []
	for d: TutorialStepDef in step_defs():
		if done.has(d.id) or d.event != event:
			continue
		if not d.targets.is_empty() and not d.targets.has(String(target)):
			continue
		progress[d.id] = count_of(d.id) + amount
		if count_of(d.id) >= d.count:
			done[d.id] = true
			out.append(d)
	return out


## Every step done and the call settled (an old save well past the first days).
func finish_all() -> void:
	for d: TutorialStepDef in step_defs():
		done[d.id] = true
		progress[d.id] = d.count
	distress_received = true
	distress_heard = false
	distress_due = -1.0


func to_dict() -> Dictionary:
	var p: Dictionary = {}
	for k: Variant in progress.keys():
		p[String(k)] = progress[k]
	var d: Array = []
	for k: Variant in done.keys():
		d.append(String(k))
	d.sort()
	return {"enabled": enabled, "progress": p, "done": d, "distress_due": distress_due, "distress_received": distress_received,
		"distress_heard": distress_heard}


func from_dict(d: Dictionary) -> void:
	enabled = bool(d.get("enabled", true))
	progress.clear()
	var p: Dictionary = d.get("progress", {})
	for k: Variant in p.keys():
		progress[StringName(str(k))] = int(p[k])
	done.clear()
	for k: Variant in d.get("done", []):
		done[StringName(str(k))] = true
	distress_due = float(d.get("distress_due", -1.0))
	distress_received = bool(d.get("distress_received", false))
	distress_heard = bool(d.get("distress_heard", false))
	legacy = false
