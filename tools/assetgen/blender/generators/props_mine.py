"""Larkspur Exploration Adit props - the Corvane Mining Co.'s small hard-rock exploration mine (1950s-80s
equipment, abandoned during the quarantine) whose drifts broke into a limestone cave. The caves are built as
underground POI levels on the 1 m kit grid (rock_drift / rock_limestone walls, rock_floor / cave_mud floors:
textures/gen/kit_rock.py); these props make those rooms read as timbered drifts and natural caves.

  mine_timber_set      drift set: two battered posts, a cap, lagging over the cap and behind the posts, wedges;
                       3.0 wide x 2.8 tall, ~0.4 deep, free-standing every 2-3 m along a drift (colliders on the
                       posts only). destroyed: a post kicked out, the cap broken and down, lagging on the floor
  mine_rail_straight   3 m of 0.6 m-gauge light rail on five sleepers bedded in ballast (tiles end to end along X)
  mine_ore_cart        side-tip ore car on flanged wheels (sits on mine_rail_straight at the same origin);
                       worn: loaded with rock; destroyed: tipped on its side, the load spilled
  mine_hoist           electric single-drum hoist on timber skids: drum with rope wraps, band brake, spur
                       gear (guarded when clean), motor, controller lever and depth dial
  mine_headframe       steel A-frame headframe over a concrete shaft collar: four-post tower, backstays,
                       sheave deck with the sheave wheel at ~9 m, cage guides, ladder, rope, shaft sign
  mine_cage            shaft cage: steel frame, sheet + mesh sides, roof and bridle, guide shoes, folding
                       scissor gate folded back across the open front, capacity plate
  mine_rock_face(_b/_c) irregular rock slab (2.0 x 2.8 x 0.6) to stand against kit walls: a granite blast face,
                       a granite face with an overhanging ledge, a limestone flowstone face
  mine_rock_pile       collapse: a mound of broken rock with boulders (worn: broken timbers in it)
  mine_stalagmites     limestone stalagmite cluster on a flowstone boss (worn: broken tips)
  mine_lamp_string     ceiling string of caged bulbs on a sagging cable, 3 m (origin on the ceiling plane)
  mine_powder_box      wooden explosives box, stencilled (worn: lid ajar on the sticks)
  mine_tool_rack       floor rack of picks, shovels and drill steels against a wall
  mine_safety_board    wall board (origin on the wall plane): SAFETY FIRST notice, shift tally, check-tag board
                       with brass tags (missing tags = men underground), a hard hat on a hook

Built on the interior-props framework (lib/props_int_core.py: Prop, clean / worn / destroyed variants, wear and
AO vertex colours, collision boxes; lib/props_int_mesh.py geometry, canonical element order). Rock relief comes
from mathutils noise seeded per prop (noise.seed_set) and is meshed through G._obj like every other part.
Graphics: textures/gen/mine.py (ATLAS below mirrors PRINT_RECTS there).

params: prop (id), seed, variants, mount, budget, builder (see blender_catalogs/props_mine.py).
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector, noise

from lib import materials
from lib import props_int_core as core
from lib import props_int_mesh as G
from lib.props_int_core import Prop


class C:
    """Material ids: mine_* from game/data/materials/props_mine.json, the rest from other families."""
    PRINT = "mine_print"
    BALLAST = "mine_ballast"
    ROCK = "mine_rock_drift"
    RUBBLE = "mine_rubble"
    LIME = "mine_limestone"
    TIMBER = "mine_timber"
    TIMBER_ROT = "mine_timber_rot"
    LAG = "mine_lagging"
    RAIL = "mine_rail"
    RUST = "mine_steel_rust"
    GREEN = "mine_paint_green"
    GREY = "mine_paint_grey"
    YELLOW = "mine_paint_yellow"
    CONCRETE = "mine_concrete"
    ROPE = "mine_rope"
    VOID = "mine_void"
    BULB = "mine_bulb_glow"
    BULB_DEAD = "mine_bulb_dead"
    DYNAMITE = "mine_dynamite"
    # shared
    OXIDE = "wild_paint_red_oxide"
    IRON = "wild_cast_iron"
    STEEL = "road_steel"
    STEEL_DARK = "road_steel_dark"
    GALV = "metal_galvanized"
    CHAIN = "trap_chain"
    CAGE_WIRE = "road_lamp_cage"
    RUBBER = "rubber_black"
    BRASS = "furn_brass"
    CREOSOTE = "wood_creosote"
    PLY = "plywood_marks"
    MESH = "ws_hesco_mesh"
    HANDLE = "item_wood_handle"
    HARDHAT = "hardhat"


materials.PREVIEW_COLORS.update({
    C.ROCK: (0.2, 0.18, 0.16), C.RUBBLE: (0.25, 0.23, 0.2), C.LIME: (0.55, 0.52, 0.46), C.TIMBER: (0.3, 0.22, 0.14),
    C.TIMBER_ROT: (0.22, 0.17, 0.12), C.LAG: (0.26, 0.2, 0.14), C.RAIL: (0.25, 0.2, 0.16), C.RUST: (0.3, 0.16, 0.08),
    C.GREEN: (0.15, 0.2, 0.15), C.GREY: (0.25, 0.25, 0.24), C.YELLOW: (0.6, 0.45, 0.1), C.CONCRETE: (0.4, 0.39, 0.36),
    C.ROPE: (0.15, 0.15, 0.14), C.VOID: (0.0, 0.0, 0.0), C.BULB: (1.0, 0.8, 0.5), C.BULB_DEAD: (0.6, 0.6, 0.55),
    C.DYNAMITE: (0.55, 0.25, 0.15), C.PRINT: (0.5, 0.5, 0.5),
})

# mine_print atlas rects (x0, y0, x1, y1) in pixels of the 1024 px texture - mirror of textures/gen/mine.py
# PRINT_RECTS.
ATLAS_SIZE = 1024.0
ATLAS: dict[str, tuple[int, int, int, int]] = {
    "notice": (0, 0, 512, 512),
    "tally": (512, 0, 1024, 256),
    "tags": (512, 256, 1024, 512),
    "box_side": (0, 512, 512, 768),
    "box_end": (512, 512, 768, 768),
    "plate": (768, 512, 1024, 640),
    "cage": (768, 640, 1024, 768),
    "shaft": (0, 768, 512, 1024),
    "car_no": (512, 768, 768, 1024),
    "box_lid": (768, 768, 1024, 1024),
    "wood": (772, 832, 826, 1020),     # plain boards (left strip of box_lid: no stencil)
}


def tag_hook(k: int) -> tuple[float, float]:
    """Pixel position in the tags cell of check-tag hook k (mirror of textures/gen/mine.py TAG_HOOK)."""
    row, c = divmod(k, 10)
    return 34.0 + c * 49.5, 80.0 + row * 58.0


def atlas(name: str, inset: float = 1.5) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = ATLAS[name]
    return core._px_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset, ATLAS_SIZE)


# ------------------------------------------------------------------------------------------------
# shared helpers
# ------------------------------------------------------------------------------------------------


def plate(p: Prop, w: float, h: float, center, uvrect, *, t: float = 0.003, mat: str = C.PRINT, rot=(0, 0, 0),
          wear: float = 0.4) -> core.Part:
    """Thin printed panel w x h in the XZ plane facing -Y (turned by rot), front face showing uvrect."""
    obj = G.box(p._name("plate"), (w, t, h), (0, 0, 0), 0.0)
    u0, v0, u1, v1 = uvrect
    edge = (u0, v0, u0 + (u1 - u0) * 0.02, v0 + (v1 - v0) * 0.02)

    def fr(poly):
        if poly.normal.y < -0.9:
            return (u0, v0, u1, v1, 0, 2, False)
        return (*edge, 0, 2, False)

    core.set_face_uvs(obj, fr)
    G.xform(obj, rot=rot, loc=center)
    return p.add(obj, mat, uv="keep", wear=wear)


def bar(p: Prop, a, b, w: float, d: float, mat: str, roll: float = 0.0, **kw) -> core.Part:
    """Rectangular beam from point a to b (w x d section, rolled by `roll` degrees about its axis)."""
    a, b = Vector(a), Vector(b)
    v = b - a
    obj = G.box(p._name("bar"), (w, d, v.length), (0, 0, 0), kw.pop("bevel", 0.004))
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    m = Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4() @ Matrix.Rotation(math.radians(roll), 4, "Z")
    obj.data.transform(m)
    obj.data.update()
    kw.setdefault("grain", "auto")
    return p.add(obj, mat, **kw)


def rod(p: Prop, a, b, r: float, mat: str, segs: int = 8, cap: bool = True, **kw) -> core.Part:
    a, b = Vector(a), Vector(b)
    v = b - a
    obj = G.cyl(p._name("rod"), r, v.length, (0, 0, 0), "Z", segs, None, 0.0, 1, cap)
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    obj.data.transform(Matrix.Translation((a + b) * 0.5) @ q.to_matrix().to_4x4())
    obj.data.update()
    kw.setdefault("edge_deg", 40.0)
    return p.add(obj, mat, **kw)


def ibeam(p: Prop, a, b, h: float, w: float, mat: str, roll: float = 0.0, **kw) -> list:
    """I-section from a to b: two flanges and a web (h deep, w wide flanges)."""
    a, b = Vector(a), Vector(b)
    ax = (b - a).normalized()
    up = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((0, 1, 0))
    side = ax.cross(up).normalized()
    up = side.cross(ax).normalized()
    if roll:
        rm = Matrix.Rotation(math.radians(roll), 3, ax)
        side, up = rm @ side, rm @ up
    tf = min(0.02, h * 0.12)
    out = []
    for s in (-1, 1):
        o = up * (s * (h * 0.5 - tf * 0.5))
        out.append(_beam_box(p, a + o, b + o, side, up, w, tf, mat, **kw))
    out.append(_beam_box(p, a, b, side, up, tf * 0.8, h - 2 * tf, mat, **kw))
    return out


def _beam_box(p: Prop, a, b, side, up, w, d, mat, **kw) -> core.Part:
    ax = (b - a)
    L = ax.length
    ax = ax.normalized()
    obj = G.box(p._name("ib"), (w, d, L), (0, 0, 0), 0.0)
    m = Matrix((side, up, ax)).transposed().to_4x4()
    obj.data.transform(Matrix.Translation((a + b) * 0.5) @ m)
    obj.data.update()
    kw.setdefault("grain", "auto")
    return p.add(obj, mat, **kw)


def place(parts, matrix: Matrix) -> None:
    for q in parts:
        q.obj.data.transform(matrix)
        q.obj.data.update()


def shift(p: Prop, dx: float, dy: float) -> None:
    """Moves every part and collider (the game's box stand-ins and def colliders are centred on the origin)."""
    for q in p.parts:
        G.xform(q.obj, loc=(dx, dy, 0.0))
    p.colliders = [(c + Vector((dx, dy, 0.0)), s, r) for c, s, r in p.colliders]


def centre(p: Prop) -> None:
    """Centres the footprint on the origin (x, y)."""
    lo, hi = p.bounds()
    shift(p, -(lo.x + hi.x) * 0.5, -(lo.y + hi.y) * 0.5)


def _mesh(p: Prop, key: str, verts, faces, mat: str, **kw) -> core.Part:
    """Mesh from explicit faces, wound as given (open sheets: recalc_face_normals guesses their side)."""
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(v)) for v in verts]
    for f in faces:
        bm.faces.new([vs[i] for i in f])
    kw.setdefault("edge_deg", 50.0)
    kw.setdefault("wear", 0.3)
    return p.add(G._obj(p._name(key), bm), mat, **kw)


def rock_chunk(p: Prop, center, size, *, key: str, mat: str = C.RUBBLE, pts: int = 14, flat: float = 0.75,
               rot: float = 0.0) -> core.Part:
    """Angular broken rock: the convex hull of jittered points on a squashed ellipsoid (centre = bottom
    centre; it rests on its lowest point)."""
    r = p.rng(key)
    sx, sy, sz = size
    co = []
    for i in range(pts):
        # Fibonacci-sphere directions jittered: even coverage, no slivers
        t = (i + 0.5) / pts
        ph = math.acos(1 - 2 * t)
        th = math.pi * (1 + 5 ** 0.5) * i + r.uniform(-0.4, 0.4)
        k = r.uniform(0.72, 1.0)
        co.append(Vector((math.sin(ph) * math.cos(th) * sx * 0.5 * k, math.sin(ph) * math.sin(th) * sy * 0.5 * k,
                          math.cos(ph) * sz * 0.5 * k)))
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in co]
    bmesh.ops.convex_hull(bm, input=vs)
    for v in list(bm.verts):
        if not v.link_faces:
            bm.verts.remove(v)
    # flatten the base a little so it sits
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        if v.co.z < zmin + sz * (1 - flat) * 0.4:
            v.co.z = zmin + (v.co.z - zmin) * 0.4
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    rm = Matrix.Rotation(math.radians(rot if rot else r.uniform(0, 360)), 4, "Z")
    bm.transform(rm)
    zmin = min(v.co.z for v in bm.verts)
    bmesh.ops.translate(bm, vec=Vector(center) - Vector((0, 0, zmin)), verts=bm.verts)
    return p.add(G._obj(p._name("rock"), bm), mat, edge_deg=35.0, wear=0.4)


def _facet_noise(seed: int):
    """Blast-facet field: f(pos) -> height, a tilted plane per Voronoi cell (mathutils voronoi; the cell's
    feature point seeds its level and slope), so faces break into flat planes meeting in ridges."""
    def f(pos: Vector, scale: float) -> float:
        q = pos / scale
        _, pts = noise.voronoi(q, distance_metric="DISTANCE", exponent=2.5)
        c = Vector(pts[0])
        hv = noise.hetero_terrain(c * 1.37 + Vector((seed * 0.013, 1.7, 3.1)), 1.0, 1.0, 1, 0.0)
        sx = noise.noise(c * 2.1 + Vector((5.3, seed * 0.017, 1.1)))
        sy = noise.noise(c * 2.1 + Vector((1.9, 7.7, seed * 0.011)))
        sz = noise.noise(c * 2.1 + Vector((seed * 0.007, 3.3, 9.1)))
        d = q - c
        return (hv * 0.5 + (sx * d.x + sy * d.y + sz * d.z) * 0.9) * scale
    return f


# ================================================================================================
# 1. timber drift set
# ================================================================================================

def _lag_board(p: Prop, x0, x1, y0, y1, z0, z1, mat=C.LAG, **kw) -> core.Part:
    return p.box((x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), mat, bevel=0.006, **kw)


def _cap(p: Prop, x0: float, x1: float, z0: float, h: float, d: float, sag: float = 0.0, mat=C.TIMBER) -> core.Part:
    part = p.rbox((x1 - x0, d, h), ((x0 + x1) / 2, 0.0, z0 + h / 2), mat, radius=0.012, inner=(10, 1, 1), edge_deg=12.0,
                  grain="X")
    if sag:
        L = (x1 - x0) / 2
        cx = (x0 + x1) / 2
        for v in part.obj.data.vertices:
            u = (v.co.x - cx) / L
            v.co.z -= sag * (1 - u * u)
        part.obj.data.update()
    return part


def _broken_beam(p: Prop, x0: float, x1: float, h: float, d: float, *, key: str, jag_at: str, mat=C.TIMBER) -> core.Part:
    """A beam along X from x0 to x1 (h tall, d deep, centred on z 0, y 0) whose `jag_at` end ("x0" / "x1")
    is splintered: a zig-zag break profile extruded through the depth, with long splinters."""
    r = p.rng(key)
    n = 7
    zs = [-h / 2 + h * i / n for i in range(n + 1)]
    teeth = [r.uniform(0.0, 0.16) * (1.6 if i % 2 else 0.6) for i in range(n + 1)]
    if jag_at == "x1":
        poly = [(x0, -h / 2)] + [(x1 + teeth[i] - 0.08, zs[i]) for i in range(n + 1)] + [(x0, h / 2)]
    else:
        poly = [(x0 - teeth[0] + 0.08, -h / 2), (x1, -h / 2), (x1, h / 2)]
        poly += [(x0 - teeth[i] + 0.08, zs[i]) for i in range(n, 0, -1)]
    # prism XZ extrudes along +Y from offset; centre the depth
    return p.prism(poly, d, mat, plane="XZ", offset=-d / 2, bevel=0.0, grain="X", edge_deg=12.0)


def mine_timber_set(p: Prop) -> None:
    """Timber drift set (3.0 x 2.8 x ~0.4): two 24 cm square posts battered in toward the top, a 26 cm cap on
    them, lagging boards laid across the cap and stood behind the posts (against the rock), blocking wedges
    up to the back. Worn: the cap sags, a post leans, boards are missing, the wood is rotting and fungus-
    stained. Destroyed: the left post kicked out and lying, the cap snapped and one half hanging from the
    right post to the floor, lagging scattered."""
    worn, dead = p.worn, p.destroyed
    vr = p.vrng("set")
    PW = 0.24
    XB, XT = 1.33, 1.27        # post centre at the foot / under the cap
    ZC = 2.40                  # cap underside
    CH, CD = 0.26, 0.28
    LAG_T = 0.05
    wood = C.TIMBER_ROT if worn else C.TIMBER
    lean = vr.uniform(2.0, 3.5) if worn and not dead else 0.0
    posts = []
    for s in (-1, 1):
        if dead and s < 0:
            continue
        a, b = (s * XB, 0.0, 0.0), (s * XT, 0.0, ZC)
        posts.append(bar(p, a, b, PW, PW, wood, bevel=0.01, edge_deg=12.0))
        if lean and s > 0:
            G.xform(posts[-1].obj, rot=(0, -lean, 0), pivot=(XB, 0, 0))
        posts[-1].floor_wear = 0.6
        p.collider((s * (XB + XT) / 2, 0.0, ZC / 2), (PW + 0.04, PW, ZC))
    # wall lagging behind the posts: boards stood on edge, running with the drift (along Y)
    for s in (-1, 1):
        if dead and s < 0:
            continue
        z = 0.25
        k = 0
        while z < ZC - 0.1:
            bh = p.rng(f"wl{s}{k}").uniform(0.18, 0.24)
            if not (worn and p.chance(f"wlmiss{s}{k}", 0.18)):
                xo = s * (XB + PW / 2 + LAG_T / 2 + 0.005 - (z / ZC) * (XB - XT))
                bd = p.rng(f"wld{s}{k}").uniform(0.36, 0.42)
                part = _lag_board(p, xo - LAG_T / 2, xo + LAG_T / 2, -bd / 2, bd / 2, z, z + bh, grain="Y")
                if worn:
                    G.xform(part.obj, rot=(vr.uniform(-4, 4), 0, 0), pivot=(xo, 0, z))
            z += bh + 0.025
            k += 1
    if not dead:
        cap = _cap(p, -1.5, 1.5, ZC, CH, CD, sag=0.045 if worn else 0.0, mat=wood)
        top = ZC + CH
        # lagging across the cap (along Y), then the wedges
        x = -1.46
        k = 0
        while x < 1.46:
            bw = p.rng(f"lag{k}").uniform(0.16, 0.22)
            if not (worn and p.chance(f"lagmiss{k}", 0.2)):
                bd = p.rng(f"lagd{k}").uniform(0.34, 0.42)
                sag = 0.045 * (1 - (x / 1.5) ** 2) if worn else 0.0
                part = _lag_board(p, x, min(1.5, x + bw), -bd / 2, bd / 2, top - sag, top - sag + LAG_T, grain="Y")
                if worn:
                    G.xform(part.obj, rot=(0, vr.uniform(-2, 2), 0), pivot=(x, 0, top))
            x += bw + 0.02
            k += 1
        for k, wx in enumerate((-0.95, 0.05, 0.9)):
            wx += p.rng(f"wedge{k}").uniform(-0.15, 0.15)
            hgt = 2.8 - (top + LAG_T)
            p.prism([(-0.14, 0.0), (0.14, 0.0), (0.1, hgt), (-0.12, hgt * 0.8)], 0.16, C.LAG, plane="XZ",
                    offset=-0.08, grain="X")
            G.xform(p.parts[-1].obj, loc=(wx, 0, top + LAG_T))
        # hitches: the cap bears on the posts through notched blocks (a darker end-grain block each side)
        for s in (-1, 1):
            p.box((0.06, CD + 0.02, 0.06), (s * (XT + PW / 2 + 0.03), 0, ZC + 0.03), wood, bevel=0.008)
        del cap
        return
    # --- destroyed -------------------------------------------------------------------------------
    # the right post still stands; the cap snapped at x ~0.1: the right half hangs from the post top down to
    # the floor, the left half lies across the floor, the left post kicked out lying beside it
    rh = _broken_beam(p, 0.12, 1.5, CH, CD, key="capR", jag_at="x0", mat=C.TIMBER_ROT)
    G.xform(rh.obj, loc=(0, 0, 0))
    # rotate so the right end stays on the post top and the broken end rests on the floor
    pivot = Vector((XT + PW / 2, 0.0, ZC + CH / 2))
    G.xform(rh.obj, loc=(0, 0, ZC + CH / 2))
    p.settle([rh], pivot, (0, -1, 0), max_deg=80.0, exclude_r=0.2)
    lh = _broken_beam(p, -1.5, 0.05, CH, CD, key="capL", jag_at="x1", mat=C.TIMBER_ROT)
    G.xform(lh.obj, rot=(0, 0, 14), loc=(-0.25, -0.05, CH / 2))
    post = bar(p, (0, 0, 0), (0, 0, ZC), PW, PW, C.TIMBER_ROT, bevel=0.01, edge_deg=12.0)
    G.xform(post.obj, rot=(0, 90, -12), loc=(-0.55, 0.42, PW / 2))
    G.xform(post.obj, loc=(0, 0, -min(v.co.z for v in post.obj.data.vertices)))
    # lagging scattered on the floor and leaning on the debris
    for k in range(7):
        r = p.rng(f"scat{k}")
        bw, bd = r.uniform(0.16, 0.22), r.uniform(0.34, 0.42)
        b = _lag_board(p, -bw / 2, bw / 2, -bd / 2, bd / 2, 0.0, LAG_T, grain="Y")
        G.xform(b.obj, rot=(r.uniform(-8, 8), r.uniform(-8, 8), r.uniform(0, 180)),
                loc=(r.uniform(-1.3, 1.1), r.uniform(-0.45, 0.45), r.uniform(0.0, 0.08) + (0.26 if k == 3 else 0.0)))
    for k in range(5):
        r = p.rng(f"fall{k}")
        rock_chunk(p, (r.uniform(-1.2, 1.0), r.uniform(-0.4, 0.4), 0.0), (r.uniform(0.15, 0.35), r.uniform(0.15, 0.3),
                   r.uniform(0.1, 0.22)), key=f"fallrock{k}")
    p.collider((0.0, 0.0, 0.25), (2.6, 0.9, 0.5))


# ================================================================================================
# 2. rail
# ================================================================================================

RAIL_Y = 0.3125           # rail centres (0.6 m gauge between the heads' inner faces; 25 mm heads)
RAIL_BASE = 0.03          # sleeper tops
RAIL_TOP = RAIL_BASE + 0.065


def _rail_profile() -> list:
    """Light flat-bottom rail section (y, z) ~30 lb/yd: 65 mm tall, 56 mm foot, 25 mm head."""
    h = 0.065
    return [(-0.028, 0.0), (0.028, 0.0), (0.028, 0.007), (0.005, 0.014), (0.005, h - 0.02), (0.0125, h - 0.016),
            (0.0125, h - 0.002), (0.010, h), (-0.010, h), (-0.0125, h - 0.002), (-0.0125, h - 0.016),
            (-0.005, h - 0.02), (-0.005, 0.014), (-0.028, 0.007)]


def rail(p: Prop, x0: float, x1: float, y: float, z: float, mat: str = C.RAIL) -> core.Part:
    part = p.prism(_rail_profile(), x1 - x0, mat, plane="YZ", offset=x0, grain="X", edge_deg=12.0, wear=1.2)
    G.xform(part.obj, loc=(0, y, z))
    return part


def mine_rail_straight(p: Prop) -> None:
    """3 m of 0.6 m-gauge light rail along X (ends at x = +-1.5 exactly, so pieces butt end to end): five
    creosoted sleepers every 0.6 m, half sunk in a strip of ballast, spiked, fishplates at the joints.
    Rail tops at 0.095 m (the ore car's wheels sit there). Worn: rusted, a split sleeper, one missing, the
    ballast washed into mud."""
    worn = p.worn
    vr = p.vrng("rail")
    p.box((3.0, 1.0, 0.02), (0, 0, 0.004), C.BALLAST, bevel=0.0, wear=0.1)
    for k, x in enumerate((-1.2, -0.6, 0.0, 0.6, 1.2)):
        if worn and k == 3:
            continue
        r = p.rng(f"sl{k}")
        sl = p.box((0.13, r.uniform(0.96, 1.04), 0.08), (x + r.uniform(-0.02, 0.02), r.uniform(-0.02, 0.02), RAIL_BASE - 0.04),
                   C.TIMBER_ROT if worn else C.CREOSOTE, bevel=0.008, grain="Y")
        G.xform(sl.obj, rot=(0, 0, r.uniform(-2.5, 2.5) + (vr.uniform(-5, 5) if worn else 0.0)), pivot=(x, 0, 0))
        for s in (-1, 1):
            p.box((0.1, 0.13, 0.008), (x, s * RAIL_Y, RAIL_BASE + 0.003), C.IRON, bevel=0.002, wear=1.2)
            for o in (-1, 1):
                p.cyl(0.009, 0.03, (x + o * 0.035, s * RAIL_Y + o * 0.04, RAIL_BASE + 0.012), C.IRON, segs=4, wear=1.2)
    for s in (-1, 1):
        rail(p, -1.5, 1.5, s * RAIL_Y, RAIL_BASE)
        for e in (-1, 1):  # half fishplates at each joint (the next piece brings the other half)
            for o in (-1, 1):
                p.box((0.1, 0.008, 0.03), (e * 1.45, s * RAIL_Y + o * 0.011, RAIL_BASE + 0.03), C.IRON, bevel=0.002, wear=1.2)
    if worn:
        # mud washed over the ballast in places, a few loose stones on the sleepers
        for k in range(5):
            r = p.rng(f"stone{k}")
            rock_chunk(p, (r.uniform(-1.4, 1.4), r.uniform(-0.45, 0.45), RAIL_BASE if k % 2 else 0.0),
                       (r.uniform(0.05, 0.1), r.uniform(0.04, 0.09), r.uniform(0.03, 0.06)), key=f"st{k}", pts=10)
    p.collider((0, 0, RAIL_TOP / 2), (3.0, 1.0, RAIL_TOP))


# ================================================================================================
# 3. ore car
# ================================================================================================

def _wheel(p: Prop, x: float, y: float, inner: int) -> list:
    """Flanged cast wheel (tread r 0.15 on the rail top, flange to the inside), axis along Y."""
    R = 0.15
    w = 0.055
    zc = RAIL_TOP + R
    prof = [(0.03, -w / 2), (R - 0.004, -w / 2), (R, -w / 2 + 0.006), (R * 0.985, w / 2 - 0.012),
            (R + 0.022, w / 2 - 0.006), (R + 0.022, w / 2), (0.05, w / 2 + 0.01), (0.03, w / 2 + 0.03)]
    part = p.lathe(prof, (0, 0, 0), C.IRON, segs=16, axis="Y", cap_bottom=True, cap_top=True, wear=1.0)
    if inner < 0:
        G.xform(part.obj, rot=(0, 0, 180))
    G.xform(part.obj, loc=(x, y, zc))
    return [part]


def _tub(p: Prop, L: float, W: float, z0: float, depth: float, mat: str) -> list:
    """Side-tip U tub along X: U-shaped steel shell (prism) closed by two end plates, a rolled rim bead."""
    t = 0.012
    n = 8
    outer, inner = [], []
    rb = W / 2
    zb = z0 + rb * 0.75
    for i in range(n + 1):
        a = math.pi + math.pi * i / n
        outer.append((math.cos(a) * rb, zb + math.sin(a) * rb * 0.75))
        inner.append((math.cos(a) * (rb - t), zb + math.sin(a) * (rb - t) * 0.75))
    top = z0 + depth
    poly = [(-rb, top)] + outer + [(rb, top), (rb - t, top)] + list(reversed(inner)) + [(-rb + t, top)]
    poly = poly[::-1]  # clockwise as built: reverse for CCW (y, z) in YZ plane
    shell = p.prism(poly, L, mat, plane="YZ", offset=-L / 2, edge_deg=40.0, wear=1.1)
    end_poly = [(-rb, top)] + outer + [(rb, top)]
    ends = []
    for s in (-1, 1):
        e = p.prism(end_poly[::-1], t, mat, plane="YZ", offset=s * (L / 2) - (t if s > 0 else 0.0), edge_deg=40.0, wear=1.1)
        ends.append(e)
    rim = []
    for s in (-1, 1):
        rim.append(rod(p, (-L / 2, s * rb, top), (L / 2, s * rb, top), 0.012, mat, segs=6))
    for s in (-1, 1):
        rim.append(rod(p, (s * L / 2, -rb, top), (s * L / 2, rb, top), 0.012, mat, segs=6))
    return [shell] + ends + rim


def _ore_load(p: Prop, L: float, W: float, z: float, key: str) -> list:
    out = []
    # a heaped mound of fines, then rocks on it
    nx, ny = 10, 7
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u, v = i / nx * 2 - 1, j / ny * 2 - 1
            hgt = 0.17 * max(0.0, 1 - (u * u * 0.8 + v * v)) + 0.02 * noise.noise(Vector((u * 3, v * 3, 1.3)))
            verts.append((u * L / 2 * 0.98, v * W / 2 * 0.95, z + hgt))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    out.append(_mesh(p, "load", verts, faces, C.RUBBLE))
    for k in range(9):
        r = p.rng(f"{key}{k}")
        u, v = r.uniform(-0.8, 0.8), r.uniform(-0.75, 0.75)
        hz = z + 0.17 * max(0.0, 1 - (u * u * 0.8 + v * v)) - 0.03
        out.append(rock_chunk(p, (u * L / 2, v * W / 2, hz), (r.uniform(0.12, 0.24), r.uniform(0.1, 0.2), r.uniform(0.08, 0.15)),
                              key=f"{key}r{k}"))
    return out


def mine_ore_cart(p: Prop) -> None:
    """Side-tip ore car (1.4 x ~1.05 x 0.8) running along X: four flanged wheels on 0.6 m gauge (wheels rest on
    rail tops at 0.095 m: stand it on mine_rail_straight at the same origin), channel frame, timber bumper
    blocks and link couplers, two rockers carrying the U tub with its tipping latch, the car number on
    the side. Worn: loaded with broken rock, rusted. Destroyed: tipped onto its side, the load spilled."""
    worn, dead = p.worn, p.destroyed
    parts = []
    for x in (-0.38, 0.38):
        for s in (-1, 1):
            parts += _wheel(p, x, s * RAIL_Y, -s)
        parts.append(rod(p, (x, -0.36, RAIL_TOP + 0.15), (x, 0.36, RAIL_TOP + 0.15), 0.025, C.STEEL_DARK, segs=8))
    zf = RAIL_TOP + 0.15 + 0.02
    for s in (-1, 1):
        parts += ibeam(p, (-0.62, s * 0.22, zf + 0.06), (0.62, s * 0.22, zf + 0.06), 0.12, 0.05, C.STEEL_DARK, roll=90)
        for x in (-0.38, 0.38):
            parts.append(p.box((0.12, 0.06, 0.1), (x, s * 0.22, zf - 0.01), C.IRON, bevel=0.006))
    for s in (-1, 1):
        parts.append(p.box((0.06, 0.56, 0.12), (s * 0.62, 0, zf + 0.06), C.STEEL_DARK, bevel=0.005))
        parts.append(p.box((0.08, 0.5, 0.16), (s * 0.67, 0, zf + 0.06), C.TIMBER, bevel=0.012, grain="Y"))
        parts.append(rod(p, (s * 0.71, 0, zf + 0.06), (s * 0.78, 0, zf + 0.06), 0.012, C.CHAIN, segs=6))
        parts.append(p.lathe([(0.0, -0.01), (0.03, -0.01), (0.035, 0.0), (0.03, 0.01), (0.0, 0.01)], (s * 0.665, 0, zf + 0.06),
                             C.CHAIN, segs=8, axis="X"))
    # rockers (curved cradle plates) on the frame
    zr = zf + 0.12
    for x in (-0.42, 0.42):
        arc = [(math.sin(a) * 0.36, zr + 0.2 - math.cos(a) * 0.2) for a in [(-0.9 + 1.8 * i / 8) for i in range(9)]]
        poly = [(arc[0][0], zr + 0.22)] + arc + [(arc[-1][0], zr + 0.22)]
        parts.append(p.prism(poly[::-1], 0.03, C.STEEL_DARK, plane="YZ", offset=x - 0.015, edge_deg=40.0))
        parts.append(p.box((0.05, 0.6, 0.03), (x, 0, zr - 0.005), C.STEEL_DARK, bevel=0.004))
    L, W = 1.24, 0.8
    tz = zr + 0.18
    tub = _tub(p, L, W, tz, 1.05 - tz, C.STEEL_DARK if not worn else C.RUST)
    parts += tub
    # tipping latch and handle on the front side
    parts.append(bar(p, (0.5, -W / 2 - 0.03, tz + 0.15), (0.5, -W / 2 - 0.03, 0.98), 0.03, 0.015, C.STEEL))
    parts.append(rod(p, (0.5, -W / 2 - 0.05, 0.98), (0.62, -W / 2 - 0.05, 1.0), 0.012, C.STEEL, segs=6))
    parts.append(plate(p, 0.24, 0.24, (-0.2, -W / 2 - 0.004, 0.86), atlas("car_no"), rot=(0, 0, 0)))
    if worn:
        parts += _ore_load(p, L - 0.05, W - 0.05, 0.86, "load")
    if dead:
        # tipped onto its front side: rotate the whole car about X and lay it on the floor, then the spill
        p.lay_on_floor(parts, rot=(-96, 0, 4), at=(0.0, -0.05))
        for k in range(8):
            r = p.rng(f"spill{k}")
            rock_chunk(p, (r.uniform(-0.6, 0.6), r.uniform(-0.95, -0.45), 0.0),
                       (r.uniform(0.12, 0.26), r.uniform(0.1, 0.22), r.uniform(0.08, 0.16)), key=f"spr{k}")
        p.collider((0, -0.1, 0.42), (1.4, 1.1, 0.84))
        centre(p)
        return
    p.collider((0, 0, 0.55), (1.4, 0.85, 1.0))


# ================================================================================================
# 4. hoist
# ================================================================================================

def _gear(p: Prop, x: float, y: float, z: float, R: float, teeth: int, w: float, mat: str) -> core.Part:
    pts = []
    for i in range(teeth):
        a0 = 2 * math.pi * i / teeth
        da = 2 * math.pi / teeth
        for f, rr in ((0.0, R - 0.025), (0.2, R + 0.012), (0.5, R + 0.012), (0.7, R - 0.025)):
            a = a0 + da * f
            pts.append((math.cos(a) * rr, math.sin(a) * rr))
    part = p.prism(pts, w, mat, plane="YZ", offset=-w / 2, edge_deg=40.0, wear=1.0)
    G.xform(part.obj, loc=(x, y, z))
    return part


def mine_hoist(p: Prop) -> None:
    """Electric single-drum hoist on timber skids (2.5 x 1.8 x 1.6): a 1 m drum wound with rope between two
    flanges on a shaft in two pedestal bearings, a band brake round the left flange with its weighted lever,
    a spur gear on the right (behind a yellow guard when clean) driven by the pinion of a ribbed motor, a
    controller lever stand and a depth dial at the operator's (front, -Y) side, the maker's plate. Worn: the
    guard gone, rust, oil, the rope end slack."""
    worn = p.worn
    zs = 0.0
    for s in (-1, 1):
        p.box((2.5, 0.22, 0.2), (0, s * 0.55, 0.1), C.TIMBER, bevel=0.012, grain="X").floor_wear = 0.5
        ibeam(p, (-1.15, s * 0.55, 0.26), (1.15, s * 0.55, 0.26), 0.12, 0.1, C.GREEN)
    for x in (-1.05, -0.1, 0.6, 1.05):
        p.box((0.08, 1.2, 0.08), (x, 0, 0.36), C.GREEN, bevel=0.004)
    zc = 0.98
    yd = 0.08
    xd0, xd1 = -0.75, 0.2
    # drum + rope wraps (a rippled surface of revolution) + flanges
    n = 26
    prof = [(0.0, xd0)]
    for i in range(n + 1):
        t = i / n
        prof.append((0.5 + 0.016 * abs(math.sin(t * math.pi * n * 0.5 * 2)), xd0 + 0.02 + t * (xd1 - xd0 - 0.04)))
    prof.append((0.0, xd1))
    drum = p.lathe([(r_, z_) for r_, z_ in prof], (0, 0, 0), C.ROPE, segs=24, axis="X", wear=0.4)
    G.xform(drum.obj, loc=(0, yd, zc))
    for x in (xd0, xd1):
        p.cyl(0.62, 0.035, (x, yd, zc), C.GREEN, axis="X", segs=28, bevel=0.006)
    p.cyl(0.07, 1.9, (-0.2, yd, zc), C.STEEL, axis="X", segs=12)
    # pedestals with bearing blocks
    for x in (-0.95, 0.38):
        p.prism([(-0.4, 0.4), (0.4, 0.4), (0.14, zc - 0.08), (-0.14, zc - 0.08)], 0.1, C.GREEN, plane="YZ", offset=x - 0.05)
        G.xform(p.parts[-1].obj, loc=(0, yd, 0))
        p.box((0.16, 0.36, 0.16), (x, yd, zc), C.IRON, bevel=0.015)
        for s in (-1, 1):
            p.cyl(0.018, 0.04, (x, yd + s * 0.14, zc + 0.09), C.STEEL, segs=6)
    # band brake on the left flange + weighted lever to the front
    band = p.cyl(0.645, 0.09, (xd0 - 0.08, yd, zc), C.STEEL_DARK, axis="X", segs=28, cap=False)
    band.edge_deg = 50.0
    rod(p, (xd0 - 0.08, yd - 0.62, zc - 0.25), (xd0 - 0.08, -0.72, 0.42), 0.02, C.STEEL_DARK, segs=6)
    p.cyl(0.09, 0.14, (xd0 - 0.08, -0.72, 0.42), C.IRON, axis="X", segs=12)
    # gear + pinion + motor
    xg = 0.52
    _gear(p, xg, yd, zc, 0.6, 44, 0.07, C.IRON)
    yp, zp = yd - 0.52, zc - 0.5
    _gear(p, xg, yp, zp, 0.12, 11, 0.08, C.STEEL)
    p.cyl(0.03, 0.5, (xg + 0.25, yp, zp), C.STEEL, axis="X", segs=8)
    p.box((0.62, 0.48, 0.12), (0.92, yp, 0.36), C.GREEN, bevel=0.006)
    mot = p.lathe([(0.0, -0.33), (0.2, -0.33), (0.24, -0.29), (0.24, 0.29), (0.2, 0.33), (0.0, 0.33)], (0.95, yp, zp), C.GREEN,
                  segs=20, axis="X", wear=1.0)
    del mot
    for k in range(8):
        a = 2 * math.pi * k / 8 + 0.2
        p.box((0.5, 0.018, 0.035), (0.95, yp + math.cos(a) * 0.245, zp + math.sin(a) * 0.245), C.GREEN, bevel=0.003)
        G.xform(p.parts[-1].obj, rot=(math.degrees(a) - 90, 0, 0), pivot=(0.95, yp + math.cos(a) * 0.245, zp + math.sin(a) * 0.245))
    p.box((0.2, 0.16, 0.14), (1.0, yp - 0.0, zp + 0.3), C.GREEN, bevel=0.01)       # terminal box
    rod(p, (1.0, yp, zp + 0.37), (1.0, 0.6, 0.6), 0.025, C.RUBBER, segs=6)         # conduit off to the back
    plate(p, 0.24, 0.12, (0.95, yp - 0.247, zp - 0.05), atlas("plate"), rot=(0, 0, 0), wear=0.6)
    if not worn:
        # gear guard: a ring wall and a front disc over the spur gear and pinion
        p.cyl(0.67, 0.14, (xg, yd, zc), C.YELLOW, axis="X", segs=28, bevel=0.008)
        p.cyl(0.18, 0.14, (xg, yp, zp), C.YELLOW, axis="X", segs=16, bevel=0.006)
    # operator's stand: controller lever and depth dial, front left
    xo = -1.0
    p.box((0.3, 0.26, 0.9), (xo, -0.6, 0.45), C.GREEN, bevel=0.01)
    p.box((0.22, 0.04, 0.3), (xo, -0.6, 0.9), C.GREEN, bevel=0.006)
    lever = rod(p, (xo, -0.6, 0.92), (xo + 0.05, -0.7, 1.45), 0.016, C.STEEL, segs=6)
    del lever
    p.cyl(0.035, 0.08, (xo + 0.05, -0.7, 1.47), C.RUBBER, segs=8)
    rod(p, (xo + 0.2, -0.55, 0.9), (xo + 0.2, -0.55, 1.5), 0.025, C.GREEN, segs=8)
    p.cyl(0.19, 0.06, (xo + 0.2, -0.58, 1.6), C.GREEN, axis="Y", segs=20, bevel=0.01)
    p.cyl(0.165, 0.004, (xo + 0.2, -0.612, 1.6), "furn_plastic_white", axis="Y", segs=20)
    bar(p, (xo + 0.2, -0.617, 1.6), (xo + 0.28, -0.617, 1.7), 0.008, 0.003, C.RUBBER)
    # rope leaving the top of the drum toward the headframe (back, +Y, up)
    rod(p, (-0.3, yd + 0.05, zc + 0.5), (-0.3, 0.8, 1.8), 0.016, C.ROPE, segs=6)
    p.collider((0, 0, 0.75), (2.5, 1.5, 1.5))
    centre(p)
    del zs


# ================================================================================================
# 5. headframe
# ================================================================================================

def mine_headframe(p: Prop) -> None:
    """Steel A-frame headframe (~4 x 9 x 4.4) over a raised concrete shaft collar: a four-post tower of
    I-section legs tapering to the sheave deck at 7.6 m, girts and X bracing, two backstays down to footings
    behind (toward the hoist house, +Y), a grated deck with handrails, the 1.5 m spoked sheave wheel on its
    bearings (top ~9.1 m), the hoist rope down the shaft and off to the hoist, timber cage guides, a ladder up
    the left side, the LARKSPUR No.1 SHAFT sign over the landing. The open collar shows the timber-lined shaft
    dropping into black. Worn: braces and a handrail run gone, a bent rail, heavier rust."""
    worn = p.worn
    st = C.OXIDE
    # collar: raised concrete ring round a 1.8 x 1.6 opening, lining and the dark drop
    CZ = 0.3
    HX, HY = 0.9, 0.8
    for (x0, x1, y0, y1) in ((-1.6, 1.6, -1.6, -HY), (-1.6, 1.6, HY, 1.6), (-1.6, -HX, -HY, HY), (HX, 1.6, -HY, HY)):
        p.box((x1 - x0, y1 - y0, CZ), ((x0 + x1) / 2, (y0 + y1) / 2, CZ / 2), C.CONCRETE, bevel=0.02, grain="X").floor_wear = 0.4
    # shaft lining (faces inward) and the void floor
    verts = []
    ring = [(-HX, -HY), (HX, -HY), (HX, HY), (-HX, HY)]
    for z in (CZ, 0.02):
        for x, y in ring:
            verts.append((x, y, z))
    faces = [(i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i) for i in range(4)]
    _mesh(p, "lining", verts, faces, C.TIMBER_ROT, uv="box")   # wound to face into the shaft
    p.box((2 * HX, 2 * HY, 0.004), (0, 0, 0.022), C.VOID, bevel=0.0, wear=0.0)
    # tower legs: four I-section posts tapering in
    TB, TT = (1.15, 1.05), (0.85, 0.8)
    ZT = 7.6
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = (sx * TB[0], sy * TB[1], CZ)
            b = (sx * TT[0], sy * TT[1], ZT)
            legs.append((a, b))
            ibeam(p, a, b, 0.2, 0.16, st, roll=0)
            p.box((0.36, 0.36, 0.03), (a[0], a[1], CZ + 0.015), C.STEEL_DARK, bevel=0.003)
    # girts and X bracing on the sides and back; the front stays open below the sign girt
    levels = [CZ + 0.1, 2.6, 4.4, 6.1, ZT - 0.1]

    def at(sx, sy, z):
        t = (z - CZ) / (ZT - CZ)
        return Vector((sx * (TB[0] + (TT[0] - TB[0]) * t), sy * (TB[1] + (TT[1] - TB[1]) * t), z))

    br = 0
    for li, z in enumerate(levels):
        for (s0, s1) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            if li == 0 and s0[1] == -1 and s1[1] == -1:
                continue  # landing side: no sill girt across the cage door
            bar(p, at(*s0, z), at(*s1, z), 0.14, 0.1, st, bevel=0.004)
    for li in range(1, len(levels) - 1):
        z0, z1 = levels[li], levels[li + 1]
        for (s0, s1) in (((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1)), ((-1, -1), (1, -1))):
            br += 1
            if worn and p.chance(f"brace{br}", 0.22):
                continue
            bar(p, at(*s0, z0), at(*s1, z1), 0.08, 0.016, st, bevel=0.002)
            bar(p, at(*s1, z0), at(*s0, z1), 0.08, 0.016, st, bevel=0.002)
    # backstays to footings behind (+Y)
    for sx in (-1, 1):
        a = Vector((sx * 1.2, 2.5, 0.0))
        b = at(sx, 1, ZT - 0.3)
        ibeam(p, a + Vector((0, 0, 0.4)), b, 0.22, 0.16, st)
        p.box((0.6, 0.6, 0.4), (a.x, a.y, 0.2), C.CONCRETE, bevel=0.02)
        A = a + Vector((0, 0, 0.4))
        for zz in (2.6, 4.4):
            bar(p, at(sx, 1, zz), A + (b - A) * ((zz - A.z) / (b.z - A.z)), 0.1, 0.1, st)
    bar(p, (-1.2, 2.5, 0.6), (1.2, 2.5, 0.6), 0.12, 0.12, st)
    # sheave deck: grating, beams, handrails
    p.box((2.3, 2.2, 0.05), (0, 0.05, ZT + 0.025), C.GALV, bevel=0.004, uv_scale=3.0)
    for x in (-0.35, 0.35):
        ibeam(p, (x, -0.95, ZT + 0.15), (x, 1.05, ZT + 0.15), 0.2, 0.12, st)
    rails = [((-1.15, -1.05), (1.15, -1.05)), ((1.15, -1.05), (1.15, 1.15)), ((1.15, 1.15), (-1.15, 1.15)),
             ((-1.15, 1.15), (-1.15, -1.05))]
    for k, ((x0, y0), (x1, y1)) in enumerate(rails):
        if worn and k == 2:
            # a run gone, its post bent outward
            rod(p, (x0, y0, ZT), (x0 + 0.1, y0 + 0.25, ZT + 0.9), 0.022, st, segs=6)
            continue
        for z in (ZT + 0.5, ZT + 1.0):
            rod(p, (x0, y0, z), (x1, y1, z), 0.02, st, segs=6)
        rod(p, (x0, y0, ZT), (x0, y0, ZT + 1.02), 0.022, st, segs=6)
    # sheave wheel (plane YZ, axis X) and its pillow blocks
    SR = 0.75
    sy0, sz0 = 0.15, ZT + 0.3 + SR + 0.02
    rim = p.lathe([(SR - 0.06, -0.06), (SR + 0.02, -0.06), (SR - 0.02, -0.02), (SR - 0.03, 0.0), (SR - 0.02, 0.02),
                   (SR + 0.02, 0.06), (SR - 0.06, 0.06)], (0, sy0, sz0), C.IRON, segs=36, axis="X", cap_bottom=False,
                  cap_top=False, wear=1.0)
    rim.edge_deg = 40.0
    p.lathe([(SR - 0.06, -0.06), (SR - 0.06, 0.06)], (0, sy0, sz0), C.IRON, segs=36, axis="X", cap_bottom=False,
            cap_top=False)
    p.cyl(0.12, 0.2, (0, sy0, sz0), C.IRON, axis="X", segs=14, bevel=0.01)
    p.cyl(0.05, 0.9, (0, sy0, sz0), C.STEEL, axis="X", segs=10)
    for k in range(8):
        a = 2 * math.pi * k / 8 + 0.2
        bar(p, (0, sy0 + math.cos(a) * 0.1, sz0 + math.sin(a) * 0.1),
            (0, sy0 + math.cos(a) * (SR - 0.06), sz0 + math.sin(a) * (SR - 0.06)), 0.03, 0.05, C.IRON, roll=90, bevel=0.003)
    for x in (-0.35, 0.35):
        p.box((0.16, 0.36, 0.2), (x, sy0, sz0 - 0.08), C.IRON, bevel=0.015)
        p.box((0.2, 0.5, 0.3), (x, sy0, ZT + 0.4), st, bevel=0.006)
    # the rope: down the shaft from the front of the sheave, and off the top back to the hoist
    yr = sy0 - SR + 0.03
    rod(p, (0, yr, sz0), (0, yr, CZ - 0.25), 0.016, C.ROPE, segs=6, cap=False)
    a = math.radians(32)
    yb, zb = sy0 + math.sin(a) * (SR - 0.03), sz0 + math.cos(a) * (SR - 0.03)
    rod(p, (0, yb, zb), (0, 2.75, 1.6), 0.016, C.ROPE, segs=6)
    # cage guides (timber) inside the tower, front landing gate and the sign
    for x in (-0.8, 0.8):
        p.box((0.1, 0.14, ZT - 0.6), (x, -0.1, CZ + (ZT - 0.6) / 2), C.TIMBER, bevel=0.01, grain="Z")
        bar(p, (x, -0.1, 2.6), at(1 if x > 0 else -1, -1, 2.6), 0.08, 0.08, st)
        bar(p, (x, -0.1, 5.2), at(1 if x > 0 else -1, 1, 5.2), 0.08, 0.08, st)
    for x0, x1 in ((-1.1, -0.45), (0.45, 1.1)):
        for z in (CZ + 0.5, CZ + 1.05):
            rod(p, (x0, -1.12, z), (x1, -1.12, z), 0.02, C.YELLOW, segs=6)
        rod(p, (x0, -1.12, CZ), (x0, -1.12, CZ + 1.07), 0.022, C.YELLOW, segs=6)
        rod(p, (x1, -1.12, CZ), (x1, -1.12, CZ + 1.07), 0.022, C.YELLOW, segs=6)
    sz = 2.6 + 0.3
    plate(p, 1.4, 0.7, (0, at(1, -1, sz).y - 0.08, sz + 0.25), atlas("shaft"), t=0.006, wear=0.8)
    # ladder up the left side (outside), to the deck
    lx = -1.2
    for dy in (-0.22, 0.22):
        rod(p, (lx - 0.12, dy, CZ), (-0.98, dy, ZT + 1.0), 0.02, C.STEEL, segs=6)
    for k in range(int((ZT - CZ) / 0.32)):
        z = CZ + 0.3 + k * 0.32
        t = (z - CZ) / (ZT + 1.0 - CZ)
        xx = lx - 0.12 + t * (-0.98 - lx + 0.12)
        rod(p, (xx, -0.22, z), (xx, 0.22, z), 0.012, C.STEEL, segs=5)
    # colliders: collar walls, legs, backstays, deck
    p.collider((0, -1.2, CZ / 2), (3.2, 0.8, CZ))
    p.collider((0, 1.2, CZ / 2), (3.2, 0.8, CZ))
    p.collider((-1.25, 0, CZ / 2), (0.7, 1.6, CZ))
    p.collider((1.25, 0, CZ / 2), (0.7, 1.6, CZ))
    for (a, b) in legs:
        c = (Vector(a) + Vector(b)) * 0.5
        p.collider(c, (0.25, 0.25, ZT - CZ))
    p.collider((0, 0.05, ZT + 0.6), (2.4, 2.3, 1.2))
    centre(p)


# ================================================================================================
# 6. cage
# ================================================================================================

def mine_cage(p: Prop) -> None:
    """Shaft cage (1.6 x 2.45 x 1.4): steel angle frame, chequer floor, sheet-steel lower sides and back with
    wire mesh above, a roof (bonnet) with the bridle and rope socket on top, guide shoes for the timber
    guides on both sides, a folding scissor gate folded back across the open front (-Y), the capacity
    plate inside. Worn: rust, a dented side sheet, the gate half drawn."""
    worn = p.worn
    W, D, H = 1.5, 1.3, 2.15
    hx, hy = W / 2, D / 2
    st = C.GREY if not worn else C.RUST
    p.box((W, D, 0.08), (0, 0, 0.04), C.STEEL_DARK, bevel=0.005, uv_scale=2.0).floor_wear = 0.5
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.06, 0.06, H), (sx * (hx - 0.03), sy * (hy - 0.03), H / 2), st, bevel=0.004, grain="Z")
    for z in (0.08, 1.05, H):
        for sy in (-1, 1):
            if sy < 0 and z < 2.0:
                continue
            p.box((W, 0.06, 0.06), (0, sy * (hy - 0.03), z - 0.03), st, bevel=0.004, grain="X")
        for sx in (-1, 1):
            p.box((0.06, D, 0.06), (sx * (hx - 0.03), 0, z - 0.03), st, bevel=0.004, grain="Y")
    # side + back sheets (lower), mesh above
    dent = 0.03 if worn else 0.0
    for sx in (-1, 1):
        sh = p.rbox((0.008, D - 0.1, 0.95), (sx * (hx - 0.02), 0, 0.55), C.GALV if not worn else C.RUST, radius=0.003,
                    inner=(1, 6, 6), edge_deg=12.0)
        if dent and sx > 0:
            for v in sh.obj.data.vertices:
                d2 = (v.co.y - 0.1) ** 2 + (v.co.z - 0.6) ** 2
                v.co.x -= dent * math.exp(-d2 / 0.04)
            sh.obj.data.update()
    for sx in (-1, 1):
        _mesh_panel(p, (0.0, D - 0.12, H - 1.12), (sx * (hx - 0.02), 0, 1.05 + (H - 1.12) / 2))
    p.box((W - 0.1, 0.008, 0.95), (0, hy - 0.02, 0.55), C.GALV if not worn else C.RUST, bevel=0.002, grain="X")
    _mesh_panel(p, (W - 0.12, 0.0, H - 1.12), (0, hy - 0.02, 1.05 + (H - 1.12) / 2))
    # roof + bridle + rope socket
    p.box((W + 0.04, D + 0.04, 0.012), (0, 0, H + 0.006), st, bevel=0.002)
    for sx in (-1, 1):
        bar(p, (sx * (hx - 0.06), -0.08, H), (sx * 0.05, -0.08, 2.38), 0.06, 0.02, st)
        bar(p, (sx * (hx - 0.06), 0.08, H), (sx * 0.05, 0.08, 2.38), 0.06, 0.02, st)
    p.box((0.16, 0.22, 0.05), (0, 0, 2.38), C.IRON, bevel=0.006)
    p.cyl(0.03, 0.12, (0, 0, 2.46), C.IRON, segs=10)
    # guide shoes both sides (top and bottom) and safety dogs
    for sx in (-1, 1):
        for z in (0.25, H - 0.15):
            p.box((0.08, 0.2, 0.14), (sx * (hx + 0.04), 0, z), C.IRON, bevel=0.008)
            p.box((0.04, 0.05, 0.14), (sx * (hx + 0.1), -0.075, z), C.IRON, bevel=0.004)
            p.box((0.04, 0.05, 0.14), (sx * (hx + 0.1), 0.075, z), C.IRON, bevel=0.004)
        p.box((0.06, 0.1, 0.1), (sx * (hx + 0.04), 0, H + 0.08), C.STEEL_DARK, bevel=0.006)
    # scissor gate: pickets folded at the left of the front opening, diagonals between them
    y = -hy - 0.01
    p.box((W, 0.04, 0.03), (0, y, H - 0.06), st, bevel=0.003, grain="X")   # top track
    p.box((W, 0.04, 0.02), (0, y, 0.09), st, bevel=0.003, grain="X")       # bottom track
    n = 9
    spread = 0.11 if worn else 0.045
    x0 = -hx + 0.06
    xs = [x0 + i * spread for i in range(n)]
    gh0, gh1 = 0.12, H - 0.1
    for x in xs:
        p.box((0.018, 0.012, gh1 - gh0), (x, y - 0.012, (gh0 + gh1) / 2), C.STEEL_DARK, bevel=0.002, grain="Z")
    seg = 0.5
    for i in range(n - 1):
        z = gh0 + 0.08
        k = 0
        while z + seg < gh1:
            a = (xs[i], y - 0.022, z)
            b = (xs[i + 1], y - 0.022, z + seg)
            if k % 2:
                a, b = (xs[i], y - 0.022, z + seg), (xs[i + 1], y - 0.022, z)
            bar(p, a, b, 0.014, 0.004, C.STEEL_DARK, bevel=0.0)
            z += seg
            k += 1
    p.box((0.03, 0.03, 0.1), (xs[-1] + 0.02, y - 0.03, 1.1), C.STEEL, bevel=0.004)  # the gate's handle
    plate(p, 0.32, 0.16, (0.3, hy - 0.03, 1.55), atlas("cage"), rot=(0, 0, 180), wear=0.6)
    p.collider((0, 0, 0.04), (W, D, 0.08))
    for sx in (-1, 1):
        p.collider((sx * (hx - 0.02), 0, H / 2), (0.05, D, H))
    p.collider((0, hy - 0.02, H / 2), (W, 0.05, H))
    p.collider((0, 0, H), (W, D, 0.05))


def _mesh_panel(p: Prop, size, center, mat: str = C.MESH) -> core.Part:
    """Single-sided quad of alpha-cut wire mesh (the foliage shader draws both sides). size has one zero."""
    sx, sy, sz = (s * 0.5 for s in size)
    if size[1] == 0.0:
        pts = [(-sx, 0, -sz), (sx, 0, -sz), (sx, 0, sz), (-sx, 0, sz)]
    else:
        pts = [(0, -sy, -sz), (0, sy, -sz), (0, sy, sz), (0, -sy, sz)]
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(Vector(q) + Vector(center)) for q in pts])
    return p.add(G._obj(p._name("mesh"), bm), mat, uv_scale=1.2, wear=0.5)


# ================================================================================================
# 7. rock faces
# ================================================================================================

def _relief(p: Prop, *, W: float, H: float, D: float, nx: int, nz: int, disp, side_mask, mat: str) -> core.Part:
    """Rock relief slab in the XZ plane facing -Y: back plane at y = +D/2 (against the wall), the surface
    pushed out to y = D/2 - disp(x, z) (disp in [0, D]); side_mask(x, z) in [0, 1] fades the relief out at
    the irregular side outline, and beyond it (mask 0) vertices tuck 2 cm behind the back plane into the
    wall, so the slab's silhouette follows the rock, not the grid."""
    verts, faces = [], []
    for j in range(nz + 1):
        z = -0.05 + (H + 0.1) * j / nz
        for i in range(nx + 1):
            x = -W / 2 + W * i / nx
            m = side_mask(x, z)
            if m <= 0.0:
                y = D / 2 + 0.02
            else:
                y = D / 2 - min(D, max(0.0, disp(x, z))) * m
            verts.append((x, y, z))
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    return _mesh(p, "relief", verts, faces, mat, edge_deg=35.0, wear=0.25)


def _rock_face(p: Prop, style: str) -> None:
    worn = p.worn
    W, H, D = 2.0, 2.8, 0.6
    noise.seed_set(p.seed % 99991)
    o = Vector((p.seed % 97 * 0.31, p.seed % 89 * 0.17, 1.3))
    fac = _facet_noise(p.seed)
    r = p.rng("outline")
    wob = [r.uniform(-0.12, 0.08) for _ in range(8)]

    def half_w(z):
        t = z / H * 7
        i = int(min(6, max(0, math.floor(t))))
        f = t - i
        return W / 2 - 0.06 + wob[i] * (1 - f) + wob[i + 1] * f + 0.04 * noise.noise(Vector((z * 3.0, 0.5, 0)) + o)

    def side_mask(x, z):
        e = half_w(z) - abs(x)
        if e < 0:
            return 0.0
        return min(1.0, (e / 0.32)) ** 0.8

    if style == "granite":
        def disp(x, z):
            pos = Vector((x, 0.0, z)) + o
            f1 = fac(pos, 0.42)
            f2 = fac(pos + Vector((3.1, 0, 7.7)), 0.17)
            base = 0.3 + 0.12 * noise.noise(pos * 0.6)
            return base + 0.35 * f1 + 0.12 * f2 + 0.025 * noise.noise(pos * 9.0)
        nx, nz = 30, 40
        mat = C.ROCK
    elif style == "ledge":
        def disp(x, z):
            pos = Vector((x, 0.0, z)) + o
            f1 = fac(pos, 0.3)
            base = 0.26 + 0.1 * noise.noise(pos * 0.7)
            # an overhanging ledge at ~1.7 m: out over a recess below it
            led = 0.2 * math.exp(-((z - 1.75) / 0.22) ** 2) - 0.14 * math.exp(-((z - 1.2) / 0.3) ** 2)
            return base + led + 0.3 * f1 + 0.03 * noise.noise(pos * 8.0)
        nx, nz = 30, 44
        mat = C.ROCK
    else:  # limestone: rounded, draped flowstone
        def disp(x, z):
            pos = Vector((x, 0.0, z)) + o
            lumps = 0.28 + 0.16 * noise.noise(pos * 1.1) + 0.06 * noise.noise(pos * 2.6)
            drape = 0.07 * abs(noise.noise(Vector((pos.x * 5.0, 0.3, pos.z * 0.6))))
            bulge = 0.12 * math.exp(-((x + 0.3) ** 2 / 0.25 + (z - 1.0) ** 2 / 0.5))
            return lumps + drape + bulge
        nx, nz = 26, 36
        mat = C.LIME
    _relief(p, W=W, H=H, D=D, nx=nx, nz=nz, disp=disp, side_mask=side_mask, mat=mat)
    # fallen blocks at the foot of the blasted faces; a fringe of small stalagmites under the limestone
    if style != "lime":
        for k in range(4 if worn else 3):
            rr = p.rng(f"foot{k}")
            x = rr.uniform(-0.8, 0.8)
            rock_chunk(p, (x, rr.uniform(-0.38, -0.22), 0.0), (rr.uniform(0.18, 0.4), rr.uniform(0.16, 0.3),
                       rr.uniform(0.12, 0.26)), key=f"footr{k}", mat=C.RUBBLE)
    else:
        for k in range(3):
            rr = p.rng(f"mite{k}")
            _stalag(p, Vector((rr.uniform(-0.7, 0.7), rr.uniform(-0.22, -0.08), 0.0)), rr.uniform(0.12, 0.3),
                    rr.uniform(0.04, 0.07), key=f"fm{k}", segs=8, rings=5)
    p.collider((0, 0, H / 2), (W, D, H))
    centre(p)


def mine_rock_face(p: Prop) -> None:
    """Granite blast face (2.0 x 2.8 x 0.6, back flat against the wall): chunky planar facets at two scales
    over a broad swell, the side outline ragged, fallen blocks at the foot."""
    _rock_face(p, "granite")


def mine_rock_face_b(p: Prop) -> None:
    """Granite face with an overhanging ledge at ~1.7 m over a recess, finer facets."""
    _rock_face(p, "ledge")


def mine_rock_face_c(p: Prop) -> None:
    """Limestone cave wall: rounded lumps, vertical flowstone draperies, a bulging boss; small stalagmites
    at its foot."""
    _rock_face(p, "lime")


# ================================================================================================
# 8. rock pile
# ================================================================================================

def mine_rock_pile(p: Prop) -> None:
    """Collapse (2.4 x ~1.2 x 1.8): a mound of broken rock and fines peaking toward the back, boulders lying
    on it and rolled out at its foot. Worn: broken timbers (a post and lagging) caught in the fall."""
    worn = p.worn
    noise.seed_set(p.seed % 99991)
    fac = _facet_noise(p.seed)
    RX, RY, PK = 1.15, 0.85, 1.25
    nx, ny = 28, 22
    verts, faces = [], []

    def hgt(x, y):
        u, v = x / RX, (y - 0.15) / RY
        rr = u * u + v * v
        if rr >= 1.0:
            return -0.02
        pos = Vector((x, y, 0.0))
        return PK * (1 - rr) ** 0.85 * (0.85 + 0.25 * noise.noise(pos * 1.4)) + 0.09 * fac(pos, 0.22) * (1 - rr) - 0.02

    for j in range(ny + 1):
        for i in range(nx + 1):
            x = -RX * 1.02 + 2 * RX * 1.02 * i / nx
            y = -RY * 1.02 + 0.15 + 2 * RY * 1.02 * j / ny
            verts.append((x, y, max(-0.02, hgt(x, y))))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    _mesh(p, "pile", verts, faces, C.RUBBLE, edge_deg=35.0)
    for k in range(13):
        r = p.rng(f"b{k}")
        a = r.uniform(0, 2 * math.pi)
        d = math.sqrt(r.uniform(0.0, 1.0)) * (1.05 if k < 9 else 1.25)
        x, y = math.cos(a) * RX * d * 0.95, 0.15 + math.sin(a) * RY * d * 0.95
        s = r.uniform(0.18, 0.5) * (1.0 if k < 9 else 0.6)
        z = max(0.0, hgt(x, y)) - s * 0.3
        rock_chunk(p, (x, y, max(0.0, z)), (s, s * r.uniform(0.7, 1.0), s * r.uniform(0.5, 0.8)), key=f"bb{k}")
    if worn:
        post = bar(p, (0, 0, 0), (0, 0, 1.9), 0.22, 0.22, C.TIMBER_ROT, bevel=0.01, edge_deg=12.0)
        G.xform(post.obj, rot=(0, 62, 25), loc=(-0.2, 0.0, 0.25))
        for k in range(3):
            r = p.rng(f"lg{k}")
            b = _lag_board(p, -0.2, 0.2, -0.09, 0.09, 0.0, 0.05, grain="X")
            G.xform(b.obj, rot=(r.uniform(-25, 25), r.uniform(-30, 30), r.uniform(0, 180)),
                    loc=(r.uniform(-0.7, 0.7), r.uniform(-0.5, 0.4), r.uniform(0.2, 0.55)))
    p.collider((0, 0.1, 0.6), (2.3, 1.7, 1.2))
    centre(p)


# ================================================================================================
# 9. stalagmites
# ================================================================================================

def _stalag(p: Prop, base: Vector, h: float, r0: float, *, key: str, segs: int = 10, rings: int = 9,
            broken: float = 0.0, lean=(0.0, 0.0)) -> core.Part:
    """One stalagmite: stacked wobbly rings narrowing to a rounded tip (or a broken stump at `broken`
    fraction of its height), leaning by lean (dx, dy at the top), with drip-ring bulges."""
    r = p.rng(key)
    ph = [r.uniform(0, 6.28) for _ in range(3)]
    rs = []
    top_t = 1.0 - broken if broken else 1.0
    for k in range(rings + 1):
        t = k / rings * top_t
        z = h * t
        rad = r0 * (1 - t) ** 0.6 * (1.0 + 0.1 * math.sin(t * 17 + ph[0])) + 0.012 * (1 - t) + 0.006
        if t < 0.12:
            rad *= 1.0 + (0.12 - t) * 3.0   # flared foot
        cx = base.x + lean[0] * t * t
        cy = base.y + lean[1] * t * t
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            w = 1.0 + 0.1 * math.sin(a * 2 + ph[1] + t * 5) + 0.06 * math.sin(a * 3 + ph[2])
            ring.append((cx + math.cos(a) * rad * w, cy + math.sin(a) * rad * w, base.z + z))
        rs.append(ring)
    if not broken:
        rs.append([(base.x + lean[0], base.y + lean[1], base.z + h + r0 * 0.12)])
    obj = G.loft(p._name("mite"), rs, cap_bottom=False, cap_top=bool(broken))
    return p.add(obj, C.LIME, edge_deg=45.0, wear=0.3, uv="box")


def mine_stalagmites(p: Prop) -> None:
    """Limestone stalagmite cluster (1.2 x 1.6 x 1.0) rising from a flowstone boss: a tall column, a few
    middling cones and stubby young ones, each with drip-ring bulges. Worn: two tips snapped off (one lies on
    the boss), mud splashed up their feet."""
    worn = p.worn
    noise.seed_set(p.seed % 99991)
    # flowstone boss: a low rounded mound
    nx, ny = 18, 16
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = -0.62 + 1.24 * i / nx
            y = -0.52 + 1.04 * j / ny
            u, v = x / 0.6, y / 0.5
            rr = u * u + v * v
            z = 0.16 * max(0.0, 1 - rr) ** 0.7 + 0.025 * noise.noise(Vector((x * 4, y * 4, 0.7))) - 0.02
            verts.append((x, y, max(-0.02, z) if rr < 1 else -0.02))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    _mesh(p, "boss", verts, faces, C.LIME, edge_deg=45.0)

    def boss_z(x, y):
        rr = (x / 0.6) ** 2 + (y / 0.5) ** 2
        return 0.16 * max(0.0, 1 - rr) ** 0.7 - 0.03

    spec = [(-0.08, 0.1, 1.58, 0.2), (0.3, -0.05, 1.05, 0.16), (-0.36, -0.12, 0.78, 0.14), (0.12, -0.3, 0.5, 0.11),
            (0.42, 0.25, 0.4, 0.1), (-0.3, 0.3, 0.32, 0.09), (0.05, 0.36, 0.22, 0.075)]
    for k, (x, y, h, r0) in enumerate(spec):
        r = p.rng(f"m{k}")
        broken = 0.0
        if worn and k in (1, 4):
            broken = r.uniform(0.25, 0.4)
        part = _stalag(p, Vector((x, y, boss_z(x, y))), h, r0, key=f"mm{k}", broken=broken,
                       lean=(r.uniform(-0.05, 0.05), r.uniform(-0.05, 0.05)))
        part.floor_wear = 0.8 if worn else 0.0
    if worn:
        tip = _stalag(p, Vector((0, 0, 0)), 0.38, 0.06, key="tip", segs=8, rings=5)
        G.xform(tip.obj, rot=(0, 84, 30), loc=(-0.15, -0.38, 0.06))
    p.collider((0, 0, 0.4), (1.1, 0.9, 0.8))
    p.collider((-0.08, 0.1, 1.0), (0.3, 0.3, 1.2))


# ================================================================================================
# 10. lamp string (ceiling)
# ================================================================================================

def _caged_bulb(p: Prop, x: float, z: float, broken: bool) -> None:
    """Pigtail socket, bulb and a wire guard cage hanging with its top at z."""
    p.cyl(0.022, 0.06, (x, 0, z - 0.03), C.RUBBER, segs=10)
    zb = z - 0.06
    if broken:
        p.lathe([(0.0, 0.0), (0.012, 0.0), (0.014, -0.012), (0.0, -0.016)], (x, 0, zb), C.BULB_DEAD, segs=8)
    else:
        p.lathe([(0.012, 0.0), (0.016, -0.01), (0.03, -0.035), (0.032, -0.06), (0.024, -0.08), (0.0, -0.086)], (x, 0, zb),
                C.BULB, segs=12, wear=0.0)
    # guard: a top ring, four bowed wires and a bottom ring
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        pts = [(x + math.cos(a) * 0.024, math.sin(a) * 0.024, zb + 0.005),
               (x + math.cos(a) * 0.045, math.sin(a) * 0.045, zb - 0.04),
               (x + math.cos(a) * 0.03, math.sin(a) * 0.03, zb - 0.095)]
        p.tube(pts, 0.0022, C.CAGE_WIRE, segs=4, cap=False)
    ring = [(x + math.cos(2 * math.pi * i / 10) * 0.046, math.sin(2 * math.pi * i / 10) * 0.046, zb - 0.045) for i in range(10)]
    p.tube(ring, 0.0022, C.CAGE_WIRE, segs=4, cap=False, closed=True)


def mine_lamp_string(p: Prop) -> None:
    """A 3 m string of caged bulbs (origin on the ceiling plane, everything hangs below): eye bolts with
    hooks every metre, the cable sagging between them, three pigtail drops with guarded bulbs (warm, dim,
    on the mine generator). Worn: the middle bulb broken, the cable sagging lower off a loose hook."""
    worn = p.worn
    hooks = [-1.5, -0.5, 0.5, 1.5]
    hz = -0.06
    for k, x in enumerate(hooks):
        drop = 0.07 if worn and k == 2 else 0.0
        p.cyl(0.012, 0.03, (x, 0, -0.015), C.STEEL, segs=6)
        p.tube([(x, 0, -0.03), (x, 0, hz - drop + 0.01), (x + 0.015, 0, hz - drop - 0.005), (x + 0.025, 0, hz - drop + 0.01)],
               0.004, C.STEEL, segs=4, cap=True)
    sag = 0.12 if worn else 0.07
    pts = []
    for k in range(len(hooks) - 1):
        a, b = hooks[k], hooks[k + 1]
        da = 0.07 if worn and k == 2 else 0.0
        db = 0.07 if worn and k + 1 == 2 else 0.0
        for i in range(9 if k == 0 else 8):
            t = (i if k == 0 else i + 1) / 8
            x = a + (b - a) * t
            z = hz - (da * (1 - t) + db * t) - sag * 4 * t * (1 - t)
            pts.append((x, 0.0, z))
    p.tube(pts, 0.006, C.RUBBER, segs=6, cap=True)
    for k, x in enumerate((-1.0, 0.0, 1.0)):
        da = 0.07 if worn and k == 2 else 0.0
        top = hz - sag - (0.035 if worn and k == 2 else 0.0)
        p.tube([(x, 0, top + 0.004), (x, 0, top - 0.12)], 0.005, C.RUBBER, segs=5, cap=True)
        _caged_bulb(p, x, top - 0.12, broken=worn and k == 1)
        del da
    p.collider((0, 0, -0.15), (3.0, 0.1, 0.3))


# ================================================================================================
# 11. powder box
# ================================================================================================

def mine_powder_box(p: Prop) -> None:
    """Wooden explosives box (0.8 x 0.5 x 0.5): stencilled HIGH EXPLOSIVES / DANGEROUS sides, DYNAMITE ends,
    THIS SIDE UP lid on brass-less iron strap hinges, corner battens and rope becket handles. Worn: the lid
    ajar on the paper-wrapped sticks inside."""
    worn = p.worn
    W, D, H = 0.8, 0.5, 0.44
    body = G.hollow_box(p._name("box"), (W, D, H), (0, 0, H / 2), 0.02, "+Z", 0.003, None)
    side, end, wood = atlas("box_side", 3), atlas("box_end", 3), atlas("wood", 2)

    def fr(poly):
        n = poly.normal
        c = poly.center
        outer = abs(c.x) > W / 2 - 0.003 or abs(c.y) > D / 2 - 0.003 or c.z < 0.003
        if not outer:
            return (*wood, 0, 2, False)
        if abs(n.y) > 0.9:
            return (*side, 0, 2, n.y > 0)
        if abs(n.x) > 0.9:
            return (*end, 1, 2, n.x < 0)
        return (*wood, 0, 1, False)

    core.set_face_uvs(body, fr)
    p.add(body, C.PRINT, uv="keep", wear=0.9).floor_wear = 0.4
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.box((0.05, 0.02, H - 0.02), (sx * (W / 2 - 0.03), sy * (D / 2 + 0.01), H / 2), C.LAG, bevel=0.004, grain="Z")
        # rope beckets on the ends
        p.tube([(sx * (W / 2 + 0.005), -0.08, 0.32), (sx * (W / 2 + 0.04), -0.06, 0.27), (sx * (W / 2 + 0.04), 0.06, 0.27),
                (sx * (W / 2 + 0.005), 0.08, 0.32)], 0.009, "item_rope", segs=6, fillet_r=0.02)
    if worn:
        for k in range(12):
            r = p.rng(f"stick{k}")
            i, j = divmod(k, 6)
            p.cyl(0.016, W - 0.12, (0, -0.17 + j * 0.068, H - 0.06 - i * 0.034 + r.uniform(-0.003, 0.003)), C.DYNAMITE,
                  axis="X", segs=8, wear=0.3)
    lid = []
    face = atlas("box_lid", 3)
    lo = G.box(p._name("lid"), (W + 0.02, D + 0.02, 0.035), (0, 0, 0), 0.004)

    def lf(poly):
        if poly.normal.z > 0.9:
            return (*face, 0, 1, False)
        return (*wood, 0, 2, False)

    core.set_face_uvs(lo, lf)
    G.xform(lo, loc=(0, 0, H + 0.0175))
    lid.append(p.add(lo, C.PRINT, uv="keep", wear=0.9))
    for x in (-0.25, 0.25):
        lid.append(p.box((0.04, 0.16, 0.006), (x, D / 2 - 0.07, H + 0.038), C.IRON, bevel=0.002, wear=1.3))
        p.box((0.04, 0.006, 0.08), (x, D / 2 + 0.013, H - 0.03), C.IRON, bevel=0.002, wear=1.3)
    lid.append(p.box((0.05, 0.006, 0.07), (0, -D / 2 - 0.013, H + 0.0), C.IRON, bevel=0.002, wear=1.3))  # hasp
    p.box((0.03, 0.02, 0.03), (0, -D / 2 - 0.02, H - 0.06), C.IRON, bevel=0.003)
    if worn:
        p.rotate(lid, rot=(-24, 0, 0), pivot=(0, D / 2 + 0.01, H + 0.035))
    p.collider((0, 0, 0.25), (0.86, 0.54, 0.5))


# ================================================================================================
# 12. tool rack
# ================================================================================================

def _pick(p: Prop, x: float, y: float, z_top: float, tilt: float) -> list:
    out = [rod(p, (0, 0, -0.85), (0, 0, 0.03), 0.017, C.HANDLE, segs=8, grain="Z")]
    pts = [(-0.3, 0, -0.07), (-0.15, 0, 0.0), (0.0, 0, 0.02), (0.15, 0, 0.0), (0.3, 0, -0.07)]
    out.append(p.tube(pts, 0.017, C.STEEL_DARK, segs=6, fillet_r=0.08, cap=True, wear=1.2))
    out.append(p.box((0.06, 0.05, 0.07), (0, 0, 0.0), C.STEEL_DARK, bevel=0.006))
    place(out, Matrix.Translation((x, y, z_top)) @ Matrix.Rotation(math.radians(tilt), 4, "Y"))
    return out


def _shovel(p: Prop, x: float, y: float, z0: float, lean: float) -> list:
    out = [rod(p, (0, 0, 0.32), (0, 0, 1.28), 0.017, C.HANDLE, segs=8, grain="Z")]
    out.append(p.tube([(-0.07, 0, 1.28), (-0.07, 0, 1.38), (0.07, 0, 1.38), (0.07, 0, 1.28)], 0.008, C.HANDLE, segs=5))
    out.append(p.box((0.14, 0.012, 0.012), (0, 0, 1.38), C.HANDLE, bevel=0.003))
    bl = p.rbox((0.25, 0.012, 0.3), (0, 0, 0.17), C.STEEL_DARK, radius=0.004, inner=(5, 1, 5), edge_deg=12.0, wear=1.4)
    for v in bl.obj.data.vertices:
        v.co.y += 0.25 * v.co.x ** 2 - 0.02 * max(0.0, 0.17 - v.co.z)
        if v.co.z < 0.1:
            v.co.x *= 0.6 + 0.4 * (v.co.z - 0.02) / 0.08 if v.co.z > 0.02 else 0.6
    bl.obj.data.update()
    out.append(bl)
    out.append(p.cyl(0.024, 0.12, (0, 0, 0.36), C.STEEL_DARK, segs=8, r_top=0.019))
    place(out, Matrix.Translation((x, y, z0)) @ Matrix.Rotation(math.radians(lean), 4, "X"))
    return out


def mine_tool_rack(p: Prop) -> None:
    """Tool rack against a wall (1.6 x 1.8 x 0.4): two posts, a pegged top rail and a back plank, a box trough
    on the floor. Three picks hang by their heads from the pegs, two round-point shovels stand blade-down in
    the trough, a bundle of hex drill steels with chisel bits leans in the right end. Worn: a pick gone, a
    shovel slid sideways, rust."""
    worn = p.worn
    yb = 0.14
    for x in (-0.76, 0.76):
        p.box((0.08, 0.08, 1.8), (x, yb, 0.9), C.TIMBER, bevel=0.008, grain="Z").floor_wear = 0.5
    p.box((1.62, 0.06, 0.12), (0, yb, 1.62), C.TIMBER, bevel=0.008, grain="X")
    p.box((1.52, 0.03, 0.2), (0, yb + 0.02, 0.9), C.LAG, bevel=0.005, grain="X")
    tr = G.hollow_box(p._name("trough"), (1.52, 0.32, 0.18), (0, 0.02, 0.09), 0.025, "+Z", 0.004, None)
    p.add(tr, C.LAG, grain="X").floor_wear = 0.7
    pegs = [-0.55, -0.25, 0.05]
    for x in pegs:
        p.cyl(0.014, 0.12, (x, yb - 0.08, 1.64), C.HANDLE, axis="Y", segs=6)
    for k, x in enumerate(pegs):
        if worn and k == 1:
            continue
        _pick(p, x, yb - 0.12, 1.6, p.rng(f"pk{k}").uniform(-4, 4))
    sh = [(0.32, -6.0), (0.47, -8.0)]
    for k, (x, lean) in enumerate(sh):
        if worn and k == 1:
            parts = _shovel(p, 0, 0, 0, 0)
            place(parts, Matrix.Translation((x + 0.1, -0.05, 0.05)) @ Matrix.Rotation(math.radians(-18), 4, "Y")
                  @ Matrix.Rotation(math.radians(-8), 4, "X"))
            continue
        _shovel(p, x, 0.0, 0.05, lean)
    for k in range(6):
        r = p.rng(f"ds{k}")
        L = r.uniform(0.9, 1.7)
        x = 0.62 + (k % 3) * 0.035
        y = -0.03 + (k // 3) * 0.05
        top = (x + r.uniform(-0.03, 0.03), yb - 0.06, min(1.75, L))
        steel = rod(p, (x, y, 0.04), top, 0.011, C.RAIL, segs=6, wear=1.2)
        del steel
        p.cyl(0.02, 0.04, (x, y, 0.06), C.RAIL, segs=6)
    p.collider((0, 0.04, 0.9), (1.6, 0.36, 1.8))
    centre(p)


# ================================================================================================
# 13. safety board (wall)
# ================================================================================================

def mine_safety_board(p: Prop) -> None:
    """Shift boss's board (1.4 x 1.2 x ~0.1, origin on the wall plane at the bottom centre, hang it ~0.9 m up):
    plywood on two battens in a timber frame, the typed SAFETY FIRST notice and the chalk shift tally on the
    left, the CHECK BOARD on the right with 30 numbered hooks and brass check tags (the missing ones are men
    still underground), a hard hat hung below it. Worn: more tags missing, the board stained and warped."""
    worn = p.worn
    W, H = 1.4, 1.2
    for x in (-0.45, 0.45):
        p.box((0.06, 0.02, H), (x, -0.01, H / 2), C.LAG, bevel=0.003, grain="Z")
    p.box((W, 0.016, H), (0, -0.028, H / 2), "road_plywood", bevel=0.002, grain="X", uv_scale=1.0)
    yf = -0.036
    for (cx, cz, w, h) in ((0, H - 0.02, W, 0.04), (0, 0.02, W, 0.04), (-W / 2 + 0.02, H / 2, 0.04, H), (W / 2 - 0.02, H / 2, 0.04, H)):
        p.box((w, 0.022, h), (cx, yf - 0.005, cz), C.TIMBER, bevel=0.004, grain="X" if w > h else "Z")
    plate(p, 0.6, 0.6, (-0.33, yf - 0.002, 0.82), atlas("notice"), t=0.002, wear=0.25)
    plate(p, 0.6, 0.3, (-0.33, yf - 0.006, 0.3), atlas("tally"), t=0.008, wear=0.5)
    TW, TH = 0.66, 0.33
    tx0, tz1 = -0.0 + 0.0, 1.07
    cx = tx0 + TW / 2 + 0.0
    plate(p, TW, TH, (cx, yf - 0.006, tz1 - TH / 2), atlas("tags"), t=0.008, wear=0.5)
    yt = yf - 0.01
    missing = {3, 11, 12, 26} | ({7, 18, 19, 22} if worn else set())
    for k in range(30):
        u, v = tag_hook(k)
        x = tx0 + u / 512.0 * TW
        z = tz1 - v / 256.0 * TH
        p.cyl(0.0035, 0.025, (x, yt - 0.0125, z), C.STEEL, axis="Y", segs=5, wear=1.0)
        if k in missing:
            continue
        r = p.rng(f"tag{k}")
        tag = p.cyl(0.017, 0.002, (0, 0, 0), C.BRASS, axis="Y", segs=10, wear=1.2)
        G.xform(tag.obj, rot=(0, r.uniform(-12, 12), 0), loc=(x, yt - 0.018, z - 0.019))
    # hard hat on a hook under the check board
    hx, hz = cx, 0.42
    p.cyl(0.006, 0.06, (hx, yf - 0.03, hz + 0.1), C.STEEL, axis="Y", segs=6)
    shell = p.lathe([(0.0, 0.0), (0.11, 0.0), (0.13, -0.004), (0.13, -0.012), (0.105, -0.008), (0.1, 0.05), (0.075, 0.1),
                     (0.035, 0.125), (0.0, 0.13)], (0, 0, 0), C.HARDHAT, segs=16, wear=0.8)
    G.xform(shell.obj, rot=(-80, 0, 8), loc=(hx, yf - 0.16, hz))
    p.box((0.06, 0.02, 0.04), (hx, yf - 0.03, hz + 0.08), C.RUBBER, bevel=0.004)
    if worn:
        for q in p.parts:
            for v in q.obj.data.vertices:
                v.co.y -= 0.008 * math.sin(v.co.x * 2.2) * (v.co.z / H)
            q.obj.data.update()
    p.collider((0, -0.05, H / 2), (W, 0.1, H))


# ================================================================================================
# registry
# ================================================================================================

BUILDERS = {
    "mine_timber_set": mine_timber_set,
    "mine_rail_straight": mine_rail_straight,
    "mine_ore_cart": mine_ore_cart,
    "mine_hoist": mine_hoist,
    "mine_headframe": mine_headframe,
    "mine_cage": mine_cage,
    "mine_rock_face": mine_rock_face,
    "mine_rock_face_b": mine_rock_face_b,
    "mine_rock_face_c": mine_rock_face_c,
    "mine_rock_pile": mine_rock_pile,
    "mine_stalagmites": mine_stalagmites,
    "mine_lamp_string": mine_lamp_string,
    "mine_powder_box": mine_powder_box,
    "mine_tool_rack": mine_tool_rack,
    "mine_safety_board": mine_safety_board,
}


def build(params: dict, outputs: list[str]) -> None:
    core.build_variants(params, outputs, BUILDERS[params.get("builder", params["prop"])])
