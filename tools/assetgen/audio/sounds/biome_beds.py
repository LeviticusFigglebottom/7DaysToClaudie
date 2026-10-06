"""Ambience beds for the burnt forest and the fen (ADR-0041), built like ambience.py's (stereo,
seamless 60 s loops: periodic layers, events on a circular canvas, circular reverb).

The burn: no crowns to sough, so the wind is lower and hollower and whistles past bare trunks; snags
creak and tick in the gusts; black-backed woodpeckers, which follow fires, drum near and far; dry
fireweed and grass rustle. At night the wind and the creaking go on, with an owl and a few crickets.
The fen: a light breeze hissing in the sedge and reeds, flies passing, gas bubbling up through the
peat, a thrush far off. From dusk the frogs: chorus frogs' rising creaks, peepers, the odd green
frog's plucked note, under crickets.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound
from .ambience import _canvas, _creak_far, _cricket, _distant, _gust, _lfilt, _lfo, _note_env, _owl, _put, _st, \
    _thrush, _wind, _woodpecker

# Built on ambience.py's helpers (the audio catalog hashes this module, dsp.py and the registry only).


def _snag_wind(n, sr, seed, g):
    gl = np.clip(g * (0.85 + 0.3 * _lfo(n, sr, dsp.rng(seed, "bl"), 0.2) - 0.15), 0, 1)
    gr = np.clip(g * (0.85 + 0.3 * _lfo(n, sr, dsp.rng(seed, "br"), 0.2) - 0.15), 0, 1)
    kw = dict(lo=170.0, hi=650.0, q=0.9, needles=0.02, rumble=0.4, howl=0.32, howl_f=(300.0, 720.0))
    return _st(_wind(n, sr, dsp.rng(seed, "wl"), gl, **kw), _wind(n, sr, dsp.rng(seed, "wr"), gr, **kw))


def _tick(sr, r):
    """A dry snag ticking or cracking in the wind: a short bright wooden knock."""
    return dsp.crack(sr, r, 0.12, n_clicks=int(r.integers(1, 3)), spread=0.008, body="wood_small",
                     body_f=dsp.vary(r, 900.0, 0.3), tail=0.2)


@sound("amb/burn_day", seed=10101, loop=True, peak_db=-4.5)
def burn_day(seed, variant, sr):
    L = 60.0
    n = dsp.ns(L, sr)
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.05, 0.45, 0.2, 1.4)
    y = 0.55 * _lfilt(dsp.normalize(_snag_wind(n, sr, seed, g)), sr, lambda x: dsp.lp(x, sr, 5500.0), 0.05)
    ev = _canvas(n)
    rr = dsp.rng(seed, "rustle")
    for _ in range(10):                              # dry fireweed and grass in the gusts
        d = rr.uniform(0.8, 2.2)
        ru = dsp.rustle(sr, d, rr, [(0, 0), (d * 0.3, 1), (d, 0)], f_lo=2000.0, f_hi=9000.0, density=900.0)
        _put(ev, _distant(ru, sr, rr.uniform(4, 15)), rr.uniform(0, L), sr, 0.035, rr.uniform(-1, 1))
    rw = dsp.rng(seed, "woodpecker")
    for k in range(5):
        near = k < 2
        dr = _woodpecker(sr, rw)
        _put(ev, dsp.normalize(_distant(dr, sr, rw.uniform(35, 60) if near else rw.uniform(90, 180))), rw.uniform(0, L), sr,
             0.5 if near else 0.25, rw.uniform(-1, 1))
    rc = dsp.rng(seed, "creaks")
    for _ in range(7):
        _put(ev, _distant(_creak_far(sr, rc, rc.uniform(1.0, 2.2)), sr, rc.uniform(20, 70)), rc.uniform(0, L), sr,
             rc.uniform(0.06, 0.12), rc.uniform(-1, 1))
    for _ in range(6):
        _put(ev, _distant(_tick(sr, rc), sr, rc.uniform(15, 50)), rc.uniform(0, L), sr, rc.uniform(0.05, 0.1), rc.uniform(-1, 1))
    rb = dsp.rng(seed, "birds")
    for t in (rb.uniform(5, 15), rb.uniform(35, 50)):
        _put(ev, dsp.normalize(_distant(_thrush(sr, rb), sr, rb.uniform(120, 200))), t, sr, 0.18, rb.uniform(-0.8, 0.8))
    ev = dsp.reverb(ev, sr, "forest", 0.3, seed=seed, stereo_=True, circular=True)
    return y + ev


@sound("amb/burn_night", seed=10102, loop=True, peak_db=-8.6)
def burn_night(seed, variant, sr):
    L = 60.0
    n = dsp.ns(L, sr)
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.04, 0.3, 0.15, 1.6) * 0.8
    y = 0.75 * dsp.normalize(_snag_wind(n, sr, seed, g))
    ev = _canvas(n)
    rc = dsp.rng(seed, "creaks")
    for _ in range(6):
        _put(ev, _distant(_creak_far(sr, rc, rc.uniform(1.0, 2.4)), sr, rc.uniform(25, 80)), rc.uniform(0, L), sr,
             rc.uniform(0.05, 0.1), rc.uniform(-1, 1))
    for _ in range(4):
        _put(ev, _distant(_tick(sr, rc), sr, rc.uniform(15, 50)), rc.uniform(0, L), sr, rc.uniform(0.04, 0.08), rc.uniform(-1, 1))
    rk = dsp.rng(seed, "crickets")
    for _ in range(2):
        cr = _cricket(sr, rk, L, rk.uniform(4200, 5100), rk.uniform(0.6, 1.2), int(rk.integers(3, 5)))
        cr *= _lfo(n, sr, rk, 0.08, 0.0, 1.0) ** 2
        dsp.loop_place(ev, dsp.pan(_distant(cr, sr, rk.uniform(10, 30)), rk.uniform(-0.9, 0.9)) * 0.03, 0)
    ro = dsp.rng(seed, "owl")
    _put(ev, dsp.normalize(_distant(_owl(sr, ro), sr, ro.uniform(100, 170))), ro.uniform(10, 25), sr, 0.2, ro.uniform(-0.8, 0.8))
    ev = dsp.reverb(ev, sr, "forest", 0.4, seed=seed, stereo_=True, circular=True)
    return y + ev


# --------------------------------------------------------------------------------------------- fen

def _bubble(sr, r):
    """Marsh gas bubbling up through the peat: a few soft low 'blups' rising in pitch."""
    k = int(r.integers(1, 5))
    y = np.zeros(dsp.ns(0.12 * k + 0.3, sr))
    for i in range(k):
        d = r.uniform(0.04, 0.09)
        m = dsp.ns(d + 0.05, sr)
        f = dsp.curve([(0, r.uniform(110, 190)), (d, r.uniform(260, 480))], m, sr, "smooth")
        env = _note_env(m, sr, d + 0.04, 0.004, 0.035, 0.5)
        dsp.place(y, dsp.sine(f, m, sr) * env, dsp.ns(i * r.uniform(0.05, 0.12), sr), r.uniform(0.5, 1.0))
    return dsp.lp(y, sr, 1200.0)


def _fly(sr, r):
    """A fly or mosquito passing: a buzzing tone whose pitch and level swell and fade (Doppler)."""
    d = r.uniform(1.2, 2.6)
    m = dsp.ns(d, sr)
    f0 = r.uniform(170.0, 240.0) if r.random() < 0.7 else r.uniform(420.0, 560.0)
    f = dsp.curve([(0, f0 * 1.04), (d * 0.5, f0), (d, f0 * 0.95)], m, sr, "smooth") * (1.0 + 0.02 * dsp.smooth_noise(m, sr, r, 9.0))
    buzz = dsp.saw(f, m, sr)
    buzz = dsp.bp(buzz, sr, f0 * 3.0, 1.2) + 0.4 * dsp.bp(buzz, sr, f0 * 6.0, 2.0)
    env = dsp.curve([(0, 0), (d * 0.45, 1.0), (d * 0.55, 1.0), (d, 0)], m, sr, "smooth")
    return dsp.normalize(buzz * env)


@sound("amb/fen_day", seed=10201, loop=True, peak_db=-6.0)
def fen_day(seed, variant, sr):
    L = 60.0
    n = dsp.ns(L, sr)
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.05, 0.4, 0.2, 1.5) * 0.7
    kw = dict(lo=500.0, hi=1600.0, q=0.6, needles=0.35, rumble=0.08)
    reeds = _st(_wind(n, sr, dsp.rng(seed, "wl"), g, **kw), _wind(n, sr, dsp.rng(seed, "wr"), np.roll(g, dsp.ns(0.7, sr)), **kw))
    y = 0.35 * _lfilt(dsp.normalize(reeds), sr, lambda x: dsp.lp(x, sr, 8000.0), 0.05)
    ev = _canvas(n)
    rb = dsp.rng(seed, "bubbles")
    for _ in range(9):
        _put(ev, _distant(_bubble(sr, rb), sr, rb.uniform(3, 15)), rb.uniform(0, L), sr, rb.uniform(0.05, 0.12), rb.uniform(-1, 1))
    rf = dsp.rng(seed, "flies")
    for _ in range(6):
        _put(ev, _fly(sr, rf), rf.uniform(0, L), sr, rf.uniform(0.015, 0.04), rf.uniform(-1, 1))
    rt = dsp.rng(seed, "birds")
    t = rt.uniform(2, 8)
    while t < L:
        _put(ev, dsp.normalize(_distant(_thrush(sr, rt), sr, rt.uniform(90, 170))), t, sr, 0.22, rt.uniform(-0.8, 0.8))
        t += rt.uniform(9.0, 16.0)
    ev = dsp.reverb(ev, sr, "forest", 0.25, seed=seed, stereo_=True, circular=True)
    return y + ev


def _chorus_frog(sr, r):
    """Boreal chorus frog: a rising 'crreeeek' - a train of 12-24 rapid pulses climbing in pitch."""
    pulses = int(r.integers(12, 24))
    rate = r.uniform(45.0, 70.0)
    f0 = r.uniform(2100.0, 2600.0)
    y = np.zeros(dsp.ns(pulses / rate + 0.1, sr))
    pl = dsp.ns(0.008, sr)
    for i in range(pulses):
        f = f0 * (1.0 + 0.25 * i / pulses)
        ph = dsp.TAU * f * np.arange(pl) / sr
        pulse = np.sin(ph) * np.sin(np.pi * np.arange(pl) / pl) ** 2
        dsp.place(y, pulse, dsp.ns(i / rate, sr), 0.5 + 0.5 * i / pulses)
    return y


def _peeper(sr, r):
    """Spring peeper: a single clear rising whistle."""
    d = r.uniform(0.09, 0.14)
    m = dsp.ns(d + 0.02, sr)
    f = dsp.curve([(0, r.uniform(2600, 2900)), (d, r.uniform(3000, 3350))], m, sr, "smooth")
    return dsp.sine(f, m, sr) * _note_env(m, sr, d, 0.01, 0.02, 0.9)


def _green_frog(sr, r):
    """Green frog: a single plucked, twangy 'gunk' like a loose banjo string."""
    md = dsp.modes("wood", dsp.vary(r, 260.0, 0.15), r, count=6, t60=0.25)
    hit = dsp.impact(sr, r, modes_=md, contact_ms=1.5, click=0.1, dur=0.35)
    return dsp.lp(hit, sr, 1400.0)


@sound("amb/fen_night", seed=10202, loop=True, peak_db=-6.5)
def fen_night(seed, variant, sr):
    L = 60.0
    n = dsp.ns(L, sr)
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.04, 0.3, 0.15, 1.6) * 0.5
    kw = dict(lo=400.0, hi=1300.0, q=0.6, needles=0.25, rumble=0.06)
    reeds = _st(_wind(n, sr, dsp.rng(seed, "wl"), g, **kw), _wind(n, sr, dsp.rng(seed, "wr"), np.roll(g, dsp.ns(0.9, sr)), **kw))
    y = 0.25 * dsp.normalize(reeds)
    ev = _canvas(n)
    rf = dsp.rng(seed, "frogs")
    # A chorus: each frog calls on its own beat, the whole chorus swelling and hushing together.
    swell = _lfo(n, sr, dsp.rng(seed, "swell"), 0.05, 0.35, 1.0)
    for k in range(10):
        dist = rf.uniform(6, 60)
        pan = rf.uniform(-1, 1)
        period = rf.uniform(0.9, 2.2)
        t = rf.uniform(0, period)
        lane = np.zeros(n)
        while t < L:
            if rf.random() < 0.8:
                dsp.loop_place(lane, _chorus_frog(sr, rf), dsp.ns(t, sr))
            t += period * rf.uniform(0.85, 1.15)
        lane = _distant(lane * swell, sr, dist)
        dsp.loop_place(ev, dsp.pan(lane, pan) * (0.12 if dist < 20 else 0.07), 0)
    for k in range(6):
        period = rf.uniform(0.8, 1.4)
        t = rf.uniform(0, period)
        lane = np.zeros(n)
        while t < L:
            dsp.loop_place(lane, _peeper(sr, rf), dsp.ns(t, sr))
            t += period * rf.uniform(0.9, 1.1)
        lane = _distant(lane * swell, sr, rf.uniform(15, 70))
        dsp.loop_place(ev, dsp.pan(lane, rf.uniform(-1, 1)) * 0.05, 0)
    for _ in range(5):
        _put(ev, _distant(_green_frog(sr, rf), sr, rf.uniform(8, 30)), rf.uniform(0, L), sr, 0.2, rf.uniform(-1, 1))
    rk = dsp.rng(seed, "crickets")
    for _ in range(3):
        cr = _cricket(sr, rk, L, rk.uniform(4000, 5200), rk.uniform(0.5, 1.0), int(rk.integers(3, 6)))
        cr *= _lfo(n, sr, rk, 0.08, 0.0, 1.0) ** 2
        dsp.loop_place(ev, dsp.pan(_distant(cr, sr, rk.uniform(8, 25)), rk.uniform(-0.9, 0.9)) * 0.03, 0)
    rb = dsp.rng(seed, "bubbles")
    for _ in range(6):
        _put(ev, _distant(_bubble(sr, rb), sr, rb.uniform(3, 15)), rb.uniform(0, L), sr, rb.uniform(0.04, 0.09), rb.uniform(-1, 1))
    ev = dsp.reverb(ev, sr, "forest", 0.35, seed=seed, stereo_=True, circular=True)
    return y + ev
