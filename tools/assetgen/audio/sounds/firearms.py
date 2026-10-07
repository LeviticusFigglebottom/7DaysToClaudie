"""Long guns (ADR-0057): the hunting rifle's shot, its bolt cycle and a round thumbed into the action.

The .308 is heavier than the revolver: a sharper supersonic crack, a deeper boom and a longer valley
tail (it carries further in game too: equip.noise). The bolt: lift, draw back with the empty
case flicked out and landing, run forward, turn down."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound
from .items import _buf, _casing, _click, _muzzle_blast, _slide


@sound("sfx/gun_rifle_shot", variants=3, seed=6101, peak_db=-0.3)
def gun_rifle_shot(seed, variant, sr):
    r = dsp.rng(seed, "rifle")
    dry = _muzzle_blast(sr, r, 0.42, crack=1.4, body_f=420.0, boom_amt=0.95)
    room, mix = [("forest", 0.6), ("valley", 0.7), ("town", 0.5)][variant]
    wet = dsp.reverb(dry, sr, room, 1.0, seed=seed, dry=0.0)
    wet = dsp.hp(wet, sr, 110.0)
    y = dsp.fit(dry, len(wet)) + mix * wet
    return dsp.limit(y / dsp.peak(y), sr, 0.3, window_ms=1.5)


@sound("sfx/gun_rifle_bolt", variants=2, seed=6102, peak_db=-5.0)
def gun_rifle_bolt(seed, variant, sr):
    """Bolt up (click), back (slide, the case kicked out and landing), forward (slide), down (lock)."""
    r = dsp.rng(seed, "bolt")
    y = _buf(1.1, sr)
    t = r.uniform(0.0, 0.02)
    dsp.place(y, _click(sr, r, 2600.0, 0.06), dsp.ns(t, sr), 0.8)
    t += r.uniform(0.1, 0.13)
    dsp.place(y, _slide(sr, r, 0.12, 900.0, 6500.0), dsp.ns(t, sr), 0.6)
    dsp.place(y, _click(sr, r, 3400.0, 0.05), dsp.ns(t + 0.12, sr), 0.7)
    dsp.place(y, _casing(sr, r, 0.45), dsp.ns(t + r.uniform(0.35, 0.45), sr))
    t += r.uniform(0.22, 0.27)
    dsp.place(y, _slide(sr, r, 0.1, 1000.0, 7000.0), dsp.ns(t, sr), 0.55)
    t += r.uniform(0.12, 0.15)
    lock = dsp.impact(sr, r, "metal", dsp.vary(r, 1900.0, 0.15), 0.2, contact_ms=0.1, t60=0.1, click=0.8)
    dsp.place(y, lock, dsp.ns(t, sr), 1.0)
    return y


@sound("sfx/gun_rifle_round", variants=3, seed=6103, peak_db=-8.0)
def gun_rifle_round(seed, variant, sr):
    """A round pressed down into the magazine past the follower spring: slide, click."""
    r = dsp.rng(seed, "round")
    y = _buf(0.4, sr)
    t = r.uniform(0.05, 0.12)
    dsp.place(y, _slide(sr, r, 0.06, 1800.0, 8000.0), dsp.ns(t, sr), 0.3)
    dsp.place(y, _click(sr, r, 3900.0, 0.04), dsp.ns(t + 0.07, sr), 0.6)
    return y * np.float64(1.0)
