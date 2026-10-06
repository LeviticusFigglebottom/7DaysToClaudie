"""Hollowed hounds (ADR-0034): dogs the Bloom took, synthesized from the same voice models as the
Hollowed and the deer.

A hound growls low and wet while it stalks (a rough, sub-heavy voice through a long muzzle), snarls
with its teeth clacking when it bites, barks in a broken, hoarse triple when it spots you, and its
pack answers a howl: a long rising "oo" doubled by a second, slightly-off voice, the Bloom in its
throat. It yelps when hurt, wheezes out when it dies, and pants hard on the run.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _outdoor(y, sr, seed, mix=0.12):
    return dsp.reverb(y, sr, "forest", mix, seed=seed, tail=True)


def _growl_voice(sr, r, dur, f0, amp, vowel="uh", rough=0.85):
    """A dog's growl: a low, irregular pulse train (roughness at 25-40 Hz) through a long muzzle
    (formants pulled down), with a sub-octave rattle."""
    return dsp.voice(sr, dur, f0, vowel, amp, r, oq=0.32, sq=3.0, jitter=0.09, shimmer=0.25, sub=0.6, breath=0.25, asp=0.4,
                     tract=0.78, bw=1.4, rough=rough, rough_rate=dsp.vary(r, 32.0, 0.2), tilt_db=-2.0, os=2)


@sound("voice/hound_growl", variants=4, seed=9401, peak_db=-6.0)
def hound_growl(seed, variant, sr):
    """Stalking: a long, wet, rising and falling growl."""
    r = dsp.rng(seed)
    d = r.uniform(1.6, 2.6)
    n = dsp.ns(d, sr)
    base = r.uniform(85.0, 120.0)
    f0 = dsp.curve([(0, base * 0.9), (d * 0.3, base * 1.15), (d * 0.6, base), (d, base * 0.85)], n, sr, "smooth")
    amp = [(0, 0), (0.15, 0.8), (d * 0.4, 1.0), (d * 0.8, 0.9), (d, 0)]
    g = _growl_voice(sr, r, d, f0, amp, [(0, "uh"), (d * 0.5, "o"), (d, "uh")])
    wet = dsp.breath(sr, d, "uh", amp, r, tract=0.8, hiss=0.2, wet=0.6, rattle=0.5, rattle_hz=dsp.vary(r, 24.0, 0.2))
    y = dsp.normalize(g) + 0.35 * dsp.normalize(wet)
    y = dsp.asym(y / dsp.peak(y), 2.5, 0.15)
    return _outdoor(dsp.lp(y, sr, 3200.0), sr, seed, 0.08)


@sound("voice/hound_snarl", variants=4, seed=9402, peak_db=-3.5)
def hound_snarl(seed, variant, sr):
    """The bite: a sudden open-mouthed snarl that ends in the clack of teeth."""
    r = dsp.rng(seed)
    d = r.uniform(0.45, 0.7)
    n = dsp.ns(d, sr)
    pk = r.uniform(170.0, 240.0)
    f0 = dsp.curve([(0, pk * 0.7), (0.05, pk), (d * 0.7, pk * 0.9), (d, pk * 0.6)], n, sr, "smooth")
    amp = [(0, 0), (0.02, 1.0), (d * 0.75, 0.9), (d, 0)]
    g = dsp.voice(sr, d, f0, [(0, "a"), (d, "ae")], amp, r, oq=0.3, sq=3.5, jitter=0.1, shimmer=0.3, sub=0.5, breath=0.4,
                  asp=0.6, tract=0.85, bw=1.3, rough=0.9, rough_rate=dsp.vary(r, 45.0, 0.2), tilt_db=4.0)
    y = _buf(d + 0.15, sr)
    dsp.place(y, dsp.normalize(g), 0)
    # teeth meeting: a short, bright double click
    for k in range(2):
        cn = dsp.ns(0.03, sr)
        click = dsp.bp(dsp.white(cn, r), sr, dsp.vary(r, 3200.0, 0.15), 3.0) * dsp.env_ar(cn, sr, 0.0005, 0.02)
        dsp.place(y, dsp.normalize(click), dsp.ns(d - 0.05 + k * 0.035, sr), 0.6)
    y = dsp.asym(y / dsp.peak(y), 3.5, 0.2)
    return _outdoor(y, sr, seed, 0.06)


@sound("voice/hound_bark", variants=3, seed=9403, peak_db=-2.5)
def hound_bark(seed, variant, sr):
    """It has seen you: two or three hoarse, broken barks, the voice cracking on each."""
    r = dsp.rng(seed)
    y = _buf(1.4, sr)
    t = 0.0
    for k in range(int(r.integers(2, 4))):
        d = r.uniform(0.13, 0.2)
        n = dsp.ns(d, sr)
        pk = r.uniform(330.0, 470.0)
        f0 = dsp.curve([(0, pk * 0.8), (0.02, pk * 1.1), (d, pk * 0.65)], n, sr, "smooth")
        amp = [(0, 0), (0.006, 1.0), (d * 0.4, 0.8), (d, 0)]
        b = dsp.voice(sr, d, f0, [(0, "a"), (d, "uh")], amp, r, oq=0.3, sq=3.5, jitter=0.08, shimmer=0.3, sub=0.35,
                      breath=0.5, asp=0.8, tract=0.9, bw=1.2, rough=0.7, rough_rate=dsp.vary(r, 60.0, 0.2), tilt_db=5.0)
        dsp.place(y, dsp.normalize(b), dsp.ns(t, sr), r.uniform(0.75, 1.0))
        t += d + r.uniform(0.12, 0.22)
    y = dsp.asym(y / dsp.peak(y), 4.0, 0.25)
    return _outdoor(y, sr, seed, 0.15)


@sound("voice/hound_howl", variants=3, seed=9404, peak_db=-2.5)
def hound_howl(seed, variant, sr):
    """The pack call: a long howl that rises, holds and falls away, doubled by a second voice a
    little off pitch (two throats in one), carrying far through the trees."""
    r = dsp.rng(seed)
    d = r.uniform(2.2, 3.0)
    n = dsp.ns(d, sr)
    lo = r.uniform(330.0, 400.0)
    hi = lo * r.uniform(1.5, 1.75)
    f0 = dsp.curve([(0, lo), (d * 0.25, hi), (d * 0.7, hi * 0.97), (d, lo * 0.8)], n, sr, "smooth")
    f0 = f0 * dsp.vibrato(n, sr, dsp.vary(r, 5.0, 0.2), r.uniform(15.0, 30.0), r, 0.4)
    amp = [(0, 0), (0.12, 0.7), (d * 0.3, 1.0), (d * 0.8, 0.85), (d, 0)]
    vow = [(0, "u"), (d * 0.3, "oo"), (d * 0.75, "o"), (d, "u")]
    a = dsp.voice(sr, d, f0, vow, amp, r, oq=0.55, sq=2.2, jitter=0.02, shimmer=0.06, breath=0.15, tract=0.85, bw=1.0,
                  rough=[(0, 0.1), (d * 0.8, 0.2), (d, 0.6)], tilt_db=-1.0)
    b = dsp.voice(sr, d, f0 * r.uniform(1.035, 1.06), vow, amp, r, oq=0.5, sq=2.5, jitter=0.04, shimmer=0.1, breath=0.25,
                  tract=0.9, bw=1.2, rough=0.35, tilt_db=1.0)
    y = dsp.normalize(a) + 0.45 * dsp.normalize(b)
    return dsp.reverb(y, sr, "forest", 0.3, seed=seed, tail=True)


@sound("voice/hound_yelp", variants=4, seed=9405, peak_db=-3.5)
def hound_yelp(seed, variant, sr):
    """Hurt: a sharp, high yelp falling off into a whine."""
    r = dsp.rng(seed)
    d = r.uniform(0.25, 0.45)
    n = dsp.ns(d, sr)
    pk = r.uniform(900.0, 1300.0)
    f0 = dsp.curve([(0, pk * 0.8), (0.03, pk), (d, pk * 0.45)], n, sr, "smooth")
    amp = [(0, 0), (0.008, 1.0), (d * 0.5, 0.6), (d, 0)]
    y = dsp.voice(sr, d, f0, [(0, "i"), (d, "ih")], amp, r, oq=0.4, sq=3.0, jitter=0.05, shimmer=0.15, breath=0.3,
                  tract=1.05, rough=0.35, tilt_db=3.0)
    return _outdoor(dsp.normalize(y), sr, seed, 0.1)


@sound("voice/hound_death", variants=3, seed=9406, peak_db=-4.0)
def hound_death(seed, variant, sr):
    """Dying: a broken yelp, then the breath going out of it in a wet wheeze."""
    r = dsp.rng(seed)
    y = _buf(1.6, sr)
    d = r.uniform(0.3, 0.45)
    pk = r.uniform(700.0, 950.0)
    f0 = dsp.curve([(0, pk), (d, pk * 0.4)], dsp.ns(d, sr), sr, "smooth")
    yelp = dsp.voice(sr, d, f0, [(0, "ih"), (d, "uh")], [(0, 0), (0.01, 1.0), (d, 0)], r, oq=0.4, jitter=0.08,
                     shimmer=0.2, breath=0.4, tract=1.0, rough=0.6)
    dsp.place(y, dsp.normalize(yelp), 0)
    wd = r.uniform(0.7, 1.0)
    wheeze = dsp.breath(sr, wd, "uh", [(0, 0), (0.05, 1.0), (wd, 0)], r, tract=0.85, hiss=0.4, wet=0.7, rattle=0.6)
    dsp.place(y, dsp.normalize(wheeze), dsp.ns(d + 0.08, sr), 0.6)
    return _outdoor(y, sr, seed, 0.1)


@sound("voice/hound_pant", variants=2, seed=9407, peak_db=-7.0)
def hound_pant(seed, variant, sr):
    """On the run: quick, shallow, wet panting with a rasp in it."""
    r = dsp.rng(seed)
    dur = 2.0
    y = _buf(dur + 0.3, sr)
    t = 0.0
    rate = r.uniform(5.0, 6.2)
    while t < dur:
        ed = r.uniform(0.06, 0.09)
        ex = dsp.breath(sr, ed, "a", [(0, 0), (0.006, 1.0), (ed, 0)], r, tract=0.85, hiss=0.6, hiss_f=2200.0, wet=0.4)
        dsp.place(y, dsp.normalize(ex), dsp.ns(t, sr), r.uniform(0.7, 1.0))
        idd = r.uniform(0.05, 0.07)
        inh = dsp.breath(sr, idd, "ih", [(0, 0), (idd * 0.6, 1.0), (idd, 0)], r, hiss=0.8, hiss_f=2800.0, rattle=0.4)
        dsp.place(y, dsp.normalize(inh), dsp.ns(t + ed + 0.015, sr), r.uniform(0.35, 0.55))
        t += 1.0 / rate * r.uniform(0.9, 1.15)
    return _outdoor(dsp.normalize(y), sr, seed, 0.06)
