"""The Remand Program's kit: the heavy-lift supply drone (ADR-0023).

sfx/drone_rotor_loop   eight coaxial rotors of a heavy-lift drone at cruise: the blade-pass buzz of
                       each rotor (a pulse train near 80 Hz) beating slowly against the others, the
                       chop of blade vortices in the air wash, and a thin motor whine. Built periodic
                       (whole cycles over the loop, FFT noise, periodic modulators) so it loops without
                       a seam; the game shifts its pitch for the doppler as it passes.
sfx/drone_release      the cargo hook letting go: a solenoid clunk, the sling slapping free and the
                       drogue chute snapping open under it.
Dry: distance and occlusion are runtime (AudioStreamPlayer3D)."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound

LOOP_S = 6.0


def _cycles(f: float) -> float:
    """Nearest frequency with a whole number of cycles over the loop."""
    return max(1.0, round(f * LOOP_S)) / LOOP_S


def _rotor(n: int, sr: int, r: np.random.Generator, f_bp: float) -> np.ndarray:
    """One rotor: a band-limited blade-pass pulse train with a little once-per-rev imbalance."""
    harmonics = np.arange(1, 40)
    freqs = [_cycles(f_bp * k) for k in harmonics]
    amps = 1.0 / harmonics ** 1.15 * (1.0 + 0.25 * r.standard_normal(len(harmonics)))
    y = dsp.partials(n, sr, freqs, np.abs(amps), phases=r.uniform(0, 2 * np.pi, len(harmonics)))
    rev = dsp.partials(n, sr, [_cycles(f_bp * 0.5), _cycles(f_bp * 1.5)], [0.22, 0.08], phases=r.uniform(0, 2 * np.pi, 2))
    return dsp.normalize(y) + rev


@sound("sfx/drone_rotor_loop", seed=17101, loop=True, peak_db=-2.0)
def drone_rotor_loop(seed, variant, sr):
    r = dsp.rng(seed)
    n = dsp.ns(LOOP_S, sr)
    t = np.arange(n) / sr
    # Eight rotors held at slightly different speeds by the flight controller: their blade-pass
    # tones beat against each other (the slow "wub" of a big multirotor).
    base = 79.0
    offsets = [0.0, 0.5, 1.0, 1.5, 2.17, 2.83, 3.5, 4.33]
    y = np.zeros(n)
    for k, off in enumerate(offsets):
        f = _cycles(base + off)
        g = 1.0 if k % 2 == 0 else 0.8      # lower rotors of each pair sit in the uppers' wash
        y += _rotor(n, sr, r, f) * g
    y = dsp.normalize(y)
    # Blade chop: the air wash's broadband noise pulsed at the blade pass, rougher in the mids.
    wash = dsp.band_noise(n, sr, r, 60.0, 2400.0, slope_db_oct=-4.0)
    chop = np.zeros(n)
    for off in offsets[:4]:
        f = _cycles(base + off)
        chop += np.abs(np.sin(np.pi * f * t + r.uniform(0, np.pi))) ** 6
    chop /= 4.0
    rumble = dsp.lp(dsp.brown(n, r, sr), sr, 220.0)
    swell = 0.85 + 0.15 * dsp.smooth_noise(n, sr, r, 0.7, periodic=True)
    # Motor whine: eight 14-pole motors (7 x the shaft rate of a 2-blade prop), very faint.
    whine = np.zeros(n)
    for off in offsets:
        fe = _cycles((base + off) * 0.5 * 7.0)
        whine += dsp.partials(n, sr, [fe, _cycles(fe * 2), _cycles(fe * 6)], [1.0, 0.4, 0.25], phases=r.uniform(0, 2 * np.pi, 3))
    out = (0.55 * y + 0.45 * dsp.normalize(wash * (0.35 + chop)) + 0.4 * dsp.normalize(rumble)) * swell
    out += 0.04 * dsp.normalize(whine)
    return dsp.peq(out, sr, 160.0, 3.0, 0.8)


@sound("sfx/drone_release", seed=17102, peak_db=-1.0)
def drone_release(seed, variant, sr):
    r = dsp.rng(seed)
    y = np.zeros(dsp.ns(1.4, sr))
    # Solenoid hook: a hard steel clunk with a short ring.
    dsp.place(y, dsp.impact(sr, r, "metal_bar", 520.0, 0.5, contact_ms=0.25, t60=0.25, click=0.5, click_hz=3500.0), 0, 1.0)
    dsp.place(y, dsp.impact(sr, r, "metal_sheet", 180.0, 0.4, contact_ms=1.5, t60=0.2, click=0.0), dsp.ns(0.01, sr), 0.6)
    # The sling slapping free.
    slap = dsp.band_noise(dsp.ns(0.12, sr), sr, r, 300.0, 3000.0) * dsp.env_ar(dsp.ns(0.12, sr), sr, 0.002, 0.08)
    dsp.place(y, slap, dsp.ns(0.09, sr), 0.35)
    # The drogue chute snapping open: a fabric crack and a short flutter.
    m = dsp.ns(0.7, sr)
    crack = dsp.band_noise(m, sr, r, 400.0, 6000.0, slope_db_oct=-2.0) * dsp.env_ar(m, sr, 0.004, 0.18)
    flutter = 0.5 + 0.5 * np.sin(2 * np.pi * 23.0 * np.arange(m) / sr)
    dsp.place(y, crack * (0.6 + 0.4 * flutter), dsp.ns(0.42, sr), 0.7)
    return y
