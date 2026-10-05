"""Interface sounds: tactile, warm and quiet. Physical sources (wood/brass mallets, a small speaker for the
tether device) rather than raw oscillators - nothing chiptune."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _mallet(sr, r, f, dur=1.2, bright=0.4, t60=0.9, wood=0.5):
    """Tuned bar under a soft mallet (marimba/kalimba-like): harmonic-ish bar partials 1:3.9:9.2, soft attack."""
    n = dsp.ns(dur, sr)
    ratios = np.array([1.0, 3.93, 9.2, 2.0 * dsp.vary(r, 1.0, 0.004)])
    amps = np.array([1.0, 0.35 * bright, 0.12 * bright, 0.12])
    t60s = np.array([t60, t60 * 0.35, t60 * 0.15, t60 * 0.6])
    y = dsp.partials(n, sr, f * ratios, amps, t60s, r.uniform(0, 6.28, 4), attack=0.002)
    k = dsp.impact(sr, r, "wood_small", f * 2.6, 0.06, contact_ms=0.8, t60=0.03, click=0.2)
    dsp.place(y, k, 0, wood * 0.4 * dsp.peak(y))
    return y


def _speaker(x, sr):
    """Small device speaker: band-limited, a resonant cone bump, slight cone breakup."""
    y = dsp.band(x, sr, 650.0, 5500.0, order=2)
    y = dsp.peq(y, sr, 2100.0, 5.0, 1.5)
    return dsp.sat(y / max(dsp.peak(y), 1e-9), 1.6)


def _beep(sr, r, f, dur, harsh=0.0):
    n = dsp.ns(dur, sr)
    tone = dsp.sine(f, n, sr) + 0.08 * dsp.sine(2 * f, n, sr) + harsh * 0.25 * dsp.square(f, n, sr, 0.35)
    tone *= dsp.curve([(0, 0.0), (0.004, 1.0), (dur * 0.6, 0.9), (dur - 0.015, 0.85), (dur, 0.0)], n, sr, "smooth")
    return tone


@sound("ui/click", variants=2, seed=8001, peak_db=-8.0)
def click(seed, variant, sr):
    r = dsp.rng(seed, "click")
    f0 = [1250.0, 980.0][variant]
    y = dsp.impact(sr, r, "wood_small", dsp.vary(r, f0, 0.03), 0.08, contact_ms=0.35, t60=0.025, click=0.35, tilt=0.6)
    body = dsp.thud(sr, r, 320.0, 0.05, contact_ms=1.5, t60=0.012, noise=0.3, knock=0.5, knock_f=900.0)
    dsp.place(y, body, 0, 0.35)
    return y


@sound("ui/hover", variants=2, seed=8002, peak_db=-16.0)
def hover(seed, variant, sr):
    """Barely-there soft tick (two interchangeable takes)."""
    r = dsp.rng(seed, "hover")
    f0 = [2100.0, 2300.0][variant]
    y = dsp.impact(sr, r, "wood_small", f0, 0.04, contact_ms=0.6, t60=0.012, click=0.1, tilt=0.8)
    n = len(y)
    air = dsp.band_noise(n, sr, r, 3000.0, 9000.0) * dsp.env_ar(n, sr, 0.004, 0.025)
    return y + 0.15 * dsp.normalize(air) * dsp.peak(y)


@sound("ui/craft_success", variants=2, seed=8003, peak_db=-10.3)
def craft_success(seed, variant, sr):
    """A firm wooden 'set' knock, then two warm mallet notes (fifth / rising fourth) in a small room."""
    r = dsp.rng(seed, "craftok")
    y = _buf(1.4, sr)
    dsp.place(y, dsp.impact(sr, r, "wood", 260.0, 0.25, contact_ms=1.2, t60=0.1, click=0.2, tilt=0.4), 0, 0.5)
    dsp.place(y, dsp.impact(sr, r, "metal_bar", 2900.0, 0.3, contact_ms=0.2, t60=0.2, click=0.0), dsp.ns(0.004, sr), 0.06)
    notes = [(293.66, 440.0), (329.63, 440.0)][variant]           # D4+A4 ; E4+A4
    for i, f in enumerate(notes):
        m = _mallet(sr, r, f, 1.2, bright=0.5, t60=0.8)
        dsp.place(y, m, dsp.ns(0.06 + 0.09 * i, sr), 0.5 if i == 0 else 0.42)
    return dsp.reverb(y, sr, "small_room", 0.18, seed=seed, tail=False)


@sound("ui/error", variants=2, seed=8004, peak_db=-8.0)
def error(seed, variant, sr):
    """Denied: two dull low knocks, the second a semitone flat, with a soft muted buzz."""
    r = dsp.rng(seed, "error")
    y = _buf(0.45, sr)
    f = [150.0, 135.0][variant]
    for i in range(2):
        k = dsp.impact(sr, r, "wood", f * (1.0 if i == 0 else 0.944), 0.2, contact_ms=2.0, t60=0.09, click=0.15, tilt=0.5)
        dsp.place(y, k, dsp.ns(0.11 * i, sr), 1.0 if i == 0 else 0.85)
    n = dsp.ns(0.22, sr)
    bz = dsp.lp(dsp.saw(f * 0.5, n, sr) + dsp.saw(f * 0.5 * 1.03, n, sr), sr, 380.0, order=4) * dsp.env_ar(n, sr, 0.01, 0.18)
    dsp.place(y, dsp.normalize(bz), 0, 0.22)
    return y


@sound("ui/tether_beep", variants=3, seed=8005, peak_db=-15.0)
def tether_beep(seed, variant, sr):
    """Tether device chirp through its little speaker (three interchangeable takes: tiny pitch, length and
    drive differences, as a real device would vary)."""
    r = dsp.rng(seed, "tether")
    f = 1568.0 * dsp.vary(r, 1.0, 0.006)
    y = _buf(0.3, sr)
    dsp.place(y, _beep(sr, r, f, dsp.vary(r, 0.11, 0.08), harsh=r.uniform(0.0, 0.15)), 0)
    y = _speaker(y, sr)
    return dsp.reverb(y, sr, "small_room", 0.08, seed=seed, tail=False)


@sound("ui/tether_alarm", variants=1, seed=8006, peak_db=-13.7)
def tether_alarm(seed, variant, sr):
    """Out of range: urgent alternating double-beeps for ~1.7 s, harsher speaker drive."""
    r = dsp.rng(seed, "alarm")
    y = _buf(1.8, sr)
    t = 0.0
    for _i in range(4):
        for k, f in enumerate((1865.0, 1397.0)):
            dsp.place(y, _beep(sr, r, f, 0.1, harsh=0.6), dsp.ns(t + 0.13 * k, sr))
        t += 0.42
    y = _speaker(y, sr)
    y = dsp.sat(y, 2.0)
    return dsp.reverb(y, sr, "small_room", 0.08, seed=seed, tail=False)


@sound("ui/learned", variants=1, seed=8007, peak_db=-10.5)
def learned(seed, variant, sr):
    """New recipe learned: a soft rising three-note figure (D-F#-A) on mallets with a brushed shimmer."""
    r = dsp.rng(seed, "learned")
    y = _buf(2.4, sr)
    for i, f in enumerate((293.66, 369.99, 440.0)):
        dsp.place(y, _mallet(sr, r, f, 1.8, bright=0.45, t60=1.3), dsp.ns(0.13 * i, sr), 0.55 - 0.05 * i)
        dsp.place(y, _mallet(sr, r, f * 2, 1.2, bright=0.2, t60=0.9, wood=0.0), dsp.ns(0.13 * i + 0.01, sr), 0.12)
    n = len(y)
    sh = dsp.band_noise(n, sr, r, 4000.0, 12000.0) * dsp.env_ar(n, sr, 0.25, 1.2) * 0.02
    y = y + sh
    return dsp.reverb(y, sr, "hall", 0.25, seed=seed, tail=False)


@sound("ui/level_up", variants=1, seed=8008, peak_db=-9.5)
def level_up(seed, variant, sr):
    """Level gained: a fuller cousin of "learned" - a four-note rising figure (D-A-D-F#) on mallets
    over a low wooden D, with a longer brushed shimmer. Warm, not triumphant: you survived, that's all."""
    r = dsp.rng(seed, "level_up")
    y = _buf(3.4, sr)
    dsp.place(y, _mallet(sr, r, 146.83, 2.6, bright=0.25, t60=1.9, wood=0.7), 0, 0.5)
    for i, f in enumerate((293.66, 440.0, 587.33, 739.99)):
        dsp.place(y, _mallet(sr, r, f, 2.0, bright=0.45, t60=1.4), dsp.ns(0.12 * i, sr), 0.5 - 0.05 * i)
        dsp.place(y, _mallet(sr, r, f * 2, 1.2, bright=0.2, t60=0.9, wood=0.0), dsp.ns(0.12 * i + 0.01, sr), 0.1)
    n = len(y)
    sh = dsp.band_noise(n, sr, r, 4000.0, 12000.0) * dsp.env_ar(n, sr, 0.4, 1.8) * 0.025
    y = y + sh
    return dsp.reverb(y, sr, "hall", 0.28, seed=seed, tail=False)
