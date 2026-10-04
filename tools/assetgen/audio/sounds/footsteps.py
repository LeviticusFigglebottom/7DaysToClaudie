"""Footsteps and landings (player + Hollowed shuffle).

Anatomy of one step (close foley perspective, dry - the game adds interior/cave reverb): heel strike
(body thump + surface-specific transient), roll/toe contact 45-120 ms later (smaller), and the surface
texture excited by both (crunch grains, swish, splash, board resonance, plate ring).
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound

STEP = -10.0   # footstep family peak level (quiet next to impacts/voices)


def _timing(r, walk=True):
    toe = r.uniform(0.055, 0.115) if walk else r.uniform(0.035, 0.07)
    return toe, r.uniform(0.35, 0.65)   # toe delay, toe relative strength


def _heel(sr, r, f=95.0, contact_ms=7.0, t60=0.09, noise=0.35, noise_lp=900.0, dur=0.25, force=1.0, knock=0.35,
          knock_f=420.0):
    """Shoe heel/sole contact: tight low thump (resonance t60 kept short) + sole knock."""
    return dsp.thud(sr, r, f=dsp.vary(r, f * 1.15, 0.12), dur=dur, contact_ms=dsp.vary(r, contact_ms, 0.25),
                    t60=dsp.vary(r, min(t60 * 0.45, 0.045), 0.2), noise=noise * 1.4, noise_lp=noise_lp * 1.3,
                    force=force, knock=knock, knock_f=dsp.vary(r, knock_f, 0.2))


def _burst_env(n, sr, r, t0, attack, t60, power=1.0):
    e = np.zeros(n)
    k = dsp.ns(t0, sr)
    if k < n:
        e[k:] = dsp.env_ar(n - k, sr, attack, t60) ** power
    return e


def _texture_env(n, sr, r, toe, toe_amt, a_ms=4.0, t60_h=0.12, t60_t=0.1):
    """Grain-density envelope: heel burst + toe burst."""
    e = _burst_env(n, sr, r, 0.0, a_ms / 1000.0, dsp.vary(r, t60_h, 0.25))
    e += toe_amt * _burst_env(n, sr, r, toe, a_ms / 1000.0 * 1.5, dsp.vary(r, t60_t, 0.25))
    return e


# --------------------------------------------------------------------------------------------- surfaces

def _gravel(seed, sr):
    r = dsp.rng(seed, "gravel")
    dur = r.uniform(0.42, 0.55)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    env = _texture_env(n, sr, r, toe, ta * 1.1, 3.0, 0.24, 0.22)
    # stone-on-stone pings (resonant clicks) + gritty broadband crunch + low grind
    pings = dsp.clicks(n, sr, r, env * dsp.vary(r, 1400.0, 0.3), 1700.0, 7500.0, q=9.0, alpha=1.5, groups=10)
    grit = dsp.clicks(n, sr, r, env * 2500.0, 900.0, 9000.0, q=1.4, alpha=1.9, groups=6)
    grind = dsp.band_noise(n, sr, r, 250.0, 1400.0) * env ** 1.5
    tex = dsp.normalize(pings) * 0.8 + dsp.normalize(grit) * 0.55 + dsp.normalize(grind) * 0.25
    heel = _heel(sr, r, 100.0, 8.0, 0.07, 0.4, 700.0, force=0.55)
    toe_t = _heel(sr, r, 130.0, 6.0, 0.05, 0.4, 900.0, force=0.25)
    y = dsp.normalize(tex)
    dsp.place(y, heel, 0)
    dsp.place(y, toe_t, dsp.ns(toe, sr))
    return dsp.hshelf(y, sr, 6000.0, dsp.vary(r, -2.0, 1.0))


def _leaves(seed, sr):
    r = dsp.rng(seed, "leaves")
    dur = r.uniform(0.5, 0.65)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    env = _texture_env(n, sr, r, toe, ta * 1.2, 6.0, 0.28, 0.3)
    env = env * (0.75 + 0.25 * dsp.smooth_noise(n, sr, r, 40.0))
    crisp = dsp.clicks(n, sr, r, np.maximum(env, 0) * dsp.vary(r, 3200.0, 0.25), 1800.0, 11000.0, q=2.2, alpha=1.6, groups=10)
    crumple = dsp.clicks(n, sr, r, np.maximum(env, 0) * 900.0, 500.0, 2400.0, q=1.8, alpha=1.7, groups=5)
    swish = dsp.band_noise(n, sr, r, 1200.0, 8000.0) * np.maximum(env, 0) ** 2
    tex = dsp.normalize(crisp) + 0.45 * dsp.normalize(crumple) + 0.2 * dsp.normalize(swish)
    heel = _heel(sr, r, 85.0, 10.0, 0.08, 0.3, 600.0, force=0.45)
    y = dsp.normalize(tex)
    dsp.place(y, heel, 0)
    dsp.place(y, _heel(sr, r, 110.0, 8.0, 0.05, 0.3, 700.0, force=0.18), dsp.ns(toe, sr))
    return y


def _forest_floor(seed, sr):
    r = dsp.rng(seed, "forest")
    dur = r.uniform(0.42, 0.55)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    env = _texture_env(n, sr, r, toe, ta, 5.0, 0.13, 0.12)
    needles = dsp.clicks(n, sr, r, env * dsp.vary(r, 1300.0, 0.3), 1300.0, 7000.0, q=2.6, alpha=1.7, groups=8)
    rust = dsp.band_noise(n, sr, r, 900.0, 6000.0) * env ** 1.8
    tex = dsp.normalize(needles) * 0.5 + dsp.normalize(rust) * 0.22
    # occasional small twig snap under the heel or toe
    if r.random() < 0.55:
        tw = dsp.crack(sr, r, 0.12, n_clicks=int(r.integers(2, 5)), spread=0.012, body="wood_small",
                       body_f=dsp.vary(r, 1400.0, 0.3), body_amt=0.5, bright=4500.0, tail=0.25, force=0.45)
        dsp.place(tex, tw, dsp.ns(r.choice([r.uniform(0.004, 0.02), toe + r.uniform(0.0, 0.02)]), sr))
    heel = _heel(sr, r, 90.0, 9.0, 0.09, 0.35, 700.0, force=1.0)
    y = heel * 0.6
    y = dsp.fit(y, n)
    y += dsp.normalize(tex) * 0.65
    dsp.place(y, _heel(sr, r, 120.0, 7.0, 0.06, 0.35, 800.0, force=0.35 * ta * 2), dsp.ns(toe, sr))
    return y


def _grass(seed, sr):
    r = dsp.rng(seed, "grass")
    dur = r.uniform(0.42, 0.55)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    env = _burst_env(n, sr, r, 0.0, r.uniform(0.012, 0.025), r.uniform(0.16, 0.24), 1.0)
    env += ta * 0.8 * _burst_env(n, sr, r, toe, 0.015, r.uniform(0.15, 0.22))
    flutter = 0.6 + 0.4 * dsp.smooth_noise(n, sr, r, 90.0)
    swish = dsp.band_noise(n, sr, r, 1800.0, 10000.0, slope_db_oct=-1.0) * env * flutter
    blades = dsp.clicks(n, sr, r, env * 5000.0, 2500.0, 10000.0, q=1.6, alpha=2.5, groups=6)
    heel = _heel(sr, r, 85.0, 11.0, 0.08, 0.25, 500.0, force=0.9)
    y = dsp.fit(heel, n) * 0.7
    y += dsp.normalize(swish) * 0.6 + dsp.normalize(blades) * 0.35
    dsp.place(y, _heel(sr, r, 110.0, 9.0, 0.05, 0.25, 600.0, force=0.3), dsp.ns(toe, sr))
    return y


def _dirt(seed, sr):
    r = dsp.rng(seed, "dirt")
    dur = r.uniform(0.38, 0.5)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    env = _texture_env(n, sr, r, toe, ta * 0.8, 3.0, 0.07, 0.06)
    grit = dsp.clicks(n, sr, r, env * dsp.vary(r, 1800.0, 0.3), 600.0, 5000.0, q=1.5, alpha=1.8, groups=7)
    heel = _heel(sr, r, 115.0, 6.0, 0.07, 0.5, 1200.0, force=1.0)
    y = dsp.fit(heel, n)
    y += dsp.normalize(grit) * 0.45
    # toe scuff: a short drag of sole on soil
    sc_d = r.uniform(0.06, 0.11)
    sp = [(0.0, 0.0), (sc_d * 0.3, 1.0), (sc_d, 0.0)]
    sc = dsp.scrape(sr, sc_d, r, sp, f_lo=500.0, f_hi=4500.0, grit=0.6, grit_rate=900.0)
    dsp.place(y, dsp.normalize(sc) * 0.35 * ta * 2, dsp.ns(toe - 0.01, sr))
    dsp.place(y, _heel(sr, r, 140.0, 5.0, 0.05, 0.5, 1400.0, force=0.35), dsp.ns(toe, sr))
    return y


def _concrete(seed, sr):
    r = dsp.rng(seed, "concrete")
    dur = r.uniform(0.32, 0.42)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    y = np.zeros(n)
    # heel: hard heel on slab - short broadband 'tock' (heel block resonance, heavily damped) + slap
    tock = dsp.impact(sr, r, "plastic", dsp.vary(r, 750.0, 0.2), 0.06, contact_ms=0.35, t60=0.018, click=0.7,
                      click_hz=2500.0, noise=0.5, force=1.0)
    L = dsp.ns(0.025, sr)
    slap = dsp.band_noise(L, sr, r, 900.0, 9000.0) * dsp.env_ar(L, sr, 0.0004, 0.012)
    body = _heel(sr, r, 150.0, 3.5, 0.06, 0.4, 2500.0, dur=0.12, force=0.55, knock=0.6, knock_f=600.0)
    dsp.place(y, tock, 0, 0.8)
    dsp.place(y, dsp.normalize(slap), 0, 0.55)
    dsp.place(y, body, 0, 0.8)
    # toe: softer tap + short gritty scuff (sole twisting on grit)
    k = dsp.ns(toe, sr)
    dsp.place(y, dsp.impact(sr, r, "plastic", dsp.vary(r, 950.0, 0.2), 0.05, contact_ms=0.5, t60=0.015,
                            click=0.5, force=1.0), k, 0.3 * ta * 2)
    sc_d = r.uniform(0.035, 0.07)
    sc = dsp.scrape(sr, sc_d, r, [(0.0, 0.0), (sc_d * 0.2, 1.0), (sc_d * 0.6, 0.4), (sc_d, 0.0)], f_lo=1800.0,
                    f_hi=9000.0, grit=1.2, grit_rate=2500.0, rough_hz=90.0)
    dsp.place(y, dsp.normalize(sc), k + dsp.ns(0.003, sr), r.uniform(0.1, 0.2))
    return y


def _wood_floor(seed, sr, creak_p=0.3):
    r = dsp.rng(seed, "woodfloor")
    dur = r.uniform(0.45, 0.6)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    y = np.zeros(n)
    boards = dsp.modes("wood_hollow", dsp.vary(r, 120.0, 0.18), r, t60=dsp.vary(r, 0.16, 0.2))
    hit = dsp.impact(sr, r, modes_=boards, contact_ms=dsp.vary(r, 2.2, 0.2), click=0.0, noise=0.2, force=1.0, dur=0.4)
    tick = dsp.impact(sr, r, "wood_small", dsp.vary(r, 1100.0, 0.2), 0.08, contact_ms=0.35, click=0.6, click_hz=2500.0)
    dsp.place(y, hit, 0, 0.9)
    dsp.place(y, tick, 0, 0.5)
    dsp.place(y, _heel(sr, r, 100.0, 7.0, 0.06, 0.2, 500.0, force=0.5), 0)
    k = dsp.ns(toe, sr)
    hit2 = dsp.impact(sr, r, modes_=boards, contact_ms=3.0, click=0.0, noise=0.2, force=1.0, dur=0.35)
    dsp.place(y, hit2, k, 0.35 * ta * 2)
    dsp.place(y, dsp.impact(sr, r, "wood_small", dsp.vary(r, 1400.0, 0.2), 0.06, contact_ms=0.5, click=0.4), k, 0.2)
    if r.random() < creak_p:
        cd = r.uniform(0.12, 0.22)
        cr = dsp.creak(sr, cd, r, [(0, r.uniform(25, 60)), (cd, r.uniform(80, 180))],
                       [(0, 0), (cd * 0.3, 1), (cd, 0)],
                       res=[(dsp.vary(r, 520.0, 0.2), 10.0, 1.0), (dsp.vary(r, 1150.0, 0.2), 12.0, 0.6),
                            (dsp.vary(r, 2100.0, 0.2), 14.0, 0.3)])
        dsp.place(y, dsp.normalize(cr), k + dsp.ns(0.02, sr), 0.22)
    return y


def _metal(seed, sr):
    r = dsp.rng(seed, "metal")
    dur = r.uniform(0.6, 0.8)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    y = np.zeros(n)
    plate = dsp.modes("metal_sheet", dsp.vary(r, 230.0, 0.25), r, t60=dsp.vary(r, 0.5, 0.25))
    clank = dsp.impact(sr, r, modes_=plate, contact_ms=dsp.vary(r, 1.0, 0.3), damp=dsp.vary(r, 1.6, 0.2),
                       click=0.25, click_hz=2500.0, noise=0.3, dur=dur)
    dsp.place(y, clank, 0, 1.0)
    dsp.place(y, _heel(sr, r, 110.0, 6.0, 0.05, 0.2, 700.0, force=0.5), 0)
    # loose plate rattle: a few quick secondary contacts
    t = r.uniform(0.012, 0.03)
    for _i in range(int(r.integers(1, 4))):
        rat = dsp.impact(sr, r, modes_=plate, contact_ms=0.5, damp=2.5, click=0.4, noise=0.4, dur=0.3)
        dsp.place(y, rat, dsp.ns(t, sr), r.uniform(0.1, 0.25))
        t += r.uniform(0.012, 0.035)
    k = dsp.ns(toe, sr)
    dsp.place(y, dsp.impact(sr, r, modes_=plate, contact_ms=1.4, damp=2.0, click=0.2, dur=0.4), k, 0.45 * ta * 2)
    return y


def _water(seed, sr):
    """Ankle-deep water: boot slaps the surface (broadband slap + spray), plunges (low slosh, a few small
    bubbles), then droplets fall back as the foot lifts."""
    r = dsp.rng(seed, "water")
    dur = r.uniform(0.6, 0.8)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    size = r.uniform(0.7, 1.0)
    y = dsp.fit(dsp.splash(sr, r, size, dur), n)
    dsp.place(y, _heel(sr, r, 85.0, 12.0, 0.06, 0.3, 450.0, force=0.35, knock=0.0), dsp.ns(0.008, sr))
    # lift-off: water streaming off the boot (dense fine droplets) and a slurp of the slosh
    lt = r.uniform(0.2, 0.3)
    m = n - dsp.ns(lt, sr)
    env = dsp.env_ar(m, sr, 0.04, r.uniform(0.25, 0.4))
    drops = dsp.clicks(m, sr, r, env * 900.0, 1800.0, 9000.0, q=5.0, alpha=1.8, groups=8)
    tiny = dsp.bubbles(m, sr, r, env * 60.0, 1200.0, 4500.0, alpha=2.5, rise=(0.0, 0.1))
    lift = dsp.normalize(drops) * 0.6 + dsp.normalize(tiny) * 0.25
    lift += dsp.normalize(dsp.lp(dsp.brown(m, r), sr, 500.0) * env ** 2) * 0.4
    dsp.place(y, lift, dsp.ns(lt, sr), 0.35)
    return dsp.lshelf(y, sr, 200.0, -3.0)


def _carpet(seed, sr):
    r = dsp.rng(seed, "carpet")
    dur = r.uniform(0.35, 0.45)
    n = dsp.ns(dur, sr)
    toe, ta = _timing(r)
    y = dsp.fit(_heel(sr, r, 88.0, 14.0, 0.07, 0.3, 380.0, force=1.0), n)
    env = _texture_env(n, sr, r, toe, ta, 15.0, 0.08, 0.07)
    fab = dsp.band_noise(n, sr, r, 300.0, 3500.0, slope_db_oct=-2.0) * env
    y += dsp.normalize(fab) * 0.22
    dsp.place(y, _heel(sr, r, 105.0, 12.0, 0.05, 0.3, 400.0, force=0.3), dsp.ns(toe, sr))
    return dsp.lp(y, sr, 3000.0)


# --------------------------------------------------------------------------------------------- registry

@sound("sfx/footstep_forest_floor", variants=8, seed=1001, peak_db=-9.6)
def footstep_forest_floor(seed, variant, sr):
    return dsp.hp(_forest_floor(seed, sr), sr, 50.0)


@sound("sfx/footstep_grass", variants=8, seed=1002, peak_db=-11.6)
def footstep_grass(seed, variant, sr):
    return dsp.hp(_grass(seed, sr), sr, 50.0)


@sound("sfx/footstep_dirt", variants=8, seed=1003, peak_db=-11.6)
def footstep_dirt(seed, variant, sr):
    return dsp.hp(_dirt(seed, sr), sr, 50.0)


@sound("sfx/footstep_gravel", variants=8, seed=1004, peak_db=-8.7)
def footstep_gravel(seed, variant, sr):
    return dsp.hp(_gravel(seed, sr), sr, 50.0)


@sound("sfx/footstep_wood_floor", variants=8, seed=1005, peak_db=-9.2)
def footstep_wood_floor(seed, variant, sr):
    return dsp.hp(_wood_floor(seed, sr), sr, 50.0)


@sound("sfx/footstep_concrete", variants=8, seed=1006, peak_db=-8.8)
def footstep_concrete(seed, variant, sr):
    return dsp.hp(_concrete(seed, sr), sr, 50.0)


@sound("sfx/footstep_water", variants=8, seed=1007, peak_db=-10.2)
def footstep_water(seed, variant, sr):
    return dsp.hp(_water(seed, sr), sr, 50.0)


@sound("sfx/footstep_leaves", variants=8, seed=1008, peak_db=-6.9)
def footstep_leaves(seed, variant, sr):
    return dsp.hp(_leaves(seed, sr), sr, 50.0)


@sound("sfx/footstep_carpet", variants=8, seed=1009, peak_db=-13.4)
def footstep_carpet(seed, variant, sr):
    return dsp.hp(_carpet(seed, sr), sr, 50.0)


@sound("sfx/footstep_metal", variants=8, seed=1010, peak_db=-9.2)
def footstep_metal(seed, variant, sr):
    return dsp.hp(_metal(seed, sr), sr, 50.0)


def _landing(seed, sr, hard):
    r = dsp.rng(seed, "land", int(hard))
    dur = 0.9 if hard else 0.6
    n = dsp.ns(dur, sr)
    y = np.zeros(n)
    flam = r.uniform(0.008, 0.03)
    f = 62.0 if hard else 78.0
    for i, t in enumerate((0.0, flam)):
        th = dsp.thud(sr, r, dsp.vary(r, f, 0.1), 0.4, contact_ms=dsp.vary(r, 9.0 if hard else 13.0, 0.2),
                      t60=0.16 if hard else 0.11, noise=0.5, noise_lp=900.0 if hard else 600.0, force=1.0)
        dsp.place(y, th, dsp.ns(t, sr), 1.0 if i == 0 else r.uniform(0.6, 0.85))
    # ground texture (dirt grit + grass/leaf swish)
    env = _burst_env(n, sr, r, 0.0, 0.004, 0.18 if hard else 0.14)
    grit = dsp.clicks(n, sr, r, env * (2600.0 if hard else 1600.0), 600.0, 6000.0, q=1.6, alpha=1.7)
    sw = dsp.band_noise(n, sr, r, 1500.0, 8000.0) * env
    y += dsp.normalize(grit) * (0.4 if hard else 0.3) + dsp.normalize(sw) * 0.15
    # clothing/gear: body settles, cloth whoosh, (hard) buckles and kit clink
    cl_d = r.uniform(0.2, 0.3)
    cloth = dsp.rustle(sr, cl_d, r, [(0, 0), (0.03, 1), (cl_d, 0)], f_lo=600.0, f_hi=5000.0, density=700.0, q=1.5,
                       swish=0.8, swish_lo=400.0)
    dsp.place(y, dsp.normalize(cloth), dsp.ns(0.01, sr), 0.22)
    if hard:
        t = r.uniform(0.02, 0.05)
        for _ in range(int(r.integers(2, 4))):
            ck = dsp.impact(sr, r, "metal", dsp.vary(r, 1900.0, 0.3), 0.12, contact_ms=0.15, t60=0.07, click=0.4)
            dsp.place(y, ck, dsp.ns(t, sr), r.uniform(0.06, 0.14))
            t += r.uniform(0.03, 0.09)
        # knee / hand catch
        dsp.place(y, dsp.thud(sr, r, 95.0, 0.3, contact_ms=12.0, t60=0.08, force=0.4), dsp.ns(r.uniform(0.12, 0.2), sr))
    return y


@sound("sfx/land_soft", variants=3, seed=1011, peak_db=STEP + 2)
def land_soft(seed, variant, sr):
    return _landing(seed, sr, False)


@sound("sfx/land_hard", variants=3, seed=1012, peak_db=STEP + 5)
def land_hard(seed, variant, sr):
    return _landing(seed, sr, True)


@sound("sfx/zombie_footstep_shuffle", variants=6, seed=1013, peak_db=-10.6)
def zombie_footstep_shuffle(seed, variant, sr):
    """Dragging, uneven gait: a heavy foot plant, then the other foot scraped forward (sometimes caught twice)."""
    r = dsp.rng(seed, "shuffle")
    dur = r.uniform(0.7, 1.0)
    n = dsp.ns(dur, sr)
    y = np.zeros(n)
    plant_first = variant % 2 == 0
    t_plant = 0.0 if plant_first else r.uniform(0.35, 0.55)
    th = dsp.thud(sr, r, dsp.vary(r, 85.0, 0.15), 0.3, contact_ms=dsp.vary(r, 12.0, 0.2), t60=0.09, noise=0.45,
                  noise_lp=700.0)
    dsp.place(y, th, dsp.ns(t_plant, sr), 0.8)
    grit_env = _burst_env(n, sr, r, t_plant, 0.004, 0.08)
    gr = dsp.clicks(n, sr, r, grit_env * 1500.0, 700.0, 5000.0, q=1.6, alpha=1.8)
    y += dsp.normalize(gr) * 0.25
    # drag: slow scrape with stuttering speed profile
    t0 = r.uniform(0.12, 0.2) if plant_first else 0.0
    dd = r.uniform(0.32, 0.5)
    pts = [(0.0, 0.0), (dd * 0.2, 1.0), (dd * 0.45, r.uniform(0.3, 0.7)), (dd * 0.65, 1.0), (dd, 0.0)]
    dr = dsp.scrape(sr, dd, r, pts, f_lo=dsp.vary(r, 250.0, 0.2), f_hi=dsp.vary(r, 3000.0, 0.2), grit=1.0,
                    grit_rate=700.0, rough_hz=45.0)
    dr = dsp.peq(dr, sr, dsp.vary(r, 900.0, 0.2), 4.0, 1.2)
    dsp.place(y, dsp.normalize(dr), dsp.ns(t0, sr), 0.55)
    # cloth flap of rotten trousers
    cl = dsp.rustle(sr, 0.25, r, [(0, 0), (0.05, 1), (0.25, 0)], f_lo=500.0, f_hi=4000.0, density=500.0, swish=0.6)
    dsp.place(y, dsp.normalize(cl), dsp.ns(t0 + dd * 0.4, sr), 0.15)
    if r.random() < 0.5:   # wet slap of a bare sole
        sl = dsp.band_noise(dsp.ns(0.05, sr), sr, r, 700.0, 3500.0) * dsp.env_ar(dsp.ns(0.05, sr), sr, 0.001, 0.03)
        sl = sl + dsp.bubbles(dsp.ns(0.05, sr), sr, r, 120.0, 400.0, 1400.0) * 2
        dsp.place(y, dsp.normalize(sl), dsp.ns(t_plant + 0.002, sr), 0.3)
    return y
