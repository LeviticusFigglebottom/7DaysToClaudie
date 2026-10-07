"""The Ashen: living men of the Bloom-country (the human faction), synthesized from the same glottal
source + formant cascade as the player's voice, so they read as people, not Hollowed.

What keeps them human (and apart from the zombie/hound voices): a clean adult male source (low
jitter/shimmer, little roughness, no subharmonic growl), vowels that move like speech (consonant
dips and formant glides between syllables), a chest-to-head register break in the war whoop, and
breath around every shout: a quick in-breath before, aspiration on the attack, an exhale after.
Their spears whoosh and thunk into wood or earth with the shaft quivering, and their hide drum
carries across the valley.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound

# An "l" (tongue tip up: low F1, mid F2) for the ululation's tongue trill, and a "y" glide.
_L = ((360, 1250, 2700, 3400, 4300), (90, 140, 200, 260, 300))
_Y = ((280, 2150, 2900, 3500, 4400), (60, 110, 160, 220, 260))


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _outdoor(y, sr, seed, mix=0.12, room="forest"):
    return dsp.reverb(y, sr, room, mix, seed=seed, tail=True)


def _man(sr, r, dur, f0, vowel, amp, *, oq=0.45, rough=0.12, breath=0.06, asp=0.3, tilt=4.0, jitter=0.014,
         shimmer=0.05, tract=None, sub=0.0):
    """An adult man's shouting voice: pressed (low open quotient), bright (positive spectral tilt), with
    natural jitter/shimmer, a little rasp and flow-modulated aspiration. tract ~0.95-1.0 (adult male)."""
    return dsp.voice(sr, dur, f0, vowel, amp, r, oq=oq, sq=3.0, jitter=jitter, shimmer=shimmer, drift=0.01, sub=sub,
                     breath=breath, asp=asp, tract=tract if tract is not None else dsp.vary(r, 0.97, 0.03), bw=1.0,
                     wander=0.03, rough=rough, rough_rate=dsp.vary(r, 34.0, 0.2), tilt_db=tilt)


def _inhale(sr, r, dur=0.14):
    b = dsp.breath(sr, dur, [(0, "ih"), (dur, "a")], [(0, 0), (dur * 0.7, 1.0), (dur, 0.0)], r, hiss=0.6, hiss_f=2400.0)
    return dsp.normalize(b)


def _exhale(sr, r, dur=0.25, vowel="a"):
    b = dsp.breath(sr, dur, [(0, vowel), (dur, "h")], [(0, 0), (0.02, 1.0), (dur, 0.0)], r, hiss=0.2)
    return dsp.normalize(b)


def _h_onset(sr, r, dur=0.05, vowel="a"):
    """Aspirated 'h' going into a vowel (the breath before the voice catches)."""
    b = dsp.breath(sr, dur, vowel, [(0, 0), (dur * 0.6, 1.0), (dur, 0.6)], r, bw=1.2, hiss=0.3)
    return dsp.normalize(b)


# ------------------------------------------------------------------------------------------- war cry

@sound("voice/ashen_warcry", variants=4, seed=9501, peak_db=-2.0)
def ashen_warcry(seed, variant, sr):
    """The charge: 0 tongue-trilled ululation "la-la-la-la-laaa" in head voice; 1 a whoop that breaks
    from chest into falsetto ("ho-ho-HOOOP!"); 2 a held "aaa" rising into "yi-yi-yi"; 3 "hey-YAAA-a!"."""
    r = dsp.rng(seed, "warcry", variant)
    y = _buf(1.9, sr)
    pre = _inhale(sr, r, r.uniform(0.1, 0.14))
    dsp.place(y, pre, 0, 0.18)
    t0 = len(pre) / sr * 0.85
    kind = variant % 4
    if kind == 0:
        # ululation: ~7 syllables a second, the tongue flicking "l" between open "a"s, pitch hopping
        # up on each syllable, then a long falling "aaa" to end
        rate = r.uniform(6.5, 8.0)
        nsyl = int(r.integers(5, 8))
        base = r.uniform(330.0, 400.0)
        hold = r.uniform(0.35, 0.5)
        d = nsyl / rate + hold
        f0p, vow, amp = [(0.0, base * 0.85)], [(0.0, _L)], [(0.0, 0.0), (0.02, 0.8)]
        for k in range(nsyl):
            ts = k / rate
            up = base * (1.12 if k % 2 else 1.0) * (1.0 + 0.03 * k)
            f0p += [(ts + 0.02, up * 0.93), (ts + 0.5 / rate, up)]
            vow += [(ts + 0.012, _L), (ts + 0.45 / rate, "a"), (ts + 0.8 / rate, "a")]
            amp += [(ts + 0.01, 0.6), (ts + 0.5 / rate, 1.0), (ts + 0.92 / rate, 0.85)]
        te = nsyl / rate
        f0p += [(te + 0.05, base * 1.25), (te + hold * 0.6, base * 1.18), (d, base * 0.8)]
        vow += [(te + 0.02, _L), (te + 0.08, "a"), (d, "uh")]
        amp += [(te, 0.7), (te + 0.06, 1.0), (d * 0.92, 0.7), (d, 0.0)]
        v = _man(sr, r, d, f0p, vow, amp, oq=0.55, rough=0.08, breath=0.08, tilt=3.0, jitter=0.012)
    elif kind == 1:
        # two short chest "ho"s, then the voice cracks up an octave-and-more into a held falsetto "OOO"
        # and drops back through the break at the end (yodel-like flip)
        chest = r.uniform(190.0, 230.0)
        head = chest * r.uniform(2.0, 2.3)
        a, b = r.uniform(0.13, 0.16), r.uniform(0.07, 0.1)
        h1 = r.uniform(0.6, 0.8)
        d = 2 * (a + b) + h1
        s2 = a + b
        s3 = 2 * (a + b)
        f0p = [(0, chest * 0.9), (0.03, chest), (a, chest * 0.92), (s2, chest * 1.05), (s2 + a, chest * 0.95),
               (s3, chest * 1.1), (s3 + 0.045, head), (s3 + h1 * 0.7, head * 1.04), (s3 + h1 * 0.88, head * 0.95),
               (s3 + h1 * 0.93, chest * 1.2), (d, chest * 0.9)]
        vow = [(0, "o"), (a, "o"), (s2, "o"), (s3, "o"), (s3 + 0.06, "u"), (s3 + h1 * 0.85, "oo"), (d, "o")]
        amp = [(0, 0), (0.015, 1.0), (a * 0.8, 0.8), (a, 0.05), (s2, 0.05), (s2 + 0.015, 1.0), (s2 + a * 0.8, 0.8),
               (s2 + a, 0.05), (s3, 0.1), (s3 + 0.03, 1.0), (s3 + h1 * 0.8, 0.9), (s3 + h1 * 0.92, 0.75), (d, 0.0)]
        oq = [(0, 0.42), (s3, 0.42), (s3 + 0.04, 0.68), (s3 + h1 * 0.9, 0.68), (s3 + h1 * 0.94, 0.45), (d, 0.5)]
        v = _man(sr, r, d, f0p, vow, amp, oq=oq, rough=[(0, 0.18), (s3, 0.18), (s3 + 0.04, 0.04), (d, 0.15)],
                 breath=[(0, 0.08), (s3, 0.08), (s3 + 0.04, 0.16), (d, 0.1)], tilt=3.5)
        dsp.place(y, _h_onset(sr, r, 0.05, "o"), dsp.ns(t0, sr), 0.25)
        dsp.place(y, _h_onset(sr, r, 0.04, "o"), dsp.ns(t0 + s2, sr), 0.25)
        t0 += 0.04
    elif kind == 2:
        # a held chest "aaa" swelling up, then three high "yi" yelps
        hd = r.uniform(0.45, 0.6)
        base = r.uniform(210.0, 250.0)
        hi = base * r.uniform(1.6, 1.8)
        yd = r.uniform(0.13, 0.16)
        d = hd + 3 * yd + 0.12
        f0p = [(0, base * 0.85), (0.05, base), (hd * 0.85, base * 1.2)]
        vow = [(0, "a"), (hd, "a")]
        amp = [(0, 0), (0.03, 0.85), (hd * 0.9, 1.0)]
        for k in range(3):
            ts = hd + k * yd
            f0p += [(ts + 0.02, hi * (1.0 + 0.04 * k)), (ts + yd * 0.85, hi * 0.9)]
            vow += [(ts + 0.01, _Y), (ts + yd * 0.4, "i"), (ts + yd * 0.8, "ih")]
            amp += [(ts, 0.5), (ts + 0.025, 1.0), (ts + yd * 0.9, 0.7)]
        f0p += [(d, hi * 0.7)]
        vow += [(d, "ih")]
        amp += [(d - 0.12, 0.7), (d, 0.0)]
        v = _man(sr, r, d, f0p, vow, amp, oq=[(0, 0.42), (hd, 0.45), (d, 0.55)], rough=0.15, tilt=4.0)
    else:
        # "hey-YAAA-a!": a short pickup, a big open shout bent up and over, falling off
        dd = r.uniform(0.16, 0.2)
        hd = r.uniform(0.6, 0.85)
        base = r.uniform(200.0, 240.0)
        pk = base * r.uniform(1.45, 1.6)
        d = dd + 0.05 + hd
        s = dd + 0.05
        f0p = [(0, base), (dd * 0.8, base * 1.12), (dd, base * 1.05), (s, base * 1.1), (s + 0.08, pk),
               (s + hd * 0.6, pk * 0.97), (s + hd * 0.8, pk * 1.03), (d, base * 0.85)]
        vow = [(0, "e"), (dd * 0.7, _Y), (dd, _Y), (s + 0.05, "ae"), (s + 0.15, "a"), (s + hd * 0.8, "a"), (d, "uh")]
        amp = [(0, 0), (0.02, 0.85), (dd * 0.7, 0.7), (dd + 0.02, 0.45), (s, 0.55), (s + 0.06, 1.0), (s + hd * 0.7, 0.9),
               (d, 0.0)]
        v = _man(sr, r, d, f0p, vow, amp, oq=[(0, 0.45), (s + 0.08, 0.38), (d, 0.55)], rough=0.2, tilt=5.0)
        dsp.place(y, _h_onset(sr, r, 0.06, "e"), dsp.ns(t0, sr), 0.3)
        t0 += 0.05
    v = dsp.normalize(v)
    dsp.place(y, v, dsp.ns(t0, sr))
    tail = t0 + len(v) / sr - 0.06
    dsp.place(y, _exhale(sr, r, r.uniform(0.18, 0.26)), dsp.ns(tail, sr), 0.12)
    y = dsp.sat(y / dsp.peak(y), 1.2)
    return _outdoor(y, sr, seed + variant, 0.16)


# ------------------------------------------------------------------------------------------- call to the band

@sound("voice/ashen_call", variants=4, seed=9502, peak_db=-2.5)
def ashen_call(seed, variant, sr):
    """Calling the band on: 0 a sharp "hai!"; 1 "hoy!"; 2 a clipped "hup-hai!"; 3 a two-note
    finger whistle (rising then a falling flick), the breath hissing round it."""
    r = dsp.rng(seed, "call", variant)
    y = _buf(1.0, sr)
    if variant == 3:
        d = r.uniform(0.5, 0.65)
        n = dsp.ns(d, sr)
        lo, hi = r.uniform(1900.0, 2300.0), r.uniform(2900.0, 3400.0)
        f = dsp.curve([(0, lo * 0.9), (0.04, lo), (d * 0.35, lo * 1.02), (d * 0.42, hi), (d * 0.75, hi * 0.97), (d, hi * 0.7)],
                      n, sr, "smooth")
        f = f * dsp.vibrato(n, sr, dsp.vary(r, 6.0, 0.2), 12.0, r, 0.5)
        env = dsp.curve([(0, 0), (0.025, 1.0), (d * 0.36, 0.85), (d * 0.4, 0.55), (d * 0.45, 1.0), (d * 0.8, 0.85), (d, 0)], n, sr)
        tone = dsp.sine(f, n, sr) + 0.08 * dsp.sine(f * 2.0, n, sr)
        tone = tone * (1.0 + 0.12 * dsp.smooth_noise(n, sr, r, 40.0))   # unsteady lip/finger airflow
        air = dsp.bp(dsp.white(n, r), sr, f, 6.0)                         # breath noise around the pitch
        hiss = dsp.hp(dsp.white(n, r), sr, 4000.0)
        w = (dsp.normalize(tone) + 0.35 * dsp.normalize(air) + 0.08 * dsp.normalize(hiss)) * env
        dsp.place(y, _inhale(sr, r, 0.1), 0, 0.12)
        dsp.place(y, w, dsp.ns(0.08, sr))
        return _outdoor(y, sr, seed + variant, 0.2)
    if variant == 2:
        # "hup" (closed short) + "hai!"
        a = r.uniform(0.09, 0.12)
        base = r.uniform(190.0, 220.0)
        hup = _man(sr, r, a, [(0, base), (a, base * 0.95)], [(0, "uh"), (a * 0.7, "uh"), (a, "m")],
                   [(0, 0), (0.01, 1.0), (a * 0.7, 0.8), (a, 0)], rough=0.12)
        dsp.place(y, _h_onset(sr, r, 0.04, "uh"), 0, 0.3)
        dsp.place(y, dsp.normalize(hup), dsp.ns(0.03, sr), 0.75)
        t = 0.03 + a + r.uniform(0.07, 0.1)
    else:
        t = 0.0
    d = r.uniform(0.36, 0.5)
    base = r.uniform(230.0, 280.0)
    pk = base * r.uniform(1.15, 1.25)
    f0 = [(0, base), (0.04, pk), (d * 0.5, pk * 0.98), (d, base * 0.75)]
    if variant == 1:
        vow = [(0, "o"), (0.06, "o"), (d * 0.55, "o"), (d * 0.85, _Y), (d, "i")]
        on = "o"
    else:
        vow = [(0, "a"), (0.05, "a"), (d * 0.5, "a"), (d * 0.8, "ih"), (d, "i")]
        on = "a"
    amp = [(0, 0), (0.012, 1.0), (d * 0.5, 0.9), (d * 0.8, 0.6), (d, 0)]
    v = _man(sr, r, d, f0, vow, amp, oq=[(0, 0.38), (d, 0.5)], rough=0.15, tilt=5.0)
    dsp.place(y, _h_onset(sr, r, 0.05, on), dsp.ns(t, sr), 0.4)
    dsp.place(y, dsp.normalize(v), dsp.ns(t + 0.04, sr))
    dsp.place(y, _exhale(sr, r, 0.15, "ih"), dsp.ns(t + 0.04 + d - 0.03, sr), 0.08)
    y = dsp.sat(y / dsp.peak(y), 1.25)
    return _outdoor(y, sr, seed + variant, 0.14)


# ------------------------------------------------------------------------------------------- effort grunt

@sound("voice/ashen_grunt", variants=4, seed=9503, peak_db=-4.0)
def ashen_grunt(seed, variant, sr):
    """A swing or a throw: a short pressed "hhuh!" / "hup!" / "hnh!" pushed out with the breath."""
    r = dsp.rng(seed, "grunt", variant)
    d = r.uniform(0.17, 0.24)
    base = r.uniform(130.0, 165.0)
    vowel = [[(0, "uh"), (d, "schwa")], [(0, "uh"), (d * 0.8, "uh"), (d, "m")], [(0, "ng"), (d, "uh")],
             [(0, "a"), (d, "uh")]][variant % 4]
    f0 = [(0, base * 0.9), (0.02, base * 1.15), (d * 0.6, base), (d, base * 0.8)]
    amp = [(0, 0), (0.008, 1.0), (d * 0.4, 0.75), (d, 0)]
    v = _man(sr, r, d, f0, vowel, amp, oq=[(0, 0.35), (d, 0.6)], rough=0.22, breath=[(0, 0.2), (0.03, 0.06), (d, 0.4)],
             asp=0.5, tilt=3.0, jitter=0.02)
    y = _buf(0.45, sr)
    dsp.place(y, _h_onset(sr, r, 0.03, "uh"), 0, 0.4)
    dsp.place(y, dsp.normalize(v), dsp.ns(0.02, sr))
    dsp.place(y, _exhale(sr, r, 0.12, "uh"), dsp.ns(0.02 + d - 0.04, sr), 0.3)
    return _outdoor(dsp.sat(y / dsp.peak(y), 1.3), sr, seed + variant, 0.07)


# ------------------------------------------------------------------------------------------- pain

@sound("voice/ashen_pain", variants=4, seed=9504, peak_db=-3.0)
def ashen_pain(seed, variant, sr):
    """Hit: a strangled "agh!" / "ah!" / "uhh!" / through-the-teeth "hnngh", voice breaking at the top
    and falling with a fry tail."""
    r = dsp.rng(seed, "pain", variant)
    d = r.uniform(0.32, 0.42)
    base = r.uniform(200.0, 250.0)
    pk = base * r.uniform(1.15, 1.3)
    vowel = [[(0, "ae"), (0.08, "a"), (d, "uh")], [(0, "a"), (d, "uh")], [(0, "uh"), (d, "schwa")],
             [(0, "ng"), (d * 0.5, "ng"), (d, "uh")]][variant % 4]
    f0 = [(0, base), (0.03, pk), (0.06, pk * 0.94), (d * 0.6, base * 0.85), (d, base * 0.5)]
    amp = [(0, 0), (0.01, 1.0), (d * 0.3, 0.8), (d * 0.75, 0.35), (d, 0)]
    v = _man(sr, r, d, f0, vowel, amp, oq=[(0, 0.36), (d * 0.6, 0.45), (d, 0.8)], rough=[(0, 0.35), (d, 0.5)],
             breath=[(0, 0.1), (d, 0.5)], asp=0.4, tilt=4.0, jitter=0.025, shimmer=0.08,
             sub=[(0, 0.0), (d * 0.6, 0.0), (d, 0.35)])
    y = _buf(0.7, sr)
    dsp.place(y, dsp.normalize(v), 0)
    dsp.place(y, _exhale(sr, r, 0.16, "uh"), dsp.ns(d - 0.05, sr), 0.2)
    return _outdoor(dsp.sat(y / dsp.peak(y), 1.35), sr, seed + variant, 0.09)


# ------------------------------------------------------------------------------------------- death

@sound("voice/ashen_death", variants=3, seed=9505, peak_db=-3.0)
def ashen_death(seed, variant, sr):
    """Dying: a high cry that cracks and falls away, the voice sinking into creak, the last breath out."""
    r = dsp.rng(seed, "death", variant)
    d = r.uniform(0.7, 0.85)
    base = r.uniform(230.0, 270.0)
    pk = base * r.uniform(1.15, 1.25)
    f0 = [(0, base), (0.05, pk), (d * 0.25, pk * 0.95), (d * 0.3, pk * 0.8), (d * 0.6, base * 0.6), (d * 0.85, base * 0.4),
          (d, base * 0.28)]
    vowel = [(0, "a"), (d * 0.3, "a"), (d * 0.6, "uh"), (d, "o")] if variant != 1 else \
        [(0, "ae"), (d * 0.2, "a"), (d * 0.55, "o"), (d, "u")]
    amp = [(0, 0), (0.015, 1.0), (d * 0.28, 0.9), (d * 0.32, 0.65), (d * 0.6, 0.45), (d * 0.85, 0.2), (d, 0)]
    v = _man(sr, r, d, f0, vowel, amp, oq=[(0, 0.4), (d * 0.5, 0.45), (d, 0.3)], rough=[(0, 0.25), (d * 0.5, 0.35), (d, 0.6)],
             breath=[(0, 0.08), (d, 0.4)], asp=0.4, tilt=[0, 3.0, 4.0][variant % 3], jitter=0.025, shimmer=0.09,
             sub=[(0, 0.0), (d * 0.5, 0.05), (d, 0.5)])
    y = _buf(1.4, sr)
    dsp.place(y, dsp.normalize(v), 0)
    ld = r.uniform(0.3, 0.4)
    last = dsp.breath(sr, ld, [(0, "uh"), (ld, "h")], [(0, 0), (0.05, 1.0), (ld, 0)], r, hiss=0.15, wet=0.2, rattle=0.3)
    dsp.place(y, dsp.normalize(last), dsp.ns(d - 0.08, sr), 0.22)
    return _outdoor(dsp.sat(y / dsp.peak(y), 1.25), sr, seed + variant, 0.12)


# ------------------------------------------------------------------------------------------- spear

@sound("sfx/spear_throw", variants=4, seed=9506, peak_db=-4.0)
def spear_throw(seed, variant, sr):
    """A thrown spear: the arm's release, then a long shaft's whoosh peaking early and going away, with
    a faint whistle off the head."""
    r = dsp.rng(seed, "throw", variant)
    d = r.uniform(0.38, 0.46)
    y = dsp.whoosh(sr, d, r, peak_t=r.uniform(0.22, 0.3), width=0.14, f_lo=220.0, f_hi=dsp.vary(r, 1700.0, 0.15), q=1.4,
                   tone=0.25, tone_q=20.0, skew=2.8)
    n = len(y)
    t = np.arange(n) / sr / d
    v = np.exp(-((t - 0.25) / 0.2) ** 2)
    low = dsp.lp(dsp.pink(n, r), sr, 300.0, order=4) * v ** 2
    y = dsp.normalize(y) + 0.3 * dsp.normalize(low)
    # going away: darken the tail
    y = dsp.lp(y, sr, dsp.curve([(0, 9000.0), (d * 0.35, 7000.0), (d, 1800.0)], n, sr))
    cl = dsp.cloth(sr, 0.12, r, [(0, 0), (0.05, 1), (0.12, 0)], heavy=0.5)
    dsp.place(y, dsp.normalize(cl), 0, 0.15)
    return y


@sound("sfx/spear_thunk", variants=4, seed=9507, peak_db=-2.0)
def spear_thunk(seed, variant, sr):
    """A spear head biting into a trunk (0, 1) or the ground (2, 3): the bite, the body of what it hit,
    then the shaft quivering - a wooden 'brrrng' wobbling at 15-25 Hz and dying out."""
    r = dsp.rng(seed, "thunk", variant)
    wood = variant < 2
    y = _buf(0.7, sr)
    L = dsp.ns(0.012, sr)
    bite = dsp.band_noise(L, sr, r, 1200.0 if wood else 600.0, 8000.0 if wood else 4000.0) * dsp.env_ar(L, sr, 0.0003, 0.008)
    dsp.place(y, dsp.normalize(bite), 0, 0.5 if wood else 0.35)
    if wood:
        body = dsp.impact(sr, r, "wood", dsp.vary(r, 240.0, 0.15), 0.35, contact_ms=0.8, t60=dsp.vary(r, 0.14, 0.2), noise=0.3,
                          click=0.2, force=1.0)
        dsp.place(y, body, 0, 0.9)
        th = dsp.thud(sr, r, dsp.vary(r, 130.0, 0.1), 0.2, contact_ms=2.0, t60=0.03, noise=0.3, knock=0.8,
                      knock_f=dsp.vary(r, 520.0, 0.15))
        dsp.place(y, th, 0, 0.45)
    else:
        th = dsp.thud(sr, r, dsp.vary(r, 85.0, 0.1), 0.25, contact_ms=4.0, t60=0.04, noise=0.7, noise_lp=900.0)
        dsp.place(y, th, 0, 1.0)
        k = dsp.ns(0.12, sr)
        dirt = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.002, 0.08) * 500.0, 800.0, 5000.0, q=2.0, alpha=1.5)
        dsp.place(y, dsp.normalize(dirt), dsp.ns(0.005, sr), 0.25)
    # shaft quiver: a few bending modes of a ~2 m ash shaft, amplitude-modulated by the wobble
    qd = r.uniform(0.45, 0.55)
    qn = dsp.ns(qd, sr)
    f1 = dsp.vary(r, 165.0, 0.15)
    shaft = dsp.modal(qn, sr, [f1, f1 * 2.76, f1 * 5.4, f1 * 8.9], [qd * 0.7, qd * 0.45, qd * 0.25, qd * 0.12],
                      [1.0, 0.5, 0.25, 0.1])
    wob = dsp.vary(r, 19.0, 0.2)
    tq = np.arange(qn) / sr
    am = 0.5 + 0.5 * np.abs(np.sin(np.pi * wob * tq)) * np.exp(-tq / (qd * 0.5)) ** 0.3
    rattle = dsp.bp(dsp.white(qn, r), sr, f1 * 4.0, 2.0) * dsp.env_exp(qn, sr, qd * 0.4)
    q = dsp.normalize(shaft * am) + 0.12 * dsp.normalize(rattle * np.abs(np.sin(np.pi * wob * tq)))
    dsp.place(y, dsp.normalize(q), dsp.ns(0.004, sr), 0.35 if wood else 0.25)
    return dsp.hp(_outdoor(y, sr, seed + variant, 0.06), sr, 45.0)


# ------------------------------------------------------------------------------------------- war drum

def _drum_hit(sr, r, f0, force, dur=1.0):
    """A big hide-headed frame drum struck with a padded beater: a pitch-dropping membrane (tension
    eases as the skin rebounds), circular-membrane overtones decaying fast, a felt thump and a little
    skin slap."""
    n = dsp.ns(dur, sr)
    t = np.arange(n) / sr
    fb = f0 * (1.0 + 0.12 * force * np.exp(-t / 0.04))
    ratios = [1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156]
    t60s = [0.75, 0.4, 0.28, 0.25, 0.18, 0.14, 0.1]
    amps = [1.0, 0.5, 0.35, 0.25, 0.18, 0.12, 0.08]
    y = np.zeros(n)
    for ra, tt, a in zip(ratios, t60s, amps):
        ph = np.cumsum(fb * ra * dsp.vary(r, 1.0, 0.01)) / sr
        y += a * np.sin(dsp.TAU * ph + r.uniform(0, dsp.TAU)) * dsp.env_ar(n, sr, 0.002, tt * dsp.vary(r, 1.0, 0.1))
    y = dsp.normalize(y)
    th = dsp.thud(sr, r, f0 * 0.75, 0.3, contact_ms=6.0, t60=0.06, noise=0.4, noise_lp=700.0)
    dsp.place(y, th, 0, 0.6)
    L = dsp.ns(0.02, sr)
    slap = dsp.band_noise(L, sr, r, 600.0, 3500.0) * dsp.env_ar(L, sr, 0.0005, 0.012)
    dsp.place(y, dsp.normalize(slap), 0, 0.12 * force)
    return y * force


@sound("sfx/ashen_drum", variants=3, seed=9508, peak_db=-1.5)
def ashen_drum(seed, variant, sr):
    """The camp's war drum: a heavy, slow pattern of a deep hide drum (BOOM - boom-boom - BOOM ...),
    with the far valley throwing it back so it carries."""
    r = dsp.rng(seed, "drum", variant)
    f0 = r.uniform(52.0, 62.0)
    beat = r.uniform(0.42, 0.5)
    pats = [  # (beat position, force, rim/off-centre)
        [(0, 1.0), (2, 0.7), (2.5, 0.6), (3, 1.0), (4, 1.0), (6, 0.7), (6.5, 0.6)],
        [(0, 1.0), (1, 0.55), (2, 0.9), (3.5, 0.6), (4, 1.0), (5, 0.55), (6, 1.0)],
        [(0, 1.0), (0.5, 0.6), (2, 1.0), (2.5, 0.6), (4, 1.0), (4.5, 0.6), (6, 1.0)],
    ]
    y = _buf(beat * 7 + 1.6, sr)
    for pos, force in pats[variant % 3]:
        t = pos * beat + r.uniform(-0.012, 0.012)
        f = f0 * (1.0 if force > 0.8 else dsp.vary(r, 1.12, 0.03))
        dsp.place(y, _drum_hit(sr, r, f, force * r.uniform(0.92, 1.0)), dsp.ns(t, sr))
    y = dsp.normalize(y)
    y = dsp.reverb(y, sr, "valley", 0.22, seed=seed + variant, tail=True)
    return dsp.hp(y, sr, 30.0)
