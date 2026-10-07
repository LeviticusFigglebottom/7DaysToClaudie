"""Bloom nests (ADR-0055, TD-256): what a burning nest sounds like, with no throat in it.

A nest has no lungs: its scream is fungal flesh shrieking as the fire boils the water out of it, a
whistle of steam forced through wet pores (several thin, detuned, rising tones that never settle on a
pitch), a gurgle of fluid in the pods and a sputtering rasp, carried far through the trees. While it
burns it roars like wet wood on a big fire, fat sizzling and its sap boiling and popping. When it dies
it falls in on itself: charred roots cracking, a heavy soft mass slumping onto the felt, a wet
squelch and the hiss of embers settling.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


@sound("voice/nest_scream", variants=2, seed=9601, peak_db=-2.0)
def nest_scream(seed, variant, sr):
    """The burn scream (2.6-3.2 s): a wet fungal shriek. Steam whistles through pores (detuned, rising
    and wavering), a strained wet voice-like formant layer under them, gurgling bubbles and squelches
    of the flesh splitting, ending in a sputtering, collapsing hiss. Baked forest tail."""
    r = dsp.rng(seed, "nest_scream")
    d = r.uniform(2.6, 3.2)
    n = dsp.ns(d, sr)
    top = r.uniform(1400.0, 1800.0)
    contour = dsp.curve([(0, top * 0.35), (0.35, top * 0.7), (1.0, top), (d * 0.7, top * 1.08), (d - 0.3, top * 0.6), (d, top * 0.3)],
                        n, sr, "smooth")
    env = dsp.curve([(0, 0), (0.08, 0.6), (0.5, 0.95), (d * 0.7, 1.0), (d - 0.35, 0.7), (d, 0)], n, sr, "smooth")
    # Steam whistles: narrow resonances on noise, each its own wavering pitch (pores, not a throat).
    whistle = np.zeros(n)
    for k, c in enumerate((0.0, -60.0, 85.0, 230.0, -190.0)):
        wav = dsp.drift(n, sr, r, 40.0, 3.5) * dsp.vibrato(n, sr, dsp.vary(r, 9.0, 0.3), r.uniform(40.0, 120.0), r, 0.9)
        f = contour * dsp.cents(c) * wav * (1.0 + 0.5 * k / 5.0)
        tone = dsp.bp(dsp.white(n, r), sr, np.clip(f, 200.0, 9000.0), r.uniform(25.0, 45.0))
        whistle += dsp.normalize(tone) * (1.0 if k == 0 else r.uniform(0.35, 0.7)) * (0.7 + 0.3 * dsp.smooth_noise(n, sr, r, 14.0))
    # A strained, wet, voice-like layer: a shriek with no chest, ring-modulated so it never sounds human.
    vf0 = contour * 0.45
    v = dsp.voice(sr, d, vf0, [(0, "ih"), (d * 0.4, "i"), (d * 0.8, "ae"), (d, "uh")], 1.0, r, oq=0.35, sq=3.2, jitter=0.06,
                  shimmer=0.25, breath=0.4, asp=0.6, tract=1.35, bw=1.6, rough=0.55, rough_rate=dsp.vary(r, 70.0, 0.2),
                  tilt_db=4.0, os=2)
    v = dsp.ring(dsp.normalize(v), sr, dsp.vary(r, 63.0, 0.15)) * 0.6 + 0.4 * dsp.normalize(v)
    # Fluid in the flesh: bubbling and gurgles that thicken as it goes on, squelches of it splitting.
    bub = dsp.bubbles(n, sr, r, dsp.curve([(0, 20.0), (d, 110.0)], n, sr), 300.0, 2200.0, 1.8, rise=(0.1, 0.6))
    hiss = dsp.band_noise(n, sr, r, 3000.0, 11000.0) * (0.5 + 0.5 * dsp.smooth_noise(n, sr, r, 22.0))
    y = 1.0 * dsp.normalize(whistle) + 0.65 * dsp.normalize(v) + 0.35 * dsp.normalize(bub) + 0.25 * dsp.normalize(hiss)
    y = y * env
    for _ in range(int(r.integers(4, 7))):
        sq = dsp.squelch(sr, r, r.uniform(0.12, 0.25), r.uniform(1600.0, 2600.0), r.uniform(400.0, 800.0), stick=0.6, bub=0.5)
        dsp.place(y, dsp.normalize(sq), dsp.ns(r.uniform(0.05, d - 0.3), sr), r.uniform(0.3, 0.6))
    y = dsp.asym(y / dsp.peak(y), 2.2, 0.15)
    # The end: the shriek gutters out into a sputtering hiss.
    out = _buf(d + 1.2, sr)
    dsp.place(out, y, 0)
    td = 1.0
    tn = dsp.ns(td, sr)
    sput = dsp.band_noise(tn, sr, r, 1500.0, 9000.0) * dsp.env_ar(tn, sr, 0.05, td) * (0.4 + 0.6 * (dsp.smooth_noise(tn, sr, r, 30.0) > 0.0))
    dsp.place(out, dsp.normalize(sput), dsp.ns(d - 0.4, sr), 0.25)
    return dsp.reverb(out, sr, "forest", 0.3, seed=seed, tail=True)


@sound("sfx/nest_burn_loop", seed=9602, loop=True, peak_db=-4.0)
def nest_burn_loop(seed, variant, sr):
    """A nest burning (20 s loop): the low roar of a big fire, crackling charred roots, the fat of the
    flesh sizzling and its sap boiling in gouts of bubbles, now and then a pod popping."""
    r = dsp.rng(seed, "nest_burn")
    L = 20.0
    X = 2.0
    n = dsp.ns(L + X, sr)
    fire = dsp.fire(n, sr, r, intensity=1.0, crackle_rate=14.0, roar=0.9, hiss=0.3, pops=1.0, size=1.6)
    sizzle = dsp.band_noise(n, sr, r, 2500.0, 10000.0) * (0.3 + 0.7 * np.maximum(dsp.smooth_noise(n, sr, r, 6.0), 0.0) ** 2)
    boil = dsp.bubbles(n, sr, r, 25.0 + 30.0 * np.maximum(dsp.smooth_noise(n, sr, r, 0.6), 0.0), 180.0, 1400.0, 1.8,
                       rise=(0.0, 0.3))
    y = dsp.normalize(fire) + 0.25 * dsp.normalize(sizzle) + 0.35 * dsp.normalize(boil)
    t = 0.3
    while t < L + X - 0.4:                                        # pods popping, wet squelches of flesh splitting
        p = dsp.squelch(sr, r, r.uniform(0.1, 0.22), r.uniform(1200.0, 2400.0), r.uniform(300.0, 700.0), stick=0.7, bub=0.6)
        dsp.place(y, dsp.normalize(p), dsp.ns(t, sr), r.uniform(0.25, 0.55))
        t += r.uniform(1.2, 3.5)
    return dsp.make_loop(y, sr, X)


@sound("sfx/nest_collapse", variants=2, seed=9603, peak_db=-1.5)
def nest_collapse(seed, variant, sr):
    """It dies (2.5-3 s): charred roots crack and give, the heavy soft mass slumps onto the felt in a
    couple of deep thuds, a wet squelch as the heart caves in, and embers hiss and tick as it settles."""
    r = dsp.rng(seed, "nest_collapse")
    d = r.uniform(2.5, 3.0)
    y = _buf(d + 0.6, sr)
    t = 0.0
    for _ in range(int(r.integers(3, 6))):                       # roots cracking
        c = dsp.crack(sr, r, r.uniform(0.25, 0.45), n_clicks=int(r.integers(4, 9)), body="wood", body_f=r.uniform(180.0, 420.0),
                      body_amt=0.8, bright=r.uniform(2500.0, 4000.0), tail=0.5)
        dsp.place(y, c, dsp.ns(t, sr), r.uniform(0.4, 0.75))
        t += r.uniform(0.08, 0.25)
    t0 = t + r.uniform(0.05, 0.15)
    for k in range(2):                                           # the mass slumping down
        th = dsp.thud(sr, r, r.uniform(45.0, 70.0), 0.9, contact_ms=22.0, t60=0.22, noise=0.6, noise_lp=500.0, knock=0.3,
                      knock_f=r.uniform(220.0, 320.0))
        dsp.place(y, th, dsp.ns(t0 + k * r.uniform(0.25, 0.45), sr), 1.0 if k == 0 else 0.7)
    sq = dsp.squelch(sr, r, 0.45, 1500.0, 250.0, q=3.5, stick=0.8, bub=0.7, attack=0.01)
    dsp.place(y, dsp.normalize(sq), dsp.ns(t0 + 0.05, sr), 0.6)
    rn = dsp.ns(d - t0, sr)                                      # embers settling
    rest = dsp.band_noise(rn, sr, r, 2000.0, 9000.0) * dsp.env_ar(rn, sr, 0.2, d - t0)
    tick = dsp.clicks(rn, sr, r, 40.0 * dsp.env_ar(rn, sr, 0.05, d - t0), 2500.0, 9000.0, q=3.0)
    dsp.place(y, 0.18 * dsp.normalize(rest) + 0.2 * dsp.normalize(tick), dsp.ns(t0 + 0.1, sr))
    y = dsp.lp(y, sr, 9000.0)
    return dsp.reverb(y, sr, "forest", 0.22, seed=seed, tail=True)
