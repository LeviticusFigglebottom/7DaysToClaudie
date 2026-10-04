@tool
extends VBoxContainer
## Editor dock: one-click content + POI validation with readable results.

var _out: RichTextLabel


func _ready() -> void:
	var row := HBoxContainer.new()
	add_child(row)
	var b1 := Button.new()
	b1.text = "Validate content"
	b1.pressed.connect(_validate_content)
	row.add_child(b1)
	var b2 := Button.new()
	b2.text = "Validate POIs"
	b2.pressed.connect(_validate_pois)
	row.add_child(b2)
	_out = RichTextLabel.new()
	_out.custom_minimum_size = Vector2(0, 300)
	_out.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_out.selection_enabled = true
	add_child(_out)


func _content() -> Node:
	return get_node_or_null("/root/Content")


func _validate_content() -> void:
	var db: Node = _content()
	if db == null:
		_out.text = "Content autoload not available in the editor."
		return
	var errs: PackedStringArray = db.load_all()
	_out.text = ("Content OK: %s" % db.summary()) if errs.is_empty() else "\n".join(errs)


func _validate_pois() -> void:
	var validator: Script = load("res://src/poi/poi_validator.gd")
	if validator == null:
		_out.text = "POI validator not available"
		return
	var report: Dictionary = validator.validate_all()
	_out.text = str(report.get("text", report))
