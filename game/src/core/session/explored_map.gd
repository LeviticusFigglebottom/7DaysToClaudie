class_name ExploredMap
extends RefCounted
## Where a player has been, for the map's fog of war (TD-014): 32 m cells, kept in 16 x 16 cell
## blocks (512 m) so only visited ground costs anything. Saved in the player's record as
## {"cell": 32, "blocks": {"bx,bz": base64 of 32 bytes}}; an old save without it starts empty and
## the map reveals the ground round the bed or drop site (ADR-0063).

const CELL: float = 32.0
const BLOCK: int = 16

## "bx,bz" -> PackedByteArray(32): one bit a cell, row-major.
var blocks: Dictionary = {}


func is_empty() -> bool:
	return blocks.is_empty()


## Marks every cell whose centre is within `radius` metres of `pos`. Returns how many were new.
func reveal(pos: Vector3, radius: float) -> int:
	var added: int = 0
	var c0 := Vector2i(int(floor((pos.x - radius) / CELL)), int(floor((pos.z - radius) / CELL)))
	var c1 := Vector2i(int(floor((pos.x + radius) / CELL)), int(floor((pos.z + radius) / CELL)))
	var r2: float = radius * radius
	for cz: int in range(c0.y, c1.y + 1):
		for cx: int in range(c0.x, c1.x + 1):
			var dx: float = (cx + 0.5) * CELL - pos.x
			var dz: float = (cz + 0.5) * CELL - pos.z
			if dx * dx + dz * dz > r2:
				continue
			if _mark(cx, cz):
				added += 1
	return added


func is_explored(x: float, z: float) -> bool:
	return cell_explored(int(floor(x / CELL)), int(floor(z / CELL)))


func cell_explored(cx: int, cz: int) -> bool:
	var bx: int = floori(float(cx) / BLOCK)
	var bz: int = floori(float(cz) / BLOCK)
	var b: Variant = blocks.get("%d,%d" % [bx, bz])
	if b == null:
		return false
	var i: int = (cz - bz * BLOCK) * BLOCK + (cx - bx * BLOCK)
	return ((b as PackedByteArray)[i >> 3] >> (i & 7)) & 1 == 1


func _mark(cx: int, cz: int) -> bool:
	var bx: int = floori(float(cx) / BLOCK)
	var bz: int = floori(float(cz) / BLOCK)
	var key: String = "%d,%d" % [bx, bz]
	var b: PackedByteArray = blocks.get(key, PackedByteArray())
	if b.is_empty():
		b.resize(BLOCK * BLOCK / 8)
	var i: int = (cz - bz * BLOCK) * BLOCK + (cx - bx * BLOCK)
	var byte: int = b[i >> 3]
	var bit: int = 1 << (i & 7)
	if byte & bit:
		return false
	b[i >> 3] = byte | bit
	# Packed arrays are values: store the changed copy back.
	blocks[key] = b
	return true


func to_dict() -> Dictionary:
	var out: Dictionary = {}
	for k: String in blocks:
		out[k] = Marshalls.raw_to_base64(blocks[k])
	return {"cell": CELL, "blocks": out}


func from_dict(d: Dictionary) -> void:
	blocks.clear()
	if float(d.get("cell", CELL)) != CELL:
		return
	var src: Dictionary = d.get("blocks", {})
	for k: String in src:
		var raw: PackedByteArray = Marshalls.base64_to_raw(str(src[k]))
		if raw.size() == BLOCK * BLOCK / 8:
			blocks[k] = raw
