class_name StructureGraph
extends RefCounted
## Structural integrity for player-built and POI structures (pure model, see ADR-0006).
##
## Pieces are nodes; links say how two pieces touch:
##   link(a, b, ON)    -> a rests on b (b supports a vertically)
##   link(a, b, SIDE)  -> a and b are joined side by side (cantilever / span)
## Grounded pieces (touching terrain/bedrock) have stability 1.0. Stability flows outward:
##   to a piece resting on X:     s - piece.vertical_loss
##   to a piece beside/below X:   s - 1 / piece.max_span
## A piece's stability is the best over all paths (max-propagation, Dijkstra on 1 - s).
## Pieces with stability <= 0 are unsupported and collapse. Removing a piece only recomputes
## the components it touched.

enum Link { ON, SIDE }

const EPS: float = 0.0001


class Piece:
	var id: StringName
	var def_id: StringName
	var max_span: float = 4.0
	var vertical_loss: float = 0.04
	var grounded: bool = false
	var stability: float = 0.0
	## neighbor id -> relation from THIS piece's view: &"below" (I rest on it), &"above" (it rests on me), &"side"
	var links: Dictionary = {}


var pieces: Dictionary = {}


func has_piece(id: StringName) -> bool:
	return pieces.has(id)


func size() -> int:
	return pieces.size()


func add_piece(id: StringName, def_id: StringName, max_span: float, vertical_loss: float, grounded: bool) -> void:
	var p := Piece.new()
	p.id = id
	p.def_id = def_id
	p.max_span = maxf(max_span, 0.5)
	p.vertical_loss = clampf(vertical_loss, 0.0, 1.0)
	p.grounded = grounded
	p.stability = 1.0 if grounded else 0.0
	pieces[id] = p


## Convenience: add using a StructureDef's support parameters.
func add_from_def(id: StringName, def: StructureDef, grounded: bool) -> void:
	add_piece(id, def.id, def.max_span, def.vertical_loss, grounded and def.grounded)


func link(a: StringName, b: StringName, relation: Link) -> void:
	if not pieces.has(a) or not pieces.has(b) or a == b:
		return
	var pa: Piece = pieces[a]
	var pb: Piece = pieces[b]
	if relation == Link.ON:
		pa.links[b] = &"below"
		pb.links[a] = &"above"
	else:
		pa.links[b] = &"side"
		pb.links[a] = &"side"


func set_grounded(id: StringName, grounded: bool) -> void:
	if pieces.has(id):
		(pieces[id] as Piece).grounded = grounded


func stability(id: StringName) -> float:
	var p: Piece = pieces.get(id)
	return 0.0 if p == null else p.stability


## Recomputes stability for the components containing `seeds` (all pieces if empty) and
## returns the ids that are now unsupported (stability <= 0), nearest-to-break first.
func recompute(seeds: Array = []) -> Array[StringName]:
	var scope: Dictionary = _components(seeds) if not seeds.is_empty() else pieces.duplicate()
	var heap := MinHeap.new()
	for id: StringName in scope:
		var p: Piece = pieces[id]
		p.stability = 1.0 if p.grounded else -1.0
		if p.grounded:
			heap.push(0.0, id)
	var done: Dictionary = {}
	while not heap.is_empty():
		var cur_id: StringName = heap.pop()
		if done.has(cur_id):
			continue
		done[cur_id] = true
		var cur: Piece = pieces[cur_id]
		if cur.stability <= 0.0:
			continue
		for nid: StringName in cur.links:
			if not scope.has(nid) or done.has(nid):
				continue
			var n: Piece = pieces[nid]
			var rel_from_cur: StringName = cur.links[nid]
			var cost: float
			if rel_from_cur == &"above":
				cost = n.vertical_loss
			else:
				cost = 1.0 / n.max_span
			var s: float = cur.stability - cost
			if s > n.stability + EPS:
				n.stability = s
				heap.push(1.0 - s, nid)
	var failed: Array[StringName] = []
	for id: StringName in scope:
		var p: Piece = pieces[id]
		if p.stability <= EPS:
			p.stability = 0.0
			failed.append(id)
	failed.sort_custom(func(a: StringName, b: StringName) -> bool: return String(a) < String(b))
	return failed


## Removes a piece and returns pieces that lost support because of it (not yet removed).
func remove_piece(id: StringName) -> Array[StringName]:
	var p: Piece = pieces.get(id)
	if p == null:
		return []
	var neighbors: Array = p.links.keys()
	for nid: StringName in neighbors:
		var n: Piece = pieces.get(nid)
		if n != null:
			n.links.erase(id)
	pieces.erase(id)
	if neighbors.is_empty():
		return []
	return recompute(neighbors)


## Removes pieces repeatedly until stable; returns every collapsed id in collapse order.
func remove_and_cascade(id: StringName) -> Array[StringName]:
	var collapsed: Array[StringName] = []
	var queue: Array[StringName] = remove_piece(id)
	while not queue.is_empty():
		var batch: Array[StringName] = queue.duplicate()
		queue.clear()
		for cid: StringName in batch:
			if pieces.has(cid):
				collapsed.append(cid)
		for cid: StringName in batch:
			if pieces.has(cid):
				for f: StringName in remove_piece(cid):
					if not queue.has(f) and not collapsed.has(f):
						queue.append(f)
	return collapsed


func _components(seeds: Array) -> Dictionary:
	var seen: Dictionary = {}
	var stack: Array = []
	for s: Variant in seeds:
		if pieces.has(s):
			stack.append(s)
	while not stack.is_empty():
		var id: StringName = stack.pop_back()
		if seen.has(id):
			continue
		seen[id] = true
		for nid: StringName in (pieces[id] as Piece).links:
			if not seen.has(nid):
				stack.append(nid)
	return seen


func to_dict() -> Dictionary:
	var out: Dictionary = {}
	for id: StringName in pieces:
		var p: Piece = pieces[id]
		var links: Dictionary = {}
		for nid: StringName in p.links:
			links[String(nid)] = String(p.links[nid])
		out[String(id)] = {"def": String(p.def_id), "span": p.max_span, "vloss": p.vertical_loss, "g": p.grounded, "links": links}
	return out


func from_dict(d: Dictionary) -> void:
	pieces.clear()
	for k: Variant in d.keys():
		var e: Dictionary = d[k]
		add_piece(StringName(str(k)), StringName(str(e.get("def", ""))), float(e.get("span", 4.0)), float(e.get("vloss", 0.04)), bool(e.get("g", false)))
	for k: Variant in d.keys():
		var p: Piece = pieces[StringName(str(k))]
		var links: Dictionary = (d[k] as Dictionary).get("links", {})
		for nid: Variant in links.keys():
			if pieces.has(StringName(str(nid))):
				p.links[StringName(str(nid))] = StringName(str(links[nid]))
	recompute()
