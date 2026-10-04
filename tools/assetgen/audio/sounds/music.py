"""Score: dread drone and menu loops, discovery / Hum / dawn / death stingers. Stereo.

Instruments (all synthesized here):
  piano   - stiff-string partials f_n = n f0 sqrt(1 + B n^2) as a modal bank struck by a felt-hammer pulse;
            each partial is a detuned string pair (prompt + aftersound two-stage decay, unison beating);
            hammer-position comb, velocity-dependent brightness, hammer thump. Cached per (key, velocity).
  strings - ensemble of detuned band-limited saws with independent slow vibrato, bowed-body EQ,
            envelope-tracking low-pass, slow attack/release.
  choir   - formant voices ('ah'/'oo') detuned in threes.
  bells/glass/metal - modal presets from dsp.
Loops use oscillators quantized to whole cycles per loop and zero-mean periodic modulation, events placed
on a circular canvas, and circular reverb, so the seam is exact.
Key centre: D minor (Hollowmere's lament); dawn resolves to D major.
"""
from __future__ import annotations

import functools
import math

import numpy as np

from .. import dsp
from ..registry import sound

SR = 44100


# --------------------------------------------------------------------------------------------- instruments

@functools.lru_cache(maxsize=128)
def _piano_note(midi: int, vq: int, dur_q: int, sr: int = SR) -> np.ndarray:
    """One piano note (mono), velocity vq/8, duration dur_q/4 s (pedal held, fades at the end)."""
    vel = vq / 8.0
    dur = dur_q / 4.0
    r = dsp.rng(midi * 131 + vq * 7 + dur_q, "piano")
    f0 = float(dsp.midi_hz(midi))
    B = 0.00012 * (f0 / 261.6) ** 0.7 + 0.00002
    nmax = int(min(30, (min(7500.0, 0.45 * sr) / f0)))
    k = np.arange(1, max(nmax, 1) + 1, dtype=np.float64)
    fn = k * f0 * np.sqrt(1.0 + B * k * k)
    keep = fn < min(7500.0, 0.45 * sr)
    k, fn = k[keep], fn[keep]
    x0 = 0.12 + 0.01 * r.uniform(-1, 1)
    amp = (0.3 + 0.7 * np.abs(np.sin(np.pi * k * x0))) / (1.0 + (k / (2.5 + 7.0 * vel)) ** 1.7)
    t2 = float(np.clip(13.0 * (f0 / 65.0) ** -0.55, 1.2, 13.0))
    t60_after = t2 / (1.0 + 0.09 * (k - 1) * (f0 / 261.6) ** 0.35)
    t60_prompt = t60_after * 0.16
    det = r.uniform(0.4, 1.6, len(k)) * (k < 14)
    freqs = np.concatenate([fn * dsp.cents(-det / 2), fn * dsp.cents(det / 2)])
    t60s = np.concatenate([t60_prompt, t60_after])
    amps = np.concatenate([amp * 0.7, amp * 0.3])
    n = dsp.ns(dur, sr)
    exc = np.zeros(n)
    contact = (0.8 + 2.6 * (1.0 - vel)) * (261.6 / f0) ** 0.25
    dsp.place(exc, dsp.pulse(sr, contact), 0)
    y = dsp.modal_bank(exc, sr, freqs, t60s, amps)
    y = dsp.normalize(y)
    L = dsp.ns(0.03, sr)
    thump = dsp.lp(r.standard_normal(L), sr, 900.0 + 2000.0 * vel) * dsp.env_ar(L, sr, 0.001, 0.02)
    dsp.place(y, dsp.normalize(thump) * (0.05 + 0.08 * vel), 0)
    y = dsp.fade(y, sr, 0.0, min(1.5, dur * 0.3))
    return y * vel ** 1.2


def piano(sr, midi, vel, dur):
    return _piano_note(int(midi), int(round(np.clip(vel, 0.05, 1.0) * 8)), int(round(dur * 4)), sr)


def _pan_for(midi):
    return float(np.clip((midi - 60) / 30.0, -0.7, 0.7))


def strings(sr, r, notes, dur, *, attack=2.0, release=2.5, bright=0.45, detune=9.0, voices=4, vib=7.0, trem=0.0):
    """String-ensemble pad over `notes` (midi list) held for dur s (+release). Returns stereo."""
    n = dsp.ns(dur + release, sr)
    out = np.zeros((n, 2))
    for m in notes:
        f = float(dsp.midi_hz(m))
        for v in range(voices):
            c = detune * ((v / max(voices - 1, 1)) * 2 - 1) + r.uniform(-2.0, 2.0)
            fv = f * dsp.cents(c) * dsp.vibrato(n, sr, r.uniform(4.6, 5.8), vib, r, 0.4, onset=attack * 0.8)
            s_ = dsp.saw(fv, n, sr, r.random())
            out += dsp.pan(s_, ((v / max(voices - 1, 1)) * 2 - 1) * 0.6 + r.uniform(-0.1, 0.1))
    t = np.arange(n) / sr
    env = dsp.smoothstep(t / attack) * np.where(t > dur, np.exp(-(t - dur) * 6.9 / release), 1.0)
    cut = (700.0 + 2600.0 * bright) * (0.55 + 0.45 * env)
    out = dsp.lp(out, sr, cut, q=0.6)
    out = dsp.eq(out, sr, ("hp", 70.0), ("peak", 320.0, 2.5, 1.0), ("peak", 1250.0, 2.0, 1.2), ("peak", 2900.0, 1.5, 1.5),
                 ("hs", 5500.0, -8.0))
    if trem:
        out = dsp.tremolo(out, sr, r.uniform(10.0, 12.0), trem, r, 0.3)
    return out * env[:, None] / (len(notes) * voices) ** 0.5


def choir(sr, r, notes, dur, vowel="a", attack=1.5, release=2.0, tract=1.05):
    n = dsp.ns(dur + release, sr)
    out = np.zeros((n, 2))
    amp = [(0, 0), (attack, 1.0), (dur, 0.85), (dur + release, 0.0)]
    for m in notes:
        f = float(dsp.midi_hz(m))
        for c in (-8.0, 0.0, 7.0):
            f0 = f * dsp.cents(c + r.uniform(-3, 3)) * dsp.vibrato(n, sr, r.uniform(4.8, 5.6), 18.0, r, 0.5, onset=attack)
            v = dsp.voice(sr, n / sr, f0, vowel, amp, r, oq=0.65, sq=2.0, jitter=0.006, shimmer=0.03, breath=0.18, asp=0.25,
                          tract=tract, wander=0.02, os=1)
            out += dsp.pan(dsp.normalize(v), r.uniform(-0.7, 0.7))
    return out / (len(notes) * 3) ** 0.5


def bell(sr, r, f0, dur=5.0, bright=1.0):
    return dsp.impact(sr, r, "bell", f0, dur, contact_ms=0.4 / bright, t60=dur * 0.7, click=0.05, noise=0.1, tilt=0.4)


def glass_tone(sr, r, f, dur, attack=0.8):
    """Soft sine 'glass harmonica' tone with gentle beating partner."""
    n = dsp.ns(dur, sr)
    y = dsp.sine(f, n, sr) + 0.5 * dsp.sine(f * dsp.cents(r.uniform(3, 6)), n, sr) + 0.08 * dsp.sine(2 * f, n, sr)
    return y * dsp.env_ar(n, sr, attack, dur * 0.9)


def sub_boom(sr, r, f=34.0, dur=3.0, t60=2.0):
    y = dsp.thud(sr, r, f, dur, contact_ms=25.0, t60=t60, noise=0.4, noise_lp=200.0)
    return dsp.normalize(y)


# --------------------------------------------------------------------------------------------- loop helpers

def _q(f, L):
    return max(1, round(f * L)) / L


def _plfo(n, sr, r, rate):
    """Zero-mean periodic modulation in about [-1, 1]."""
    x = dsp.smooth_noise(n, sr, r, rate, periodic=True)
    return x - x.mean()


def _psaw(f, n, sr, r, L, cents_depth=6.0, rate=0.2):
    fq = _q(f, L)
    ff = fq * (1.0 + (2 ** (cents_depth / 1200.0) - 1.0) * _plfo(n, sr, r, rate))
    return dsp.saw(ff, n, sr, r.random())


def _ploop_lp(x, sr, cut, q=0.6, pre=0.5):
    P = dsp.ns(pre, sr)
    xx = np.concatenate([x[-P:], x], axis=0)
    cc = np.concatenate([cut[-P:], cut]) if isinstance(cut, np.ndarray) else cut
    return dsp.biquad(xx, sr, "lp", cc, q, block=256)[P:]


def _circ(fn, x, sr, pre=0.5):
    return dsp.circular(fn, x, sr, pre)


# --------------------------------------------------------------------------------------------- loops

@sound("music/dread_drone", seed=11001, loop=True, peak_db=-6.2)
def dread_drone(seed, variant, sr):
    """Low D pedal (D1/A1 saw drones under a breathing filter), a minor-second string cluster that swells
    and recedes, bowed-metal resonances, glassy high tones bleeding in, two distant sub booms."""
    L = 60.0
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "dread")
    out = np.zeros((n, 2))
    breath = 0.5 + 0.5 * _plfo(n, sr, dsp.rng(seed, "b"), 1.0 / 15.0) / 1.0
    # drones
    for m, g, p in ((26, 1.0, -0.2), (33, 0.6, 0.25), (38, 0.35, 0.0)):
        f = float(dsp.midi_hz(m))
        s_ = sum(_psaw(f * dsp.cents(c), n, sr, r, L, 4.0, 0.1) for c in (-6.0, 0.0, 5.0))
        out += dsp.pan(s_ * g, p)
    cut = 140.0 + 260.0 * np.clip(breath, 0, 1)
    out = _ploop_lp(out, sr, cut, 0.8)
    out = dsp.normalize(out)
    # string cluster D3 Eb3 A3 Bb3 swelling independently
    cl = np.zeros((n, 2))
    for m in (50, 51, 57, 58):
        f = float(dsp.midi_hz(m))
        sw = np.clip(0.5 + 0.9 * _plfo(n, sr, r, r.uniform(1 / 30.0, 1 / 18.0)), 0, 1) ** 2
        v = sum(_psaw(f * dsp.cents(c), n, sr, r, L, 8.0, 0.3) for c in (-9.0, -3.0, 4.0, 10.0))
        cl += dsp.pan(v * sw, r.uniform(-0.6, 0.6))
    cl = _circ(lambda x: dsp.eq(dsp.lp(x, sr, 1400.0, 0.6), sr, ("hp", 120.0), ("peak", 900.0, 2.0, 1.0)), cl, sr)
    out += 0.45 * dsp.normalize(cl)
    # bowed metal: noise-excited pipe modes, slow swells
    rm = dsp.rng(seed, "metal")
    md = dsp.modes("pipe", float(dsp.midi_hz(62)), rm, t60=3.0)
    exc = dsp._spec_shape(n, rm, lambda f: dsp.smoothstep((f - 200.0) / 200.0) / (1 + (f / 4000.0) ** 2), sr)
    exc *= np.clip(0.3 + _plfo(n, sr, rm, 1 / 20.0), 0, 1) ** 3 * 0.01
    met = _circ(lambda x: dsp.modal_bank(x, sr, md[0], md[1], md[2]), exc, sr, 3.0)
    out += 0.18 * dsp.normalize(_circ(lambda x: dsp.decorrelate(x, sr, dsp.rng(seed, "dec"), 0.8), met, sr, 0.1))
    # glass tones (whole-cycle sines) bleeding in
    rg = dsp.rng(seed, "glass")
    for m in (86, 87, 93):
        f = _q(float(dsp.midi_hz(m)), L)
        sw = np.clip(0.2 + 0.9 * _plfo(n, sr, rg, 1 / 25.0), 0, 1) ** 3
        tone = np.sin(dsp.TAU * f * np.arange(n) / sr + rg.uniform(0, 6.28)) * sw
        out += dsp.pan(tone, rg.uniform(-0.8, 0.8)) * 0.03
    # two distant booms
    rb = dsp.rng(seed, "boom")
    for t in (rb.uniform(5, 15), rb.uniform(35, 45)):
        dsp.loop_place(out, dsp.pan(sub_boom(sr, rb, 32.0, 4.0, 2.5) * 0.35, rb.uniform(-0.3, 0.3)), dsp.ns(t, sr))
    return dsp.reverb(out, sr, "hall", 0.35, seed=seed, stereo_=True, circular=True, rt=(4.5, 3.6, 2.0))


_MENU_CHORDS = [   # (bass midi, pad midis)
    (38, [50, 53, 57, 64]),        # Dm9
    (34, [53, 57, 58, 62]),        # Bbmaj7
    (41, [53, 57, 60, 64]),        # Fmaj7
    (40, [55, 60, 62, 64]),        # C(add9)/E
    (43, [53, 57, 58, 62]),        # Gm9
    (41, [50, 53, 57, 62]),        # Dm/F
    (34, [50, 53, 57, 60]),        # Bb6/9-ish
    (33, [50, 52, 55, 62]),        # A7sus4  -> back to Dm9
]
_D_MINOR = [62, 64, 65, 67, 69, 70, 72, 74, 76, 77, 79, 81, 82, 84, 86]


@sound("music/menu", seed=11006, loop=True, peak_db=-5.4)
def menu(seed, variant, sr):
    """Main menu: slow, sparse, melancholic. String chords breathe through a D-minor progression while a
    piano picks out falling phrases; a bass note anchors each change; faint glass sparkles; big hall."""
    L = 90.0
    n = dsp.ns(L, sr)
    r = dsp.rng(seed, "menu")
    out = np.zeros((n, 2))
    span = L / len(_MENU_CHORDS)
    for i, (bass, pad) in enumerate(_MENU_CHORDS):
        t0 = i * span
        st = strings(sr, r, pad, span + 1.0, attack=3.0, release=4.0, bright=0.35, voices=4)
        dsp.loop_place(out, st * 0.55, dsp.ns(t0 - 1.0, sr) % n)
        b = piano(sr, bass, 0.42, 7.0)
        dsp.loop_place(out, dsp.pan(b, -0.35), dsp.ns(t0 + 0.05, sr) % n)
        if r.random() < 0.6:
            b2 = piano(sr, bass + 7, 0.3, 6.0)
            dsp.loop_place(out, dsp.pan(b2, -0.25), dsp.ns(t0 + r.uniform(0.6, 1.2), sr) % n)
        # melody: one or two falling phrases per chord
        chord_tones = set(m % 12 for m in pad) | {bass % 12}
        t = t0 + r.uniform(1.5, 3.0)
        phrases = 1 if r.random() < 0.5 else 2
        for _ in range(phrases):
            idx = int(r.integers(7, len(_D_MINOR)))
            for k in range(int(r.integers(3, 6))):
                cands = [j for j in range(max(0, idx - 3), min(len(_D_MINOR), idx + 2))]
                w = np.array([3.0 if _D_MINOR[j] % 12 in chord_tones else 1.0 for j in cands])
                w *= np.array([1.6 if j < idx else 1.0 for j in cands])          # tend to fall
                idx = cands[int(r.choice(len(cands), p=w / w.sum()))]
                m = _D_MINOR[idx]
                d = r.choice([0.55, 0.8, 1.1, 1.6])
                note = piano(sr, m, r.uniform(0.28, 0.5), 5.0)
                dsp.loop_place(out, dsp.pan(note, _pan_for(m)), dsp.ns(t, sr) % n)
                t += d
            t += r.uniform(1.0, 2.5)
            if t > t0 + span - 1.0:
                break
    rg = dsp.rng(seed, "sparkle")
    for _ in range(6):
        m = int(rg.choice([81, 86, 88, 93]))
        g = glass_tone(sr, rg, float(dsp.midi_hz(m)), 5.0, 1.5)
        dsp.loop_place(out, dsp.pan(g, rg.uniform(-0.8, 0.8)) * 0.03, dsp.ns(rg.uniform(0, L), sr))
    air = np.stack([dsp._spec_shape(n, r, lambda f: dsp.smoothstep((f - 2000.0) / 2000.0) / (1 + (f / 9000.0) ** 2), sr)
                    for _ in range(2)], axis=1)
    out += 0.004 * air
    return dsp.reverb(out, sr, "hall", 0.42, seed=seed, stereo_=True, circular=True, rt=(3.6, 3.0, 1.8))


# --------------------------------------------------------------------------------------------- stingers

@sound("music/discovery", seed=11002, peak_db=-4.0)
def discovery(seed, variant, sr):
    """Found something: a quick rising piano arpeggio over a soft D-minor(add9) string swell, a glass
    shimmer answering at the top."""
    r = dsp.rng(seed, "discovery")
    dur = 6.5
    out = np.zeros((dsp.ns(dur, sr), 2))
    st = strings(sr, r, [50, 57, 62, 64, 65], 2.8, attack=0.9, release=2.2, bright=0.45)
    dsp.place(out, st * 0.6, dsp.ns(0.1, sr))
    for i, m in enumerate((57, 62, 65, 69, 76)):
        dsp.place(out, dsp.pan(piano(sr, m, 0.5 + 0.04 * i, 5.0), _pan_for(m)), dsp.ns(0.09 * i, sr), 0.9)
    for m, t in ((81, 0.55), (88, 0.75)):
        dsp.place(out, dsp.pan(glass_tone(sr, r, float(dsp.midi_hz(m)), 3.5, 0.4), r.uniform(-0.6, 0.6)) * 0.08, dsp.ns(t, sr))
    return dsp.reverb(out, sr, "hall", 0.4, seed=seed, stereo_=True)


@sound("music/hum_start", seed=11003, peak_db=-1.7)
def hum_start(seed, variant, sr):
    """The Hum begins: a seismic sub hit and a brassy low cluster tearing open, tremolo strings rising in
    tritones, the Hollowed chorus swelling from far away, bowed metal singing - then the drone holds."""
    r = dsp.rng(seed, "humstart")
    dur = 10.0
    n = dsp.ns(dur, sr)
    out = np.zeros((n, 2))
    dsp.place(out, dsp.pan(sub_boom(sr, r, 30.0, 4.0, 3.0), 0.0), 0, 1.0)
    rum = dsp.lp(dsp.brown(n, r), sr, 90.0, order=4) * dsp.env_ar(n, sr, 0.05, 5.0)
    out += 0.4 * dsp.normalize(rum)[:, None]
    # braam: detuned saws D1 D2 A2 D3 through an opening/closing filter, overdriven
    br = np.zeros(n)
    for m in (26, 38, 45, 50):
        f = float(dsp.midi_hz(m))
        for c in (-12.0, 0.0, 11.0):
            br += dsp.saw(f * dsp.cents(c), n, sr, r.random())
    cut = dsp.curve([(0, 120.0), (0.35, 1700.0), (2.5, 600.0), (dur, 250.0)], n, sr, "exp")
    br = dsp.lp(br, sr, cut, q=1.1) * dsp.curve([(0, 0), (0.06, 1.0), (3.0, 0.7), (dur - 1.0, 0.35), (dur, 0.0)], n, sr)
    br = dsp.asym(br / dsp.peak(br), 2.5, 0.15)
    out += 0.7 * dsp.decorrelate(br, sr, r, 0.5)
    # tremolo strings: tritone cluster rising in
    st = strings(sr, r, [62, 63, 68, 69], 6.0, attack=3.5, release=2.5, bright=0.6, trem=0.6)
    dsp.place(out, st * 0.7, dsp.ns(0.6, sr))
    # far chorus of Hollowed
    ch = np.zeros(n)
    for _ in range(9):
        d = r.uniform(3.0, 6.0)
        f0 = r.uniform(65.0, 120.0)
        v = dsp.voice(sr, d, [(0, f0), (d * 0.5, f0 * r.uniform(1.1, 1.4)), (d, f0 * 0.75)], [(0, "uh"), (d * 0.5, "a"), (d, "u")],
                      [(0, 0), (d * 0.5, 1.0), (d, 0)], r, oq=0.4, jitter=0.05, shimmer=0.12, sub=0.4, rough=0.4, breath=0.1,
                      tract=0.86, bw=1.5, os=1)
        dsp.place(ch, dsp.lp(dsp.normalize(v), sr, 1500.0), dsp.ns(r.uniform(1.0, 3.5), sr), r.uniform(0.4, 1.0))
    chs = dsp.reverb(ch, sr, "valley", 1.0, seed=seed, stereo_=True, tail=False)
    out += 0.3 * dsp.normalize(chs)
    # bowed metal
    md = dsp.modes("pipe", float(dsp.midi_hz(57)), r, t60=3.0)
    exc = dsp.band_noise(n, sr, r, 300.0, 4000.0) * dsp.curve([(0, 0), (2.0, 0.2), (6.0, 1.0), (dur, 0.0)], n, sr) * 0.01
    met = dsp.modal_bank(exc, sr, md[0], md[1], md[2])
    out += 0.2 * dsp.normalize(dsp.decorrelate(met, sr, r, 0.8))
    out = dsp.fade(out, sr, 0.0, 1.5)
    return dsp.reverb(out, sr, "cave", 0.3, seed=seed, stereo_=True, rt=(4.5, 3.5, 1.6))


@sound("music/dawn_relief", seed=11004, peak_db=-4.8)
def dawn_relief(seed, variant, sr):
    """Dawn after horde night: warm strings settle from G(add9) onto D major (a plagal 'amen'), a few soft
    piano notes, light glass at the top. Relief, not triumph."""
    r = dsp.rng(seed, "dawn")
    dur = 10.0
    out = np.zeros((dsp.ns(dur, sr), 2))
    s1 = strings(sr, r, [43, 50, 59, 69], 3.6, attack=1.6, release=2.5, bright=0.4)
    s2 = strings(sr, r, [38, 45, 54, 62, 64], 4.0, attack=1.8, release=3.0, bright=0.45)
    dsp.place(out, s1 * 0.7, 0)
    dsp.place(out, s2 * 0.7, dsp.ns(3.3, sr))
    for m, t, v in ((71, 0.4, 0.38), (69, 1.4, 0.34), (66, 3.6, 0.4), (74, 4.6, 0.36), (69, 5.9, 0.3)):
        dsp.place(out, dsp.pan(piano(sr, m, v, 5.0), _pan_for(m)), dsp.ns(t, sr))
    for m, t in ((86, 4.0), (93, 5.2)):
        dsp.place(out, dsp.pan(glass_tone(sr, r, float(dsp.midi_hz(m)), 4.5, 1.2), r.uniform(-0.6, 0.6)) * 0.05, dsp.ns(t, sr))
    return dsp.reverb(out, sr, "hall", 0.4, seed=seed, stereo_=True)


@sound("music/death", seed=11005, peak_db=-5.0)
def death(seed, variant, sr):
    """You died: a low struck piano cluster with a sub hit, strings sagging down a minor third, a distant
    bell tolling once, everything sinking into the dark."""
    r = dsp.rng(seed, "death")
    dur = 9.0
    n = dsp.ns(dur, sr)
    out = np.zeros((n, 2))
    for m, v in ((26, 0.9), (33, 0.8), (38, 0.85), (39, 0.7)):
        dsp.place(out, dsp.pan(piano(sr, m, v, 8.0), -0.2), 0, 0.8)
    dsp.place(out, dsp.pan(sub_boom(sr, r, 36.0, 3.0, 1.6), 0.0), 0, 0.8)
    st = strings(sr, r, [50, 51, 57], 5.0, attack=0.4, release=3.0, bright=0.35)
    m = st.shape[0]
    bend = dsp.curve([(0, 1.0), (1.0, 1.0), (4.5, float(dsp.semis(-3))), (m / sr, float(dsp.semis(-3)))], m, sr, "smooth")
    rate = bend
    st = np.stack([dsp.varispeed(st[:, c], rate) for c in range(2)], axis=1)
    dsp.place(out, st * 0.6, dsp.ns(0.05, sr))
    b = bell(sr, r, float(dsp.midi_hz(50)) * 0.5, 6.0, 0.6)
    dsp.place(out, dsp.pan(dsp.air(b, sr, 150.0), 0.3) * 0.18, dsp.ns(2.4, sr))
    ch = choir(sr, r, [50, 57], 3.5, "oo", attack=1.5, release=2.5, tract=1.0)
    dsp.place(out, dsp.lp(ch, sr, 1200.0) * 0.18, dsp.ns(1.5, sr))
    out = dsp.lp(out, sr, dsp.curve([(0, 9000.0), (dur, 1500.0)], n, sr, "exp"))
    return dsp.reverb(out, sr, "hall", 0.38, seed=seed, stereo_=True)
