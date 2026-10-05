"""POI dungeon mechanics (ADR-0018): bear traps, the shotgun trip-wire, alarms, loose and rotten
floorboards, padlocks being beaten off, a trap taken apart, and the stir of an ambush waking.
Dry unless noted (interior reverb is a runtime bus); the shotgun bakes a short room so it reads as
indoors even far from the listener's bus."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _clink(sr, r, f0=2600.0, t60=0.06, force=1.0):
    """One small steel contact (chain link, spring leaf, hasp)."""
    return dsp.impact(sr, r, "metal_bar", dsp.vary(r, f0, 0.25), 0.18, contact_ms=0.08, t60=t60, click=0.5,
                      click_hz=4500.0, force=force)


def _chain_rattle(sr, r, dur, n, start=0.0, gain=0.6):
    y = _buf(dur, sr)
    t = start
    for i in range(n):
        dsp.place(y, _clink(sr, r, dsp.loguni(r, 1800.0, 4200.0), r.uniform(0.03, 0.08)), dsp.ns(t, sr), gain * r.uniform(0.35, 1.0))
        t += r.uniform(0.015, 0.06)
        if t > dur - 0.1:
            break
    return y


@sound("sfx/trap_bear_snap", variants=3, seed=7301, peak_db=-0.8)
def trap_bear_snap(seed, variant, sr):
    """Jaws slamming shut: two steel jaws clashing (bright, short, a ringing spring under it), the
    trap jumping on the floor, then the chain settling."""
    r = dsp.rng(seed, "bearsnap", variant)
    y = _buf(1.3, sr)
    jaw = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 1150.0, 0.12), 0.5, contact_ms=0.12, t60=0.35, click=0.9,
                     click_hz=3500.0, noise=0.5)
    dsp.place(y, jaw, 0, 1.0)
    dsp.place(y, dsp.impact(sr, r, "metal_bar", dsp.vary(r, 1650.0, 0.12), 0.35, contact_ms=0.1, t60=0.2, click=0.7),
              dsp.ns(r.uniform(0.002, 0.006), sr), 0.7)
    spring = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 230.0, 0.1), 0.9, contact_ms=1.5, t60=0.6, click=0.0, noise=0.1)
    dsp.place(y, spring, 0, 0.45)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 95.0, 0.1), 0.25, contact_ms=2.5, t60=0.05, noise=0.6, knock=0.6, knock_f=420.0),
              dsp.ns(0.004, sr), 0.6)
    dsp.place(y, _chain_rattle(sr, r, 1.2, int(r.integers(4, 8)), 0.08, 0.35), 0)
    return dsp.limit(dsp.normalize(y), sr, 0.6, window_ms=1.0)


@sound("sfx/trap_bear_rattle", variants=3, seed=7302, peak_db=-3.0)
def trap_bear_rattle(seed, variant, sr):
    """Struggling against the jaws: a wrench of the spring leaves and a burst of chain."""
    r = dsp.rng(seed, "bearrattle", variant)
    y = _buf(0.7, sr)
    dsp.place(y, dsp.scrape(sr, 0.25, r, [(0.0, 0.2), (0.1, 1.0), (0.25, 0.0)], f_lo=900.0, f_hi=6000.0, grit=0.6), 0, 0.35)
    dsp.place(y, _chain_rattle(sr, r, 0.7, int(r.integers(5, 10)), 0.02, 0.8), 0)
    dsp.place(y, dsp.impact(sr, r, "metal_bar", dsp.vary(r, 260.0, 0.15), 0.4, contact_ms=1.0, t60=0.3, click=0.2), 0, 0.3)
    return y


@sound("sfx/trap_shotgun_blast", variants=2, seed=7303, peak_db=-0.3)
def trap_shotgun_blast(seed, variant, sr):
    """A 12-gauge going off in a hallway: a heavier, lower blast than the revolver, a big room
    thump, the chair kicking back, and the house ringing."""
    r = dsp.rng(seed, "shotgun", variant)
    dur = 0.45
    y = _buf(dur, sr)
    T = dsp.vary(r, 0.0011, 0.12)
    L = dsp.ns(2 * T, sr)
    t = np.arange(L) / sr
    dsp.place(y, np.sin(np.pi * t / T) * np.exp(-t / (T * 1.5)), 0, 1.0)
    n = len(y)
    env = dsp.env_ar(n, sr, 0.0005, dsp.vary(r, 0.16, 0.12)) * (0.5 + 0.5 * dsp.env_ar(n, sr, 0.0003, 0.03))
    blast = dsp.band_noise(n, sr, r, 80.0, 8000.0, slope_db_oct=-3.0) * env
    blast = dsp.eq(blast, sr, ("peak", dsp.vary(r, 420.0, 0.1), 6.0, 0.9), ("peak", dsp.vary(r, 1900.0, 0.15), 3.0, 1.2),
                   ("peak", 120.0, 4.0, 0.8))
    dsp.place(y, dsp.normalize(blast), 0, 1.0)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 48.0, 0.1), dur, contact_ms=4.0, t60=0.14, noise=0.4, noise_lp=400.0, knock=0.4,
                          knock_f=180.0), 0, 0.9)
    kick = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 160.0, 0.15), 0.3, contact_ms=1.2, t60=0.12, click=0.2)
    dsp.place(y, kick, dsp.ns(0.02, sr), 0.25)
    y = dsp.sat(y / dsp.peak(y), 2.8)
    wet = dsp.reverb(y, sr, "house", 1.0, seed=seed, dry=0.0)
    out = dsp.fit(y, len(wet)) + 0.55 * wet
    return dsp.limit(out / dsp.peak(out), sr, 0.3, window_ms=1.5)


@sound("sfx/trap_alarm_siren", variants=1, seed=7304, loop=True, peak_db=-2.0)
def trap_alarm_siren(seed, variant, sr):
    """Cheap piezo door alarm: a harsh two-tone yelp, square-ish and nasal, looped."""
    r = dsp.rng(seed, "siren")
    loop_s, xf = 2.0, 0.2
    n = dsp.ns(loop_s + xf, sr)
    tt = np.arange(n) / sr
    # 4 yelps a second: a fast upward sweep each period between two piezo resonances.
    ph = (tt * 4.0) % 1.0
    f = 2750.0 + 650.0 * ph ** 0.7
    tone = dsp.square(f, n, sr, pw=0.42)
    tone = dsp.bp(tone, sr, 3100.0, 1.2) + 0.35 * dsp.bp(tone, sr, 6200.0, 2.0) + 0.12 * tone
    buzz = dsp.band_noise(n, sr, r, 2500.0, 7000.0) * 0.04
    y = dsp.sat(dsp.normalize(tone + buzz), 1.8)
    return dsp.make_loop(y, sr, xf)


@sound("sfx/trap_alarm_bell", variants=1, seed=7305, loop=True, peak_db=-2.0)
def trap_alarm_bell(seed, variant, sr):
    """A brass hand bell yanked on its cord: irregular double strikes ringing over each other, looped."""
    r = dsp.rng(seed, "bell")
    loop_s, xf = 2.4, 0.3
    y = _buf(loop_s + xf + 1.5, sr)
    md = dsp.modes("bell", dsp.vary(r, 1250.0, 0.05), r, t60=1.2)
    t = 0.0
    while t < loop_s + xf:
        for k in range(2):
            amp = r.uniform(0.5, 1.0) * (1.0 if k == 0 else r.uniform(0.3, 0.6))
            h = dsp.impact(sr, r, modes_=(md[0], md[1], md[2] * r.uniform(0.4, 1.0, len(md[2]))), contact_ms=0.12, click=0.4,
                           dur=1.5)
            dsp.place(y, h, dsp.ns(t + k * r.uniform(0.04, 0.07), sr), amp)
        t += r.uniform(0.14, 0.24)
    y = y[:dsp.ns(loop_s + xf, sr)]
    return dsp.make_loop(dsp.normalize(y), sr, xf)


def _board_groan(sr, r, dur, pitch=1.0):
    k = int(r.integers(2, 5))
    ts = np.sort(r.uniform(0.05, dur - 0.05, k))
    rate = [(0.0, 25.0 * pitch)] + [(t, dsp.loguni(r, 30.0, 160.0) * pitch) for t in ts] + [(dur, 20.0 * pitch)]
    amp = [(0.0, 0.0), (0.05, 0.7)] + [(t, r.uniform(0.4, 1.0)) for t in ts] + [(dur - 0.04, 0.3), (dur, 0.0)]
    res = [(dsp.vary(r, 180.0 * pitch, 0.2), 6.0, 1.0), (dsp.vary(r, 390.0 * pitch, 0.2), 8.0, 0.8),
           (dsp.vary(r, 820.0 * pitch, 0.2), 10.0, 0.45), (dsp.vary(r, 1500.0 * pitch, 0.2), 12.0, 0.25)]
    n = dsp.ns(dur, sr)
    y = dsp.creak(sr, dur, r, rate, amp, res=res, jitter=0.35, pulse_ms=0.7, roughness=0.6, bright=1800.0)
    return dsp.normalize(y) + 0.35 * dsp.normalize(dsp.lp(y, sr, 220.0)) if n else y


@sound("sfx/trap_floor_creak", variants=6, seed=7306, peak_db=-2.5)
def trap_floor_creak(seed, variant, sr):
    """A loose floorboard taking weight: a low wooden groan, a nail squeaking in its hole, a tick."""
    r = dsp.rng(seed, "floorcreak", variant)
    dur = r.uniform(0.35, 0.8)
    y = _buf(dur + 0.15, sr)
    dsp.place(y, _board_groan(sr, r, dur, r.uniform(0.85, 1.2)), 0, 1.0)
    if variant % 2 == 0:
        sq = dsp.creak(sr, 0.12, r, [(0, 300.0), (0.12, 600.0)], [(0, 0), (0.03, 0.6), (0.12, 0)],
                       res=[(dsp.vary(r, 2400.0, 0.2), 25.0, 1.0), (dsp.vary(r, 4100.0, 0.2), 30.0, 0.5)], jitter=0.1)
        dsp.place(y, dsp.normalize(sq), dsp.ns(r.uniform(0.05, dur * 0.6), sr), 0.25)
    dsp.place(y, dsp.impact(sr, r, "wood", dsp.vary(r, 520.0, 0.2), 0.08, contact_ms=0.6, t60=0.05, click=0.3),
              dsp.ns(dur * r.uniform(0.6, 0.95), sr), 0.3)
    return y


@sound("sfx/trap_floor_crack", variants=2, seed=7307, peak_db=-1.5)
def trap_floor_crack(seed, variant, sr):
    """The rotten boards starting to go: a deep groan and the first sharp splinters under the feet."""
    r = dsp.rng(seed, "floorcrack", variant)
    y = _buf(0.7, sr)
    dsp.place(y, _board_groan(sr, r, 0.5, 0.75), 0, 0.8)
    for k in range(int(r.integers(2, 4))):
        c = dsp.crack(sr, r, 0.25, n_clicks=int(r.integers(3, 7)), spread=0.02, body="wood", body_f=dsp.loguni(r, 300.0, 800.0),
                      body_amt=0.6, bright=3200.0, tail=0.3)
        dsp.place(y, c, dsp.ns(r.uniform(0.05, 0.4), sr), r.uniform(0.5, 1.0))
    return y


@sound("sfx/trap_floor_collapse", variants=2, seed=7308, peak_db=-0.8)
def trap_floor_collapse(seed, variant, sr):
    """Floorboards giving way: a burst of splintering, the joist cracking, boards and plaster
    clattering down into the room below and a hiss of falling dust."""
    r = dsp.rng(seed, "collapse", variant)
    dur = 2.2
    y = _buf(dur, sr)
    dsp.place(y, dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 95.0, 0.2), 0.8, contact_ms=2.5, t60=0.4, noise=0.6, click=0.0), 0, 0.8)
    t = 0.0
    for i in range(int(r.integers(4, 7))):
        c = dsp.crack(sr, r, 0.3, n_clicks=int(r.integers(3, 8)), spread=0.02, body="wood", body_f=dsp.loguni(r, 200.0, 900.0),
                      body_amt=0.7, bright=dsp.vary(r, 3200.0, 0.3), tail=0.4, tail_rate=700.0)
        dsp.place(y, c, dsp.ns(t, sr), 1.0 if i == 0 else r.uniform(0.35, 0.8))
        t += r.uniform(0.02, 0.09)
    t = r.uniform(0.35, 0.5)
    for i in range(int(r.integers(6, 11))):
        mat = "wood" if r.random() < 0.65 else "stone"
        h = dsp.impact(sr, r, mat, dsp.loguni(r, 180.0, 700.0), 0.25, contact_ms=r.uniform(0.5, 2.0), t60=r.uniform(0.04, 0.12), click=0.3)
        dsp.place(y, h, dsp.ns(t, sr), r.uniform(0.25, 0.7) * (0.85 ** i))
        t += r.uniform(0.04, 0.16)
        if t > dur - 0.4:
            break
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 70.0, 0.1), 0.4, contact_ms=6.0, t60=0.08, noise=0.6, knock=0.5, knock_f=300.0),
              dsp.ns(0.42, sr), 0.7)
    n = len(y)
    dust = dsp.band_noise(n, sr, r, 1500.0, 9000.0) * dsp.curve([(0, 0), (0.3, 0.0), (0.5, 0.25), (dur, 0.0)], n, sr, "smooth")
    return y + 0.25 * dust


@sound("sfx/lock_padlock_hit", variants=4, seed=7309, peak_db=-1.5)
def lock_padlock_hit(seed, variant, sr):
    """A blow on a padlock and hasp: a hard dull clank, the shackle jumping in the staple."""
    r = dsp.rng(seed, "padhit", variant)
    y = _buf(0.6, sr)
    dsp.place(y, dsp.impact(sr, r, "metal", dsp.vary(r, 880.0, 0.15), 0.4, contact_ms=0.25, t60=0.18, click=0.7, noise=0.4), 0, 1.0)
    dsp.place(y, dsp.impact(sr, r, "metal_bar", dsp.vary(r, 2300.0, 0.15), 0.25, contact_ms=0.1, t60=0.12, click=0.5),
              dsp.ns(r.uniform(0.03, 0.07), sr), 0.45)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 140.0, 0.1), 0.15, contact_ms=1.5, t60=0.04, noise=0.5, knock=0.5, knock_f=500.0), 0, 0.4)
    return y


@sound("sfx/lock_padlock_break", variants=2, seed=7310, peak_db=-1.0)
def lock_padlock_break(seed, variant, sr):
    """The hasp tearing out: a sharp metallic snap, screws squealing, the padlock dropping and
    bouncing on the floor."""
    r = dsp.rng(seed, "padbreak", variant)
    y = _buf(1.4, sr)
    dsp.place(y, dsp.crack(sr, r, 0.2, n_clicks=4, spread=0.01, body="metal_bar", body_f=dsp.vary(r, 1900.0, 0.15), body_amt=0.9,
                           bright=5000.0, tail=0.1), 0, 1.0)
    dsp.place(y, dsp.impact(sr, r, "metal", dsp.vary(r, 760.0, 0.15), 0.4, contact_ms=0.2, t60=0.2, click=0.6), 0, 0.6)
    t, a = r.uniform(0.25, 0.35), 0.7
    for i in range(int(r.integers(3, 5))):
        dsp.place(y, dsp.impact(sr, r, "metal", dsp.vary(r, 1100.0, 0.2), 0.3, contact_ms=0.15, t60=0.15, click=0.5), dsp.ns(t, sr), a)
        t += r.uniform(0.09, 0.18) * (0.75 ** i)
        a *= r.uniform(0.4, 0.65)
    return y


@sound("sfx/trap_disarm", variants=2, seed=7311, peak_db=-3.0)
def trap_disarm(seed, variant, sr):
    """Working a trap loose: the dog eased off, a spring let down slowly, the chain lifted."""
    r = dsp.rng(seed, "disarm", variant)
    y = _buf(1.0, sr)
    for k in range(3):
        dsp.place(y, _clink(sr, r, dsp.loguni(r, 2500.0, 4500.0), 0.04, 0.7), dsp.ns(0.04 + k * r.uniform(0.07, 0.12), sr), 0.6)
    dsp.place(y, dsp.scrape(sr, 0.35, r, [(0.0, 0.0), (0.15, 0.8), (0.35, 0.0)], f_lo=700.0, f_hi=4500.0, grit=0.3),
              dsp.ns(0.35, sr), 0.3)
    dsp.place(y, _chain_rattle(sr, r, 0.5, 4, 0.0, 0.4), dsp.ns(0.5, sr))
    return y


@sound("sfx/ambush_stir", variants=3, seed=7312, peak_db=-2.0)
def ambush_stir(seed, variant, sr):
    """An ambush waking: something heavy shifting in the dark, a board complaining under it, and
    a low wet groan rising out of more than one throat."""
    r = dsp.rng(seed, "stir", variant)
    dur = 2.4
    y = _buf(dur, sr)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 60.0, 0.15), 0.4, contact_ms=8.0, t60=0.1, noise=0.5, knock=0.3, knock_f=260.0), 0, 0.8)
    dsp.place(y, _board_groan(sr, r, 0.6, 0.8), dsp.ns(0.12, sr), 0.4)
    for k in range(2 + variant % 2):
        d = r.uniform(1.2, 1.8)
        base = r.uniform(55.0, 80.0)
        f0 = dsp.curve([(0, base * 0.9), (d * 0.5, base * r.uniform(1.05, 1.25)), (d, base)], dsp.ns(d, sr), sr, "smooth")
        v = dsp.voice(sr, d, f0, [(0.0, "uh"), (d * 0.6, "o"), (d, "u")], [(0, 0), (d * 0.3, 0.8), (d * 0.8, 1.0), (d, 0)], r,
                      rough=r.uniform(0.3, 0.6), sub=0.4, breath=0.08, tract=r.uniform(0.82, 0.9), bw=1.6, jitter=0.05)
        dsp.place(y, dsp.normalize(v), dsp.ns(0.3 + k * r.uniform(0.15, 0.35), sr), r.uniform(0.5, 0.9))
    wet = dsp.reverb(y, sr, "house", 1.0, seed=seed, dry=0.0)
    return dsp.fit(y, len(wet)) + 0.35 * wet
