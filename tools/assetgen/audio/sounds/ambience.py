"""Ambience beds (stereo, seamless loops) and fire loops (mono, positional).

Loop construction: every continuous layer is periodic by construction (FFT-generated noise of exactly
the loop length, periodic control curves, time-varying filters run with a wrap-around pre-roll), and
every discrete event (bird phrase, drip, creak, groan) is placed on a circular canvas so whatever runs
past the end continues at the start. Reverb is circular convolution. The seam is therefore continuous
in waveform, spectrum and level.

Hollowmere: a northern conifer/birch valley in late autumn, an abandoned 1990s logging town, and the
Hum - a seismic exhale from the fungal colony every 7th night that draws every Hollowed to the player.
"""
from __future__ import annotations

import math

import numpy as np

from .. import dsp
from ..registry import sound

AMB = -6.0


# --------------------------------------------------------------------------------------------- loop helpers

def _pn(n, sr, r, slope=-3.0, lo=20.0, hi=16000.0):
    """Periodic band-limited coloured noise (unit RMS)."""
    k = slope / (20.0 * math.log10(2.0))
    return dsp._spec_shape(n, r, lambda f: (f / 1000.0) ** k * dsp.smoothstep((f - lo) / lo)
                           / (1.0 + (f / hi) ** 4), sr)


def _lfo(n, sr, r, rate, lo=0.0, hi=1.0):
    x = dsp.smooth_noise(n, sr, r, rate, periodic=True)
    x = (x - x.min()) / max(x.max() - x.min(), 1e-9)
    return lo + (hi - lo) * x


def _gust(n, sr, r, slow=0.06, fast=0.5, floor=0.2, shape=1.3):
    g = 0.65 * _lfo(n, sr, r, slow) + 0.35 * _lfo(n, sr, r, fast)
    g = (g - g.min()) / max(g.max() - g.min(), 1e-9)
    return floor + (1.0 - floor) * g ** shape


def _ltv(x, sr, kind, f, q=0.7071, gain_db=0.0, pre=0.6):
    """Time-varying biquad on a loop (state wraps around via pre-roll)."""
    P = min(dsp.ns(pre, sr), len(x))
    wrap = lambda a: np.concatenate([a[-P:], a]) if isinstance(a, np.ndarray) and a.shape[0] == len(x) else a
    y = dsp.biquad(wrap(x), sr, kind, wrap(f), wrap(q), wrap(gain_db), block=256)
    return y[P:]


def _lfilt(x, sr, fn, pre=0.6):
    return dsp.circular(fn, x, sr, pre)


def _fold(y, n):
    """Folds a render longer than the loop back onto its start (wrap events that ran past the end)."""
    out = np.array(y[:n], copy=True)
    k = len(y) - n
    while k > 0:
        m = min(k, n)
        out[:m] += y[len(y) - k:len(y) - k + m]
        k -= m
    return out


def _canvas(n):
    return np.zeros((n, 2))


def _put(canvas, sig, t, sr, gain=1.0, pan=0.0):
    """Mono event -> panned onto the stereo loop canvas (wraps)."""
    dsp.loop_place(canvas, dsp.pan(sig, pan) * gain, dsp.ns(t, sr) % canvas.shape[0])


def _distant(sig, sr, dist, foliage=0.4):
    return dsp.air(dsp.hp(sig, sr, 150.0), sr, dist, foliage)


def _st(l, r_):
    return np.stack([l, r_], axis=1)


def _finish_bed(y, sr, room=None, mix=0.0, seed=0):
    if room:
        y = dsp.reverb(y, sr, room, mix, seed=seed, stereo_=True, circular=True)
    return y


# --------------------------------------------------------------------------------------------- building blocks

def _wind(n, sr, r, g, *, lo=250.0, hi=1100.0, q=0.7, needles=0.15, rumble=0.3, howl=0.0, howl_f=(380.0, 900.0)):
    """Wind through conifers ('soughing'): gust-driven band of pink noise peaking ~0.3-1 kHz whose centre
    rises with gust strength and rolls off above ~2 kHz, a little needle hiss on strong gusts, low rumble,
    optional whistling howl (narrow moving resonances)."""
    src = _pn(n, sr, r, -3.0, 60.0, 5000.0)
    fc = lo + (hi - lo) * g
    y = _ltv(src, sr, "bp", fc, q) * g ** 1.6
    if needles:
        hs = _ltv(_pn(n, sr, r, -3.0, 2000.0, 9000.0), sr, "hp", 3000.0 + 2000.0 * g, 0.7)
        y = y + needles * hs * g ** 3.0
    if rumble:
        rb = _pn(n, sr, r, -6.0, 25.0, 180.0) * (0.35 + 0.65 * g)
        y = y + rumble * rb
    if howl:
        h = np.zeros(n)
        for k in range(2):
            fw = howl_f[0] + (howl_f[1] - howl_f[0]) * (0.6 * g + 0.4 * _lfo(n, sr, r, 0.15))
            h += _ltv(dsp.white(n, r), sr, "bp", fw * (1.0 + 0.5 * k), 30.0 + 10 * k) * g ** 2.5
        y = y + howl * dsp.normalize(h) * dsp.rms(y) * 4.0
    return y


def _leaves(n, sr, r, g, density=900.0):
    """Dry autumn leaves fluttering on birches/aspens; activity follows the gusts."""
    tail = dsp.ns(0.3, sr)
    rate = np.concatenate([density * g ** 2.2, np.zeros(tail)])
    y = dsp.clicks(n + tail, sr, r, rate, 1800.0, 9500.0, q=2.6, alpha=1.8, groups=10)
    return _fold(y, n)


def _note_env(m, sr, d, att=0.02, rel=0.04, end=0.8, shape="smooth"):
    """Sustained call/note envelope: soft attack, held (slightly falling) body, soft release; zero after d."""
    att = min(att, d * 0.4)
    rel = min(rel, d * 0.4)
    return dsp.curve([(0.0, 0.0), (att, 1.0), (max(att, d - rel), end), (d, 0.0)], m, sr, shape)


def _thrush(sr, r):
    """Hermit-thrush-like phrase: a pure introductory whistle, then a tumbling flutey cascade higher up."""
    base = dsp.loguni(r, 1900.0, 3100.0)
    notes = [(0.0, r.uniform(0.22, 0.38), base, base * r.uniform(0.97, 1.03), 1.0)]
    t = notes[0][1] + r.uniform(0.02, 0.06)
    hi = base * r.uniform(1.35, 1.8)
    for _ in range(int(r.integers(6, 13))):
        d = r.uniform(0.03, 0.065)
        f = hi * dsp.semis(r.choice([0, 3, 5, 7, 8, 12, -2])) * r.uniform(0.98, 1.02)
        notes.append((t, d, f, f * r.uniform(0.92, 1.08), r.uniform(0.35, 0.8)))
        t += d * r.uniform(0.7, 1.05)
    n = dsp.ns(t + 0.15, sr)
    y = np.zeros(n)
    for t0, d, f0, f1, a in notes:
        m = dsp.ns(d + 0.03, sr)
        f = dsp.curve([(0, f0), (d, f1)], m, sr) * (1.0 + 0.012 * np.sin(dsp.TAU * dsp.phase(r.uniform(30, 55), m, sr)))
        env = _note_env(m, sr, d, 0.025 if d > 0.15 else 0.008, 0.05 if d > 0.15 else 0.012, 0.75)
        tone = (dsp.sine(f, m, sr) + 0.06 * dsp.sine(2 * f, m, sr)) * env
        dsp.place(y, tone, dsp.ns(t0, sr), a)
    return y


def _jay(sr, r):
    """Jay: harsh nasal screech, 2-3 calls."""
    out = np.zeros(dsp.ns(1.6, sr))
    t = 0.0
    for _ in range(int(r.integers(2, 4))):
        d = r.uniform(0.25, 0.42)
        m = dsp.ns(d, sr)
        f0 = dsp.curve([(0, r.uniform(1050, 1350)), (d * 0.3, r.uniform(1400, 1700)), (d, r.uniform(800, 1000))], m, sr, "smooth")
        src = dsp.saw(f0 * (1 + 0.02 * dsp.smooth_noise(m, sr, r, 90.0)), m, sr)
        src = src * (0.6 + 0.4 * dsp.smooth_noise(m, sr, r, 110.0)) + 0.6 * dsp.band_noise(m, sr, r, 1200.0, 6000.0)
        y = dsp.bp(src, sr, 2300.0, 2.5) + 0.8 * dsp.bp(src, sr, 3700.0, 3.0) + 0.4 * dsp.bp(src, sr, 5200.0, 3.0)
        y *= _note_env(m, sr, d, 0.015, 0.06, 0.6)
        dsp.place(out, y, dsp.ns(t, sr))
        t += d + r.uniform(0.12, 0.3)
    return out


def _woodpecker(sr, r):
    taps = int(r.integers(12, 24))
    rate = r.uniform(14.0, 19.0)
    y = np.zeros(dsp.ns(taps / rate + 0.3, sr))
    t = 0.0
    md = dsp.modes("wood", dsp.vary(r, 900.0, 0.2), r, count=10, t60=0.05)
    for i in range(taps):
        a = 1.0 - 0.5 * (i / taps)
        dsp.place(y, dsp.impact(sr, r, modes_=md, contact_ms=0.25, click=0.4, dur=0.08), dsp.ns(t, sr), a)
        t += 1.0 / (rate * (1.0 - 0.15 * i / taps))
    return y


def _owl(sr, r):
    """Great-horned-type hooting: 'hoo, hoo-hoo, hoooo, hoo, hoo' - soft, breathy, ~300 Hz."""
    f = r.uniform(270.0, 360.0)
    pattern = [(0.0, 0.32), (0.55, 0.16), (0.76, 0.16), (1.05, 0.7), (1.95, 0.3), (2.45, 0.3)]
    y = np.zeros(dsp.ns(3.0, sr))
    for t0, d in pattern:
        m = dsp.ns(d + 0.08, sr)
        fc = dsp.curve([(0, f * 0.93), (d * 0.3, f), (d, f * 0.9)], m, sr, "smooth")
        if d > 0.5:
            fc = fc * (1.0 + 0.012 * np.sin(dsp.TAU * dsp.phase(11.0, m, sr)))
        env = _note_env(m, sr, d + 0.06, 0.06, 0.12, 0.7)
        tone = dsp.sine(fc, m, sr) + 0.12 * dsp.sine(2 * fc, m, sr) + 0.04 * dsp.sine(3 * fc, m, sr)
        br = dsp.bp(dsp.white(m, r), sr, fc * 2, 4.0) * 0.15
        dsp.place(y, (tone + br) * env, dsp.ns(t0, sr))
    return y


def _cricket(sr, r, dur, f, period, pulses):
    """One cricket over `dur` seconds: chirps of a few carrier pulses (sine ~4-5 kHz)."""
    n = dsp.ns(dur, sr)
    y = np.zeros(n)
    pl = dsp.ns(0.014, sr)
    pw = np.sin(np.pi * np.arange(pl) / pl) ** 2
    t = r.uniform(0, period)
    while t < dur:
        if r.random() < 0.85:
            for k in range(pulses):
                k0 = dsp.ns(t + k * 0.032, sr)
                m = min(pl, n - k0)
                if m <= 0:
                    break
                ph = dsp.TAU * f * (np.arange(m) + k0) / sr
                y[k0:k0 + m] += np.sin(ph) * pw[:m]
        t += period * r.uniform(0.9, 1.1)
    return y


def _creak_far(sr, r, dur):
    k = int(r.integers(3, 6))
    ts = np.sort(r.uniform(0.05, dur - 0.05, k))
    rate = [(0.0, 20.0)] + [(t, dsp.loguni(r, 20.0, 160.0)) for t in ts] + [(dur, 25.0)]
    amp = [(0.0, 0.0), (dur * 0.2, 0.8)] + [(t, r.uniform(0.4, 1.0)) for t in ts] + [(dur, 0.0)]
    res = [(dsp.vary(r, 260.0, 0.2), 7.0, 1.0), (dsp.vary(r, 520.0, 0.2), 9.0, 0.7), (dsp.vary(r, 1000.0, 0.2), 11.0, 0.4)]
    return dsp.normalize(dsp.creak(sr, dur, r, rate, amp, res=res, jitter=0.2, pulse_ms=0.7, bright=1500.0))


def _groan(sr, r, dur, f=70.0):
    """A distant Hollowed moan (for the Hum chorus)."""
    f0 = [(0, f * r.uniform(0.9, 1.1)), (dur * r.uniform(0.3, 0.6), f * r.uniform(1.0, 1.35)), (dur, f * r.uniform(0.6, 0.85))]
    vow = [(0, dsp.pick(r, ["uh", "o", "a"])), (dur * 0.5, dsp.pick(r, ["a", "o", "oo"])), (dur, dsp.pick(r, ["u", "m"]))]
    amp = [(0, 0), (dur * 0.35, 1.0), (dur * 0.7, 0.7), (dur, 0)]
    v = dsp.voice(sr, dur, f0, vow, amp, r, oq=0.4, jitter=0.06, shimmer=0.15, sub=r.uniform(0.2, 0.5), rough=0.4,
                  breath=0.1, tract=0.86, bw=1.6, os=1, hop_ms=25.0)
    return dsp.normalize(v)


# --------------------------------------------------------------------------------------------- beds

@sound("amb/forest_day", seed=10001, loop=True, peak_db=-3.7)
def forest_day(seed, variant, sr):
    """Autumn conifer forest by day: gusty wind in the crowns, birch leaves fluttering, a hermit thrush's
    flute phrases near and far, jays scolding, a woodpecker drumming, a distant trunk creaking."""
    L = 60.0
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "fday")
    gc = _gust(n, sr, dsp.rng(seed, "g"), 0.05, 0.4, 0.25)
    gl = np.clip(gc * (0.85 + 0.3 * _lfo(n, sr, r, 0.2) - 0.15), 0, 1)
    gr = np.clip(gc * (0.85 + 0.3 * _lfo(n, sr, r, 0.2) - 0.15), 0, 1)
    wind = _st(_wind(n, sr, dsp.rng(seed, "wl"), gl), _wind(n, sr, dsp.rng(seed, "wr"), gr))
    leaves = _st(_leaves(n, sr, dsp.rng(seed, "ll"), gl), _leaves(n, sr, dsp.rng(seed, "lr"), gr))
    y = 0.5 * _lfilt(dsp.normalize(wind), sr, lambda x: dsp.lp(x, sr, 7000.0), 0.05) + 0.08 * dsp.normalize(leaves)
    ev = _canvas(n)
    rb = dsp.rng(seed, "birds")
    t = rb.uniform(0.5, 2.0)
    while t < L:                                    # thrushes: a near one and a far one
        near = rb.random() < 0.45
        ph = _thrush(sr, rb)
        ph = _distant(ph, sr, rb.uniform(25, 45) if near else rb.uniform(70, 140))
        _put(ev, dsp.normalize(ph), t, sr, 1.0 if near else 0.4, rb.uniform(-0.8, 0.8))
        t += rb.uniform(3.5, 8.0)
    for _ in range(3):
        _put(ev, dsp.normalize(_distant(_jay(sr, rb), sr, rb.uniform(50, 120))), rb.uniform(0, L), sr, 0.35, rb.uniform(-1, 1))
    for _ in range(2):
        _put(ev, dsp.normalize(_distant(_woodpecker(sr, rb), sr, rb.uniform(80, 160))), rb.uniform(0, L), sr, 0.3,
             rb.uniform(-1, 1))
    for _ in range(2):
        _put(ev, _distant(_creak_far(sr, rb, rb.uniform(1.0, 1.8)), sr, 60.0), rb.uniform(0, L), sr, 0.05, rb.uniform(-1, 1))
    ev = dsp.reverb(ev, sr, "forest", 0.45, seed=seed, stereo_=True, circular=True)
    y = y + ev
    return y


@sound("amb/forest_night", seed=10002, loop=True, peak_db=-8.6)
def forest_night(seed, variant, sr):
    """Forest at night: low wind, sparse late-season crickets, a distant owl, the odd twig snapping."""
    L = 60.0
    n = dsp.ns(L, sr)
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.04, 0.3, 0.15, 1.6) * 0.75
    wind = _st(_wind(n, sr, dsp.rng(seed, "wl"), g, lo=200.0, hi=900.0, needles=0.08),
               _wind(n, sr, dsp.rng(seed, "wr"), np.roll(g, dsp.ns(1.5, sr)), lo=200.0, hi=900.0, needles=0.08))
    y = 0.8 * dsp.normalize(wind)
    ev = _canvas(n)
    rc = dsp.rng(seed, "crickets")
    for _k in range(3):
        cr = _cricket(sr, rc, L, rc.uniform(4100, 5200), rc.uniform(0.55, 1.1), int(rc.integers(3, 6)))
        cr *= _lfo(n, sr, rc, 0.08, 0.0, 1.0) ** 2                      # crickets pause and resume
        cr = _distant(cr, sr, rc.uniform(8, 30))
        dsp.loop_place(ev, dsp.pan(cr, rc.uniform(-0.9, 0.9)) * rc.uniform(0.02, 0.05), 0)
    ro = dsp.rng(seed, "owl")
    for t in (ro.uniform(3, 10), ro.uniform(30, 40)):
        _put(ev, dsp.normalize(_distant(_owl(sr, ro), sr, ro.uniform(90, 160))), t, sr, 0.22, ro.uniform(-0.8, 0.8))
    rt = dsp.rng(seed, "twigs")
    for _ in range(4):
        c = dsp.crack(sr, rt, 0.15, n_clicks=int(rt.integers(1, 4)), spread=0.01, body="wood_small",
                      body_f=dsp.vary(rt, 1300.0, 0.3), tail=0.15)
        _put(ev, _distant(c, sr, rt.uniform(15, 40)), rt.uniform(0, L), sr, rt.uniform(0.04, 0.09), rt.uniform(-1, 1))
    for _ in range(3):                               # leaf drops / small movements
        ru = dsp.rustle(sr, 0.5, rt, [(0, 0), (0.1, 1), (0.5, 0)], f_lo=1500.0, f_hi=8000.0, density=600.0)
        _put(ev, _distant(ru, sr, 20.0), rt.uniform(0, L), sr, 0.02, rt.uniform(-1, 1))
    ev = dsp.reverb(ev, sr, "forest", 0.5, seed=seed, stereo_=True, circular=True)
    return y + ev


@sound("amb/wind_strong", seed=10003, loop=True, peak_db=-6.5)
def wind_strong(seed, variant, sr):
    """Storm wind: big gusts roaring through the canopy, howling resonances, branches creaking, leaf bursts."""
    L = 40.0
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "storm")
    gc = _gust(n, sr, dsp.rng(seed, "g"), 0.09, 0.7, 0.35, 1.2)
    gl = np.clip(gc + 0.15 * (_lfo(n, sr, r, 0.3) - 0.5), 0, 1)
    gr = np.clip(np.roll(gc, dsp.ns(0.7, sr)) + 0.15 * (_lfo(n, sr, r, 0.3) - 0.5), 0, 1)
    kw = dict(lo=380.0, hi=2000.0, q=0.6, needles=0.4, rumble=0.45, howl=0.25)
    wind = _st(_wind(n, sr, dsp.rng(seed, "wl"), gl, **kw), _wind(n, sr, dsp.rng(seed, "wr"), gr, **kw))
    leaves = _st(_leaves(n, sr, dsp.rng(seed, "ll"), gl, 2500.0), _leaves(n, sr, dsp.rng(seed, "lr"), gr, 2500.0))
    y = dsp.normalize(wind) + 0.15 * dsp.normalize(leaves)
    ev = _canvas(n)
    re = dsp.rng(seed, "creaks")
    for _ in range(5):
        _put(ev, _creak_far(sr, re, re.uniform(1.2, 2.4)), re.uniform(0, L), sr, re.uniform(0.04, 0.09), re.uniform(-1, 1))
    for _ in range(3):
        c = dsp.crack(sr, re, 0.2, n_clicks=int(re.integers(2, 4)), spread=0.012, body="wood_small",
                      body_f=dsp.vary(re, 1000.0, 0.3), tail=0.2)
        _put(ev, _distant(c, sr, 40.0), re.uniform(0, L), sr, 0.05, re.uniform(-1, 1))
    ev = dsp.reverb(ev, sr, "forest", 0.4, seed=seed, stereo_=True, circular=True)
    return y + ev


def _rain(n, sr, r, density, *, leaf=1.0, puddle=0.3, hiss=0.3, drips=3.0):
    """Rain: drops ticking on leaves/needles (resonant clicks), drops into puddles (small bubbles), a fine
    hiss bed, and heavier drips falling off branches."""
    tail = dsp.ns(0.4, sr)
    m = n + tail
    mod = 0.85 + 0.15 * np.concatenate([_lfo(n, sr, r, 0.15), np.zeros(tail)])
    tick = dsp.clicks(m, sr, r, density * mod, 900.0, 9000.0, q=2.6, alpha=2.0, groups=14, follow=0.0)
    y = dsp.normalize(_fold(tick, n)) * leaf
    if puddle:
        pb = dsp.bubbles(m, sr, r, density * 0.04, 900.0, 5000.0, alpha=2.2, rise=(0.0, 0.3))
        y = y + puddle * dsp.normalize(_fold(pb, n))
    if hiss:
        y = y + hiss * _pn(n, sr, r, -2.0, 350.0, 10000.0) * 0.25 * mod[:n]
    if drips:
        times = dsp.poisson(r, n / sr, drips, sr)
        dd = np.zeros(m)
        for t in times:
            dsp.place(dd, dsp.impact(sr, r, "wood_small", dsp.loguni(r, 1200.0, 3000.0), 0.06, contact_ms=0.3, t60=0.03,
                                     click=0.5), dsp.ns(t, sr), r.uniform(0.3, 1.0))
        y = y + 0.35 * dsp.normalize(_fold(dd, n))
    return y


@sound("amb/rain_light", seed=10004, loop=True, peak_db=-7.2)
def rain_light(seed, variant, sr):
    L = 40.0
    n = dsp.ns(L, sr)
    y = _st(_rain(n, sr, dsp.rng(seed, "l"), 260.0, puddle=0.25, hiss=0.35, drips=4.0),
            _rain(n, sr, dsp.rng(seed, "r"), 260.0, puddle=0.25, hiss=0.35, drips=4.0))
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.05, 0.3, 0.1, 1.8) * 0.5
    w = _wind(n, sr, dsp.rng(seed, "w"), g, lo=250.0, hi=1200.0, needles=0.1)
    y = dsp.normalize(y) + 0.25 * dsp.normalize(w)[:, None]
    return dsp.reverb(y, sr, "forest", 0.25, seed=seed, stereo_=True, circular=True)


@sound("amb/rain_heavy", seed=10005, loop=True, peak_db=-9.6)
def rain_heavy(seed, variant, sr):
    L = 40.0
    n = dsp.ns(L, sr)
    y = _st(_rain(n, sr, dsp.rng(seed, "l"), 2200.0, puddle=0.5, hiss=1.0, drips=10.0),
            _rain(n, sr, dsp.rng(seed, "r"), 2200.0, puddle=0.5, hiss=1.0, drips=10.0))
    rr = dsp.rng(seed, "rumble")
    body = _st(_pn(n, sr, rr, -3.0, 80.0, 900.0), _pn(n, sr, rr, -3.0, 80.0, 900.0))
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.07, 0.5, 0.3, 1.3)
    w = _wind(n, sr, dsp.rng(seed, "w"), g, lo=300.0, hi=1800.0, needles=0.2)
    y = dsp.normalize(y) + 0.35 * dsp.normalize(body) + 0.3 * dsp.normalize(w)[:, None]
    return dsp.reverb(y, sr, "forest", 0.3, seed=seed, stereo_=True, circular=True)


def _water_flow(n, sr, r, babble=600.0, roar=0.5, f_lo=250.0, f_hi=2600.0):
    """Turbulent stream: dense babble of resonant bubbles, broadband rush with slow surges, low roar."""
    tail = dsp.ns(0.4, sr)
    surge = _lfo(n, sr, r, 0.25, 0.6, 1.0) * _lfo(n, sr, r, 1.3, 0.75, 1.0)
    rate = np.concatenate([babble * surge, babble * surge[:tail]])
    bb = _fold(dsp.bubbles(n + tail, sr, r, rate, f_lo, f_hi, alpha=1.8, rise=(0.2, 1.2)), n)
    rush = _ltv(_pn(n, sr, r, -2.0, 150.0, 9000.0), sr, "bp", 700.0 + 900.0 * surge, 0.5) * surge
    low = _pn(n, sr, r, -5.0, 40.0, 350.0) * surge
    return dsp.normalize(bb) + 0.6 * dsp.normalize(rush) + roar * dsp.normalize(low)


@sound("amb/river", seed=10006, loop=True, peak_db=-7.6)
def river(seed, variant, sr):
    """Shallow rocky river: babbling over stones, broadband rush, low roar; wide stereo."""
    L = 40.0
    n = dsp.ns(L, sr)
    a = _water_flow(n, sr, dsp.rng(seed, "a"), 650.0, 0.5)
    b = _water_flow(n, sr, dsp.rng(seed, "b"), 650.0, 0.5)
    c = _water_flow(n, sr, dsp.rng(seed, "c"), 300.0, 0.3, 500.0, 4000.0)          # a riffle nearby, brighter
    y = _st(a + 0.5 * c, b + 0.35 * c)
    ev = _canvas(n)
    rs = dsp.rng(seed, "slosh")
    for _ in range(10):
        sp = dsp.splash(sr, rs, rs.uniform(0.3, 0.6), 0.7)
        _put(ev, dsp.normalize(sp), rs.uniform(0, L), sr, rs.uniform(0.08, 0.18), rs.uniform(-0.9, 0.9))
    return dsp.reverb(y + ev, sr, "forest", 0.2, seed=seed, stereo_=True, circular=True)


def _wave(sr, r, size=1.0):
    """One small lake wave: swell, lap on the stones, fizzy retreat with pebbles rattling."""
    d = r.uniform(2.2, 3.4)
    n = dsp.ns(d, sr)
    t = np.arange(n) / sr
    tl = r.uniform(0.5, 0.8)
    swell = dsp.lp(dsp.pink(n, r), sr, 600.0) * np.exp(-((t - tl) / 0.35) ** 2)
    lap = dsp.band_noise(n, sr, r, 400.0, 5000.0) * np.where(t >= tl, np.exp(-(t - tl) / 0.12), np.exp((t - tl) / 0.06))
    ret_env = np.where(t >= tl + 0.1, np.exp(-(t - tl - 0.1) / r.uniform(0.6, 1.0)), 0.0) * \
        np.minimum(1.0, np.maximum(t - tl, 0) / 0.15)
    fizz = dsp.clicks(n, sr, r, ret_env * 2500.0 * size, 1500.0, 9000.0, q=3.0, alpha=2.0)
    peb = dsp.clicks(n, sr, r, ret_env * 120.0 * size, 2000.0, 6000.0, q=10.0, alpha=1.5)
    bub = dsp.bubbles(n, sr, r, ret_env * 80.0, 800.0, 3500.0, alpha=2.2)
    y = 0.6 * dsp.normalize(swell) + 0.8 * dsp.normalize(lap) + 0.45 * dsp.normalize(fizz) + 0.2 * dsp.normalize(peb) + \
        0.25 * dsp.normalize(bub)
    return y * size


def _loon(sr, r):
    """Distant loon wail: a slow, rising-falling tonal call with a break - the lake's loneliest sound."""
    d = r.uniform(2.2, 3.0)
    n = dsp.ns(d, sr)
    f = dsp.curve([(0, 560.0), (0.4, 740.0), (d * 0.45, 760.0), (d * 0.5, 1020.0), (d * 0.85, 990.0), (d, 860.0)], n, sr,
                  "smooth") * dsp.vibrato(n, sr, 5.0, 12.0, r, 0.3, onset=0.5)
    env = dsp.curve([(0, 0), (0.25, 1.0), (d * 0.45, 0.9), (d * 0.48, 0.5), (d * 0.55, 1.0), (d * 0.85, 0.8), (d, 0)], n, sr,
                    "smooth")
    y = (dsp.sine(f, n, sr) + 0.3 * dsp.sine(2 * f, n, sr) + 0.08 * dsp.sine(3 * f, n, sr)) * env
    return y


@sound("amb/lake_shore", seed=10007, loop=True, peak_db=-3.6)
def lake_shore(seed, variant, sr):
    """Still northern lake: small waves lapping on stones, a light breeze in the reeds, a loon far off."""
    L = 45.0
    n = dsp.ns(L, sr)
    ev = _canvas(n)
    rw = dsp.rng(seed, "waves")
    t = 0.0
    while t < L:
        w = _wave(sr, rw, rw.uniform(0.6, 1.0))
        _put(ev, w, t, sr, 0.5, rw.uniform(-0.6, 0.6))
        t += rw.uniform(2.5, 5.0)
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.05, 0.4, 0.2, 1.5) * 0.6
    breeze = _st(_wind(n, sr, dsp.rng(seed, "wl"), g, lo=300.0, hi=1800.0, needles=0.1),
                 _wind(n, sr, dsp.rng(seed, "wr"), np.roll(g, dsp.ns(2.0, sr)), lo=300.0, hi=1800.0, needles=0.1))
    reeds = _st(_leaves(n, sr, dsp.rng(seed, "rl"), g, 500.0), _leaves(n, sr, dsp.rng(seed, "rr"), g, 500.0))
    rl = dsp.rng(seed, "loon")
    _put(ev, dsp.normalize(_distant(_loon(sr, rl), sr, 400.0, 0.0)), rl.uniform(10, 30), sr, 0.06, rl.uniform(-0.7, 0.7))
    ev = dsp.reverb(ev, sr, "valley", 0.3, seed=seed, stereo_=True, circular=True)
    return dsp.normalize(ev) + 0.3 * dsp.normalize(breeze) + 0.05 * dsp.normalize(reeds)


@sound("amb/interior_house", seed=10008, loop=True, peak_db=-12.0)
def interior_house(seed, variant, sr):
    """Abandoned house: dead air (no power), muffled wind against the walls, the frame settling and
    creaking, a slow drip from the roof into a puddle."""
    L = 45.0
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "house")
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.06, 0.4, 0.2, 1.5)
    outside = _wind(n, sr, dsp.rng(seed, "w"), g, lo=200.0, hi=900.0, needles=0.0, rumble=0.5)
    outside = _lfilt(outside, sr, lambda x: dsp.lp(x, sr, 500.0, order=4))
    tone = _pn(n, sr, r, -4.0, 30.0, 2500.0)
    y = _st(0.8 * dsp.normalize(outside) + 0.12 * tone, 0.8 * dsp.normalize(np.roll(outside, dsp.ns(0.4, sr))) + 0.12 * _pn(n, sr, r, -4.0, 30.0, 2500.0))
    ev = _canvas(n)
    rc = dsp.rng(seed, "creaks")
    for _ in range(5):
        d = rc.uniform(0.6, 1.6)
        k = int(rc.integers(3, 6))
        ts = np.sort(rc.uniform(0.05, d - 0.05, k))
        rate = [(0.0, 15.0)] + [(t, dsp.loguni(rc, 15.0, 120.0)) for t in ts] + [(d, 15.0)]
        amp = [(0, 0), (d * 0.2, 0.8)] + [(t, rc.uniform(0.3, 1.0)) for t in ts] + [(d, 0)]
        cr = dsp.creak(sr, d, rc, rate, amp, res=[(dsp.vary(rc, 240.0, 0.2), 8.0, 1.0), (dsp.vary(rc, 520.0, 0.2), 9.0, 0.7),
                                                  (dsp.vary(rc, 1100.0, 0.2), 11.0, 0.4)], jitter=0.2, bright=1800.0)
        _put(ev, dsp.normalize(cr), rc.uniform(0, L), sr, rc.uniform(0.12, 0.25), rc.uniform(-0.9, 0.9))
    for _ in range(6):
        tk = dsp.impact(sr, rc, "wood", dsp.loguni(rc, 300.0, 900.0), 0.12, contact_ms=0.6, t60=0.05, click=0.3)
        _put(ev, tk, rc.uniform(0, L), sr, rc.uniform(0.03, 0.08), rc.uniform(-1, 1))
    rd = dsp.rng(seed, "drip")
    pan = rd.uniform(-0.5, 0.5)
    t = rd.uniform(0.0, 2.0)
    period = rd.uniform(2.2, 3.2)
    while t < L - 0.1:
        _put(ev, dsp.drip(sr, rd, dsp.vary(rd, 1450.0, 0.06), plink=0.8, splat=0.5), t, sr, 0.2, pan)
        t += period * rd.uniform(0.85, 1.25)
    ev = dsp.reverb(ev, sr, "house", 0.45, seed=seed, stereo_=True, circular=True)
    return y * 0.5 + ev


def _crow(sr, r):
    out = np.zeros(dsp.ns(2.0, sr))
    t = 0.0
    for _ in range(int(r.integers(2, 4))):
        d = r.uniform(0.28, 0.4)
        m = dsp.ns(d, sr)
        f0 = dsp.curve([(0, r.uniform(560, 650)), (d * 0.3, r.uniform(680, 760)), (d, r.uniform(480, 560))], m, sr, "smooth")
        src = dsp.saw(f0 * (1 + 0.03 * dsp.smooth_noise(m, sr, r, 80.0)), m, sr) + 0.5 * dsp.band_noise(m, sr, r, 800.0, 5000.0)
        src *= 0.7 + 0.3 * dsp.smooth_noise(m, sr, r, 60.0)
        y = dsp.bp(src, sr, 1300.0, 3.0) + 0.7 * dsp.bp(src, sr, 2100.0, 4.0) + 0.3 * dsp.bp(src, sr, 3400.0, 4.0)
        y *= _note_env(m, sr, d, 0.02, 0.07, 0.55)
        dsp.place(out, y, dsp.ns(t, sr))
        t += d + r.uniform(0.2, 0.4)
    return out


@sound("amb/town", seed=10009, loop=True, peak_db=-8.5)
def town(seed, variant, sr):
    """Abandoned logging town: wind worrying the buildings (gap whistles), a tarp flapping in the gusts, a
    sign creaking on its hinges, loose sheet metal knocking, crows."""
    L = 60.0
    n = dsp.ns(L, sr)
    g = _gust(n, sr, dsp.rng(seed, "g"), 0.07, 0.5, 0.25, 1.3)
    kw = dict(lo=280.0, hi=1400.0, needles=0.12, howl=0.35, howl_f=(450.0, 1100.0))
    wind = _st(_wind(n, sr, dsp.rng(seed, "wl"), g, **kw), _wind(n, sr, dsp.rng(seed, "wr"), np.roll(g, dsp.ns(0.8, sr)), **kw))
    y = dsp.normalize(wind)
    ev = _canvas(n)
    # tarp: flutter bursts during strong gusts
    rt = dsp.rng(seed, "tarp")
    tarp = np.zeros(n + dsp.ns(0.5, sr))
    t = 0.0
    while t < L:
        gi = g[min(n - 1, dsp.ns(t, sr))]
        if rt.random() < gi ** 1.5:
            fl = dsp.thud(sr, rt, dsp.vary(rt, 140.0, 0.2), 0.12, contact_ms=6.0, t60=0.03, noise=0.9, noise_lp=3000.0,
                          knock=0.5, knock_f=600.0)
            dsp.place(tarp, fl, dsp.ns(t, sr), gi * rt.uniform(0.5, 1.0))
        t += rt.uniform(0.07, 0.16) if gi > 0.5 else rt.uniform(0.3, 0.9)
    tarp = _fold(tarp, n) + 0.3 * _fold(dsp.cloth(sr, len(tarp) / sr, rt, np.concatenate([g, g[:len(tarp) - n]]) ** 2, heavy=1.0), n)
    dsp.loop_place(ev, dsp.pan(dsp.normalize(tarp), -0.45) * 0.25, 0)
    # sign creak on hinges, swinging with the wind
    rs = dsp.rng(seed, "sign")
    for _ in range(6):
        d = rs.uniform(0.6, 1.2)
        cr = dsp.creak(sr, d, rs, [(0, 80.0), (d * 0.5, rs.uniform(250, 600)), (d, 90.0)], [(0, 0), (d * 0.3, 1), (d, 0)],
                       res=[(dsp.vary(rs, 1300.0, 0.15), 20.0, 1.0), (dsp.vary(rs, 2500.0, 0.15), 25.0, 0.6),
                            (dsp.vary(rs, 600.0, 0.15), 10.0, 0.5)], jitter=0.1, bright=3000.0)
        _put(ev, _distant(dsp.normalize(cr), sr, 30.0), rs.uniform(0, L), sr, rs.uniform(0.05, 0.1), 0.6)
    # loose sheet metal knocking
    rm = dsp.rng(seed, "sheet")
    md = dsp.modes("metal_sheet", dsp.vary(rm, 150.0, 0.1), rm, t60=0.7)
    for _ in range(7):
        h = dsp.impact(sr, rm, modes_=md, contact_ms=rm.uniform(1.0, 3.0), click=0.3, noise=0.4, dur=1.2)
        _put(ev, _distant(h, sr, 70.0), rm.uniform(0, L), sr, rm.uniform(0.03, 0.08), -0.8)
    rc = dsp.rng(seed, "crows")
    for _ in range(2):
        _put(ev, dsp.normalize(_distant(_crow(sr, rc), sr, rc.uniform(80, 150))), rc.uniform(0, L), sr, 0.1, rc.uniform(-1, 1))
    ev = dsp.reverb(ev, sr, "town", 0.4, seed=seed, stereo_=True, circular=True)
    return y + ev


@sound("amb/the_hum", seed=10010, loop=True, peak_db=AMB + 3)
def the_hum(seed, variant, sr):
    """Horde night. The colony beneath the valley exhales: a seismic sub drone in two slowly beating
    layers, ground rumble swelling like breath, metallic resonances singing out of the rock, and from every
    direction, far off, the Hollowed answering in a chorus of groans."""
    L = 60.0
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "hum")
    breath = _lfo(n, sr, dsp.rng(seed, "breath"), 1.0 / 12.0, 0.45, 1.0)       # ~12 s exhale cycle
    # sub drone: two detuned harmonic stacks -> slow beating; frequencies quantized to whole cycles per loop
    def stack(f0, amps, r_):
        k = max(1, round(f0 * L))
        f = k / L
        out = np.zeros(n)
        tt = np.arange(n) / sr
        for h, a in enumerate(amps, start=1):
            out += a * np.sin(dsp.TAU * f * h * tt + r_.uniform(0, 6.28))
        return out
    d1 = stack(36.0, [1.0, 0.55, 0.3, 0.14, 0.06], r)
    d2 = stack(36.0 + 0.15, [1.0, 0.5, 0.25, 0.12, 0.05], r)     # 0.15 Hz beat
    d3 = stack(54.0 + 0.1, [0.5, 0.25, 0.1], r)                 # fifth above, beating against d1's 3rd
    drone = (d1 + d2 + 0.5 * d3) * breath
    drone = dsp.asym(drone / dsp.peak(drone), 1.6, 0.1)
    rumble = _pn(n, sr, r, -6.0, 18.0, 90.0) * breath ** 1.5
    mid = _ltv(_pn(n, sr, r, -3.0, 60.0, 2000.0), sr, "bp", 110.0 + 120.0 * breath, 2.0) * breath ** 2
    low = 1.0 * dsp.normalize(drone) + 0.8 * dsp.normalize(rumble)          # sub stays mono (no cancellation)
    mid2 = _ltv(_pn(n, sr, r, -3.0, 60.0, 2000.0), sr, "bp", 110.0 + 120.0 * breath, 2.0) * breath ** 2
    y = _st(low + 0.25 * dsp.normalize(mid), low + 0.25 * dsp.normalize(mid2))
    # metallic singing: inharmonic partials swelling in and out, slowly drifting
    rm = dsp.rng(seed, "metal")
    ratios = [1.0, 2.756, 5.404, 8.933]
    metl = np.zeros(n)
    metr = np.zeros(n)
    tt = np.arange(n) / sr
    for _k in range(5):
        base = rm.uniform(150.0, 420.0)
        sw = _lfo(n, sr, rm, rm.uniform(0.03, 0.08)) ** 3
        for i, ra in enumerate(ratios):
            f = max(1, round(base * ra * L)) / L
            tone = np.sin(dsp.TAU * f * tt + rm.uniform(0, 6.28)) * (0.6 ** i) * sw
            a = (rm.uniform(-0.8, 0.8) + 1.0) * np.pi / 4.0
            metl += tone * (0.6 * 1.4142 * np.cos(a))
            metr += tone * (0.6 * 1.4142 * np.sin(a))
    met = _st(metl, metr)
    # distant chorus of Hollowed
    ch = _canvas(n)
    rg = dsp.rng(seed, "chorus")
    t = 0.0
    while t < L:
        d = rg.uniform(2.0, 4.0)
        gr = _groan(sr, rg, d, rg.uniform(60.0, 110.0))
        gr = dsp.air(dsp.lp(gr, sr, 1800.0), sr, rg.uniform(150, 400), 0.5)
        _put(ch, gr, t, sr, rg.uniform(0.3, 0.7), rg.uniform(-1, 1))
        t += rg.uniform(0.4, 1.4)
    ch = dsp.reverb(ch, sr, "valley", 0.9, seed=seed, stereo_=True, circular=True)
    met = dsp.reverb(met, sr, "cave", 0.6, seed=seed + 1, stereo_=True, circular=True)
    return dsp.normalize(y) + 0.12 * dsp.normalize(met) + 0.22 * dsp.normalize(ch) * (0.6 + 0.4 * breath[:, None])


@sound("amb/cave_drips", seed=10011, loop=True, peak_db=-10.4)
def cave_drips(seed, variant, sr):
    """Cave: still cold air, a low resonant room tone, drips into pools at several rhythms, a trickle,
    the odd pebble ticking down the rock - all in a long stone reverb."""
    L = 45.0
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "cave")
    tone = _st(_pn(n, sr, r, -6.0, 25.0, 400.0), _pn(n, sr, r, -6.0, 25.0, 400.0))
    air_ = _st(_pn(n, sr, r, -2.0, 300.0, 5000.0), _pn(n, sr, r, -2.0, 300.0, 5000.0)) * _lfo(n, sr, r, 0.07, 0.5, 1.0)[:, None]
    y = 0.5 * dsp.normalize(tone) + 0.06 * dsp.normalize(air_)
    ev = _canvas(n)
    rd = dsp.rng(seed, "drips")
    for _k in range(4):                                     # several drip points, each with its own rhythm/pitch
        period = rd.uniform(1.1, 4.5)
        f = dsp.loguni(rd, 900.0, 2600.0)
        pan = rd.uniform(-0.9, 0.9)
        gain = rd.uniform(0.25, 0.6)
        t = rd.uniform(0, period)
        while t < L:
            _put(ev, dsp.drip(sr, rd, f * rd.uniform(0.94, 1.06), plink=1.0, splat=0.4), t, sr, gain * rd.uniform(0.7, 1.0), pan)
            t += period * rd.uniform(0.92, 1.12)
    for _ in range(12):
        _put(ev, dsp.drip(sr, rd, dsp.loguni(rd, 700.0, 3200.0), plink=0.8, splat=0.5), rd.uniform(0, L), sr, rd.uniform(0.1, 0.3),
             rd.uniform(-1, 1))
    tr_n = n + dsp.ns(0.5, sr)
    trick = _fold(dsp.bubbles(tr_n, sr, rd, 90.0, 900.0, 3500.0, alpha=2.0), n)
    dsp.loop_place(ev, dsp.pan(dsp.normalize(trick), 0.7) * 0.05, 0)
    for _ in range(3):
        t0 = rd.uniform(0, L)
        for j in range(int(rd.integers(2, 5))):
            pb = dsp.impact(sr, rd, "stone", dsp.loguni(rd, 1500.0, 4000.0), 0.06, contact_ms=0.2, t60=0.03, click=0.5)
            _put(ev, pb, t0 + j * rd.uniform(0.08, 0.2), sr, 0.06 * (0.7 ** j), rd.uniform(-1, 1))
    ev = dsp.reverb(ev, sr, "cave", 0.8, seed=seed, stereo_=True, circular=True)
    return y + ev


# --------------------------------------------------------------------------------------------- fire loops (mono)

def _fire_loop(seed, sr, L, *, crackle, roar, hiss, size, flutter=0.0, settle=0):
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "fire")
    it = _lfo(n, sr, r, 0.12, 0.7, 1.0)
    if flutter:
        it = it * (1.0 - flutter * _lfo(n, sr, r, 7.0) ** 2)
    roar_ = _pn(n, sr, r, -6.0, 30.0, 420.0 / size ** 0.4) * (0.6 + 0.4 * _lfo(n, sr, r, 3.0 / size)) * it
    hs = _pn(n, sr, r, -1.0, 1500.0, 9000.0) * (0.4 + 0.6 * _lfo(n, sr, r, 9.0) ** 2) * it
    tail = dsp.ns(0.5, sr)
    cr = _fold(dsp.crackles(n + tail, sr, r, crackle * np.concatenate([it, it[:tail]]), size=size), n)
    flut = _ltv(_pn(n, sr, r, -2.0, 200.0, 3000.0), sr, "bp", 500.0 + 700.0 * _lfo(n, sr, r, 5.0), 0.8) * it
    y = roar * dsp.normalize(roar_) + hiss * 0.5 * dsp.normalize(hs) + 0.25 * dsp.normalize(flut) + dsp.normalize(cr)
    if settle:                                   # logs shifting / embers collapsing
        for _ in range(settle):
            t = r.uniform(0, L)
            k = dsp.impact(sr, r, "wood", dsp.loguni(r, 250.0, 600.0), 0.2, contact_ms=2.0, t60=0.1, click=0.2)
            dsp.loop_place(y, k * 0.3, dsp.ns(t, sr))
            emb = dsp.clicks(dsp.ns(0.4, sr), sr, r, 900.0 * dsp.env_ar(dsp.ns(0.4, sr), sr, 0.01, 0.3), 2000.0, 9000.0, q=3.0)
            dsp.loop_place(y, dsp.normalize(emb) * 0.25, dsp.ns(t + 0.02, sr))
    for _ in range(int(L / 4)):                  # sap sizzles
        d = r.uniform(0.4, 1.2)
        m = dsp.ns(d, sr)
        sz = dsp.band_noise(m, sr, r, 3500.0, 8000.0) * dsp.env_ar(m, sr, 0.1, d) * (0.5 + 0.5 * dsp.smooth_noise(m, sr, r, 25.0))
        dsp.loop_place(y, sz * 0.06, dsp.ns(r.uniform(0, L), sr))
    return y


@sound("sfx/fire_loop_small", seed=10012, loop=True, peak_db=-6.0)
def fire_loop_small(seed, variant, sr):
    """Campfire: soft roar, clustered crackles and resonant pops, sap sizzles, logs settling."""
    return _fire_loop(seed, sr, 30.0, crackle=12.0, roar=0.3, hiss=0.25, size=1.0, settle=3)


@sound("sfx/fire_loop_torch", seed=10013, loop=True, peak_db=-7.0)
def fire_loop_torch(seed, variant, sr):
    """Handheld pitch torch: smaller, breathier flame fluttering in the air, fewer crackles, more sizzle."""
    return _fire_loop(seed, sr, 30.0, crackle=4.0, roar=0.45, hiss=0.4, size=0.45, flutter=0.35)


@sound("sfx/flare_loop", seed=10014, loop=True, peak_db=-8.0)
def flare_loop(seed, variant, sr):
    """Program signal flare burning beside a landed supply canister: a hard, sputtering hiss with
    little crackle, so it reads as chemical rather than wood fire when you track it by ear."""
    return _fire_loop(seed, sr, 20.0, crackle=1.5, roar=0.12, hiss=1.0, size=0.3, flutter=0.55)
