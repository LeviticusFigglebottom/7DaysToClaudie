"""Wildlife (ADR-0027): the valley's animals, synthesized like everything else.

Deer blow an alarm snort (a forced nasal exhale: turbulent air through the nostrils' resonances,
fluttering) and bleat when hurt; their hooves drum when they bolt. A hare thumps its hind foot
and screams when caught. Songbirds chatter in FM sweeps and give sharp alarm chips; crows caw
through a nasal syrinx. A flushing flock is a flurry of wingbeats, small and fast for songbirds,
slow heavy whooshes for crows. Butchering is wet work. Outdoor calls carry a little forest air.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _outdoor(y, sr, seed, mix=0.12):
    return dsp.reverb(y, sr, "forest", mix, seed=seed, tail=True)


# --- Deer -------------------------------------------------------------------------------------

@sound("wildlife/deer_snort", variants=3, seed=7101, peak_db=-1.5)
def deer_snort(seed, variant, sr):
    """The alarm 'blow': a hard nasal exhale, often doubled."""
    r = dsp.rng(seed)
    out = _buf(1.4, sr)
    t = 0.0
    for k in range(1 + int(r.integers(0, 2))):
        d = r.uniform(0.32, 0.5)
        n = dsp.ns(d, sr)
        env = dsp.env_ar(n, sr, 0.008, d * 0.55, power=1.4)
        air = dsp.band_noise(n, sr, r, 200.0, 7000.0, slope_db_oct=-2.0)
        flutter = 1.0 - 0.45 * (0.5 + 0.5 * np.sin(2 * np.pi * dsp.phase(r.uniform(26.0, 38.0), n, sr)))
        y = (dsp.bp(air, sr, dsp.vary(r, 640.0, 0.1), 2.2) + 0.8 * dsp.bp(air, sr, dsp.vary(r, 1250.0, 0.1), 3.0)
             + 0.45 * dsp.bp(air, sr, dsp.vary(r, 2600.0, 0.1), 3.5) + 0.25 * dsp.hp(air, sr, 4000.0))
        # a faint whistle where the nostrils pinch
        y = y + 0.08 * dsp.sine(dsp.curve([(0, r.uniform(1800, 2200)), (d, r.uniform(1300, 1600))], n, sr), n, sr)
        dsp.place(out, dsp.normalize(y * env * flutter) * (1.0 if k == 0 else 0.7), dsp.ns(t, sr))
        t += d + r.uniform(0.12, 0.3)
    return _outdoor(out, sr, seed)


@sound("wildlife/deer_bleat", variants=2, seed=7102, peak_db=-2.0)
def deer_bleat(seed, variant, sr):
    """A hurt deer's bawl: voiced, nasal, falling."""
    r = dsp.rng(seed)
    d = r.uniform(0.55, 0.8)
    f0 = [(0.0, r.uniform(380, 460)), (d * 0.25, r.uniform(520, 600)), (d, r.uniform(260, 320))]
    amp = [(0.0, 0.0), (0.04, 1.0), (d * 0.7, 0.8), (d, 0.0)]
    y = dsp.voice(sr, d, f0, vowel=[(0.0, "a"), (d * 0.4, "e"), (d, "u")], amp=amp, r=r, tract=0.7, jitter=0.02, shimmer=0.06,
                  rough=0.25, breath=0.08, tilt_db=-2.0)
    y = dsp.peq(y, sr, 1100.0, 5.0, 3.0)   # the nasal ring
    return _outdoor(y, sr, seed, 0.15)


@sound("wildlife/hoof_run", variants=2, seed=7103, peak_db=-3.0)
def hoof_run(seed, variant, sr):
    """A band bolting: hooves drumming the turf in a gallop's four-beat, fading as they go."""
    r = dsp.rng(seed)
    dur = 2.6
    out = _buf(dur, sr)
    t = 0.0
    gait = 0.42
    while t < dur - 0.2:
        fade = 1.0 - t / dur
        for k, off in enumerate((0.0, 0.07, 0.19, 0.25)):
            th = dsp.thud(sr, r, f=dsp.vary(r, 95.0, 0.2), dur=0.12, contact_ms=4.0, noise=0.5, knock=0.4,
                          knock_f=dsp.vary(r, 380.0, 0.2))
            dsp.place(out, th * fade * r.uniform(0.6, 1.0), dsp.ns(t + off + r.uniform(-0.01, 0.01), sr))
        t += gait * r.uniform(0.95, 1.05)
    out = dsp.lp(out, sr, 2200.0)
    return _outdoor(out, sr, seed, 0.2)


# --- Hare -------------------------------------------------------------------------------------

@sound("wildlife/hare_thump", variants=2, seed=7104, peak_db=-3.0)
def hare_thump(seed, variant, sr):
    r = dsp.rng(seed)
    out = _buf(0.9, sr)
    for k in range(int(r.integers(2, 4))):
        dsp.place(out, dsp.thud(sr, r, f=dsp.vary(r, 70.0, 0.15), dur=0.18, contact_ms=6.0, noise=0.4) * (1.0 - 0.2 * k),
                  dsp.ns(k * r.uniform(0.16, 0.24), sr))
    return out


@sound("wildlife/hare_squeal", variants=2, seed=7105, peak_db=-2.0)
def hare_squeal(seed, variant, sr):
    """A caught hare's scream: high, harsh, pulsing."""
    r = dsp.rng(seed)
    d = r.uniform(0.5, 0.75)
    n = dsp.ns(d, sr)
    f0 = dsp.curve([(0.0, r.uniform(1100, 1300)), (d * 0.3, r.uniform(1700, 1900)), (d, r.uniform(1200, 1400))], n, sr, "smooth")
    f0 = f0 * (1 + 0.03 * dsp.smooth_noise(n, sr, r, 30.0))
    src = dsp.saw(f0, n, sr) * 0.6 + 0.4 * dsp.square(f0 * 0.5, n, sr, pw=0.3)
    pulse = 0.65 + 0.35 * np.sin(2 * np.pi * dsp.phase(r.uniform(9.0, 13.0), n, sr))
    env = dsp.env_ar(n, sr, 0.01, d * 0.8) * pulse
    y = dsp.bp(src, sr, 2400.0, 1.5) + 0.6 * dsp.bp(src, sr, 4200.0, 2.5) + 0.2 * dsp.band_noise(n, sr, r, 2000, 7000)
    return _outdoor(dsp.sat(dsp.normalize(y * env), 1.6), sr, seed)


# --- Songbirds --------------------------------------------------------------------------------

def _chirp(sr, r, f0, f1, d, shape="smooth", fm=0.0):
    n = dsp.ns(d, sr)
    f = dsp.curve([(0.0, f0), (d, f1)], n, sr, shape)
    if fm:
        f = f * (1 + fm * np.sin(2 * np.pi * dsp.phase(r.uniform(40, 90), n, sr)))
    y = dsp.sine(f, n, sr) + 0.18 * dsp.sine(f * 2.0, n, sr)
    return y * dsp.env_ar(n, sr, d * 0.15, d * 0.6) * np.hanning(n) ** 0.3


@sound("wildlife/songbird_chatter", variants=4, seed=7106, peak_db=-4.0)
def songbird_chatter(seed, variant, sr):
    """A few birds talking: trills, slurred whistles and chips, overlapping."""
    r = dsp.rng(seed)
    dur = r.uniform(1.8, 2.6)
    out = _buf(dur + 0.3, sr)
    for bird in range(int(r.integers(2, 4))):
        t = r.uniform(0.0, 0.6)
        base = r.uniform(3200, 5200)
        g = r.uniform(0.4, 1.0)
        while t < dur:
            kind = r.integers(0, 3)
            if kind == 0:          # trill
                for k in range(int(r.integers(4, 9))):
                    dsp.place(out, _chirp(sr, r, base * 1.15, base * 0.9, 0.035) * g, dsp.ns(t, sr))
                    t += 0.045
            elif kind == 1:        # slurred whistle
                d = r.uniform(0.12, 0.25)
                dsp.place(out, _chirp(sr, r, base * r.uniform(0.7, 0.9), base * r.uniform(1.1, 1.4), d, fm=0.02) * g, dsp.ns(t, sr))
                t += d
            else:                  # chips
                for k in range(int(r.integers(1, 4))):
                    dsp.place(out, _chirp(sr, r, base * 1.6, base * 1.1, 0.02, "lin") * g, dsp.ns(t, sr))
                    t += r.uniform(0.07, 0.12)
            t += r.uniform(0.08, 0.35)
    out = dsp.hp(out, sr, 1500.0)
    return _outdoor(out, sr, seed, 0.18)


@sound("wildlife/songbird_alarm", variants=2, seed=7107, peak_db=-3.0)
def songbird_alarm(seed, variant, sr):
    """Alarm: hard 'tchik' chips in a rattle, every bird at once."""
    r = dsp.rng(seed)
    out = _buf(1.2, sr)
    for bird in range(int(r.integers(3, 6))):
        t = r.uniform(0.0, 0.2)
        base = r.uniform(4500, 6500)
        for k in range(int(r.integers(3, 7))):
            dsp.place(out, _chirp(sr, r, base, base * 0.6, 0.018, "lin") * r.uniform(0.5, 1.0), dsp.ns(t, sr))
            t += r.uniform(0.05, 0.11)
    return _outdoor(dsp.hp(out, sr, 2000.0), sr, seed)


# --- Crows ------------------------------------------------------------------------------------

def _caw(sr, r, harsh=1.0, d=None):
    d = d if d is not None else r.uniform(0.28, 0.42)
    m = dsp.ns(d, sr)
    f0 = dsp.curve([(0, r.uniform(520, 620)), (d * 0.3, r.uniform(660, 760)), (d, r.uniform(440, 540))], m, sr, "smooth")
    src = dsp.saw(f0 * (1 + 0.04 * harsh * dsp.smooth_noise(m, sr, r, 90.0)), m, sr) + 0.5 * harsh * dsp.band_noise(m, sr, r, 800.0, 5000.0)
    src *= 0.7 + 0.3 * dsp.smooth_noise(m, sr, r, 60.0)
    y = dsp.bp(src, sr, 1300.0, 3.0) + 0.7 * dsp.bp(src, sr, 2100.0, 4.0) + 0.3 * dsp.bp(src, sr, 3400.0, 4.0)
    env = dsp.env_ar(m, sr, 0.02, d * 0.75)
    return dsp.sat(y * env, 1.0 + 0.6 * harsh)


@sound("wildlife/crow_caw", variants=4, seed=7108, peak_db=-2.0)
def crow_caw(seed, variant, sr):
    r = dsp.rng(seed)
    out = _buf(2.2, sr)
    t = 0.0
    for _ in range(int(r.integers(1, 4))):
        c = _caw(sr, r, harsh=r.uniform(0.6, 1.0))
        dsp.place(out, c, dsp.ns(t, sr))
        t += len(c) / sr + r.uniform(0.15, 0.35)
    return _outdoor(out, sr, seed, 0.2)


@sound("wildlife/crow_alarm", variants=2, seed=7109, peak_db=-1.5)
def crow_alarm(seed, variant, sr):
    """Mobbing calls: rapid, harsh, several birds."""
    r = dsp.rng(seed)
    out = _buf(2.0, sr)
    for bird in range(3):
        t = r.uniform(0.0, 0.3)
        while t < 1.6:
            c = _caw(sr, r, harsh=1.4, d=r.uniform(0.16, 0.24))
            dsp.place(out, c * r.uniform(0.5, 1.0), dsp.ns(t, sr))
            t += len(c) / sr + r.uniform(0.06, 0.16)
    return _outdoor(out, sr, seed, 0.2)


# --- Wings --------------------------------------------------------------------------------------

def _flurry(sr, r, birds, rate, f_lo, f_hi, dur, start_spread, decay):
    n = dsp.ns(dur, sr)
    out = np.zeros(n)
    for b in range(birds):
        t0 = r.uniform(0.0, start_spread)
        m = n - dsp.ns(t0, sr)
        if m <= 0:
            continue
        beat = rate * r.uniform(0.85, 1.15)
        ph = dsp.phase(beat * (1.0 - 0.25 * np.linspace(0, 1, m)), m, sr)
        strokes = np.maximum(0.0, np.sin(2 * np.pi * ph)) ** 3
        noise = dsp.band_noise(m, sr, r, f_lo, f_hi, slope_db_oct=-1.5)
        env = dsp.env_ar(m, sr, 0.01, decay * r.uniform(0.7, 1.2))
        y = noise * strokes * env * r.uniform(0.5, 1.0)
        dsp.place(out, y, dsp.ns(t0, sr))
    return out


@sound("wildlife/wingbeats_small", variants=3, seed=7110, peak_db=-2.0)
def wingbeats_small(seed, variant, sr):
    """A songbird flock going up: a whirring burst of tiny fast wings."""
    r = dsp.rng(seed)
    y = _flurry(sr, r, int(r.integers(6, 11)), 16.0, 900.0, 6500.0, 1.4, 0.3, 0.55)
    return _outdoor(dsp.normalize(y), sr, seed, 0.1)


@sound("wildlife/wingbeats_large", variants=2, seed=7111, peak_db=-2.0)
def wingbeats_large(seed, variant, sr):
    """Crows lifting off: heavy, slow whooshes and a clatter of primaries."""
    r = dsp.rng(seed)
    y = _flurry(sr, r, int(r.integers(4, 8)), 5.0, 180.0, 2600.0, 2.0, 0.5, 0.9)
    y = y + 0.25 * dsp.normalize(dsp.clicks(len(y), sr, r, 60.0 * np.exp(-np.linspace(0, 4, len(y))), 1500.0, 6000.0))
    return _outdoor(dsp.normalize(y), sr, seed, 0.12)


# --- Butchering -------------------------------------------------------------------------------

@sound("sfx/butcher_cut", variants=3, seed=7112, peak_db=-3.0)
def butcher_cut(seed, variant, sr):
    """Knife work on a carcass: hide parting, wet tissue, a joint giving."""
    r = dsp.rng(seed)
    out = _buf(1.1, sr)
    dsp.place(out, dsp.tear(sr, 0.45, r, [(0.0, 0.2), (0.15, 1.0), (0.45, 0.0)], f_lo=400.0, f_hi=4500.0, wet=0.8), 0)
    dsp.place(out, dsp.squelch(sr, r, 0.25, 1800.0, 500.0) * 0.7, dsp.ns(0.35, sr))
    if r.uniform() < 0.6:
        dsp.place(out, dsp.crack(sr, r, 0.2, n_clicks=3) * 0.5, dsp.ns(0.7, sr))
    return out
