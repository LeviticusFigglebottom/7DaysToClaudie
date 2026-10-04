"""Handheld items: revolver (shot, distant shot, dry fire, reload), lighter, torch, eating and drinking.

The revolver shot is the loudest sound in the game (peak -0.3 dBFS, limited for density) and bakes its
outdoor tail (forest / valley / town reflections per variant); the distant shot is mostly echo."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _punch(y, sr, ceiling):
    """Transient limiting (~1 ms look-ahead): trims only the initial spike so the body reads louder."""
    return dsp.limit(dsp.normalize(y), sr, ceiling, window_ms=1.0)


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _muzzle_blast(sr, r, dur=0.3, crack=1.0, body_f=650.0, boom_amt=0.6):
    """Close revolver report, dry: N-wave crack, dense gas blast with a resonant body, low thump, action clack."""
    y = _buf(dur, sr)
    # N-wave: a ~0.5 ms over-pressure spike followed by the under-pressure lobe
    T = dsp.vary(r, 0.0007, 0.15)
    L = dsp.ns(2 * T, sr)
    t = np.arange(L) / sr
    nwave = np.sin(np.pi * t / T) * np.exp(-t / (T * 1.5))
    dsp.place(y, nwave, 0, crack)
    L2 = dsp.ns(0.006, sr)
    sharp = dsp.hp(dsp.white(L2, r), sr, 1500.0) * dsp.env_ar(L2, sr, 0.0002, 0.004)
    dsp.place(y, dsp.normalize(sharp), 0, 0.7 * crack)
    n = len(y)
    env = dsp.env_ar(n, sr, 0.0004, dsp.vary(r, 0.11, 0.15)) * (0.55 + 0.45 * dsp.env_ar(n, sr, 0.0003, 0.02))
    blast = dsp.band_noise(n, sr, r, 120.0, 9000.0, slope_db_oct=-2.5) * env
    blast = dsp.eq(blast, sr, ("peak", dsp.vary(r, body_f, 0.12), 6.0, 0.9), ("peak", dsp.vary(r, 2300.0, 0.15), 3.0, 1.2),
                   ("peak", 180.0, 3.0, 0.8))
    dsp.place(y, dsp.normalize(blast), 0, 1.0)
    boom = dsp.thud(sr, r, dsp.vary(r, 62.0, 0.1), dur, contact_ms=3.0, t60=0.09, noise=0.4, noise_lp=500.0,
                    knock=0.5, knock_f=220.0)
    dsp.place(y, boom, 0, boom_amt)
    mech = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 3100.0, 0.15), 0.15, contact_ms=0.08, t60=0.1, click=0.4)
    dsp.place(y, mech, 0, 0.12)
    y = dsp.sat(y / dsp.peak(y), 2.6)
    return y


@sound("sfx/gun_revolver_shot", variants=3, seed=6001, peak_db=-0.3)
def gun_revolver_shot(seed, variant, sr):
    r = dsp.rng(seed, "shot")
    dry = _muzzle_blast(sr, r, 0.3)
    room, mix = [("forest", 0.5), ("valley", 0.55), ("town", 0.45)][variant]
    wet = dsp.reverb(dry, sr, room, 1.0, seed=seed, dry=0.0)
    wet = dsp.hp(wet, sr, 140.0)                      # open air does not sustain the sub; tail lives in the mids
    y = dsp.fit(dry, len(wet)) + mix * wet
    y = dsp.limit(y / dsp.peak(y), sr, 0.3, window_ms=1.5)     # pin the transient, lift the body and tail
    return y


@sound("sfx/gun_revolver_distant", variants=2, seed=6002, peak_db=-5.0)
def gun_revolver_distant(seed, variant, sr):
    """Shot across the valley: no crack, a dull thump smeared by distance, rolling echoes off the slopes."""
    r = dsp.rng(seed, "distant")
    dry = _muzzle_blast(sr, r, 0.35, crack=0.15, body_f=480.0, boom_amt=0.35)
    dry = dsp.air(dry, sr, dsp.vary(r, 600.0, 0.2), foliage=0.6)
    dry = dsp.band(dry, sr, 90.0, 1800.0, order=4)
    wet = dsp.reverb(dry, sr, "valley", 1.0, seed=seed, dry=0.0, rt=(4.0, 3.2, 1.2))
    y = dsp.fit(dry, len(wet)) * 0.5 + 1.2 * dsp.hp(wet, sr, 110.0)
    return dsp.lp(y, sr, 2500.0)


@sound("sfx/gun_click_empty", variants=2, seed=6003, peak_db=-3.0)
def gun_click_empty(seed, variant, sr):
    """Dry fire: trigger pull turns the cylinder (soft ratchet), the hammer falls on an empty chamber."""
    r = dsp.rng(seed, "dryfire")
    y = _buf(0.45, sr)
    t = 0.0
    for _ in range(int(r.integers(2, 4))):
        c = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 4200.0, 0.2), 0.05, contact_ms=0.06, t60=0.03, click=0.6)
        dsp.place(y, c, dsp.ns(t, sr), r.uniform(0.12, 0.25))
        t += r.uniform(0.02, 0.05)
    th = t + r.uniform(0.06, 0.12)
    hammer = dsp.impact(sr, r, "metal", dsp.vary(r, 2600.0, 0.15), 0.15, contact_ms=0.05, t60=0.07, click=0.9, click_hz=4500.0)
    dsp.place(y, hammer, dsp.ns(th, sr), 1.0)
    frame = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 1300.0, 0.15), 0.2, contact_ms=0.1, t60=0.12, click=0.0)
    dsp.place(y, frame, dsp.ns(th, sr), 0.35)
    dsp.place(y, dsp.thud(sr, r, 250.0, 0.06, contact_ms=1.0, t60=0.015, knock=0.8, knock_f=900.0), dsp.ns(th, sr), 0.3)
    return _punch(y, sr, 0.6)


def _click(sr, r, f=3500.0, t60=0.04, gain=1.0):
    return dsp.impact(sr, r, "metal_bar", dsp.vary(r, f, 0.2), 0.08, contact_ms=0.07, t60=t60, click=0.6) * gain


def _slide(sr, r, d, f_lo=1500.0, f_hi=8000.0):
    return dsp.normalize(dsp.scrape(sr, d, r, [(0, 0), (d * 0.2, 1.0), (d, 0.2)], f_lo=f_lo, f_hi=f_hi, grit=0.3,
                                    res=[(dsp.vary(r, 2800.0, 0.2), 15.0, 0.6), (dsp.vary(r, 4600.0, 0.2), 18.0, 0.4)]))


def _casing(sr, r, gain):
    """Brass casing landing (two bounces)."""
    y = _buf(0.4, sr)
    f = dsp.vary(r, 4300.0, 0.15)
    for i, (t, g) in enumerate(((0.0, 1.0), (r.uniform(0.05, 0.1), 0.4), (r.uniform(0.12, 0.18), 0.15))):
        c = dsp.impact(sr, r, "pipe", f, 0.3, contact_ms=0.05, t60=0.25, click=0.4)
        dsp.place(y, c, dsp.ns(t, sr), g)
    return y * gain


@sound("sfx/gun_reload", variants=2, seed=6004, peak_db=-5.0)
def gun_reload(seed, variant, sr):
    """Revolver reload: cylinder swings out, empties ejected and tinkling to the ground, rounds thumbed in one
    by one, cylinder snapped shut, hammer cocked."""
    r = dsp.rng(seed, "reload")
    y = _buf(3.0, sr)
    dsp.place(y, _click(sr, r, 3000.0, 0.05), 0, 0.6)
    dsp.place(y, _slide(sr, r, 0.12), dsp.ns(0.03, sr), 0.25)
    dsp.place(y, _click(sr, r, 2200.0, 0.08), dsp.ns(0.16, sr), 0.9)
    te = r.uniform(0.38, 0.45)
    dsp.place(y, _slide(sr, r, 0.15, 1000.0, 6000.0), dsp.ns(te, sr), 0.35)
    for _ in range(int(r.integers(4, 7))):
        dsp.place(y, _casing(sr, r, r.uniform(0.25, 0.55)), dsp.ns(te + r.uniform(0.25, 0.55), sr))
    t = te + r.uniform(0.75, 0.9)
    for i in range(int(r.integers(4, 7))):
        dsp.place(y, _slide(sr, r, 0.06, 2000.0, 8000.0), dsp.ns(t, sr), 0.18)
        dsp.place(y, _click(sr, r, 3800.0, 0.04), dsp.ns(t + 0.05, sr), r.uniform(0.35, 0.55))
        t += r.uniform(0.2, 0.27)
        if t > 2.3:
            break
    t += r.uniform(0.1, 0.18)
    close = dsp.impact(sr, r, "metal", dsp.vary(r, 1800.0, 0.15), 0.25, contact_ms=0.1, t60=0.12, click=0.8)
    dsp.place(y, close, dsp.ns(t, sr), 1.0)
    dsp.place(y, dsp.thud(sr, r, 220.0, 0.08, contact_ms=1.2, t60=0.02, knock=0.8, knock_f=800.0), dsp.ns(t, sr), 0.35)
    t += r.uniform(0.25, 0.35)
    for k in range(2):
        dsp.place(y, _click(sr, r, 3300.0 + 600 * k, 0.05), dsp.ns(t + 0.06 * k, sr), 0.7 - 0.2 * k)
    return y


@sound("sfx/lighter_flick", variants=3, seed=6005, peak_db=-7.0)
def lighter_flick(seed, variant, sr):
    """0/1: brass flip-top (lid clink, wheel, whoomp, flame); 2: disposable (two wheel strikes, then the flame)."""
    r = dsp.rng(seed, "lighter")
    y = _buf(1.3, sr)
    t = 0.0
    if variant < 2:
        lid = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 2700.0, 0.1), 0.3, contact_ms=0.08, t60=0.25, click=0.6)
        dsp.place(y, lid, 0, 0.8)
        dsp.place(y, dsp.impact(sr, r, "metal", dsp.vary(r, 1500.0, 0.15), 0.12, contact_ms=0.1, t60=0.05, click=0.3), 0, 0.3)
        t = r.uniform(0.3, 0.42)
    strikes = 1 if variant < 2 else 2
    for s_ in range(strikes):
        wd = r.uniform(0.035, 0.06)
        wheel = dsp.scrape(sr, wd, r, [(0, 1.0), (wd, 0.2)], f_lo=2000.0, f_hi=12000.0, grit=1.5, grit_rate=4000.0,
                           rough_hz=300.0)
        dsp.place(y, dsp.normalize(wheel), dsp.ns(t, sr), 0.6)
        sparks = dsp.clicks(dsp.ns(0.06, sr), sr, r, 1500.0, 3000.0, 12000.0, q=3.0, alpha=1.5)
        dsp.place(y, dsp.normalize(sparks), dsp.ns(t + 0.01, sr), 0.25)
        if s_ < strikes - 1:
            t += r.uniform(0.25, 0.35)
    ti = t + 0.03
    wd = 0.25
    m = dsp.ns(wd, sr)
    whomp = dsp.lp(dsp.pink(m, r), sr, dsp.curve([(0, 300.0), (0.05, 2500.0), (wd, 800.0)], m, sr, "exp")) * \
        dsp.env_ar(m, sr, 0.01, 0.15)
    dsp.place(y, dsp.normalize(whomp), dsp.ns(ti, sr), 0.45)
    fd = 1.3 - ti - 0.05
    if fd > 0.1:
        fl = dsp.fire(dsp.ns(fd, sr), sr, r, intensity=dsp.curve([(0, 1.0), (fd, 0.7)], dsp.ns(fd, sr), sr), crackle_rate=0.0,
                      roar=0.5, hiss=0.5, pops=0.0, size=0.25)
        fl = dsp.band(fl, sr, 150.0, 6000.0)
        dsp.place(y, dsp.normalize(fl), dsp.ns(ti + 0.02, sr), 0.08)
    return y


@sound("sfx/torch_ignite", variants=2, seed=6006, peak_db=-6.2)
def torch_ignite(seed, variant, sr):
    """Pitch-soaked torch catching: soft ignition whoomph that opens up, then the flame settles to crackling."""
    r = dsp.rng(seed, "torch")
    dur = 2.0
    n = dsp.ns(dur, sr)
    y = np.zeros(n)
    wd = 0.7
    m = dsp.ns(wd, sr)
    fc = dsp.curve([(0, 150.0), (0.12, 3500.0), (wd, 900.0)], m, sr, "exp")
    whoomph = dsp.lp(dsp.pink(m, r), sr, fc, q=0.9) * dsp.env_ar(m, sr, 0.06, 0.45)
    dsp.place(y, dsp.normalize(whoomph), 0, 0.9)
    dsp.place(y, dsp.thud(sr, r, 70.0, 0.5, contact_ms=60.0, t60=0.2, noise=0.6, noise_lp=300.0), 0, 0.5)
    it = dsp.curve([(0, 0.0), (0.15, 1.3), (0.6, 1.0), (dur, 0.85)], n, sr)
    fl = dsp.fire(n, sr, r, intensity=it, crackle_rate=14.0, roar=0.8, hiss=0.4, pops=0.8, size=0.5)
    y += 0.7 * dsp.normalize(fl)
    return dsp.fade(y, sr, 0.0, 0.4)


@sound("sfx/eat_crunch", variants=3, seed=6007, peak_db=-5.0)
def eat_crunch(seed, variant, sr):
    """Biting something crisp (dried apple, cracker, roots), then chewing: muffled crunches heard through the jaw."""
    r = dsp.rng(seed, "crunch")
    y = _buf(1.4, sr)
    bd = r.uniform(0.1, 0.15)
    m = dsp.ns(bd, sr)
    bite = dsp.clicks(m, sr, r, dsp.env_ar(m, sr, 0.003, bd * 0.8) * 4500.0, 900.0, 7000.0, q=2.0, alpha=1.4)
    dsp.place(y, dsp.normalize(bite), 0, 1.0)
    dsp.place(y, dsp.thud(sr, r, 160.0, 0.1, contact_ms=4.0, t60=0.03, knock=0.6, knock_f=500.0), 0, 0.35)
    t = bd + r.uniform(0.15, 0.25)
    a = 0.7
    for _ in range(int(r.integers(3, 5))):
        cd = r.uniform(0.09, 0.14)
        m = dsp.ns(cd, sr)
        ch = dsp.clicks(m, sr, r, dsp.env_ar(m, sr, 0.01, cd * 0.8) * 2500.0, 500.0, 4500.0, q=1.8, alpha=1.6)
        ch = dsp.lp(ch, sr, 3500.0)
        dsp.place(y, dsp.normalize(ch), dsp.ns(t, sr), a)
        sq = dsp.squelch(sr, r, cd, 1200.0, 600.0, q=2.5, stick=0.6, bub=0.1)
        dsp.place(y, dsp.normalize(sq), dsp.ns(t, sr), a * 0.3)
        t += r.uniform(0.2, 0.28)
        a *= 0.8
    return _punch(dsp.lp(y, sr, 7000.0), sr, 0.6)


@sound("sfx/eat_can", variants=2, seed=6008, peak_db=-9.3)
def eat_can(seed, variant, sr):
    """Spoon scraping a tin can (thin-walled ring), clinking the rim, wet chewing."""
    r = dsp.rng(seed, "can")
    y = _buf(1.6, sr)
    can = dsp.modes("metal_sheet", dsp.vary(r, 1100.0, 0.15), r, count=14, t60=0.35)
    t = 0.0
    for _ in range(2):
        d = r.uniform(0.18, 0.3)
        sc = dsp.scrape(sr, d, r, [(0, 0), (0.03, 1.0), (d, 0.1)], f_lo=900.0, f_hi=7000.0, grit=0.4, grit_rate=500.0)
        ring = dsp.modal_bank(sc * 0.05, sr, can[0], can[1], can[2])
        dsp.place(y, dsp.normalize(sc) * 0.4 + dsp.normalize(ring) * 0.6, dsp.ns(t, sr), 0.8)
        t += d + r.uniform(0.05, 0.12)
    clink = dsp.impact(sr, r, modes_=can, contact_ms=0.08, click=0.5, dur=0.5)
    dsp.place(y, clink, dsp.ns(t, sr), 0.9)
    t += r.uniform(0.2, 0.3)
    for _ in range(int(r.integers(2, 4))):
        sq = dsp.squelch(sr, r, r.uniform(0.12, 0.18), 1300.0, 500.0, q=2.5, stick=0.8, bub=0.2)
        dsp.place(y, dsp.normalize(dsp.lp(sq, sr, 3000.0)), dsp.ns(t, sr), 0.35)
        t += r.uniform(0.2, 0.26)
        if t > 1.4:
            break
    return y


@sound("sfx/drink_gulp", variants=3, seed=6009, peak_db=-5.8)
def drink_gulp(seed, variant, sr):
    """Swallows: liquid gush, throat 'glug' (low resonant pulse + bubble), a breath out after the last one."""
    r = dsp.rng(seed, "gulp")
    y = _buf(1.6, sr)
    t = 0.02
    for i in range(int(r.integers(2, 4))):
        g = dsp.thud(sr, r, dsp.vary(r, 170.0, 0.15), 0.12, contact_ms=dsp.vary(r, 12.0, 0.2), t60=0.04, noise=0.4,
                     noise_lp=800.0, knock=0.5, knock_f=dsp.vary(r, 380.0, 0.2))
        dsp.place(y, g, dsp.ns(t, sr), 0.7)
        b = dsp.bubble(sr, r, dsp.vary(r, 330.0, 0.25), 1.0, rise=r.uniform(0.8, 1.6), dur=0.08)
        dsp.place(y, b, dsp.ns(t + 0.01, sr), 0.45)
        sq = dsp.squelch(sr, r, 0.12, 900.0, 350.0, q=3.0, stick=0.4, bub=0.6)
        dsp.place(y, dsp.normalize(sq), dsp.ns(t - 0.03, sr), 0.25)
        t += r.uniform(0.33, 0.45)
    if variant != 1:
        bd = r.uniform(0.35, 0.5)
        br = dsp.breath(sr, bd, [(0, "a"), (bd, "uh")], [(0, 0.0), (0.05, 1.0), (bd, 0.0)], r, hiss=0.2)
        dsp.place(y, dsp.normalize(br), dsp.ns(t + 0.05, sr), 0.3)
    return dsp.lp(y, sr, 6000.0)
