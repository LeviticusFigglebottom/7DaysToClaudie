class_name Directives
extends RefCounted
## A player's Remand Program directives: progress per directive, which are done, and the open
## chapter. Only the open chapter's directives advance, so the chain teaches the loop in order
## (gather and build, then search and fight, then hold through the Hum...). Serializable.

## Infected tier strength for DirectiveDef.min_tier.
const TIER_RANK: Dictionary = {"": 0, "normal": 1, "seeded": 2, "bloomed": 3}

var progress: Dictionary = {}
var done: Dictionary = {}
var chapter: int = 1


static func chapters() -> PackedInt32Array:
	var out := PackedInt32Array()
	for d: DirectiveDef in Content.all(&"directive"):
		if not out.has(d.chapter):
			out.append(d.chapter)
	out.sort()
	return out


static func chapter_defs(ch: int) -> Array[DirectiveDef]:
	var out: Array[DirectiveDef] = []
	for d: DirectiveDef in Content.all(&"directive"):
		if d.chapter == ch:
			out.append(d)
	out.sort_custom(func(a: DirectiveDef, b: DirectiveDef) -> bool: return a.order < b.order if a.order != b.order else String(a.id) < String(b.id))
	return out


static func chapter_name(ch: int) -> String:
	for d: DirectiveDef in chapter_defs(ch):
		if d.chapter_name != "":
			return d.chapter_name
	return "Chapter %d" % ch


## The open chapter's directives not done yet.
func open() -> Array[DirectiveDef]:
	return chapter_defs(chapter).filter(func(d: DirectiveDef) -> bool: return not done.has(d.id))


## Every chapter's directives finished.
func all_done() -> bool:
	var chs: PackedInt32Array = chapters()
	return chs.is_empty() or (chapter >= chs[chs.size() - 1] and open().is_empty())


func count_of(id: StringName) -> int:
	return int(progress.get(id, 0))


## Feeds one gameplay event. `amount` adds to counts (for "level" it is the level reached).
## Returns the directives this completed (the caller pays their rewards).
func record(event: String, target: StringName = &"", amount: int = 1, tier: StringName = &"") -> Array[DirectiveDef]:
	var out: Array[DirectiveDef] = []
	for d: DirectiveDef in chapter_defs(chapter):
		if done.has(d.id) or d.event != event:
			continue
		if not d.targets.is_empty() and not d.targets.has(String(target)):
			continue
		if d.min_tier != "" and int(TIER_RANK.get(String(tier), 0)) < int(TIER_RANK.get(d.min_tier, 0)):
			continue
		progress[d.id] = maxi(count_of(d.id), amount) if event == "level" else count_of(d.id) + amount
		if count_of(d.id) >= d.count:
			done[d.id] = true
			out.append(d)
	if not out.is_empty():
		_advance()
	return out


## Opens the next chapter once the current one is finished.
func _advance() -> void:
	var chs: PackedInt32Array = chapters()
	while open().is_empty():
		var nxt: int = -1
		for c: int in chs:
			if c > chapter:
				nxt = c
				break
		if nxt < 0:
			return
		chapter = nxt


func to_dict() -> Dictionary:
	var p: Dictionary = {}
	for k: Variant in progress.keys():
		p[String(k)] = progress[k]
	var d: Array = []
	for k: Variant in done.keys():
		d.append(String(k))
	d.sort()
	return {"chapter": chapter, "progress": p, "done": d}


func from_dict(d: Dictionary) -> void:
	chapter = maxi(1, int(d.get("chapter", 1)))
	progress.clear()
	for k: Variant in (d.get("progress", {}) as Dictionary).keys():
		progress[StringName(str(k))] = int(d["progress"][k])
	done.clear()
	for k: Variant in d.get("done", []):
		done[StringName(str(k))] = true
	# Directives added to an older chapter after this save: carry on rather than stall.
	_advance()
