"""Character surfaces: Hollowed skin, player skin, 1990s clothing, boots, hair, teeth, milky eyes,
Bloom growth, gore, the wrist tether and its screen, and a blood/grime wear layer.

All tileable (except the eye and the screen, which are planar-mapped decals). Physical tile sizes
are set by `uv_scale` in game/data/materials/characters.json (meshes use metre UVs).
"""
from __future__ import annotations

import numpy as np

from .. import texlib as T
from ..registry import texture


def _c(h):
    return T.hex_rgb(h)[None, None, :]


def _branching(size, seed, trunks=6, steps=180, step=3.0, w0=2.4, wmin=0.45, branch_p=0.045, turn=0.22,
               taper=0.996, flow_amt=0.12):
    """Tileable branching line network (veins / mycelium): random walks steered by a smooth
    flow field, tapering, splitting into thinner branches. Returns 0..1 coverage."""
    r = T.rng(seed)
    canvas = np.zeros((size, size), np.float32)
    flow = T.spectral(size, 2.6, seed + 1) * 2 * np.pi * 1.5
    stack = []
    for _ in range(trunks):
        stack.append((r.uniform(0, size), r.uniform(0, size), r.uniform(0, 2 * np.pi), w0 * r.uniform(0.7, 1.2),
                      steps * step))
    stamps = 0
    while stack and stamps < 120000:
        x, y, a, w, length = stack.pop()
        travelled = 0.0
        while travelled < length:
            st = max(0.35, min(step, 0.55 * w))       # continuous lines: stamp spacing < width
            fa = flow[int(y) % size, int(x) % size]
            da = (fa - a + np.pi) % (2 * np.pi) - np.pi
            a += (flow_amt * da + r.normal(0, turn)) * (st / step)
            x += np.cos(a) * st
            y += np.sin(a) * st
            travelled += st
            rad = int(np.ceil(w * 2.5)) + 1
            ix, iy = int(np.floor(x)), int(np.floor(y))
            xs = np.arange(ix - rad, ix + rad + 1)
            ys = np.arange(iy - rad, iy + rad + 1)
            dx = (xs + 0.5 - x)[None, :]
            dy = (ys + 0.5 - y)[:, None]
            g = np.exp(-(dx * dx + dy * dy) / max(w * w, 0.05))
            sub = np.ix_(ys % size, xs % size)
            canvas[sub] = np.maximum(canvas[sub], g)
            stamps += 1
            w *= taper ** (st / step)
            if w < wmin:
                break
            if r.random() < branch_p * (st / step):
                stack.append((x, y, a + r.choice([-1, 1]) * r.uniform(0.35, 1.0), w * r.uniform(0.5, 0.75),
                              (length - travelled) * 0.6))
    return np.clip(canvas, 0, 1)


def _veins(size, seed, scale_cells=60, width=1.2, warp=18.0):
    """Branching, meandering vein network (ridged band-limited noise, domain-warped).
    `scale_cells` ~ number of vein loops across the tile, `width` ~ line width in texels."""
    fmin = max(1.0, scale_cells / 8.0)
    n = T.spectral(size, 1.9, seed, fmin=fmin, fmax=scale_cells * 1.5)
    wx = T.spectral(size, 2.2, seed + 1)
    wy = T.spectral(size, 2.2, seed + 2)
    n = T.warp(n, wx, wy, warp)
    # distance (in texels) to the 0.5 iso-line approximated by |n-0.5| / |grad n|
    gy, gx = np.gradient(n)
    g = np.sqrt(gx * gx + gy * gy) + 1e-6
    dist = np.abs(n - 0.5) / g
    return np.clip(1.0 - dist / width, 0.0, 1.0) ** 1.5


def _level_lines(n, width_px):
    """1 on the median level set of n, falling to 0 at width_px pixels (uniform-width lines)."""
    m = float(np.median(n))
    gx = (np.roll(n, -1, 1) - np.roll(n, 1, 1)) * 0.5
    gy = (np.roll(n, -1, 0) - np.roll(n, 1, 0)) * 0.5
    d = np.abs(n - m) / (np.sqrt(gx * gx + gy * gy) + 1e-6)
    return np.clip(1.0 - d / width_px, 0.0, 1.0).astype(np.float32)


def _skin_micro(size, seed, *, cells=2600, pores=5200):
    """Skin micro-relief: the fine polygonal crease net (dermatoglyphs), patches of roughly
    parallel wrinkle lines, and pores. Returns (crease, wrinkle, pore) masks, 1 = in the feature."""
    f1, f2, _ = T.worley(size, cells, seed, jitter=0.85)
    fine = 1.0 - T.smoothstep(0.0, 1.6, f2 - f1)
    wx = T.spectral(size, 2.0, seed + 1)
    wy = T.spectral(size, 2.0, seed + 2)
    n = T.warp(T.spectral(size, 1.6, seed + 3, anisotropy=(1.0, 5.0), fmin=6.0), wx, wy, size * 0.01)
    wrinkle = _level_lines(n, 1.4) * T.smoothstep(0.45, 0.7, T.spectral(size, 2.0, seed + 5))
    p1, _, _ = T.worley(size, pores, seed + 4, jitter=0.95)
    pore = 1.0 - T.smoothstep(0.7, 1.7, p1)
    return fine.astype(np.float32), wrinkle.astype(np.float32), pore.astype(np.float32)


@texture("skin_hollow", size=1024, seed=301)
def skin_hollow(size: int, seed: int, out) -> None:
    """Pale grey-green mottled dead skin: veins, bruising, sallow blotches, pores."""
    broad = T.spectral(size, 2.4, seed)
    mid = T.spectral(size, 1.6, seed + 1)
    fine = T.spectral(size, 0.8, seed + 2)
    mottle = T.normalize(0.55 * broad + 0.45 * mid)
    col = T.gradient(mottle, [(0.0, "#7d8676"), (0.35, "#959d88"), (0.65, "#a9ad97"), (1.0, "#b8b39c")])
    # sallow / necrotic blotches and bruising
    blot = T.smoothstep(0.62, 0.85, T.spectral(size, 2.2, seed + 3, fmin=3.0))
    col = T.mix(col, _c("#8a7c5f") * np.ones_like(col), blot * 0.35)
    bruise = T.smoothstep(0.70, 0.90, T.spectral(size, 2.3, seed + 4, fmin=4.0))
    col = T.mix(col, _c("#655462") * np.ones_like(col), bruise * 0.40)
    # Bloom veins: dark green-grey networks, stronger in patches
    veins_big = _branching(size, seed + 5, trunks=4, steps=200, step=3.0, w0=3.0, wmin=0.6, branch_p=0.07, turn=0.16,
                           taper=0.993, flow_amt=0.04)
    veins_small = _branching(size, seed + 6, trunks=12, steps=80, step=2.5, w0=1.5, wmin=0.45, branch_p=0.08, turn=0.28,
                             taper=0.99, flow_amt=0.02)
    patch = T.smoothstep(0.30, 0.70, T.spectral(size, 2.0, seed + 7))
    vein = np.clip(veins_big * (0.45 + 0.55 * patch) + veins_small * 0.7 * patch, 0, 1)
    col = T.mix(col, _c("#3a4a40") * np.ones_like(col), vein * 0.8)
    # faint darker halo around the veins (blood pooling under the skin)
    halo = T.blur(vein, 4.0)
    col = T.mix(col, _c("#6f786a") * np.ones_like(col), np.clip(halo * 1.5, 0, 1) * 0.35)
    # pores / speckle, and the dried-out crease net of dead skin
    pores = T.smoothstep(0.80, 0.95, T.spectral(size, 0.3, seed + 8))
    crease, wrinkle, pore = _skin_micro(size, seed + 20, cells=2200, pores=4200)
    col *= (1.0 - 0.10 * pores)[..., None]
    col *= (0.92 + 0.12 * fine)[..., None]
    col *= (1.0 - 0.04 * crease - 0.10 * wrinkle - 0.08 * pore)[..., None]
    height = T.normalize(0.35 * mid + 0.25 * fine - 0.25 * pores + 0.35 * vein * patch
                         - 0.05 * crease - 0.09 * wrinkle - 0.05 * pore)
    rough = np.clip(0.62 + 0.12 * (1 - mottle) - 0.10 * vein + 0.06 * fine + 0.05 * wrinkle, 0.35, 0.9)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.5)


@texture("skin_human", size=1024, seed=311)
def skin_human(size: int, seed: int, out) -> None:
    """The convict's arms: weathered warm skin, freckles, grime, fine hairs."""
    broad = T.spectral(size, 2.5, seed)
    mid = T.spectral(size, 1.5, seed + 1)
    fine = T.spectral(size, 0.7, seed + 2)
    col = T.gradient(T.normalize(0.6 * broad + 0.4 * mid), [(0.0, "#a8765c"), (0.5, "#bf8c6e"), (1.0, "#cf9f80")])
    freck = T.smoothstep(0.84, 0.95, T.spectral(size, 0.45, seed + 3)) * T.smoothstep(0.4, 0.7, broad)
    col = T.mix(col, _c("#8a5a40") * np.ones_like(col), freck * 0.6)
    grime = T.smoothstep(0.55, 0.9, T.spectral(size, 1.8, seed + 4))
    col = T.mix(col, _c("#5e4a3a") * np.ones_like(col), grime * 0.35)
    hairs = T.smoothstep(0.86, 0.97, T.spectral(size, 0.5, seed + 5, anisotropy=(7.0, 1.0)))
    col = T.mix(col, _c("#3a2a20") * np.ones_like(col), hairs * 0.35)
    col *= (0.94 + 0.08 * fine)[..., None]
    # skin micro-relief: the fine crease net, deeper creases, pores (a slight redness in creases)
    crease, wrinkle, pore = _skin_micro(size, seed + 20)
    col = T.mix(col, col * np.array([0.93, 0.86, 0.84], np.float32), np.clip(0.4 * crease + wrinkle, 0, 1) * 0.35)
    col *= (1.0 - 0.06 * pore)[..., None]
    height = T.normalize(0.4 * mid + 0.4 * fine - 0.2 * freck - 0.04 * crease - 0.07 * wrinkle - 0.04 * pore)
    rough = np.clip(0.55 + 0.15 * grime + 0.05 * fine + 0.04 * wrinkle, 0.3, 0.9)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.6)


def _weave(size, count, seed, twill=False):
    """Fabric weave height: `count` threads per tile in each direction."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    if twill:
        d = (x + y) * count
        h = 0.5 + 0.5 * np.cos(d * 2 * np.pi)
        cross = 0.5 + 0.5 * np.cos(x * count * 2 * np.pi)
        return T.normalize(0.75 * h + 0.25 * cross)
    a = 0.5 + 0.5 * np.cos(x * count * 2 * np.pi)
    b = 0.5 + 0.5 * np.cos(y * count * 2 * np.pi)
    checker = (np.floor(x * count) + np.floor(y * count)) % 2
    return T.normalize(np.where(checker > 0, a, b) * 0.7 + 0.3 * (a * b))


def _wear_stains(size, seed, col, amount=0.5):
    stain = T.smoothstep(0.62, 0.85, T.spectral(size, 2.2, seed)) * amount
    col = T.mix(col, _c("#4a4034") * np.ones_like(col), stain * 0.5)
    fade = T.spectral(size, 2.6, seed + 1)
    col = col * (0.88 + 0.22 * fade)[..., None]
    return col, stain


@texture("cloth_denim", size=1024, seed=321)
def cloth_denim(size: int, seed: int, out) -> None:
    weave = _weave(size, 180, seed, twill=True)
    slub = T.spectral(size, 1.2, seed + 1, anisotropy=(10.0, 1.0))
    fade = T.smoothstep(0.35, 0.9, T.spectral(size, 2.2, seed + 2))
    base = T.gradient(T.normalize(0.7 * slub + 0.3 * weave), [(0.0, "#22364f"), (0.6, "#2f4a68"), (1.0, "#46607e")])
    worn = _c("#8296aa") * np.ones_like(base)
    col = T.mix(base, worn, fade * 0.45 * (0.6 + 0.4 * weave))
    white = T.smoothstep(0.7, 1.0, weave) * 0.15
    col = col + white[..., None] * 0.25
    col, stain = _wear_stains(size, seed + 3, col, 0.6)
    height = T.normalize(0.6 * weave + 0.4 * slub)
    rough = np.clip(0.82 + 0.08 * stain - 0.05 * fade, 0.5, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=4.0)


def _tartan(size, setts, palette):
    """Periodic tartan: setts = [(colour_index, width), ...] mirrored, repeated across the tile."""
    stripes = []
    for ci, w in setts + setts[::-1]:
        stripes += [ci] * w
    seq = np.array(stripes)
    n = len(seq)
    reps = 2
    idx = (np.arange(size) * n * reps // size) % n
    warp_c = seq[idx]
    pal = np.stack([T.hex_rgb(h) for h in palette])
    cx = pal[warp_c][None, :, :]
    cy = pal[warp_c][:, None, :]
    y, x = np.mgrid[0:size, 0:size]
    twill = ((x + y) // 2) % 2
    col = np.where(twill[..., None] > 0, cx, cy)
    # where both threads share a colour it is solid; mixed areas blend visually
    col = 0.65 * col + 0.35 * (cx + cy) / 2
    return col.astype(np.float32)


@texture("cloth_flannel", size=1024, seed=331)
def cloth_flannel(size: int, seed: int, out) -> None:
    """Faded 1990s red/black plaid flannel with a thin pale stripe, fuzzy nap, stains."""
    pal = ["#7a1c18", "#1a1717", "#b9a98a", "#2b3a2c"]
    setts = [(0, 22), (1, 4), (0, 3), (1, 18), (2, 1), (1, 18), (0, 3), (1, 4), (3, 6)]
    col = _tartan(size, setts, pal)
    nap = T.spectral(size, 0.9, seed)
    fuzz = T.spectral(size, 0.4, seed + 1)
    col = col * (0.85 + 0.25 * nap)[..., None]
    col = T.mix(col, col * 0.6 + 0.4 * _c("#8a7a6a"), T.smoothstep(0.4, 0.95, T.spectral(size, 2.4, seed + 2)) * 0.45)
    col, stain = _wear_stains(size, seed + 3, col, 0.7)
    weave = _weave(size, 140, seed + 4)
    height = T.normalize(0.5 * weave + 0.3 * nap + 0.2 * fuzz)
    rough = np.clip(0.9 + 0.05 * fuzz - 0.05 * stain, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.5)


@texture("cloth_tshirt", size=1024, seed=341)
def cloth_tshirt(size: int, seed: int, out) -> None:
    """Washed-out grey-beige cotton jersey, sweat yellowing, grime."""
    knit = _weave(size, 220, seed)
    slub = T.spectral(size, 1.0, seed + 1, anisotropy=(8.0, 1.0))
    col = T.gradient(T.normalize(0.6 * T.spectral(size, 2.2, seed + 2) + 0.4 * slub),
                     [(0.0, "#7f7a70"), (0.5, "#959084"), (1.0, "#a8a294")])
    yel = T.smoothstep(0.55, 0.9, T.spectral(size, 2.5, seed + 3))
    col = T.mix(col, _c("#a39060") * np.ones_like(col), yel * 0.35)
    col, stain = _wear_stains(size, seed + 4, col, 0.8)
    height = T.normalize(0.6 * knit + 0.4 * slub)
    rough = np.clip(0.88 + 0.06 * stain, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.0)


@texture("cloth_jacket", size=1024, seed=351)
def cloth_jacket(size: int, seed: int, out) -> None:
    """Brown duck-canvas work jacket: coarse weave, worn pale patches, oil/grime."""
    weave = _weave(size, 110, seed)
    slub = T.spectral(size, 1.1, seed + 1, anisotropy=(6.0, 1.0))
    col = T.gradient(T.normalize(0.65 * T.spectral(size, 2.3, seed + 2) + 0.35 * slub),
                     [(0.0, "#4a3622"), (0.5, "#6b4f32"), (1.0, "#86684a")])
    worn = T.smoothstep(0.55, 0.92, T.spectral(size, 2.0, seed + 3))
    col = T.mix(col, _c("#a08a6c") * np.ones_like(col), worn * 0.4 * (0.5 + 0.5 * weave))
    col, stain = _wear_stains(size, seed + 4, col, 0.7)
    oil = T.smoothstep(0.75, 0.95, T.spectral(size, 2.4, seed + 5))
    col = T.mix(col, _c("#231a12") * np.ones_like(col), oil * 0.5)
    height = T.normalize(0.65 * weave + 0.35 * slub)
    rough = np.clip(0.85 - 0.25 * oil + 0.05 * stain, 0.4, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=4.0)


@texture("cloth_hospital", size=1024, seed=361)
def cloth_hospital(size: int, seed: int, out) -> None:
    """Pale teal hospital gown with a small diamond print, stained."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    n = 16
    u = (x * n) % 1.0 - 0.5
    v = (y * n + 0.5 * (np.floor(x * n) % 2)) % 1.0 - 0.5
    diamond = 1.0 - T.smoothstep(0.10, 0.16, np.abs(u) + np.abs(v))
    col = T.gradient(T.spectral(size, 2.2, seed), [(0.0, "#8aa6a2"), (0.5, "#9db8b3"), (1.0, "#b0c7c1")])
    col = T.mix(col, _c("#4f6f7a") * np.ones_like(col), diamond * 0.7)
    col, stain = _wear_stains(size, seed + 1, col, 0.9)
    yel = T.smoothstep(0.6, 0.9, T.spectral(size, 2.6, seed + 2))
    col = T.mix(col, _c("#a8955a") * np.ones_like(col), yel * 0.3)
    weave = _weave(size, 200, seed + 3)
    height = T.normalize(0.7 * weave + 0.3 * T.spectral(size, 1.2, seed + 4))
    rough = np.clip(0.9 - 0.1 * stain, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.5)


@texture("cloth_jumpsuit", size=1024, seed=371)
def cloth_jumpsuit(size: int, seed: int, out) -> None:
    """Remand Program jumpsuit: sun-faded orange twill going grey with wear and grime."""
    weave = _weave(size, 160, seed, twill=True)
    slub = T.spectral(size, 1.0, seed + 1, anisotropy=(8.0, 1.0))
    col = T.gradient(T.normalize(0.6 * T.spectral(size, 2.3, seed + 2) + 0.4 * slub),
                     [(0.0, "#8f4a24"), (0.5, "#b05e2e"), (1.0, "#c27040")])
    grey = T.smoothstep(0.45, 0.9, T.spectral(size, 2.1, seed + 3))
    col = T.mix(col, _c("#8a7d72") * np.ones_like(col), grey * 0.45)
    col, stain = _wear_stains(size, seed + 4, col, 0.6)
    height = T.normalize(0.65 * weave + 0.35 * slub)
    rough = np.clip(0.86 + 0.06 * stain, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)


@texture("leather_boot", size=1024, seed=381)
def leather_boot(size: int, seed: int, out) -> None:
    """Dark brown work-boot leather: pebbled grain, creases, scuffs, dried mud."""
    f1, f2, _ = T.worley(size, 2600, seed, jitter=1.0)
    grain = T.normalize(f1)
    crease = _veins(size, seed + 1, 18, 1.0, 30.0)
    col = T.gradient(T.normalize(0.6 * T.spectral(size, 2.2, seed + 2) + 0.4 * grain),
                     [(0.0, "#24180f"), (0.5, "#3a2819"), (1.0, "#523a26")])
    scuff = T.smoothstep(0.65, 0.92, T.spectral(size, 1.6, seed + 3))
    col = T.mix(col, _c("#7a6248") * np.ones_like(col), scuff * 0.5)
    mud = T.smoothstep(0.62, 0.9, T.spectral(size, 2.4, seed + 4))
    col = T.mix(col, _c("#4e4436") * np.ones_like(col), mud * 0.55)
    col *= (1.0 - 0.35 * crease)[..., None]
    height = T.normalize(0.5 * grain - 0.4 * crease + 0.1 * scuff)
    rough = np.clip(0.55 + 0.25 * scuff + 0.2 * mud, 0.3, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)


@texture("hair", size=1024, seed=391)
def hair(size: int, seed: int, out) -> None:
    """Greasy dark hair clumps: strands run along V."""
    strands = T.spectral(size, 0.9, seed, anisotropy=(40.0, 1.0))
    clumps = T.spectral(size, 1.6, seed + 1, anisotropy=(6.0, 1.0))
    s = T.normalize(0.65 * strands + 0.35 * clumps)
    col = T.gradient(s, [(0.0, "#120e0b"), (0.5, "#2a221c"), (0.85, "#43382e"), (1.0, "#6a5c4e")])
    grey = T.smoothstep(0.88, 0.98, T.spectral(size, 0.6, seed + 2, anisotropy=(30.0, 1.0)))
    col = T.mix(col, _c("#8c8780") * np.ones_like(col), grey * 0.5)
    height = s
    rough = np.clip(0.45 + 0.3 * (1 - s), 0.3, 0.9)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)


@texture("teeth", size=512, seed=401)
def teeth(size: int, seed: int, out) -> None:
    """Yellowed, stained enamel / bone."""
    b = T.spectral(size, 2.0, seed)
    col = T.gradient(b, [(0.0, "#a8946a"), (0.5, "#c9b98e"), (1.0, "#ddd2b0")])
    stain = T.smoothstep(0.6, 0.9, T.spectral(size, 1.8, seed + 1))
    col = T.mix(col, _c("#5a4632") * np.ones_like(col), stain * 0.6)
    cracks = _veins(size, seed + 2, 30, 0.7, 6.0)
    col *= (1 - 0.4 * cracks)[..., None]
    height = T.normalize(b - 0.5 * cracks)
    rough = np.clip(0.35 + 0.35 * stain, 0.2, 0.9)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.5)


@texture("eyes_hollow", size=512, seed=411)
def eyes_hollow(size: int, seed: int, out) -> None:
    """Milky dead eye (planar decal, centre = cornea): bloodshot sclera, washed-out iris,
    cataract film over the pupil."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / (size / 2)
    ang = np.arctan2(y - c, x - c)
    sclera = T.gradient(T.spectral(size, 2.0, seed), [(0.0, "#b9b3a2"), (1.0, "#d3cfc2")])
    vessels = _veins(size, seed + 1, 40, 1.0, 12.0) * T.smoothstep(0.45, 0.95, r)
    sclera = T.mix(sclera, _c("#8a3a30") * np.ones_like(sclera), vessels * 0.6)
    iris_r = 0.42
    fib = 0.5 + 0.5 * np.sin(ang * 60 + T.spectral(size, 1.0, seed + 2) * 6)
    iris = T.mix(_c("#6f7d84") * np.ones_like(sclera), _c("#9aa5a6") * np.ones_like(sclera), fib[..., None] * 0.6)
    iris_m = 1 - T.smoothstep(iris_r - 0.03, iris_r + 0.01, r)
    col = T.mix(sclera, iris, iris_m)
    pupil_m = 1 - T.smoothstep(0.12, 0.16, r)
    col = T.mix(col, _c("#3a3a3a") * np.ones_like(col), pupil_m * 0.8)
    # milky cataract film
    film = (1 - T.smoothstep(0.05, iris_r + 0.05, r)) * (0.6 + 0.4 * T.spectral(size, 1.5, seed + 3))
    col = T.mix(col, _c("#d9dbd2") * np.ones_like(col), film * 0.75)
    limbus = np.exp(-((r - iris_r) / 0.02) ** 2)
    col *= (1 - 0.35 * limbus)[..., None]
    height = np.clip(1 - r, 0, 1) * 0.3
    rough = np.clip(0.12 + 0.2 * vessels, 0.05, 0.6).astype(np.float32)
    T.save_pbr_set(out, np.clip(col, 0, 1), height.astype(np.float32), rough, normal_strength=1.0)


@texture("bloom_growth", size=1024, seed=421)
def bloom_growth(size: int, seed: int, out) -> None:
    """Pale fungal growth: matted mycelium threads over a waxy, lumpy cream body; dark pits."""
    base = T.spectral(size, 1.9, seed)
    lumps = T.spectral(size, 1.4, seed + 1)
    threads = np.maximum.reduce([
        _branching(size, seed + 10, trunks=40, steps=140, step=2.0, w0=1.4, wmin=0.5, branch_p=0.03, turn=0.12,
                   taper=0.998, flow_amt=0.2),
        _branching(size, seed + 11, trunks=30, steps=90, step=1.6, w0=0.9, wmin=0.4, branch_p=0.05, turn=0.25,
                   taper=0.997, flow_amt=0.05) * 0.8,
    ])
    pores = T.smoothstep(0.80, 0.95, T.spectral(size, 0.6, seed + 5))
    shade = T.normalize(0.55 * base + 0.45 * lumps)
    col = T.gradient(shade, [(0.0, "#8f8a72"), (0.45, "#bdb79d"), (1.0, "#d9d3bb")])
    col = T.mix(col, _c("#f3efe2") * np.ones_like(col), threads * 0.75)
    tinge = T.smoothstep(0.55, 0.85, T.spectral(size, 2.4, seed + 4))
    col = T.mix(col, _c("#aeb784") * np.ones_like(col), tinge * 0.30)
    col = T.mix(col, _c("#5e5440") * np.ones_like(col), pores * 0.6)
    height = T.normalize(0.35 * base + 0.25 * lumps + 0.5 * threads - 0.3 * pores)
    rough = np.clip(0.60 - 0.22 * threads + 0.15 * pores, 0.25, 0.9)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=4.0)


@texture("gore", size=1024, seed=431)
def gore(size: int, seed: int, out) -> None:
    """Wet torn flesh: dark muscle with fibre streaks, clots, fat and pale membrane."""
    fib = T.spectral(size, 0.8, seed, anisotropy=(1.0, 12.0))
    fib = T.warp(fib, T.spectral(size, 2.0, seed + 1), T.spectral(size, 2.0, seed + 2), 40.0)
    lumps = T.spectral(size, 1.7, seed + 3)
    col = T.gradient(T.normalize(0.55 * fib + 0.45 * lumps),
                     [(0.0, "#2a0605"), (0.4, "#4f0c0a"), (0.75, "#7a1a16"), (1.0, "#a3423a")])
    fat_m = T.smoothstep(0.74, 0.86, T.spectral(size, 1.4, seed + 4))
    col = T.mix(col, _c("#b8955c") * np.ones_like(col), fat_m * 0.7)
    memb = T.smoothstep(0.82, 0.95, T.spectral(size, 1.2, seed + 5))
    col = T.mix(col, _c("#c9b3a6") * np.ones_like(col), memb * 0.5)
    clot = T.smoothstep(0.7, 0.9, T.spectral(size, 2.2, seed + 6))
    col = T.mix(col, _c("#170303") * np.ones_like(col), clot * 0.7)
    height = T.normalize(0.4 * fib + 0.4 * lumps + 0.2 * fat_m)
    rough = np.clip(0.18 + 0.2 * clot + 0.15 * fat_m, 0.08, 0.6)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=4.0)


@texture("tether", size=512, seed=441)
def tether(size: int, seed: int, out) -> None:
    """Rugged dark polymer housing with scuffs, grime and worn bare-metal edges."""
    b = T.spectral(size, 2.0, seed)
    grit = T.spectral(size, 0.5, seed + 1)
    col = T.gradient(T.normalize(0.7 * b + 0.3 * grit), [(0.0, "#22262a"), (0.6, "#30353a"), (1.0, "#40464a")])
    scuff = T.smoothstep(0.7, 0.95, T.spectral(size, 1.0, seed + 2, anisotropy=(1.0, 5.0)))
    col = T.mix(col, _c("#7b7f80") * np.ones_like(col), scuff * 0.55)
    grime = T.smoothstep(0.6, 0.9, T.spectral(size, 2.2, seed + 3))
    col = T.mix(col, _c("#3a3226") * np.ones_like(col), grime * 0.4)
    height = T.normalize(0.5 * b + 0.3 * grit - 0.3 * scuff)
    rough = np.clip(0.55 + 0.2 * grime - 0.25 * scuff, 0.2, 0.9)
    metal = scuff * 0.8
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, metal=metal, normal_strength=2.0)


@texture("tether_screen", size=512, seed=451)
def tether_screen(size: int, seed: int, out) -> None:
    """Dim green monochrome display (planar decal): vitals trace, status rows, scanlines."""
    r = T.rng(seed)
    img = np.zeros((size, size), np.float32)
    y, x = np.mgrid[0:size, 0:size]
    # status text rows (blocky glyphs)
    cell = size // 32
    for row in range(3, 12):
        if row % 3 == 2:
            continue
        ncols = int(r.integers(8, 26))
        for col in range(2, 2 + ncols):
            if r.random() < 0.18:
                continue
            gx, gy = col * cell, row * cell * 2
            glyph = r.random((5, 3)) > 0.45
            for gy_i in range(5):
                for gx_i in range(3):
                    if glyph[gy_i, gx_i]:
                        y0 = gy + gy_i * (cell // 3)
                        x0 = gx + gx_i * (cell // 4)
                        img[y0:y0 + cell // 3, x0:x0 + cell // 4] = 1.0
    # heart-rate trace in the lower half
    xs = np.arange(size)
    base_y = int(size * 0.78)
    trace = np.zeros(size)
    for k in range(0, size, size // 4):
        trace[k:k + 6] = np.linspace(0, -60, 6)
        trace[k + 6:k + 14] = np.linspace(-60, 40, 8)
        trace[k + 14:k + 20] = np.linspace(40, 0, 6)
    for xi in xs:
        yi = int(base_y + trace[xi] * size / 1024)
        img[max(0, yi - 2):yi + 2, xi] = 1.0
    glow = T.blur(img, 2.0)
    scan = 0.85 + 0.15 * (y % 4 < 2)
    level = np.clip(0.12 + 0.9 * img + 0.5 * glow, 0, 1) * scan
    col = np.stack([level * 0.25, level * 0.95, level * 0.35], -1)
    col = col * 0.8 + _c("#04110a") * 0.2
    height = np.zeros((size, size), np.float32)
    rough = np.full((size, size), 0.15, np.float32)
    T.save_pbr_set(out, np.clip(col, 0, 1).astype(np.float32), height, rough, normal_strength=0.0)


@texture("blood_grime", size=1024, seed=461)
def blood_grime(size: int, seed: int, out) -> None:
    """Wear layer for skin/cloth: dried blood soaked into grime (revealed by vertex G)."""
    b = T.spectral(size, 1.8, seed)
    splat = T.smoothstep(0.45, 0.8, T.spectral(size, 1.3, seed + 1))
    col = T.gradient(T.normalize(0.6 * b + 0.4 * splat), [(0.0, "#1e0b08"), (0.5, "#3b120d"), (1.0, "#5c1c14")])
    dirt = T.smoothstep(0.5, 0.9, T.spectral(size, 2.3, seed + 2))
    col = T.mix(col, _c("#3a3024") * np.ones_like(col), dirt * 0.5)
    height = T.normalize(0.5 * b + 0.5 * splat)
    rough = np.clip(0.45 + 0.35 * dirt - 0.15 * splat, 0.2, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.5)


# --------------------------------------------------------------------------------------------
# The valley's wardrobe and the specials' armour (ADR-0028). Neutral sets are tinted per material
# (game/data/materials/characters.json `tint`), so one weave serves several garments.
# --------------------------------------------------------------------------------------------

def _knit_rib(size, ribs, seed):
    """Vertical knit ribs with the V-stitch texture along them."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    u = (x * ribs) % 1.0
    rib = 0.5 + 0.5 * np.cos(u * 2 * np.pi)
    v = (y * ribs * 2.2 + np.where(u < 0.5, 0.0, 0.5)) % 1.0
    vst = 1.0 - np.abs(v - 0.5) * 2.0
    return T.normalize(0.6 * rib + 0.4 * vst * rib)


@texture("cloth_hivis", size=1024, seed=471)
def cloth_hivis(size: int, seed: int, out) -> None:
    """Hi-vis polyester mesh (neutral bright: tinted fluorescent per material): a fine hexagonal
    knit with open holes, faded at the stress points, grimy."""
    f1, f2, _ = T.worley(size, 73 * 73, seed, jitter=0.35)    # a full grid: a partial last row seamed
    holes = 1.0 - T.smoothstep(0.0, 2.2, f2 - f1)
    cell = T.smoothstep(0.5, 3.5, f1)
    base = 0.86 + 0.08 * T.spectral(size, 2.0, seed + 1)
    col = np.stack([base, base, base], -1)
    col = col * (1.0 - 0.45 * holes)[..., None]
    fade = T.smoothstep(0.55, 0.9, T.spectral(size, 2.2, seed + 2))
    col = T.mix(col, _c("#d8d2bc") * np.ones_like(col), fade * 0.35)
    col, stain = _wear_stains(size, seed + 3, col, 0.35)
    grime = T.smoothstep(0.72, 0.95, T.spectral(size, 1.6, seed + 4))
    col = T.mix(col, _c("#6a6456") * np.ones_like(col), grime * 0.3)
    height = T.normalize(0.7 * cell - 0.5 * holes + 0.2 * T.spectral(size, 1.2, seed + 5))
    rough = np.clip(0.62 + 0.15 * stain + 0.1 * holes, 0.4, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.5)


@texture("cloth_drill", size=1024, seed=481)
def cloth_drill(size: int, seed: int, out) -> None:
    """Workwear cotton drill (neutral, tinted navy / orange / khaki per material): steep twill,
    worn pale along the ridges, oil and grime."""
    weave = _weave(size, 150, seed, twill=True)
    slub = T.spectral(size, 1.1, seed + 1, anisotropy=(7.0, 1.0))
    col = T.gradient(T.normalize(0.65 * T.spectral(size, 2.3, seed + 2) + 0.35 * slub),
                     [(0.0, "#8e8e8a"), (0.5, "#a8a8a2"), (1.0, "#bdbcb4")])
    worn = T.smoothstep(0.55, 0.92, T.spectral(size, 2.0, seed + 3))
    col = T.mix(col, _c("#d6d3c8") * np.ones_like(col), worn * 0.35 * (0.5 + 0.5 * weave))
    col, stain = _wear_stains(size, seed + 4, col, 0.7)
    oil = T.smoothstep(0.76, 0.95, T.spectral(size, 2.4, seed + 5))
    col = T.mix(col, _c("#24201a") * np.ones_like(col), oil * 0.55)
    height = T.normalize(0.7 * weave + 0.3 * slub)
    rough = np.clip(0.84 - 0.25 * oil + 0.06 * stain, 0.4, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.5)


@texture("cloth_wool", size=1024, seed=491)
def cloth_wool(size: int, seed: int, out) -> None:
    """Sunday suiting wool (neutral, tinted charcoal / brown per material): a fine herringbone,
    a faint pinstripe, shine on the worn ridges, moth holes."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    band = np.floor(x * 24) % 2
    d = np.where(band > 0, x + y, x - y) * 220
    hb = 0.5 + 0.5 * np.cos(d * 2 * np.pi)
    pin = T.smoothstep(0.985, 1.0, 0.5 + 0.5 * np.cos(x * 16 * 2 * np.pi))
    fuzz = T.spectral(size, 0.6, seed)
    col = T.gradient(T.normalize(0.5 * T.spectral(size, 2.2, seed + 1) + 0.25 * hb + 0.25 * fuzz),
                     [(0.0, "#5e5e60"), (0.5, "#717174"), (1.0, "#858589")])
    col = T.mix(col, _c("#b4b4b8") * np.ones_like(col), pin * 0.5)
    col, stain = _wear_stains(size, seed + 2, col, 0.5)
    moth = T.smoothstep(0.9, 0.97, T.spectral(size, 0.8, seed + 3)) * T.smoothstep(0.6, 0.8, T.spectral(size, 2.0, seed + 4))
    col = T.mix(col, _c("#141414") * np.ones_like(col), moth)
    height = T.normalize(0.6 * hb + 0.4 * fuzz - 0.6 * moth)
    rough = np.clip(0.80 - 0.18 * T.smoothstep(0.6, 0.95, hb) * 0.5 + 0.08 * stain, 0.45, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.0)


@texture("cloth_shirt", size=1024, seed=501)
def cloth_shirt(size: int, seed: int, out) -> None:
    """White cotton poplin (dress shirts; tinted for scrubs): a very fine plain weave, sweat
    yellowing, grey grime and creases."""
    weave = _weave(size, 260, seed)
    col = T.gradient(T.normalize(0.7 * T.spectral(size, 2.3, seed + 1) + 0.3 * weave),
                     [(0.0, "#c7c6c0"), (0.5, "#d9d8d2"), (1.0, "#e6e5df")])
    yel = T.smoothstep(0.55, 0.9, T.spectral(size, 2.5, seed + 2))
    col = T.mix(col, _c("#c2b07a") * np.ones_like(col), yel * 0.35)
    col, stain = _wear_stains(size, seed + 3, col, 0.7)
    crease = _level_lines(T.warp(T.spectral(size, 1.8, seed + 4, anisotropy=(1.0, 4.0)), T.spectral(size, 2.0, seed + 5),
                                 T.spectral(size, 2.0, seed + 6), size * 0.02), 1.6)
    col *= (1.0 - 0.08 * crease)[..., None]
    height = T.normalize(0.5 * weave - 0.5 * crease)
    rough = np.clip(0.84 + 0.05 * stain, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.6)


@texture("cloth_knit", size=1024, seed=511)
def cloth_knit(size: int, seed: int, out) -> None:
    """Wool cardigan / sweater knit (neutral, tinted per material): ribs of V stitches, pilling,
    snags."""
    rib = _knit_rib(size, 90, seed)
    pill = T.smoothstep(0.8, 0.95, T.spectral(size, 0.4, seed + 1)) * T.smoothstep(0.5, 0.8, T.spectral(size, 2.2, seed + 2))
    col = T.gradient(T.normalize(0.6 * rib + 0.4 * T.spectral(size, 2.1, seed + 3)),
                     [(0.0, "#8a8478"), (0.5, "#a49e90"), (1.0, "#bab4a6")])
    col = T.mix(col, _c("#c8c2b4") * np.ones_like(col), pill * 0.6)
    col, stain = _wear_stains(size, seed + 4, col, 0.6)
    height = T.normalize(0.75 * rib + 0.25 * pill)
    rough = np.clip(0.93 + 0.04 * stain, 0.7, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.5)


@texture("cloth_buffalo", size=1024, seed=521)
def cloth_buffalo(size: int, seed: int, out) -> None:
    """Hunting coat wool: red and black buffalo check, heavy nap, burrs and mud."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    n = 4
    cx = (np.floor(x * n * 2) % 2)
    cy = (np.floor(y * n * 2) % 2)
    red, black = _c("#7c1714"), _c("#141110")
    both = (cx * cy)[..., None]
    one = ((cx + cy) % 2)[..., None]
    col = red * (1 - both - one) * np.ones((size, size, 3)) + black * both + (0.55 * red + 0.45 * black) * one
    nap = T.spectral(size, 0.7, seed)
    col = col * (0.82 + 0.3 * nap)[..., None]
    col, stain = _wear_stains(size, seed + 1, col.astype(np.float32), 0.6)
    mud = T.smoothstep(0.7, 0.92, T.spectral(size, 2.3, seed + 2))
    col = T.mix(col, _c("#3c3226") * np.ones_like(col), mud * 0.5)
    weave = _weave(size, 120, seed + 3, twill=True)
    height = T.normalize(0.4 * weave + 0.6 * nap)
    rough = np.clip(0.95 - 0.05 * stain, 0.75, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.6)


@texture("cloth_dress", size=1024, seed=531)
def cloth_dress(size: int, seed: int, out) -> None:
    """A Sunday dress: small cream-and-rose flowers on faded navy rayon, stained."""
    r = T.rng(seed)
    col = T.gradient(T.spectral(size, 2.3, seed + 1), [(0.0, "#1c2340"), (0.5, "#252d4c"), (1.0, "#313a5a")])
    flowers = np.zeros((size, size), np.float32)
    centres = np.zeros((size, size), np.float32)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    for _ in range(70):
        cx0, cy0 = r.uniform(0, size), r.uniform(0, size)
        rad = r.uniform(18.0, 34.0)
        ang0 = r.uniform(0, 2 * np.pi)
        dx = (x - cx0 + size / 2) % size - size / 2
        dy = (y - cy0 + size / 2) % size - size / 2
        rr = np.sqrt(dx * dx + dy * dy)
        th = np.arctan2(dy, dx) + ang0
        petal = rad * (0.62 + 0.38 * np.abs(np.cos(th * 2.5)))
        flowers = np.maximum(flowers, 1.0 - T.smoothstep(petal - 1.2, petal + 0.6, rr))
        centres = np.maximum(centres, 1.0 - T.smoothstep(rad * 0.22, rad * 0.32, rr))
    petal_col = T.mix(_c("#d9cdb2") * np.ones((size, size, 3)), _c("#b86a72") * np.ones((size, size, 3)),
                      T.smoothstep(0.4, 0.7, T.spectral(size, 1.6, seed + 2)))
    col = T.mix(col, petal_col, flowers * 0.9)
    col = T.mix(col, _c("#c9a64a") * np.ones_like(col), centres * 0.8)
    col, stain = _wear_stains(size, seed + 3, col, 0.7)
    weave = _weave(size, 240, seed + 4)
    height = T.normalize(0.7 * weave + 0.3 * T.spectral(size, 1.4, seed + 5))
    rough = np.clip(0.72 + 0.1 * stain, 0.5, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.4)


@texture("hide", size=1024, seed=541)
def hide(size: int, seed: int, out) -> None:
    """The Ashen's hides: smoked buckskin with scars, veining, hair left in patches, ash rubbed in."""
    f1, f2, _ = T.worley(size, 1800, seed, jitter=1.0)
    grain = T.normalize(f1)
    veins = _veins(size, seed + 1, 14, 1.2, 40.0)
    smoke = T.spectral(size, 2.4, seed + 2)
    col = T.gradient(T.normalize(0.6 * smoke + 0.4 * grain), [(0.0, "#4a3422"), (0.5, "#6e5136"), (1.0, "#8f704e")])
    scars = _level_lines(T.spectral(size, 2.0, seed + 3, anisotropy=(1.0, 3.0)), 1.2) * \
        T.smoothstep(0.6, 0.8, T.spectral(size, 2.0, seed + 4))
    col = T.mix(col, _c("#a88a66") * np.ones_like(col), scars * 0.6)
    col *= (1.0 - 0.25 * veins)[..., None]
    hair = T.smoothstep(0.62, 0.85, T.spectral(size, 2.1, seed + 5)) * \
        T.smoothstep(0.5, 0.9, T.spectral(size, 0.5, seed + 6, anisotropy=(1.0, 14.0)))
    col = T.mix(col, _c("#3a2c20") * np.ones_like(col), hair * 0.7)
    ash = T.smoothstep(0.55, 0.85, T.spectral(size, 2.2, seed + 7))
    col = T.mix(col, _c("#8a8780") * np.ones_like(col), ash * 0.35)
    height = T.normalize(0.5 * grain - 0.4 * veins + 0.3 * hair + 0.2 * scars)
    rough = np.clip(0.78 + 0.12 * ash - 0.1 * smoke, 0.5, 0.98)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)


@texture("fur", size=1024, seed=551)
def fur(size: int, seed: int, out) -> None:
    """Matted pelt: strands along V in clumps, grey-brown with pale tips, ash and filth."""
    strands = T.spectral(size, 0.8, seed, anisotropy=(30.0, 1.0))
    clumps = T.spectral(size, 1.5, seed + 1, anisotropy=(4.0, 1.0))
    s = T.normalize(0.6 * strands + 0.4 * clumps)
    col = T.gradient(s, [(0.0, "#1e1813"), (0.45, "#3d3127"), (0.8, "#6b5a48"), (1.0, "#9a8a76")])
    filth = T.smoothstep(0.6, 0.9, T.spectral(size, 2.2, seed + 2))
    col = T.mix(col, _c("#2a241c") * np.ones_like(col), filth * 0.5)
    height = s
    rough = np.clip(0.75 + 0.2 * (1 - s), 0.5, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=4.0)


@texture("plastic_hard", size=1024, seed=561)
def plastic_hard(size: int, seed: int, out) -> None:
    """Moulded hard plastic (neutral: hard hats, riot armour, buttons; tinted per material):
    scuffs, gouges, sun-chalked patches, grime in the scratches."""
    base = 0.82 + 0.06 * T.spectral(size, 2.4, seed)
    col = np.stack([base, base, base], -1).astype(np.float32)
    scratch = T.smoothstep(0.86, 0.97, T.spectral(size, 0.9, seed + 1, anisotropy=(1.0, 9.0)))
    scratch = np.maximum(scratch, T.smoothstep(0.88, 0.98, T.spectral(size, 0.9, seed + 2, anisotropy=(9.0, 1.0))))
    gouge = T.smoothstep(0.92, 0.99, T.spectral(size, 1.2, seed + 3))
    chalk = T.smoothstep(0.5, 0.85, T.spectral(size, 2.2, seed + 4))
    col = T.mix(col, _c("#e8e6df") * np.ones_like(col), chalk * 0.25)
    grime = T.smoothstep(0.62, 0.9, T.spectral(size, 2.3, seed + 5))
    col = T.mix(col, _c("#4a4438") * np.ones_like(col), np.clip(grime * 0.4 + scratch * 0.45 + gouge * 0.6, 0, 1))
    height = T.normalize(-0.5 * scratch - 0.8 * gouge + 0.1 * T.spectral(size, 1.6, seed + 6))
    rough = np.clip(0.38 + 0.3 * chalk + 0.25 * scratch + 0.2 * grime, 0.25, 0.95)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.0)


@texture("debris_metal", size=1024, seed=571)
def debris_metal(size: int, seed: int, out) -> None:
    """Husk debris: painted sheet steel torn from cars and sheds, paint flaking off rust."""
    paint_n = T.spectral(size, 2.4, seed)
    paint = T.gradient(paint_n, [(0.0, "#3e5446"), (0.5, "#4f6656"), (1.0, "#61786a")])
    rust_n = T.spectral(size, 2.0, seed + 1)
    flake = T.smoothstep(0.5, 0.56, rust_n + 0.15 * T.spectral(size, 1.0, seed + 2))
    rust = T.gradient(T.spectral(size, 1.6, seed + 3), [(0.0, "#3a1d0e"), (0.5, "#6a3417"), (1.0, "#8c4a22")])
    col = T.mix(paint, rust, flake)
    edge = T.smoothstep(0.48, 0.5, rust_n) * (1 - flake)
    col = T.mix(col, _c("#20160f") * np.ones_like(col), edge * 0.5)
    pits = T.smoothstep(0.85, 0.95, T.spectral(size, 0.5, seed + 4)) * flake
    height = T.normalize(0.4 * (1 - flake) + 0.2 * paint_n - 0.5 * pits)
    rough = np.clip(0.55 + 0.35 * flake, 0.3, 0.95)
    metal = (1 - flake) * 0.0 + flake * 0.15
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, metal=metal, normal_strength=3.0)


@texture("pustule", size=1024, seed=581)
def pustule(size: int, seed: int, out) -> None:
    """A Blister's pustules: taut, translucent yellow-green membrane over pale fluid, a fine net
    of dark veins, milky clouding."""
    base = T.spectral(size, 2.2, seed)
    col = T.gradient(base, [(0.0, "#8e8a3c"), (0.5, "#b0a752"), (1.0, "#cfc47a")])
    veins = _branching(size, seed + 1, trunks=10, steps=120, step=2.5, w0=1.8, wmin=0.45, branch_p=0.06, turn=0.22,
                       taper=0.993, flow_amt=0.05)
    col = T.mix(col, _c("#5a3f2a") * np.ones_like(col), veins * 0.7)
    milk = T.smoothstep(0.55, 0.85, T.spectral(size, 2.0, seed + 2))
    col = T.mix(col, _c("#e2dcb6") * np.ones_like(col), milk * 0.3)
    height = T.normalize(0.3 * base + 0.6 * veins)
    rough = np.clip(0.18 + 0.15 * milk, 0.1, 0.5)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=1.6)


@texture("cord", size=512, seed=591)
def cord(size: int, seed: int, out) -> None:
    """Twisted plant-fibre and rawhide cord (Ashen lashings, charms)."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    twist = 0.5 + 0.5 * np.cos((x * 6 + y * 18) * 2 * np.pi)
    fib = T.spectral(size, 0.8, seed, anisotropy=(1.0, 12.0))
    col = T.gradient(T.normalize(0.6 * twist + 0.4 * fib), [(0.0, "#3b2e20"), (0.5, "#5e4a33"), (1.0, "#80684a")])
    height = T.normalize(0.7 * twist + 0.3 * fib)
    rough = np.clip(0.88 + 0.08 * fib, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=3.0)


@texture("cloth_flannel_green", size=1024, seed=601)
def cloth_flannel_green(size: int, seed: int, out) -> None:
    """A second flannel: faded forest-green and black plaid with a mustard line."""
    pal = ["#2c4a2e", "#141614", "#9a8a4a", "#3c3a30"]
    setts = [(0, 20), (1, 6), (0, 3), (1, 16), (2, 1), (1, 16), (0, 3), (1, 6), (3, 5)]
    col = _tartan(size, setts, pal)
    nap = T.spectral(size, 0.9, seed)
    col = col * (0.85 + 0.25 * nap)[..., None]
    col = T.mix(col, col * 0.6 + 0.4 * _c("#7a7a66"), T.smoothstep(0.4, 0.95, T.spectral(size, 2.4, seed + 2)) * 0.45)
    col, stain = _wear_stains(size, seed + 3, col, 0.7)
    weave = _weave(size, 140, seed + 4)
    height = T.normalize(0.5 * weave + 0.3 * nap + 0.2 * T.spectral(size, 0.4, seed + 1))
    rough = np.clip(0.9 - 0.05 * stain, 0.6, 1.0)
    T.save_pbr_set(out, np.clip(col, 0, 1), height, rough, normal_strength=2.5)
