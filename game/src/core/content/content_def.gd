class_name ContentDef
extends Resource
## Base class for every data-driven definition (items, recipes, enemies, POIs, ...).
##
## Subclasses override `_parse()` (read fields via DefReader) and optionally `_validate()`
## (cross-reference checks once *all* content is loaded). Content is immutable at runtime:
## per-instance state lives in models (ItemStack, StructurePiece, ...) — never in defs.

## Fields every def understands. Subclasses list their own in `_fields()`.
const BASE_FIELDS: PackedStringArray = ["id", "tags", "name", "description"]

var id: StringName
var kind: StringName
var display_name: String
var description: String
var tags: PackedStringArray = []
## "items/food.json" — for error messages and tooling.
var source: String


func parse(d: Dictionary, kind_name: StringName, source_path: String) -> PackedStringArray:
	kind = kind_name
	source = source_path
	var ctx: String = "%s#%s" % [source_path, d.get("id", "?")]
	var r := DefReader.new(d, ctx)
	id = StringName(r.req_str("id"))
	if id != &"" and not _is_valid_id(String(id)):
		r.err("id '%s' must be lower_snake_case [a-z0-9_]" % id)
	display_name = r.str_field("name", String(id).capitalize())
	description = r.str_field("description", "")
	tags = r.strings("tags")
	_parse(r)
	var known: PackedStringArray = BASE_FIELDS.duplicate()
	known.append_array(_fields())
	r.check_unknown(known)
	return r.errors


func has_tag(tag: String) -> bool:
	return tags.has(tag)


## Override: read subclass fields.
func _parse(_r: DefReader) -> void:
	pass


## Override: list of subclass field names (for unknown-field detection).
func _fields() -> PackedStringArray:
	return []


## Override: cross-reference validation. Append human-readable problems to `out`.
func _validate(_db: Node, _out: PackedStringArray) -> void:
	pass


func ctx() -> String:
	return "%s#%s" % [source, id]


static func _is_valid_id(s: String) -> bool:
	if s.is_empty():
		return false
	for c: String in s:
		if not ((c >= "a" and c <= "z") or (c >= "0" and c <= "9") or c == "_"):
			return false
	return true
