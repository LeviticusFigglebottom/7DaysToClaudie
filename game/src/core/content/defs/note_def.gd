class_name NoteDef
extends ContentDef
## A readable note / document for environmental storytelling.

var title: String = ""
var body: String = ""
## "handwritten" | "typed" | "printed" | "scrawl"
var style: String = "handwritten"
var author: String = ""


func _fields() -> PackedStringArray:
	return ["title", "body", "style", "author"]


func _parse(r: DefReader) -> void:
	title = r.str_field("title", display_name)
	body = r.req_str("body")
	style = r.enum_str("style", ["handwritten", "typed", "printed", "scrawl"], "handwritten")
	author = r.str_field("author", "")
