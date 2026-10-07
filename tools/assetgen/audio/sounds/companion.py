"""Ezra Vane's voice (ADR-0058 phase 3, TD-303): short spoken barks from the same glottal source +
formant cascade as the player and the Ashen, driven by a small phoneme sequencer so each bark has
the rhythm, stress and intonation of its status-bar line ("Hollowed. Coming in.", "Pack's full.").

He is a lineman in his fifties: a low, worn baritone (f0 ~100-120 Hz, a slightly long tract), a
little rasp and breath, unhurried. The sequencer is deliberately crude (stops are a closure and a
burst, fricatives a band of noise, nasals and liquids formant targets in the voiced stream): the
words half-read, the way a voice does over a radio or across a clearing; the status bar carries the
text. Variant N of a sound is line N of its bark list in data/companions/ezra.json (CompanionMind
plays the variant matching the line it shows). Dry but for a touch of outdoor air: distance and
occlusion are runtime (Sound3D, played from his body).
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound

# Formant targets (F1..F5, B1..B5) the dsp vowel table lacks: liquids, glides, "n", "r".
_L = ((360, 1250, 2700, 3400, 4300), (90, 140, 200, 260, 300))
_Y = ((280, 2150, 2900, 3500, 4400), (60, 110, 160, 220, 260))
_W = ((300, 650, 2200, 3300, 4200), (70, 90, 140, 220, 260))
_R = ((420, 1250, 1550, 3300, 4200), (80, 110, 130, 220, 260))
_N = ((280, 1650, 2500, 3300, 4200), (120, 280, 320, 350, 400))

VOWELS = {"a", "o", "u", "oo", "uh", "e", "ae", "i", "ih", "er", "schwa"}
DIPHTHONGS = {"ai": ("a", "ih"), "ei": ("e", "ih"), "ou": ("o", "oo"), "au": ("a", "oo"), "oi": ("o", "ih")}
# stop: (voiced, burst centre Hz)
STOPS = {"p": (False, 900.0), "b": (True, 900.0), "t": (False, 3900.0), "d": (True, 3300.0), "k": (False, 2100.0),
         "g": (True, 1900.0)}
# fricative: (voiced, centre Hz, gain)
FRICS = {"s": (False, 6200.0, 0.32), "z": (True, 5800.0, 0.2), "sh": (False, 2800.0, 0.28), "f": (False, 4800.0, 0.08),
         "v": (True, 4200.0, 0.06), "th": (False, 5200.0, 0.07), "h": (False, 1600.0, 0.12)}
NASALS = {"m": "m", "n": _N, "ng": "ng"}
APPROX = {"l": _L, "y": _Y, "w": _W, "r": _R}


def _tokens(line):
    """['*h a l', 'o', ','] -> [(phonemes, stressed) | None for a pause]."""
    out = []
    for s in line:
        if s.strip() == ",":
            out.append(None)
            continue
        out.append((s.replace("*", "").split(), s.startswith("*")))
    return out


def say(sr, r, line, *, f0=110.0, rate=1.0, end="fall", energy=1.0, rasp=0.16, breath=0.07, oq=0.5, tilt=3.0,
        tract=0.96, pitch_range=0.22, tail=0.3, lead=0.06):
    """Speaks a line: syllables of phonemes ('*' = stressed, ',' = a pause), a pitch that drifts down
    over the phrase (declination) with a lift on each stressed vowel, and an ending: 'fall'
    (statement), 'rise' (question), 'flat' (trailing off). -> a mono buffer."""
    syl = _tokens(line)
    t = lead
    f0_pts, vow, amp, noise = [], [(0.0, "schwa")], [(0.0, 0.0)], []
    centres = []  # (t, stressed)

    def vt(at, v):
        vow.append((at, v))

    for k, s in enumerate(syl):
        if s is None:
            amp.append((t + 0.01, 0.0))
            t += 0.17 / rate
            amp.append((t, 0.0))
            continue
        ph, stressed = s
        av = (1.0 if stressed else 0.78) * energy
        for i, p in enumerate(ph):
            nxt = ph[i + 1] if i + 1 < len(ph) else None
            if p in VOWELS or p in DIPHTHONGS:
                d = (0.1 if stressed else 0.075) * (1.35 if p in DIPHTHONGS else 1.0) / rate
                if k == len(syl) - 1 or (k + 1 < len(syl) and syl[k + 1] is None):
                    d *= 1.3  # phrase-final lengthening
                a, b = DIPHTHONGS.get(p, (p, p))
                vt(t + 0.012, a)
                vt(t + d * (0.45 if a != b else 0.8), a)
                vt(t + d, b)
                amp += [(t + 0.015, av), (t + d * 0.7, av * 0.92), (t + d - 0.005, av * 0.8)]
                centres.append((t + d * 0.4, stressed))
                t += d
            elif p in STOPS:
                voiced, fc = STOPS[p]
                cl = 0.05 / rate
                amp += [(t + 0.008, 0.1 * av if voiced else 0.0), (t + cl, 0.1 * av if voiced else 0.0)]
                noise.append((t + cl, 0.014 if voiced else 0.022, "burst", fc, 0.5 if voiced else 0.8))
                t += cl
                if not voiced and nxt is None and (k + 1 >= len(syl) or syl[k + 1] is None):
                    t += 0.03  # a released final stop
                elif not voiced:
                    noise.append((t + 0.01, 0.035 / rate, "asp", 1800.0, 0.25))
                    amp.append((t + 0.04 / rate, 0.0))
                    t += 0.04 / rate
                else:
                    t += 0.012
            elif p in FRICS:
                voiced, fc, g = FRICS[p]
                d = (0.055 if p == "h" else 0.085) / rate
                lvl = 0.25 * av if voiced else 0.0
                amp += [(t + 0.012, lvl), (t + d - 0.008, lvl)]
                noise.append((t, d, p, fc, g))
                if p == "h" and nxt is not None:
                    vt(t + d * 0.5, DIPHTHONGS.get(nxt, (nxt,))[0] if nxt in VOWELS or nxt in DIPHTHONGS else "h")
                t += d
            elif p in NASALS:
                d = 0.065 / rate
                vt(t + 0.015, NASALS[p])
                vt(t + d - 0.01, NASALS[p])
                amp += [(t + 0.015, 0.4 * av), (t + d - 0.01, 0.38 * av)]
                t += d
            elif p in APPROX:
                d = 0.055 / rate
                vt(t + d * 0.5, APPROX[p])
                amp += [(t + 0.012, 0.6 * av), (t + d, 0.65 * av)]
                t += d
            else:
                raise ValueError(f"unknown phoneme {p!r} in {line}")
        t += 0.012 / rate  # syllable joint
    dur = t + 0.04
    amp += [(dur - 0.03, 0.0), (dur, 0.0)]
    vt(dur, "schwa")
    # Pitch: declination over the phrase, a lift on stressed vowels, the ending.
    f0_pts.append((0.0, f0 * (1.0 + pitch_range * 0.4)))
    for tc, st in centres:
        x = tc / dur
        f0_pts.append((tc, f0 * (1.0 + pitch_range * (0.45 - 0.6 * x)) * (1.0 + (0.12 if st else 0.0))))
    last = f0_pts[-1][1]
    endf = {"fall": 0.78, "rise": 1.3, "flat": 0.92}[end]
    f0_pts.append((dur, last * endf))
    v = dsp.voice(sr, dur, f0_pts, vow, amp, r, oq=[(0, oq), (dur * 0.8, oq), (dur, oq + 0.2)], sq=2.8, jitter=0.018,
                  shimmer=0.06, drift=0.012, breath=breath, asp=0.25, tract=tract, bw=1.05, wander=0.025,
                  rough=[(0, rasp), (dur * 0.8, rasp), (dur, rasp + 0.2)], rough_rate=dsp.vary(r, 30.0, 0.2),
                  sub=[(0, 0.0), (dur * 0.85, 0.0), (dur, 0.3)], tilt_db=tilt)
    y = dsp.normalize(v)
    for (t0, d, kind, fc, g) in noise:
        n = dsp.ns(d, sr)
        if n < 8:
            continue
        w = dsp.white(n, r)
        if kind == "burst":
            w = dsp.bp(w, sr, fc, 1.2)
            env = dsp.curve([(0, 1.0), (d, 0.0)], n, sr)
        elif kind == "asp" or kind == "h":
            w = dsp.band(w, sr, 500.0, 3500.0)
            env = dsp.curve([(0, 0.0), (d * 0.3, 1.0), (d, 0.3)], n, sr)
        else:
            w = dsp.bp(dsp.hp(w, sr, fc * 0.6), sr, fc, 1.5 if kind in ("s", "z", "sh") else 0.7)
            env = dsp.curve([(0, 0.0), (d * 0.25, 1.0), (d * 0.75, 1.0), (d, 0.0)], n, sr)
        dsp.place(y, dsp.normalize(w * env) * g, dsp.ns(t0, sr))
    out = np.zeros(len(y) + dsp.ns(tail, sr))
    dsp.place(out, y, 0)
    if tail:
        b = dsp.breath(sr, tail, "h", [(0, 0.0), (0.03, 1.0), (tail, 0.0)], r, hiss=0.15)
        dsp.place(out, dsp.normalize(b) * 0.07, dsp.ns(dur - 0.03, sr))
    return out


def _grunt(sr, r, f0, d, vowel, *, rough=0.35, fall=0.6):
    """A pained, pressed grunt ("agh", "nngh") falling into fry."""
    amp = [(0, 0), (0.012, 1.0), (d * 0.35, 0.7), (d * 0.75, 0.3), (d, 0)]
    v = dsp.voice(sr, d, [(0, f0), (0.03, f0 * 1.25), (d * 0.6, f0 * 0.95), (d, f0 * fall)], vowel, amp, r, oq=[(0, 0.38), (d, 0.8)],
                  sq=3.0, jitter=0.025, shimmer=0.08, breath=[(0, 0.1), (d, 0.45)], asp=0.4, tract=0.96, rough=rough,
                  rough_rate=dsp.vary(r, 32.0, 0.2), sub=[(0, 0.0), (d * 0.6, 0.0), (d, 0.4)], tilt_db=4.0)
    return dsp.normalize(v)


def _master(y, sr, seed, mix=0.07):
    y = dsp.sat(y / max(dsp.peak(y), 1e-9), 1.15)
    y = dsp.lshelf(y, sr, 180.0, 2.0)
    return dsp.reverb(y, sr, "forest", mix, seed=seed, tail=True)


def _line(seed, variant, sr, lines, **kw):
    r = dsp.rng(seed, "ezra", variant)
    spec = lines[variant % len(lines)]
    opts = dict(kw)
    opts.update(spec[1] if len(spec) > 1 else {})
    return _master(say(sr, r, spec[0], f0=dsp.vary(r, opts.pop("f0", 110.0), 0.03), **opts), sr, seed + variant)


# Each list matches its bark lines in data/companions/ezra.json, in order.

SPOTTED = [
    (["*h a l", "o", "w e d", ",", "*k uh", "m i ng", "*i n"], {"rate": 1.15, "energy": 1.0, "f0": 124.0, "oq": 0.42}),
    (["g a t", "*m u v", "m e n t"], {"rate": 1.1, "f0": 118.0, "oq": 0.45}),
    (["o n", "y o r", "*l e f t"], {"rate": 1.15, "f0": 122.0, "oq": 0.42}),
]


@sound("voice/ezra_spotted", variants=3, seed=9801, peak_db=-3.0)
def ezra_spotted(seed, variant, sr):
    """Hostiles: low and urgent, pressed, a little faster."""
    return _line(seed, variant, sr, SPOTTED, tilt=4.0)


@sound("voice/ezra_hurt", variants=3, seed=9802, peak_db=-3.5)
def ezra_hurt(seed, variant, sr):
    """Hit hard: 0 "Ah, hell." through the teeth; 1 a pained "agh!"; 2 "Damn it." winded."""
    r = dsp.rng(seed, "ezra_hurt", variant)
    if variant % 3 == 1:
        y = _grunt(sr, r, dsp.vary(r, 150.0, 0.05), dsp.vary(r, 0.38, 0.1), [(0, "ae"), (0.08, "a"), (0.38, "uh")])
        return _master(np.concatenate([y, np.zeros(dsp.ns(0.2, sr))]), sr, seed + variant)
    lines = [["*a", ",", "*h e l"], None, ["*d ae m", "i t"]]
    g = _grunt(sr, r, dsp.vary(r, 140.0, 0.05), 0.22, [(0, "a"), (0.22, "uh")], rough=0.4)
    s = say(sr, r, lines[variant % 3], f0=dsp.vary(r, 108.0, 0.03), rate=0.95, rasp=0.3, breath=0.12, oq=0.42, lead=0.0)
    y = np.zeros(len(g) + len(s))
    dsp.place(y, g * 0.7, 0)
    dsp.place(y, s, dsp.ns(0.2, sr))
    return _master(y, sr, seed + variant)


FULL = [
    (["th a t s", "*o l", "ai", "k a n", "*k ae", "r i"], {"rate": 1.0, "f0": 108.0}),
    (["*p ae k s", "*f u l", ",", "w e r", "d u", "y u", "*w o n t", "i t"], {"rate": 1.05, "f0": 110.0, "end": "rise"}),
]


@sound("voice/ezra_full", variants=2, seed=9803, peak_db=-4.0)
def ezra_full(seed, variant, sr):
    """His pack is full: matter-of-fact, a breath after the weight."""
    return _line(seed, variant, sr, FULL)


CANT_REACH = [
    (["*k ae n t", "g e t", "t u", "*th ae t"], {"rate": 1.0, "f0": 106.0, "end": "flat"}),
]


@sound("voice/ezra_cant_reach", variants=1, seed=9804, peak_db=-4.0)
def ezra_cant_reach(seed, variant, sr):
    """Can't get to it: flat, a little put out."""
    return _line(seed, variant, sr, CANT_REACH)


@sound("voice/ezra_downed", variants=2, seed=9805, peak_db=-4.0)
def ezra_downed(seed, variant, sr):
    """Going down: 0 a long pained groan; 1 a groan and "I'm down" on what breath is left."""
    r = dsp.rng(seed, "ezra_down", variant)
    g = _grunt(sr, r, dsp.vary(r, 128.0, 0.05), dsp.vary(r, 0.7, 0.1), [(0, "a"), (0.2, "uh"), (0.7, "schwa")], rough=0.5,
               fall=0.45)
    if variant % 2 == 0:
        y = np.concatenate([g, np.zeros(dsp.ns(0.35, sr))])
        b = dsp.breath(sr, 0.35, "h", [(0, 0), (0.05, 1.0), (0.35, 0.0)], r, hiss=0.2)
        dsp.place(y, dsp.normalize(b) * 0.2, len(g) - dsp.ns(0.05, sr))
        return _master(y, sr, seed + variant)
    s = say(sr, r, ["ai m", "*d au n"], f0=dsp.vary(r, 98.0, 0.03), rate=0.8, rasp=0.4, breath=0.2, oq=0.6, energy=0.7,
            end="flat", lead=0.0)
    y = np.zeros(len(g) + dsp.ns(0.25, sr) + len(s))
    dsp.place(y, g, 0)
    dsp.place(y, s, len(g) + dsp.ns(0.2, sr))
    return _master(y, sr, seed + variant)


REVIVED = [
    (["n a t", "*d e d", "y e t", ",", "*th ae ng k s"], {"rate": 0.9, "f0": 104.0, "breath": 0.14, "rasp": 0.25}),
]


@sound("voice/ezra_revived", variants=1, seed=9806, peak_db=-4.0)
def ezra_revived(seed, variant, sr):
    """Patched up: a breath in, tired and grateful."""
    r = dsp.rng(seed, "ezra_rev_in", variant)
    pre = dsp.normalize(dsp.breath(sr, 0.3, [(0, "ih"), (0.3, "a")], [(0, 0), (0.2, 1.0), (0.3, 0)], r, hiss=0.5,
                                   hiss_f=2400.0)) * 0.25
    y = _line(seed, variant, sr, REVIVED)
    return np.concatenate([pre, y])


RECRUITED = [
    (["*th ae", "t l", "*h o l d", "th uh", "*l e g", ",", "o l", "*r ai t", ",", "ai m", "w i th", "*y u"], {"rate": 0.95, "f0": 106.0}),
]


@sound("voice/ezra_recruited", variants=1, seed=9807, peak_db=-4.0)
def ezra_recruited(seed, variant, sr):
    """The kit on his leg, getting up: gruff, decided."""
    return _line(seed, variant, sr, RECRUITED)


# The order acknowledgements: one sound for every order (CompanionDef.VOICES maps follow, stay,
# guard, gather, fetch, store, fetched, stored, given, done to it).
ACK = [
    (["*o n", "i t"], {"rate": 1.1, "f0": 112.0}),
    (["*r ai t"], {"rate": 1.0, "f0": 110.0}),
    (["l i d", "*o n"], {"rate": 1.05, "f0": 112.0}),
    (["*h o l", "d i ng"], {"rate": 1.0, "f0": 108.0}),
]


@sound("voice/ezra_ack", variants=4, seed=9808, peak_db=-4.5)
def ezra_ack(seed, variant, sr):
    """An order taken: short and easy."""
    return _line(seed, variant, sr, ACK)
