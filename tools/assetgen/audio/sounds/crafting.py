"""Crafting and handling: cordage, knots, flint knapping, nails, sawing, bandages, paper, canvas,
setting items down. Hand-scale, dry, close perspective."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _punch(y, sr, ceiling):
    """Transient limiting (~1 ms look-ahead): trims only the initial spike so the body reads louder."""
    return dsp.limit(dsp.normalize(y), sr, ceiling, window_ms=1.0)


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _fibre_rub(sr, r, dur, rate_lo=120.0, rate_hi=420.0, amt=1.0):
    """Plant fibre / rope rubbing on itself: fast stick-slip through fibrous mid-high resonances + dry rustle."""
    pts = [(0.0, rate_lo), (dur * r.uniform(0.3, 0.6), rate_hi), (dur, rate_lo * 1.2)]
    cr = dsp.creak(sr, dur, r, pts, [(0, 0), (dur * 0.2, 1.0), (dur * 0.8, 0.8), (dur, 0)],
                   res=[(dsp.vary(r, 1300.0, 0.2), 4.0, 1.0), (dsp.vary(r, 2600.0, 0.2), 5.0, 0.8),
                        (dsp.vary(r, 4800.0, 0.2), 6.0, 0.3)], jitter=0.35, pulse_ms=0.2, roughness=0.6, body=0.15,
                   bright=4000.0)
    ru = dsp.rustle(sr, dur, r, [(0, 0), (dur * 0.2, 1.0), (dur, 0.2)], f_lo=1800.0, f_hi=9000.0, density=900.0,
                    swish=0.6, swish_lo=1200.0)
    return amt * (dsp.normalize(cr) * 0.5 + dsp.normalize(ru) * 0.55)


@sound("sfx/craft_twist", variants=3, seed=4001, peak_db=-9.0)
def craft_twist(seed, variant, sr):
    r = dsp.rng(seed, "twist")
    y = _buf(1.2, sr)
    t = 0.0
    for i in range(int(r.integers(3, 5))):
        d = r.uniform(0.18, 0.3)
        dsp.place(y, _fibre_rub(sr, r, d, r.uniform(40, 90), r.uniform(140, 320)), dsp.ns(t, sr), r.uniform(0.6, 1.0))
        t += d + r.uniform(0.02, 0.08)
        if t > 1.0:
            break
    return y


@sound("sfx/craft_tie", variants=3, seed=4002, peak_db=-9.0)
def craft_tie(seed, variant, sr):
    r = dsp.rng(seed, "tie")
    y = _buf(1.0, sr)
    d1 = r.uniform(0.3, 0.45)
    rub = dsp.scrape(sr, d1, r, [(0, 0), (0.05, 0.8), (d1 * 0.6, 1.0), (d1, 0.2)], f_lo=700.0, f_hi=6000.0, grit=0.5,
                     grit_rate=800.0, rough_hz=70.0)
    dsp.place(y, dsp.normalize(rub), 0, 0.5)
    dsp.place(y, _fibre_rub(sr, r, d1 * 0.8, 60.0, 200.0, 0.6), dsp.ns(0.05, sr))
    # cinch: tension rises fast and the knot bites
    t2 = d1 + r.uniform(0.02, 0.08)
    d2 = r.uniform(0.15, 0.22)
    pull = dsp.creak(sr, d2, r, [(0, 60.0), (d2 * 0.8, r.uniform(350, 600)), (d2, 600.0)], [(0, 0.2), (d2 * 0.8, 1.0), (d2, 0)],
                     res=[(dsp.vary(r, 900.0, 0.2), 6.0, 1.0), (dsp.vary(r, 2100.0, 0.2), 7.0, 0.6)], jitter=0.25,
                     pulse_ms=0.3)
    dsp.place(y, dsp.normalize(pull), dsp.ns(t2, sr), 0.6)
    snap = dsp.thud(sr, r, dsp.vary(r, 300.0, 0.2), 0.08, contact_ms=1.5, t60=0.02, noise=0.8, noise_lp=5000.0, knock=0.8,
                    knock_f=1200.0)
    dsp.place(y, snap, dsp.ns(t2 + d2 * 0.85, sr), 0.6)
    return y


@sound("sfx/craft_knap", variants=4, seed=4003, peak_db=-3.0)
def craft_knap(seed, variant, sr):
    """Hammerstone on flint: glassy bright strike, stone body knock, a flake skittering away."""
    r = dsp.rng(seed, "knap")
    y = _buf(0.7, sr)
    strike = dsp.impact(sr, r, "glass", dsp.vary(r, 2300.0, 0.2), 0.12, contact_ms=0.12, t60=0.04, click=0.4,
                        click_hz=3000.0, noise=0.6, tilt=0.8)
    dsp.place(y, strike, 0, 0.7)
    body = dsp.impact(sr, r, "stone", dsp.vary(r, 750.0, 0.2), 0.12, contact_ms=0.35, t60=0.05, click=0.15, tilt=0.9)
    dsp.place(y, body, 0, 1.0)
    dsp.place(y, dsp.thud(sr, r, 200.0, 0.08, contact_ms=2.0, t60=0.02, knock=0.6, knock_f=700.0), 0, 0.3)
    t = r.uniform(0.12, 0.25)
    for _ in range(int(r.integers(1, 4))):
        fl = dsp.impact(sr, r, "glass", dsp.loguni(r, 4000.0, 9000.0), 0.06, contact_ms=0.06, t60=0.03, click=0.5)
        dsp.place(y, fl, dsp.ns(t, sr), r.uniform(0.05, 0.15))
        t += r.uniform(0.03, 0.08)
    return _punch(y, sr, 0.6)


@sound("sfx/hammer_nail", variants=6, seed=4004, peak_db=-3.0)
def hammer_nail(seed, variant, sr):
    """Steel hammer on a nail into a board. Variants go from first tap (long bright nail ring) to the
    final blow (nail flush: board knock dominates)."""
    r = dsp.rng(seed, "nail")
    depth = variant / 5.0
    y = _buf(0.6, sr)
    nail = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 2200.0 + 2600.0 * depth, 0.08), 0.5, contact_ms=0.12,
                      t60=dsp.vary(r, 0.22 - 0.15 * depth, 0.15), click=0.4, click_hz=4000.0)
    dsp.place(y, nail, 0, 0.9 * (1 - 0.5 * depth))
    head = dsp.impact(sr, r, "metal", dsp.vary(r, 1400.0, 0.15), 0.2, contact_ms=0.1, t60=0.05, click=0.6, click_hz=5000.0)
    dsp.place(y, head, 0, 0.55)
    board = dsp.impact(sr, r, "wood", dsp.vary(r, 260.0, 0.2), 0.35, contact_ms=0.8, t60=0.14, click=0.0, noise=0.3)
    dsp.place(y, board, 0, 0.35 + 0.6 * depth)
    dsp.place(y, dsp.thud(sr, r, 130.0, 0.15, contact_ms=2.0, t60=0.03, knock=0.6, knock_f=450.0), 0, 0.25 + 0.3 * depth)
    return y


@sound("sfx/saw_wood", variants=3, seed=4005, peak_db=-2.6)
def saw_wood(seed, variant, sr):
    """Hand saw: push/pull strokes; teeth rasp at a tooth rate that follows stroke speed, through the board's
    wood resonances, with blade whine and sawdust hiss. Push strokes cut harder."""
    r = dsp.rng(seed, "saw")
    strokes = int(r.integers(4, 6))
    lens = r.uniform(0.32, 0.45, strokes)
    dur = float(lens.sum()) + 0.25
    n = dsp.ns(dur, sr)
    speed = np.zeros(n)
    load = np.zeros(n)
    t = 0.05
    for i, L in enumerate(lens):
        k0, k1 = dsp.ns(t, sr), dsp.ns(t + L, sr)
        u = np.arange(k1 - k0) / max(1, k1 - k0)
        speed[k0:k1] = np.sin(np.pi * u) ** 1.2 * r.uniform(0.85, 1.1)
        load[k0:k1] = (1.0 if i % 2 == 0 else 0.45) * np.sin(np.pi * u) ** 0.8
        t += L
    teeth = dsp.vary(r, 520.0, 0.15)
    rate = teeth * speed
    board = [(dsp.vary(r, 340.0, 0.15), 5.0, 1.0), (dsp.vary(r, 760.0, 0.15), 6.0, 0.8), (dsp.vary(r, 1500.0, 0.15), 7.0, 0.6),
             (dsp.vary(r, 3100.0, 0.15), 6.0, 0.5)]
    rasp = dsp.creak(sr, dur, r, rate, load, res=board, jitter=0.3, pulse_ms=0.12, roughness=0.5, body=0.25, bright=5000.0)
    dust = dsp.band_noise(n, sr, r, 2000.0, 8000.0, slope_db_oct=-3.0) * load * speed
    md = dsp.modes("metal_sheet", dsp.vary(r, 900.0, 0.2), r, count=10, t60=0.4)
    whine = dsp.modal_bank(dsp.hp(rasp, sr, 1000.0) * 0.05, sr, md[0], md[1], md[2])
    y = dsp.normalize(rasp) + 0.15 * dsp.normalize(dust) + 0.12 * dsp.normalize(whine)
    return y


@sound("sfx/bandage_wrap", variants=2, seed=4006, peak_db=-8.9)
def bandage_wrap(seed, variant, sr):
    r = dsp.rng(seed, "bandage")
    y = _buf(1.7, sr)
    td = r.uniform(0.25, 0.35)
    tr = dsp.tear(sr, td, r, [(0, 0.3), (0.03, 1.0), (td * 0.7, 0.9), (td, 0)], f_lo=900.0, f_hi=8000.0, rate=2500.0)
    dsp.place(y, dsp.normalize(tr), 0, 0.8)
    t = td + 0.12
    for _ in range(int(r.integers(3, 5))):
        d = r.uniform(0.18, 0.28)
        cl = dsp.cloth(sr, d, r, [(0, 0), (d * 0.4, 1.0), (d, 0)], heavy=0.2)
        dsp.place(y, dsp.normalize(cl), dsp.ns(t, sr), r.uniform(0.4, 0.7))
        t += d + r.uniform(0.0, 0.05)
    dsp.place(y, dsp.thud(sr, r, 180.0, 0.1, contact_ms=8.0, t60=0.03, noise=0.6, noise_lp=2000.0), dsp.ns(min(t, 1.55), sr), 0.4)
    return y


@sound("sfx/book_page_turn", variants=4, seed=4007, peak_db=-10.0)
def book_page_turn(seed, variant, sr):
    r = dsp.rng(seed, "page")
    dur = r.uniform(0.5, 0.7)
    y = _buf(dur, sr)
    lift = r.uniform(0.08, 0.14)
    cr = dsp.rustle(sr, lift + 0.05, r, [(0, 0), (lift * 0.5, 1.0), (lift + 0.05, 0.2)], f_lo=2000.0, f_hi=11000.0,
                    density=2500.0, q=3.0, alpha=1.5, swish=0.3)
    dsp.place(y, dsp.normalize(cr), 0, 0.6)
    fl = r.uniform(0.18, 0.26)
    sw = dsp.whoosh(sr, fl, r, peak_t=0.55, width=0.3, f_lo=900.0, f_hi=4500.0, q=0.9, power=1.5)
    dsp.place(y, dsp.normalize(sw), dsp.ns(lift, sr), 0.4)
    land = dsp.ns(lift + fl * 0.85, sr)
    L = dsp.ns(0.05, sr)
    flap = dsp.band_noise(L, sr, r, 300.0, 5000.0) * dsp.env_ar(L, sr, 0.001, 0.03)
    dsp.place(y, dsp.normalize(flap), land, 0.5)
    dsp.place(y, dsp.normalize(dsp.rustle(sr, 0.12, r, [(0, 1.0), (0.12, 0)], f_lo=2500.0, f_hi=10000.0, density=1500.0)),
              land, 0.25)
    return y


@sound("sfx/canvas_unroll", variants=2, seed=4008, peak_db=-13.3)
def canvas_unroll(seed, variant, sr):
    r = dsp.rng(seed, "canvas")
    dur = 1.6
    n = dsp.ns(dur, sr)
    motion = [(0, 0), (0.1, 0.8), (0.5, 1.0), (1.0, 0.7), (1.4, 0.2), (dur, 0)]
    y = dsp.cloth(sr, dur, r, motion, heavy=1.0)
    y = dsp.normalize(y)
    t = 0.12
    for _ in range(int(r.integers(4, 7))):
        fl = dsp.thud(sr, r, dsp.vary(r, 110.0, 0.2), 0.15, contact_ms=12.0, t60=0.04, noise=0.8, noise_lp=1500.0)
        dsp.place(y, fl, dsp.ns(t, sr), r.uniform(0.25, 0.5))
        t += r.uniform(0.15, 0.3)
        if t > dur - 0.2:
            break
    stiff = dsp.clicks(n, sr, r, dsp.curve(motion, n, sr) * 600.0, 600.0, 4000.0, q=2.0, alpha=1.5)
    y += 0.3 * dsp.normalize(stiff)
    return y


@sound("sfx/item_place_mat", variants=4, seed=4009, peak_db=-6.9)
def item_place_mat(seed, variant, sr):
    """Setting an item down on a mat/table: soft padded thud, the item's own little knock, settle."""
    r = dsp.rng(seed, "place")
    y = _buf(0.45, sr)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 170.0, 0.2), 0.15, contact_ms=dsp.vary(r, 7.0, 0.3), t60=0.035, noise=0.6,
                          noise_lp=1800.0, knock=0.8, knock_f=dsp.vary(r, 650.0, 0.25)), 0, 1.0)
    mat = ["wood_small", "metal_bar", "plastic", "ceramic"][variant]
    f0 = {"wood_small": 1000.0, "metal_bar": 2200.0, "plastic": 800.0, "ceramic": 1800.0}[mat]
    dsp.place(y, dsp.impact(sr, r, mat, dsp.vary(r, f0, 0.2), 0.12, contact_ms=0.4, t60=0.05, click=0.3), dsp.ns(0.002, sr), 0.25)
    if r.random() < 0.6:
        dsp.place(y, dsp.impact(sr, r, mat, dsp.vary(r, f0, 0.2), 0.08, contact_ms=0.5, t60=0.03, click=0.2),
                  dsp.ns(r.uniform(0.04, 0.09), sr), 0.12)
    cl = dsp.cloth(sr, 0.15, r, [(0, 1.0), (0.15, 0)], heavy=0.6)
    dsp.place(y, dsp.normalize(cl), 0, 0.12)
    return y
