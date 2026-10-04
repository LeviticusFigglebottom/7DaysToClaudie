class_name DefReader
extends RefCounted
## Typed field access for JSON-sourced content definitions.
##
## JSON has no ints, no vectors and no schema; this helper converts and reports problems with
## file + def context so content authors get actionable errors ("items/food.json#canned_beans:
## field 'stack_size' expected int, got String").

var errors: PackedStringArray = []
var _d: Dictionary
var _ctx: String


func _init(d: Dictionary, ctx: String) -> void:
	_d = d
	_ctx = ctx


func has(key: String) -> bool:
	return _d.has(key)


func raw(key: String, default: Variant = null) -> Variant:
	return _d.get(key, default)


func err(msg: String) -> void:
	errors.append("%s: %s" % [_ctx, msg])


func req_str(key: String) -> String:
	if not _d.has(key):
		err("missing required field '%s'" % key)
		return ""
	return str_field(key, "")


func str_field(key: String, default: String = "") -> String:
	var v: Variant = _d.get(key, default)
	if v == null:
		return default
	if v is String or v is StringName:
		return String(v)
	err("field '%s' expected String, got %s" % [key, type_string(typeof(v))])
	return default


func sname(key: String, default: StringName = &"") -> StringName:
	return StringName(str_field(key, String(default)))


func num(key: String, default: float = 0.0) -> float:
	var v: Variant = _d.get(key, default)
	if v is float or v is int:
		return float(v)
	err("field '%s' expected number, got %s" % [key, type_string(typeof(v))])
	return default


func integer(key: String, default: int = 0) -> int:
	var v: Variant = _d.get(key, default)
	if v is int:
		return v
	if v is float:
		if not is_equal_approx(v, roundf(v)):
			err("field '%s' expected int, got fractional %s" % [key, v])
		return int(roundf(v))
	err("field '%s' expected int, got %s" % [key, type_string(typeof(v))])
	return default


func boolean(key: String, default: bool = false) -> bool:
	var v: Variant = _d.get(key, default)
	if v is bool:
		return v
	err("field '%s' expected bool, got %s" % [key, type_string(typeof(v))])
	return default


func dict(key: String) -> Dictionary:
	var v: Variant = _d.get(key, {})
	if v is Dictionary:
		return v
	err("field '%s' expected object, got %s" % [key, type_string(typeof(v))])
	return {}


func arr(key: String) -> Array:
	var v: Variant = _d.get(key, [])
	if v is Array:
		return v
	err("field '%s' expected array, got %s" % [key, type_string(typeof(v))])
	return []


func strings(key: String) -> PackedStringArray:
	var out: PackedStringArray = []
	for v: Variant in arr(key):
		if v is String:
			out.append(v)
		else:
			err("field '%s' expected array of strings" % key)
	return out


## [min, max] range given as a number or a two-element array.
func range2(key: String, default: Vector2) -> Vector2:
	var v: Variant = _d.get(key, null)
	if v == null:
		return default
	if v is float or v is int:
		return Vector2(float(v), float(v))
	if v is Array and v.size() == 2 and (v[0] is float or v[0] is int) and (v[1] is float or v[1] is int):
		return Vector2(float(v[0]), float(v[1]))
	err("field '%s' expected number or [min, max]" % key)
	return default


func vec3(key: String, default: Vector3 = Vector3.ZERO) -> Vector3:
	var v: Variant = _d.get(key, null)
	if v == null:
		return default
	if v is Array and v.size() == 3:
		return Vector3(float(v[0]), float(v[1]), float(v[2]))
	err("field '%s' expected [x, y, z]" % key)
	return default


func color(key: String, default: Color = Color.WHITE) -> Color:
	var v: Variant = _d.get(key, null)
	if v == null:
		return default
	if v is String and Color.html_is_valid(v):
		return Color.html(v)
	if v is Array and (v.size() == 3 or v.size() == 4):
		return Color(float(v[0]), float(v[1]), float(v[2]), float(v[3]) if v.size() == 4 else 1.0)
	err("field '%s' expected color" % key)
	return default


## Restricts a string field to an allowed set.
func enum_str(key: String, allowed: PackedStringArray, default: String) -> String:
	var s: String = str_field(key, default)
	if not allowed.has(s):
		err("field '%s' = '%s' not in %s" % [key, s, allowed])
		return default
	return s


## Warns about fields not declared by the def class (catches typos like "stak_size").
func check_unknown(known: PackedStringArray) -> void:
	for k: Variant in _d.keys():
		if not known.has(String(k)) and not String(k).begins_with("_"):
			err("unknown field '%s' (typo? prefix with '_' for comments)" % k)
