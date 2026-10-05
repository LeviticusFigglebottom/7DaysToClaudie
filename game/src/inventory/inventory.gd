class_name Inventory
extends RefCounted
## A list of item stacks with optional limits:
##  - max_slots: number of stacks (containers);
##  - max_bulk: total encumbrance (player salvage roll);
##  - per-item carry caps (ItemDef.carry_max) when enforce_carry_max is set (player).
## All mutating operations are atomic: they either fully succeed or leave the inventory unchanged
## (except add(), which reports the leftover that did not fit).

signal changed()

var owner_id: StringName = &""
var max_slots: int = 0
var max_bulk: float = 0.0
var enforce_carry_max: bool = false
## Extra carry allowance per item id on top of ItemDef.carry_max (perks: Timberwright's third
## log). Derived from progression, never saved (PlayerState.refresh_derived).
var carry_bonus: Dictionary = {}
var stacks: Array[ItemStack] = []


func _init(owner: StringName = &"", slots: int = 0, bulk_cap: float = 0.0, carry_caps: bool = false) -> void:
	owner_id = owner
	max_slots = slots
	max_bulk = bulk_cap
	enforce_carry_max = carry_caps


func is_empty() -> bool:
	return stacks.is_empty()


func count_of(item_id: StringName) -> int:
	var n: int = 0
	for s: ItemStack in stacks:
		if s.item_id == item_id:
			n += s.count
	return n


func has(item_id: StringName, n: int = 1) -> bool:
	return count_of(item_id) >= n


func has_all(requirements: Dictionary) -> bool:
	for k: Variant in requirements.keys():
		if count_of(StringName(k)) < int(requirements[k]):
			return false
	return true


## Missing amounts for a requirement dictionary ({} if satisfied).
func missing(requirements: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for k: Variant in requirements.keys():
		var lack: int = int(requirements[k]) - count_of(StringName(k))
		if lack > 0:
			out[StringName(k)] = lack
	return out


func total_bulk() -> float:
	var b: float = 0.0
	for s: ItemStack in stacks:
		var d: ItemDef = s.def()
		if d != null:
			b += d.bulk * s.count
	return b


func first(item_id: StringName) -> ItemStack:
	for s: ItemStack in stacks:
		if s.item_id == item_id:
			return s
	return null


func find_tool(tool_kind: String) -> ItemStack:
	for s: ItemStack in stacks:
		var d: ItemDef = s.def()
		if d != null and d.provides_tool(tool_kind) and (s.durability != 0.0):
			return s
	return null


## The most of `item_id` this inventory may hold (0 = unlimited by carry caps).
func carry_limit(item_id: StringName) -> int:
	var d: ItemDef = Content.item(item_id)
	if d == null or not enforce_carry_max or d.carry_max <= 0:
		return 0
	return d.carry_max + int(carry_bonus.get(item_id, 0))


## How many of `stack` would fit right now (respects slots, bulk and carry caps).
func capacity_for(stack: ItemStack) -> int:
	var d: ItemDef = stack.def()
	if d == null:
		return 0
	var limit: int = stack.count
	var cap: int = carry_limit(stack.item_id)
	if cap > 0:
		limit = mini(limit, cap - count_of(stack.item_id))
	if max_bulk > 0.0 and d.bulk > 0.0:
		limit = mini(limit, int(floor((max_bulk - total_bulk()) / d.bulk + 0.0001)))
	if limit <= 0:
		return 0
	if max_slots > 0:
		var room: int = 0
		for s: ItemStack in stacks:
			if s.can_merge(stack):
				room += s.max_stack() - s.count
		room += (max_slots - stacks.size()) * d.stack_max
		limit = mini(limit, room)
	return maxi(limit, 0)


## Adds as much of `stack` as fits. Returns the number of items that did NOT fit.
## The passed stack is not modified.
func add(stack: ItemStack) -> int:
	if stack == null or stack.count <= 0:
		return 0
	var fit: int = capacity_for(stack)
	var remaining: int = fit
	if remaining <= 0:
		return stack.count
	for s: ItemStack in stacks:
		if remaining <= 0:
			break
		if s.can_merge(stack):
			var room: int = s.max_stack() - s.count
			var put: int = mini(room, remaining)
			s.count += put
			remaining -= put
	while remaining > 0:
		var ns: ItemStack = stack.duplicate_stack()
		ns.count = mini(remaining, ns.max_stack())
		stacks.append(ns)
		remaining -= ns.count
	changed.emit()
	return stack.count - fit


func add_item(item_id: StringName, n: int = 1, quality: int = 0) -> int:
	return add(ItemStack.make(item_id, n, quality))


## Removes exactly n of item_id (lowest quality first, then most-damaged first). All-or-nothing.
func remove(item_id: StringName, n: int = 1) -> bool:
	if n <= 0:
		return true
	if count_of(item_id) < n:
		return false
	var candidates: Array[ItemStack] = stacks.filter(func(s: ItemStack) -> bool: return s.item_id == item_id)
	candidates.sort_custom(func(a: ItemStack, b: ItemStack) -> bool:
		if a.quality != b.quality:
			return a.quality < b.quality
		return a.durability < b.durability)
	var left: int = n
	for s: ItemStack in candidates:
		var take: int = mini(s.count, left)
		s.count -= take
		left -= take
		if left == 0:
			break
	_compact()
	changed.emit()
	return true


## Removes several requirements at once ({item: count}); all-or-nothing.
func remove_all(requirements: Dictionary) -> bool:
	if not has_all(requirements):
		return false
	for k: Variant in requirements.keys():
		remove(StringName(k), int(requirements[k]))
	return true


## Removes a specific stack instance (or part of it).
func take_from(stack: ItemStack, n: int) -> ItemStack:
	if not stacks.has(stack):
		return null
	var out: ItemStack = stack.split(n)
	_compact()
	changed.emit()
	return out


func clear() -> void:
	stacks.clear()
	changed.emit()


## Moves everything that fits into `other`. Returns number of items moved.
func transfer_all_to(other: Inventory) -> int:
	var moved: int = 0
	for s: ItemStack in stacks.duplicate():
		var leftover: int = other.add(s)
		var put: int = s.count - leftover
		s.count -= put
		moved += put
	_compact()
	changed.emit()
	return moved


func _compact() -> void:
	stacks = stacks.filter(func(s: ItemStack) -> bool: return s.count > 0)


func to_dict() -> Dictionary:
	var arr: Array = []
	for s: ItemStack in stacks:
		arr.append(s.to_dict())
	return {"owner": String(owner_id), "slots": max_slots, "bulk": max_bulk, "caps": enforce_carry_max, "stacks": arr}


static func from_dict(d: Dictionary) -> Inventory:
	var inv := Inventory.new(StringName(str(d.get("owner", ""))), int(d.get("slots", 0)), float(d.get("bulk", 0.0)), bool(d.get("caps", false)))
	for sd: Variant in d.get("stacks", []):
		if sd is Dictionary:
			var s: ItemStack = ItemStack.from_dict(sd)
			if s.count > 0 and Content.item(s.item_id) != null:
				inv.stacks.append(s)
			elif s.count > 0:
				push_warning("Inventory: dropping unknown item '%s' from save" % s.item_id)
	return inv
