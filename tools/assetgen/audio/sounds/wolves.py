"""Grey wolves (ADR-0055): the pack's howl at dusk and through the night, carried a long way through
the trees. A clean, pure voice (no Bloom in the throat, unlike the Hollowed hound's doubled howl):
a soft onset sliding up to a long held note with a slow vibrato, often breaking down a step near
the end, then falling away, with the forest's long reverb behind it. The other bites, growls and
yelps are the hound's (voice/hound_*).
"""
from __future__ import annotations

from .. import dsp
from ..registry import sound


@sound("voice/wolf_howl", variants=4, seed=9501, peak_db=-2.0)
def wolf_howl(seed, variant, sr):
    """One wolf's howl: rise, hold, sometimes a break down a step, fall."""
    r = dsp.rng(seed)
    d = r.uniform(3.2, 4.6)
    n = dsp.ns(d, sr)
    lo = r.uniform(300.0, 360.0)
    hi = lo * r.uniform(1.45, 1.7)
    brk = r.random() < 0.6
    pts = [(0, lo * 0.9), (d * 0.18, hi), (d * 0.55, hi * 0.99)]
    if brk:
        pts += [(d * 0.62, hi * 0.89), (d * 0.82, hi * 0.87)]
    else:
        pts += [(d * 0.8, hi * 0.96)]
    pts += [(d, lo * 0.75)]
    f0 = dsp.curve(pts, n, sr, "smooth")
    f0 = f0 * dsp.vibrato(n, sr, dsp.vary(r, 4.5, 0.15), r.uniform(10.0, 22.0), r, 0.3)
    amp = [(0, 0), (0.25, 0.6), (d * 0.25, 1.0), (d * 0.8, 0.9), (d, 0)]
    vow = [(0, "u"), (d * 0.2, "oo"), (d * 0.6, "o"), (d * 0.9, "u"), (d, "u")]
    y = dsp.voice(sr, d, f0, vow, amp, r, oq=0.6, sq=2.0, jitter=0.008, shimmer=0.03, breath=0.08, tract=0.9, bw=0.9,
                  rough=[(0, 0.0), (d * 0.85, 0.05), (d, 0.25)], tilt_db=-2.0)
    y = dsp.lp(dsp.normalize(y), sr, 4200.0)
    return dsp.reverb(y, sr, "forest", 0.38, seed=seed, tail=True)
