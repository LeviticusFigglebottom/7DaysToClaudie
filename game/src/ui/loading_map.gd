class_name LoadingMap
extends Control
## The world's map on the loading screen (ADR-0038, RWG_V2_PLAN §4): the generated map image with
## each region's state over it (pending, being shaped, done) and the drop site, so a long first
## load of a big random world shows where the work is. The map covers the world's square rect
## (RwgMap: x to the right, z down), so region (col, row) of a cols x rows grid is the cell at
## (col / cols, row / rows).

const PENDING: int = 0
const WORKING: int = 1
const DONE: int = 2
const COLORS: Array = [Color(0.0, 0.0, 0.0, 0.45), Color(0.95, 0.75, 0.3, 0.35), Color(0.0, 0.0, 0.0, 0.0)]

var texture: Texture2D = null
## {"grid": Vector2i(cols, rows), "cells": {Vector2i: PENDING|WORKING|DONE}, "point": Vector2 (0..1)}
var marks: Dictionary = {}
var _t: float = 0.0


func _process(delta: float) -> void:
	_t += delta
	if visible and not marks.is_empty():
		queue_redraw()


func set_map(p_texture: Texture2D, p_marks: Dictionary) -> void:
	texture = p_texture
	marks = p_marks
	visible = texture != null
	queue_redraw()


func _draw() -> void:
	if texture == null:
		return
	var side: float = minf(size.x, size.y)
	var r := Rect2(Vector2.ZERO, Vector2(side, side))
	draw_texture_rect(texture, r, false)
	var grid: Vector2i = marks.get("grid", Vector2i.ZERO)
	if grid.x > 0 and grid.y > 0:
		var cell := Vector2(side / grid.x, side / grid.y)
		var cells: Dictionary = marks.get("cells", {})
		for c: Vector2i in cells:
			var st: int = int(cells[c])
			var col: Color = COLORS[clampi(st, 0, 2)]
			if st == WORKING:
				# The regions being shaped now pulse.
				col.a *= 0.6 + 0.4 * sin(_t * 4.0)
			if col.a > 0.0:
				draw_rect(Rect2(Vector2(c) * cell, cell), col)
	if marks.has("point"):
		var p: Vector2 = (marks["point"] as Vector2) * side
		draw_circle(p, 7.0, Color(0.1, 0.05, 0.02))
		draw_circle(p, 5.0, Color(0.95, 0.35, 0.2))
	draw_rect(r, Color(0.5, 0.48, 0.42), false, 2.0)
