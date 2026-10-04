"""Gathering & trees: creaks, cracks and falls, logs, sticks, stones, foliage, digging, pickups.

Big outdoor events (tree crack/fall) bake a forest reverb tail; hand-scale sounds are dry.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _punch(y, sr, ceiling):
    """Transient limiting (~1 ms look-ahead): trims only the initial spike so the body reads louder."""
    return dsp.limit(dsp.normalize(y), sr, ceiling, window_ms=1.0)


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _trunk_creak(sr, r, dur, lo=18.0, hi=110.0, big=True):
    """Timber under bending strain: slow stick-slip groan with tick bursts, low wood resonances."""
    k = int(r.integers(4, 8))
    ts = np.sort(r.uniform(0.0, dur, k))
    pts = [(0.0, lo)] + [(t, dsp.loguni(r, lo, hi)) for t in ts] + [(dur, lo * 1.2)]
    amp = [(0.0, 0.0), (dur * 0.15, 0.8)] + [(t, r.uniform(0.35, 1.0)) for t in ts] + [(dur * 0.9, 0.5), (dur, 0.0)]
    f = 0.75 if big else 1.0
    res = [(dsp.vary(r, 250.0 * f, 0.15), 6.0, 1.0), (dsp.vary(r, 340.0 * f, 0.15), 7.0, 0.8),
           (dsp.vary(r, 640.0 * f, 0.15), 9.0, 0.55), (dsp.vary(r, 1150.0 * f, 0.15), 11.0, 0.35),
           (dsp.vary(r, 2100.0, 0.15), 12.0, 0.15)]
    y = dsp.creak(sr, dur, r, pts, amp, res=res, jitter=0.18, pulse_ms=0.8, roughness=0.45)
    y = dsp.normalize(y) + 0.3 * dsp.normalize(dsp.lp(y, sr, 300.0))
    return y


@sound("sfx/tree_creak", variants=3, seed=3001, peak_db=-5.0)
def tree_creak(seed, variant, sr):
    r = dsp.rng(seed, "treecreak")
    dur = r.uniform(1.8, 2.6)
    y = _trunk_creak(sr, r, dur)
    n = len(y)
    # fibre ticks and the crown swaying
    for _ in range(int(r.integers(2, 6))):
        t = r.uniform(0.2, dur - 0.2)
        tk = dsp.crack(sr, r, 0.08, n_clicks=int(r.integers(1, 3)), spread=0.004, body="wood", body_f=dsp.vary(r, 500.0, 0.3),
                       body_amt=0.6, bright=3000.0, tail=0.0)
        dsp.place(y, tk, dsp.ns(t, sr), r.uniform(0.08, 0.2))
    crown = dsp.rustle(sr, dur, r, 0.4 + 0.6 * np.abs(dsp.smooth_noise(n, sr, r, 0.8)), f_lo=1500.0, f_hi=8000.0,
                       density=700.0, swish=0.7)
    y = dsp.fit(y, n) + 0.06 * dsp.normalize(crown)
    return dsp.reverb(y, sr, "forest", 0.12, seed=seed)


@sound("sfx/tree_crack", variants=3, seed=3002, peak_db=-2.0)
def tree_crack(seed, variant, sr):
    """Hinge wood giving way: a loud split, fibres tearing in an accelerating/decelerating run of cracks,
    the trunk groaning as it starts to lean."""
    r = dsp.rng(seed, "treecrack")
    dur = 2.4
    y = _buf(dur, sr)
    big = dsp.crack(sr, r, 0.5, n_clicks=int(r.integers(4, 8)), spread=0.02, body="wood", body_f=dsp.vary(r, 210.0, 0.15),
                    body_amt=0.9, bright=dsp.vary(r, 3200.0, 0.2), tail=0.5, tail_rate=500.0)
    dsp.place(y, big, 0, 1.0)
    dsp.place(y, dsp.thud(sr, r, 70.0, 0.4, contact_ms=6.0, t60=0.12, noise=0.5, knock=0.6, knock_f=250.0), 0, 0.6)
    run = r.uniform(0.6, 1.2)
    t = r.uniform(0.08, 0.15)
    while t < run:
        u = t / run
        a = 0.25 + 0.5 * np.sin(np.pi * u) * r.uniform(0.5, 1.0)
        c = dsp.crack(sr, r, 0.2, n_clicks=int(r.integers(1, 4)), spread=0.01, body="wood", body_f=dsp.vary(r, 450.0, 0.4),
                      body_amt=0.7, bright=dsp.vary(r, 3500.0, 0.3), tail=0.2)
        dsp.place(y, c, dsp.ns(t, sr), a)
        t += r.uniform(0.02, 0.09) * (1.6 - np.sin(np.pi * u))
    cd = dur - 0.2
    cr = _trunk_creak(sr, r, cd, 25.0, 160.0)
    dsp.place(y, dsp.normalize(cr), dsp.ns(0.15, sr), 0.35)
    return _punch(dsp.reverb(y, sr, "forest", 0.22, seed=seed), sr, 0.75)


@sound("sfx/tree_fall_crash", variants=3, seed=3003, peak_db=-1.0)
def tree_fall_crash(seed, variant, sr):
    """Lean (creak + accelerating crown whoosh, neighbour branches snapping), ground impact (sub boom,
    trunk resonance, branch-snap barrage, foliage crash, bounce), settling debris."""
    r = dsp.rng(seed, "treefall")
    t_hit = r.uniform(1.5, 2.0)
    dur = t_hit + 3.2
    n = dsp.ns(dur, sr)
    y = np.zeros(n)
    # lean
    cr = _trunk_creak(sr, r, t_hit + 0.1, 30.0, 220.0)
    dsp.place(y, dsp.normalize(cr), 0, 0.5)
    m = dsp.ns(t_hit, sr)
    acc = (np.arange(m) / m) ** 2.5
    rush = dsp.rustle(sr, t_hit, r, acc, f_lo=900.0, f_hi=9000.0, density=3500.0, swish=0.8, swish_lo=500.0)
    air = dsp.lp(dsp.pink(m, r), sr, dsp.curve([(0, 200.0), (t_hit, 1600.0)], m, sr, "exp")) * acc
    dsp.place(y, dsp.normalize(rush) * 0.22 + dsp.normalize(air) * 0.2, 0)
    for _ in range(int(r.integers(2, 5))):
        tb = r.uniform(t_hit * 0.5, t_hit - 0.05)
        c = dsp.crack(sr, r, 0.15, n_clicks=int(r.integers(2, 4)), spread=0.01, body="wood_small",
                      body_f=dsp.vary(r, 900.0, 0.3), tail=0.2)
        dsp.place(y, c, dsp.ns(tb, sr), r.uniform(0.15, 0.35))
    # impact
    k = dsp.ns(t_hit, sr)
    boom = dsp.thud(sr, r, dsp.vary(r, 42.0, 0.1), 1.2, contact_ms=30.0, t60=0.45, noise=0.6, noise_lp=300.0, force=1.0)
    dsp.place(y, boom, k, 1.0)
    trunk = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 75.0, 0.15), 1.0, contact_ms=6.0, t60=0.6, noise=0.5, click=0.0)
    dsp.place(y, trunk, k, 0.6)
    rum_n = dsp.ns(2.0, sr)
    rumble = dsp.lp(dsp.brown(rum_n, r), sr, 140.0, order=4) * dsp.env_ar(rum_n, sr, 0.02, 1.6)
    dsp.place(y, dsp.normalize(rumble), k, 0.5)
    # branch-snap barrage
    t = 0.0
    while t < 0.6:
        c = dsp.crack(sr, r, 0.18, n_clicks=int(r.integers(1, 5)), spread=0.012, body=dsp.pick(r, ["wood", "wood_small"]),
                      body_f=dsp.loguni(r, 350.0, 1600.0), body_amt=0.6, tail=0.25)
        dsp.place(y, c, k + dsp.ns(t, sr), r.uniform(0.35, 1.0) * (1.0 - t))
        t += r.exponential(0.03)
    # foliage crash and settling
    rest = n - k
    fe = dsp.env_ar(rest, sr, 0.004, 1.4) ** 1.5
    crash = dsp.rustle(sr, rest / sr, r, fe, f_lo=700.0, f_hi=10000.0, density=8000.0, q=2.0, swish=0.9, swish_lo=400.0)
    dsp.place(y, dsp.normalize(crash), k, 0.8)
    tb = r.uniform(0.25, 0.4)
    dsp.place(y, dsp.thud(sr, r, 55.0, 0.6, contact_ms=20.0, t60=0.25, noise=0.5, noise_lp=400.0), k + dsp.ns(tb, sr), 0.45)
    dsp.place(y, dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 85.0, 0.15), 0.6, contact_ms=8.0, t60=0.35, click=0.0),
              k + dsp.ns(tb, sr), 0.3)
    t = 0.8
    while t < 2.8:
        c = dsp.crack(sr, r, 0.1, n_clicks=int(r.integers(1, 3)), spread=0.006, body="wood_small",
                      body_f=dsp.loguni(r, 700.0, 2500.0), tail=0.1)
        dsp.place(y, c, k + dsp.ns(t, sr), r.uniform(0.03, 0.12) * (1.5 - t / 2.8))
        t += r.exponential(0.25)
    y = dsp.sat(y / dsp.peak(y), 1.6)
    return dsp.reverb(y, sr, "forest", 0.3, seed=seed)


@sound("sfx/log_drop", variants=4, seed=3004, peak_db=-3.0)
def log_drop(seed, variant, sr):
    r = dsp.rng(seed, "logdrop")
    y = _buf(1.2, sr)
    md = dsp.modes("wood", dsp.vary(r, 150.0, 0.2), r, t60=dsp.vary(r, 0.25, 0.2))
    hit = dsp.impact(sr, r, modes_=md, contact_ms=3.0, noise=0.4, click=0.2, click_hz=2000.0, dur=0.6)
    dsp.place(y, hit, 0, 1.0)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 70.0, 0.1), 0.4, contact_ms=10.0, t60=0.08, noise=0.5, knock=0.5,
                          knock_f=260.0), 0, 0.8)
    t, a = 0.0, 1.0
    for _ in range(int(r.integers(1, 3))):
        t += r.uniform(0.11, 0.2)
        a *= r.uniform(0.3, 0.5)
        b = dsp.impact(sr, r, modes_=md, contact_ms=4.0, noise=0.4, click=0.1, dur=0.4)
        dsp.place(y, b, dsp.ns(t, sr), a)
        dsp.place(y, dsp.thud(sr, r, 80.0, 0.3, contact_ms=10.0, t60=0.06), dsp.ns(t, sr), a * 0.6)
    rd = r.uniform(0.25, 0.4)
    roll = dsp.scrape(sr, rd, r, [(0, 0), (0.05, 0.8), (rd, 0)], f_lo=200.0, f_hi=3000.0, grit=0.8, grit_rate=500.0,
                      res=[(md[0][0], 6.0, 1.0), (md[0][1], 6.0, 0.7)], rough_hz=25.0)
    dsp.place(y, dsp.normalize(roll), dsp.ns(t + 0.05, sr), 0.2)
    n = len(y)
    grit = dsp.clicks(n, sr, r, dsp.env_ar(n, sr, 0.005, 0.3) * 1200.0, 700.0, 6000.0, q=1.8, alpha=1.7)
    y += 0.15 * dsp.normalize(grit)
    return y


@sound("sfx/log_place", variants=4, seed=3005, peak_db=-6.0)
def log_place(seed, variant, sr):
    r = dsp.rng(seed, "logplace")
    y = _buf(0.7, sr)
    a = dsp.impact(sr, r, "wood", dsp.vary(r, 300.0, 0.25), 0.4, contact_ms=2.5, t60=0.16, noise=0.3, click=0.3, click_hz=1800.0)
    b = dsp.impact(sr, r, "wood", dsp.vary(r, 230.0, 0.25), 0.4, contact_ms=3.5, t60=0.2, noise=0.3, click=0.1)
    dsp.place(y, a, 0, 1.0)
    dsp.place(y, b, dsp.ns(r.uniform(0.004, 0.02), sr), 0.7)
    dsp.place(y, dsp.thud(sr, r, 110.0, 0.2, contact_ms=6.0, t60=0.04, knock=0.6, knock_f=350.0), 0, 0.4)
    sd = r.uniform(0.12, 0.2)
    sl = dsp.scrape(sr, sd, r, [(0, 0), (0.02, 1.0), (sd, 0)], f_lo=300.0, f_hi=3500.0, grit=0.6, rough_hz=40.0)
    dsp.place(y, dsp.normalize(sl), dsp.ns(r.uniform(0.04, 0.08), sr), 0.15)
    bark = dsp.clicks(dsp.ns(0.2, sr), sr, r, 400.0 * dsp.env_ar(dsp.ns(0.2, sr), sr, 0.005, 0.15), 1500.0, 7000.0, q=2.0)
    dsp.place(y, dsp.normalize(bark), 0, 0.08)
    return y


@sound("sfx/stick_pickup", variants=4, seed=3006, peak_db=-8.0)
def stick_pickup(seed, variant, sr):
    r = dsp.rng(seed, "stick")
    y = _buf(0.6, sr)
    lv = dsp.rustle(sr, 0.3, r, [(0, 0), (0.04, 1.0), (0.3, 0.0)], f_lo=1500.0, f_hi=9000.0, density=1500.0)
    dsp.place(y, dsp.normalize(lv), 0, 0.4)
    t = r.uniform(0.03, 0.08)
    for _ in range(int(r.integers(2, 5))):
        k = dsp.impact(sr, r, "wood_small", dsp.loguni(r, 800.0, 2400.0), 0.12, contact_ms=0.4, t60=dsp.vary(r, 0.06, 0.3),
                       click=0.4)
        dsp.place(y, k, dsp.ns(t, sr), r.uniform(0.35, 1.0))
        t += r.uniform(0.03, 0.09)
    sc = dsp.scrape(sr, 0.12, r, [(0, 0), (0.03, 1), (0.12, 0)], f_lo=800.0, f_hi=6000.0, grit=0.7)
    dsp.place(y, dsp.normalize(sc), dsp.ns(0.01, sr), 0.2)
    return y


@sound("sfx/stone_pickup", variants=4, seed=3007, peak_db=-6.8)
def stone_pickup(seed, variant, sr):
    r = dsp.rng(seed, "stonepick")
    y = _buf(0.5, sr)
    sd = r.uniform(0.08, 0.14)
    sc = dsp.scrape(sr, sd, r, [(0, 0), (0.02, 1.0), (sd, 0)], f_lo=900.0, f_hi=8000.0, grit=1.0, grit_rate=1500.0)
    dsp.place(y, dsp.normalize(sc), 0, 0.45)
    t = r.uniform(0.05, 0.12)
    for _ in range(int(r.integers(1, 3))):
        c = dsp.impact(sr, r, "stone", dsp.loguni(r, 1600.0, 3500.0), 0.08, contact_ms=0.25, t60=0.03, click=0.6, noise=0.5)
        dsp.place(y, c, dsp.ns(t, sr), r.uniform(0.6, 1.0))
        t += r.uniform(0.04, 0.1)
    dsp.place(y, dsp.thud(sr, r, 180.0, 0.1, contact_ms=5.0, t60=0.03, knock=0.6, knock_f=700.0), dsp.ns(t, sr), 0.35)
    return y


@sound("sfx/foliage_rustle", variants=6, seed=3008, peak_db=-8.0)
def foliage_rustle(seed, variant, sr):
    """Pushing through bushes/low branches: two leafy surges, twigs flicking back."""
    r = dsp.rng(seed, "foliage")
    dur = r.uniform(0.8, 1.2)
    t1 = r.uniform(0.3, 0.55) * dur
    motion = [(0, 0), (0.08, r.uniform(0.6, 1.0)), (t1, r.uniform(0.3, 0.5)), (t1 + 0.12, 1.0), (dur * 0.85, 0.25), (dur, 0)]
    n = dsp.ns(dur, sr)
    mc = dsp.curve(motion, n, sr, "smooth") * (0.7 + 0.3 * dsp.smooth_noise(n, sr, r, 9.0))
    y = dsp.rustle(sr, dur, r, np.maximum(mc, 0.0) ** 1.8, f_lo=900.0, f_hi=8500.0, density=dsp.vary(r, 1300.0, 0.25), q=2.2,
                   alpha=1.6, swish=0.6, swish_lo=500.0)
    for _ in range(int(r.integers(1, 4))):
        t = r.uniform(0.05, dur - 0.15)
        w = dsp.whoosh(sr, 0.12, r, peak_t=0.4, width=0.2, f_lo=1200.0, f_hi=5000.0, q=2.0)
        dsp.place(y, dsp.normalize(w), dsp.ns(t, sr), r.uniform(0.2, 0.4))
    if r.random() < 0.5:
        c = dsp.crack(sr, r, 0.1, n_clicks=2, spread=0.005, body="wood_small", body_f=dsp.vary(r, 1500.0, 0.3), tail=0.1)
        dsp.place(y, c, dsp.ns(r.uniform(0.1, dur - 0.2), sr), 0.3)
    return y


@sound("sfx/pickup_generic", variants=4, seed=3009, peak_db=-8.8)
def pickup_generic(seed, variant, sr):
    """Grab and stow: hand/sleeve swish, the item knocking against kit in the pack."""
    r = dsp.rng(seed, "pickup")
    y = _buf(0.5, sr)
    cl = dsp.cloth(sr, 0.25, r, [(0, 0), (0.06, 1), (0.25, 0)], heavy=0.4)
    dsp.place(y, dsp.normalize(cl), 0, 0.55)
    t = r.uniform(0.12, 0.18)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 170.0, 0.2), 0.12, contact_ms=7.0, t60=0.03, noise=0.6, noise_lp=1500.0,
                          knock=0.8, knock_f=dsp.vary(r, 600.0, 0.2)), dsp.ns(t, sr), 0.8)
    mat = ["metal_bar", "wood_small", "plastic", "glass"][variant]
    f0 = {"metal_bar": 2400.0, "wood_small": 1100.0, "plastic": 900.0, "glass": 2600.0}[mat]
    k = dsp.impact(sr, r, mat, dsp.vary(r, f0, 0.2), 0.15, contact_ms=0.3, t60=0.06 if mat != "glass" else 0.15, click=0.3)
    dsp.place(y, k, dsp.ns(t + r.uniform(0.005, 0.02), sr), 0.3)
    return y


@sound("sfx/dig_shovel", variants=6, seed=3010, peak_db=-3.0)
def dig_shovel(seed, variant, sr):
    """Blade bites into soil (steel scrape + crunch + chunk), lift, soil tossed and landing."""
    r = dsp.rng(seed, "dig")
    y = _buf(1.3, sr)
    bd = r.uniform(0.1, 0.16)
    bite = dsp.scrape(sr, bd, r, [(0, 1.0), (bd, 0.0)], f_lo=700.0, f_hi=6000.0, grit=1.0, grit_rate=2500.0,
                      res=[(dsp.vary(r, 1500.0, 0.2), 12.0, 0.6), (dsp.vary(r, 2900.0, 0.2), 14.0, 0.4)])
    dsp.place(y, dsp.normalize(bite), 0, 0.6)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 120.0, 0.15), 0.2, contact_ms=5.0, t60=0.04, noise=0.6, knock=0.6,
                          knock_f=380.0), 0, 0.7)
    blade = dsp.impact(sr, r, "metal_sheet", dsp.vary(r, 520.0, 0.2), 0.3, contact_ms=0.6, t60=0.2, click=0.0)
    dsp.place(y, blade, 0, 0.12)
    k = dsp.ns(0.25, sr)
    soil = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.003, 0.18) * 3000.0, 500.0, 5000.0, q=1.6, alpha=1.7)
    dsp.place(y, dsp.normalize(soil), 0, 0.45)
    # toss
    tt = r.uniform(0.45, 0.6)
    td = r.uniform(0.35, 0.5)
    m = dsp.ns(td, sr)
    fall = dsp.clicks(m, sr, r, dsp.env_ar(m, sr, 0.04, td * 0.8) * 2500.0, 400.0, 6000.0, q=1.5, alpha=1.8)
    dsp.place(y, dsp.normalize(fall), dsp.ns(tt, sr), 0.4)
    dsp.place(y, dsp.thud(sr, r, 90.0, 0.25, contact_ms=15.0, t60=0.05, noise=0.6, noise_lp=800.0), dsp.ns(tt + 0.03, sr), 0.4)
    sw = dsp.whoosh(sr, 0.25, r, peak_t=0.5, width=0.25, f_lo=200.0, f_hi=900.0, q=1.0)
    dsp.place(y, dsp.normalize(sw), dsp.ns(tt - 0.15, sr), 0.15)
    return y
