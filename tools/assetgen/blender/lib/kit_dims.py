"""POI building kit geometry contract (docs/POI_KIT.md), shared by every kit generator.

All values in metres, Blender space (Z up, front = -Y). Change together with the POI builder.
"""
from __future__ import annotations

GRID = 1.0
WALL_T = 0.16                 # wall thickness, centred on the cell edge (y = -0.08 .. +0.08)
HALF_T = WALL_T / 2
WALL_H = 2.8                  # slab top -> next slab bottom
STOREY_H = 3.0
SLAB_T = 0.2                  # floor slab (origin = top centre, extends down to -0.2)

# Layered construction used by damaged / breach walls (side A skin, stud cavity, side B skin).
SKIN_T = 0.022                # plaster (+ lath key) / siding + sheathing
CAVITY = HALF_T - SKIN_T      # 0.058: half depth of the stud cavity
STUD_W = 0.045
STUD_D = 0.050                # half depth of a stud (studs span y = -0.05 .. 0.05)
LATH_W = 0.035                # lath strip height
LATH_T = 0.008
LATH_PITCH = 0.046
PLATE_H = 0.04                # bottom plate; the double top plate is 0.08

# Openings: CLEAR (finished) opening between the jamb linings: width, height, sill height.
OPENINGS: dict[str, tuple[float, float, float]] = {
    "window_1m": (0.70, 1.10, 0.90),
    "window_2m": (1.60, 1.20, 0.85),
    "door_1m": (0.86, 2.10, 0.0),
    "door_2m": (1.70, 2.10, 0.0),
}
JAMB_T = 0.02                 # jamb lining boards (the rough opening is 2 cm larger per side / top)
CASING_W = 0.07               # casing trim width
CASING_T = 0.02               # casing projection from the wall face
SILL_T = 0.03                 # window stool / sill board thickness (rough opening bottom = sill - SILL_T)
SILL_PROUD = 0.035            # how far the stool projects past the casing faces
HEAD_H = 0.09                 # head casing height (plus a 2 cm drip cap above)

# Door leaves: hinged on the LEFT edge seen from -Y; origin = bottom of the hinge edge.
DOOR_W, DOOR_H, DOOR_T = 0.82, 2.05, 0.04
DOOR_GAP_SIDE = 0.02          # (clear 0.86 - leaf 0.82) / 2
DOOR_GAP_BOTTOM = 0.012
# Builder placement of a leaf in a 1 m door wall: origin at (-0.41, 0, 0.012), rotate about local Z.

# Stairs: 12 risers x 0.25 = 3.0 over 4.0 (treads 0.333). Origin bottom-front edge centre, ascends +Y.
STAIR_W = 1.0
STAIR_RISERS = 12
STAIR_RISE = 0.25
STAIR_RUN = 4.0 / 12
STAIR_NOSING = 0.025
STRINGER_T = 0.04             # closed stringers at x = +-(0.5 - 0.04 .. 0.5)
STRINGER_ABOVE = 0.06         # stringer top edge, vertically above the nosing line
STRINGER_DEPTH = 0.32         # vertical depth of the stringer board


def stair_nosing_z(y: float) -> float:
    """Height of the nosing line (front edge of each tread) at distance y along the flight."""
    return STAIR_RISE + STAIR_RISE / STAIR_RUN * y


def stringer_top_z(y: float) -> float:
    top = STAIR_RISERS * STAIR_RISE + STRINGER_ABOVE
    return min(top, stair_nosing_z(y) + STRINGER_ABOVE)


RAILING_H = 0.95              # landing railing height
HANDRAIL_ABOVE_NOSING = 0.90  # stair banister height (vertical, above the nosing line)

# Exterior.
FOUNDATION = (1.0, 0.2, 0.6)
PORCH_H = 0.6                 # porch deck top / ground-floor offset above grade
PORCH_POST = (0.12, 0.12, 2.8)
CHIMNEY = (0.8, 0.6, 4.5)


def sash_layout(kind: str) -> dict:
    """Window sash/pane layout of the glass pieces, relative to the CLEAR opening's bottom centre.

    Returns {"frames": [(x0, x1, z0, z1, y0, y1), ...] sash members (M_kit_trim),
             "lites": [(x0, x1, z0, z1, yc), ...] glass areas (pane edges hide 1 cm in the members),
             "locks": [(x, z, y), ...] sash lock positions}.
    window_1m: 2-over-2 double-hung. window_2m: twin units (mullion) each with a fixed lower lite and a
    transom lite, which reads both as a house picture window and as a diner / shop front.
    """
    frames: list[tuple] = []
    lites: list[tuple] = []
    locks: list[tuple] = []
    w, h, _ = OPENINGS[kind]
    if kind == "window_1m":
        x0, x1 = -w / 2, w / 2
        meet = h * 0.5
        # (z0, z1, y0, y1, bottom rail, top rail)
        sashes = [(meet - 0.018, h, -0.034, 0.0, 0.035, 0.05),     # upper sash, outer track
                  (0.0, meet + 0.018, 0.002, 0.036, 0.075, 0.035)]  # lower sash, inner track
        stile = 0.05
        for z0, z1, y0, y1, rb, rt in sashes:
            frames.append((x0, x0 + stile, z0, z1, y0, y1))
            frames.append((x1 - stile, x1, z0, z1, y0, y1))
            frames.append((x0 + stile, x1 - stile, z0, z0 + rb, y0, y1))
            frames.append((x0 + stile, x1 - stile, z1 - rt, z1, y0, y1))
            # vertical muntin (2 lites per sash)
            mw = 0.022
            frames.append((-mw / 2, mw / 2, z0 + rb, z1 - rt, y0 + 0.004, y1 - 0.004))
            yc = (y0 + y1) / 2
            lites.append((x0 + stile, -mw / 2, z0 + rb, z1 - rt, yc))
            lites.append((mw / 2, x1 - stile, z0 + rb, z1 - rt, yc))
        locks.append((0.0, meet + 0.018, 0.036))
    elif kind == "window_2m":
        mull = 0.09
        units = [(-w / 2, -mull / 2), (mull / 2, w / 2)]
        frames.append((-mull / 2, mull / 2, 0.0, h, -0.04, 0.04))
        stile = 0.055
        trans = h * 0.70
        for ux0, ux1 in units:
            y0, y1 = -0.02, 0.02
            frames.append((ux0, ux0 + stile, 0.0, h, y0, y1))
            frames.append((ux1 - stile, ux1, 0.0, h, y0, y1))
            frames.append((ux0 + stile, ux1 - stile, 0.0, 0.08, y0, y1))
            frames.append((ux0 + stile, ux1 - stile, h - 0.055, h, y0, y1))
            frames.append((ux0 + stile, ux1 - stile, trans - 0.025, trans + 0.025, y0, y1))
            lites.append((ux0 + stile, ux1 - stile, 0.08, trans - 0.025, 0.0))
            lites.append((ux0 + stile, ux1 - stile, trans + 0.025, h - 0.055, 0.0))
    else:
        raise ValueError(kind)
    return {"frames": frames, "lites": lites, "locks": locks}
