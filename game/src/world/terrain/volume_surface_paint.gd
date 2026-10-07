class_name VolumeSurfacePaint
extends RefCounted
## Vertex weights that let a volume chunk look like the heightmap where its mesh is the old ground
## (ADR-0056, CAVES_PLAN WS-D, TD-163 gap 3). Before this the volume shader painted by normal only,
## so a column that turned into volume (a dig past the heightmap, a cave running under it) showed a
## square of dug earth in the forest floor.
##
## Per vertex (volume_terrain.gdshader reads them as COLOR):
##  * R, surface: the vertex lies on the heightfield (|y - h| under SURFACE_BAND) and faces up
##    (normal.y over UP_MIN), with a smooth falloff on both, so the region's splat and palette
##    take over there; tunnel walls, dug pits and cave floors keep the volume's own earth and rock.
##  * G, cave interior: more than DEEP m under the ground, faded in over DEEP_FADE m (wet limestone).
##  * B = 0, A = 1.
## Pure and thread-safe: called on the volume worker job right after SurfaceNets, with the job's
## captured height function.

## Within this of the ground (m) a vertex is the old surface; full weight within SURFACE_FULL.
const SURFACE_BAND: float = 0.35
const SURFACE_FULL: float = 0.2
## Up-facing from this normal.y (zero weight) to UP_FULL (full weight).
const UP_MIN: float = 0.55
const UP_FULL: float = 0.75
## Cave interior from this depth under the ground (m), full DEEP_FADE m deeper.
const DEEP: float = 1.5
const DEEP_FADE: float = 1.0


## The weights of `verts` (chunk-local, with their `normals`) of a chunk at world `origin`, against
## the ground `height_fn(x, z)`.
static func weights(verts: PackedVector3Array, normals: PackedVector3Array, origin: Vector3, height_fn: Callable) -> PackedColorArray:
	var out := PackedColorArray()
	out.resize(verts.size())
	var has_n: bool = normals.size() == verts.size()
	for i: int in verts.size():
		var w: Vector3 = verts[i] + origin
		var h: float = height_fn.call(w.x, w.z)
		var ny: float = normals[i].y if has_n else 1.0
		out[i] = Color(surface(w.y - h, ny), interior(h - w.y), 0.0, 1.0)
	return out


## Surface weight of a vertex `dy` m above the ground (negative under it) whose normal has `ny` up.
static func surface(dy: float, ny: float) -> float:
	return (1.0 - smoothstep(SURFACE_FULL, SURFACE_BAND, absf(dy))) * smoothstep(UP_MIN, UP_FULL, ny)


## Cave interior weight of a vertex `depth` m under the ground.
static func interior(depth: float) -> float:
	return smoothstep(DEEP, DEEP + DEEP_FADE, depth)
