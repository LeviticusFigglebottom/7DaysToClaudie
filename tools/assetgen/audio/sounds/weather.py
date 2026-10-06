"""Thunder (ADR-0033): played by EnvironmentController when a strike's sound arrives, distance /
343 m/s after its flash.

Thunder is built from the channel, not from noise: a tortuous lightning channel is a random walk of
short segments from the cloud base down to the ground. Every segment fires a shock (an N-wave a few
milliseconds long) and its sound reaches the listener when its own distance allows, so a channel
kilometres long arrives as a roll lasting seconds: the nearest kink first (the crack of a close
strike), the far reaches of the channel last. Segments radiate most broadside to their own line, so
a kink that turns across the line of sight claps louder than one pointing at you. Air absorbs the
highs with distance (dsp.air, ~f^2), so far thunder is a low rumble; the valley's walls echo it.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _channel(r: np.random.Generator, dist: float, seg: float = 12.0) -> np.ndarray:
    """A tortuous channel from ~2 km up down to the ground `dist` metres away: (N, 3) points,
    listener at the origin, x toward the strike, y up."""
    top = r.uniform(1700.0, 2600.0)
    p = np.array([dist + r.uniform(-400.0, 400.0), top, r.uniform(-400.0, 400.0)])
    pts = [p.copy()]
    d = np.array([0.0, -1.0, 0.0])
    while p[1] > 0.0 and len(pts) < 900:
        # Tortuosity: each step turns by ~16 degrees on average around a mostly-downward drift.
        d = d + r.normal(0.0, 0.32, 3) + np.array([0.0, -0.35, 0.0])
        d /= np.linalg.norm(d)
        p = p + d * seg
        pts.append(p.copy())
    # Upper horizontal reaches (cloud-to-cloud spider lightning) on some strikes.
    if r.random() < 0.6:
        q = pts[0].copy()
        h = np.array([r.normal(), 0.0, r.normal()])
        h /= np.linalg.norm(h)
        for _ in range(int(r.integers(60, 160))):
            h = h + r.normal(0.0, 0.25, 3) * np.array([1.0, 0.3, 1.0])
            h /= np.linalg.norm(h)
            q = q + h * seg
            pts.append(q.copy())
    return np.array(pts)


def _thunder(sr: int, r: np.random.Generator, dist: float, tail: float) -> np.ndarray:
    pts = _channel(r, dist)
    mids = (pts[1:] + pts[:-1]) * 0.5
    segs = pts[1:] - pts[:-1]
    rng_d = np.linalg.norm(mids, axis=1)
    t = (rng_d - rng_d.min()) / 343.0
    # Broadside radiation: |sin| of the angle between a segment and the line to the listener.
    los = mids / rng_d[:, None]
    seg_u = segs / np.maximum(np.linalg.norm(segs, axis=1)[:, None], 1e-6)
    broad = np.sqrt(np.maximum(1.0 - np.sum(los * seg_u, axis=1) ** 2, 0.0))
    amp = (0.15 + broad ** 2) * (rng_d.min() / rng_d) * dsp.power_amps(r, len(t), 1.6, 12.0) ** 0.5
    n = dsp.ns(float(t.max()) + tail, sr)
    imp = dsp.impulses(n, sr, t + 0.02, amp)
    # The shock: an N-wave a few milliseconds long (longer for a bigger channel).
    k = dsp.ns(r.uniform(0.004, 0.008), sr)
    nwave = np.linspace(1.0, -1.0, k)
    y = np.convolve(imp, nwave)[:n]
    # Rolling body: the same arrivals smeared, as the shocks overlap into a rumble.
    body = dsp.lp(dsp.brown(n, r, sr), sr, 160.0, order=2)
    env = dsp.lp(np.abs(imp), sr, 3.0, order=2)
    env /= max(float(env.max()), 1e-9)
    y = dsp.normalize(y) + 0.9 * dsp.normalize(body * env)
    # Air absorption over the distance, and a ground-hugging low end.
    y = dsp.air(y, sr, dist, 0.0)
    y = dsp.lshelf(y, sr, 120.0, 6.0)
    return y


def _stereo(y: np.ndarray, sr: int, seed: int, wet: float) -> np.ndarray:
    return dsp.reverb(y, sr, "valley", wet, seed=seed, stereo_=True)


@sound("amb/thunder_near", variants=4, seed=10401, peak_db=-1.0)
def thunder_near(seed, variant, sr):
    """A strike within ~1.6 km: a ripping crack from the nearest kinks, then the long roll of the
    rest of the channel echoing down the valley."""
    r = dsp.rng(seed, "near")
    dist = float(r.uniform(450.0, 1500.0))
    y = _thunder(sr, r, dist, 2.5)
    # The first arrivals still carry their highs: a crackle over the opening clap.
    crack = dsp.hp(dsp.clicks(dsp.ns(0.9, sr), sr, r, 260.0, 900.0, 6000.0, q=1.6, alpha=1.6, groups=8), sr, 500.0)
    crack *= dsp.env_ar(len(crack), sr, 0.004, 0.5)
    dsp.place(y, dsp.normalize(crack) * 0.55, dsp.ns(0.02, sr))
    return _stereo(dsp.normalize(y), sr, seed, 0.35)


@sound("amb/thunder_far", variants=4, seed=10402, peak_db=-1.0)
def thunder_far(seed, variant, sr):
    """A strike kilometres off: a low, long rumble that swells and rolls away."""
    r = dsp.rng(seed, "far")
    dist = float(r.uniform(3000.0, 8000.0))
    y = _thunder(sr, r, dist, 3.0)
    y = dsp.lp(y, sr, 420.0, order=2)
    return _stereo(dsp.normalize(y), sr, seed, 0.5)
