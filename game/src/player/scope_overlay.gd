class_name ScopeOverlay
extends CanvasLayer
## The picture through a rifle scope (ADR-0057), drawn over the view while a scoped gun is fully
## aimed (PlayerAim): black outside the round eyepiece, a dark ring and soft vignette at its edge,
## a faint lens tint and a duplex reticle (heavy posts thinning to fine crosshairs at the centre).
## All in one shader on a full-screen rect: no texture to generate.

const SHADER: String = """
shader_type canvas_item;
uniform float radius = 0.46;
uniform float edge = 0.018;
uniform vec4 ink : source_color = vec4(0.02, 0.02, 0.02, 1.0);
uniform vec2 size = vec2(1280.0, 720.0);

float line(float d, float w, float px) {
	return 1.0 - smoothstep(w, w + px, abs(d));
}

void fragment() {
	vec2 p = (UV - 0.5) * size / min(size.x, size.y);
	float r = length(p);
	float px = 1.0 / min(size.x, size.y);
	// Outside the eyepiece: black; at its rim a dark ring, then a soft vignette inward.
	float outside = smoothstep(radius - edge * 0.25, radius + edge * 0.25, r);
	float vig = smoothstep(radius * 0.55, radius, r) * 0.55;
	// Duplex reticle: fine crosshair near the centre, heavy posts from a third of the way out.
	float fine = max(line(p.x, 0.0006, px), line(p.y, 0.0006, px));
	float post_w = 0.0035;
	float posts = max(line(p.x, post_w, px) * step(radius * 0.36, abs(p.y)),
		line(p.y, post_w, px) * step(radius * 0.36, abs(p.x)));
	float ret = max(fine, posts) * (1.0 - outside);
	float a = max(outside, max(vig, ret * 0.92));
	vec3 c = mix(vec3(0.03, 0.04, 0.035), ink.rgb, max(outside, ret));
	COLOR = vec4(c, a);
}
"""

var _rect: ColorRect
var _mat: ShaderMaterial


func _init() -> void:
	layer = 5
	name = "ScopeOverlay"
	_rect = ColorRect.new()
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := Shader.new()
	sh.code = SHADER
	_mat = ShaderMaterial.new()
	_mat.shader = sh
	_rect.material = _mat
	add_child(_rect)


func _ready() -> void:
	_rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


func _process(_delta: float) -> void:
	if visible:
		_mat.set_shader_parameter(&"size", _rect.size if _rect.size.x > 0.0 else Vector2(1280, 720))
