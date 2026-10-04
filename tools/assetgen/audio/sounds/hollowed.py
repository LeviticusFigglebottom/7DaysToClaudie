"""The Hollowed: humans hollowed out by the valley's fungus. Their voices are still human at the core
(glottal source + formants) but broken: creaky irregular phonation (jitter, period doubling, rattling
false folds), a longer and wetter tract (lower formants, wide bandwidths, fluid bubbling in the airway),
a 'hollow' tubular cavity resonance (feedback comb), inhaled (time-reversed) vocalizations, and harsh
asymmetric overdrive at high effort. Variants differ in contour, vowel path, wetness and roughness."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _wet(n, sr, r, env, amount=1.0, lo=220.0, hi=1300.0):
    """Fluid in the airway: bubbles, sticky pops and a low gurgle, all following env."""
    e = np.maximum(env, 0.0) / max(float(np.max(env)), 1e-9)
    bub = dsp.bubbles(n, sr, r, 20.0 + 90.0 * e * amount, lo, hi, alpha=2.0, rise=(0.1, 0.8))
    pops = dsp.clicks(n, sr, r, e * 450.0 * amount + 1e-3, 300.0, 2500.0, q=4.0, alpha=1.6)
    gurg = dsp.bp(dsp.white(n, r), sr, dsp.vary(r, 380.0, 0.2), 3.0) * (0.5 + 0.5 * dsp.smooth_noise(n, sr, r, 12.0)) * e
    return dsp.normalize(bub) * 0.6 + dsp.normalize(pops) * 0.4 + dsp.normalize(gurg) * 0.5


def _hollow(x, sr, r, amount=0.35, delay=None, fb=None):
    """Tubular cavity colouring (feedback comb), blended."""
    d = delay if delay else r.uniform(0.0025, 0.0055)
    y = dsp.comb(x, sr, d, fb=fb if fb else r.uniform(0.45, 0.62), damp=0.35)
    return x * (1.0 - amount) + dsp.normalize(y) * dsp.peak(x) * amount


def _hvoice(sr, r, dur, f0, vowel, amp, *, rough=0.4, sub=0.3, jitter=0.05, oq=0.45, tract=0.88, bw=1.5,
            breath=0.08, wet=0.5, hollow=0.35, drive=1.5, tilt=0.0, rough_rate=None, sq=2.8):
    v = dsp.voice(sr, dur, f0, vowel, amp, r, oq=oq, sq=sq, jitter=jitter, shimmer=0.14, sub=sub, drift=0.03,
                  breath=breath, asp=0.4, tract=tract, bw=bw, wander=0.05, rough=rough,
                  rough_rate=rough_rate if rough_rate else dsp.vary(r, 28.0, 0.3), tilt_db=tilt)
    v = dsp.normalize(v)
    n = len(v)
    if wet:
        env = dsp.env_follow(v, sr, 5.0, 80.0)
        v = v + wet * 0.35 * _wet(n, sr, r, env)
    if hollow:
        v = _hollow(v, sr, r, hollow)
    return dsp.asym(v / max(dsp.peak(v), 1e-9), drive, 0.15)


def _contour(r, dur, base, lo=0.75, hi=1.3, end=(0.6, 0.85), k=(2, 5)):
    ts = np.sort(r.uniform(0.1, dur - 0.1, int(r.integers(*k))))
    return [(0.0, base * r.uniform(0.9, 1.1))] + [(t, base * r.uniform(lo, hi)) for t in ts] + [(dur, base * r.uniform(*end))]


_GROAN_VOWELS = ["uh", "o", "a", "u", "oo", "er", "uh", "m"]


@sound("voice/hollow_groan_idle", variants=8, seed=9001, peak_db=-6.0)
def hollow_groan_idle(seed, variant, sr):
    """Idle moan: slow, creaky, wet; vowel drifting; two of eight are inhaled (reversed) groans."""
    r = dsp.rng(seed, "groan")
    dur = r.uniform(1.7, 3.3)
    base = r.uniform(56.0, 92.0)
    f0 = _contour(r, dur, base)
    nv = int(r.integers(2, 5))
    vt = np.concatenate([[0.0], np.sort(r.uniform(0.2, dur - 0.1, nv - 1))])
    vowels = [(float(t), dsp.pick(r, _GROAN_VOWELS)) for t in vt] + [(dur, dsp.pick(r, ["u", "m", "uh"]))]
    sw = r.uniform(0.25, 0.45) * dur
    amp = [(0, 0), (min(0.25, dur * 0.1), 0.5), (sw, 1.0), (sw + r.uniform(0.2, 0.5), r.uniform(0.45, 0.7)),
           (dur * 0.75, r.uniform(0.6, 1.0)), (dur - 0.15, 0.3), (dur, 0)]
    v = _hvoice(sr, r, dur, f0, vowels, amp, rough=r.uniform(0.25, 0.6), sub=r.uniform(0.2, 0.6), jitter=r.uniform(0.03, 0.08),
                oq=r.uniform(0.35, 0.55), tract=r.uniform(0.82, 0.92), bw=r.uniform(1.3, 1.9), wet=r.uniform(0.3, 0.8),
                hollow=r.uniform(0.25, 0.5), drive=r.uniform(1.2, 2.2))
    if variant in (3, 6):
        v = v[::-1].copy()                                     # inhaled: swells then cuts off
        v = dsp.fade(v, sr, 0.15, 0.03)
    y = dsp.fit(v, len(v) + dsp.ns(0.6, sr))
    ex = dsp.breath(sr, 0.6, [(0, "uh"), (0.6, "h")], [(0, 0), (0.2, 1.0), (0.6, 0)], r, tract=0.88, wet=0.6, rattle=0.4,
                    rattle_hz=dsp.vary(r, 24.0, 0.2), hiss=0.08)
    dsp.place(y, dsp.normalize(ex), len(v) - dsp.ns(0.25, sr), 0.25)
    return y


@sound("voice/hollow_alert", variants=4, seed=9002, peak_db=-4.7)
def hollow_alert(seed, variant, sr):
    """Spotted you: a wet sucking intake, then a rising guttural snarl."""
    r = dsp.rng(seed, "alert")
    gd = r.uniform(0.18, 0.28)
    y = _buf(gd + 1.4, sr)
    gasp = dsp.breath(sr, gd, [(0, "ih"), (gd, "uh")], [(0, 0), (gd * 0.6, 1.0), (gd, 0.0)], r, tract=0.9, hiss=0.5,
                      hiss_f=2000.0, wet=0.8, rattle=0.5)
    dsp.place(y, dsp.normalize(dsp.hp(gasp, sr, 300.0)), 0, 0.45)
    d = r.uniform(0.75, 1.1)
    pk = r.uniform(170.0, 215.0)
    f0 = [(0, 90.0), (0.12, pk), (0.35, pk * r.uniform(0.9, 1.1)), (d * 0.75, pk * 0.8), (d, 105.0)]
    amp = [(0, 0), (0.05, 0.7), (0.15, 1.0), (d * 0.6, 0.85), (d * 0.85, 0.4), (d, 0)]
    v = _hvoice(sr, r, d, f0, [(0, "uh"), (0.12, "a"), (d * 0.7, "ae"), (d, "uh")], amp, rough=r.uniform(0.5, 0.7),
                sub=r.uniform(0.35, 0.6), jitter=0.05, oq=0.35, tract=0.9, bw=1.3, wet=0.4, hollow=0.3, drive=3.2, tilt=6.0,
                rough_rate=dsp.vary(r, 45.0, 0.25))
    dsp.place(y, v, dsp.ns(gd - 0.03, sr), 1.0)
    return y


@sound("voice/hollow_attack", variants=4, seed=9003, peak_db=-4.8)
def hollow_attack(seed, variant, sr):
    """Lunging roar: forced exhale burst into a growling, overdriven 'raagh' with spittle."""
    r = dsp.rng(seed, "attack")
    d = r.uniform(0.55, 0.9)
    y = _buf(d + 0.4, sr)
    pk = r.uniform(190.0, 250.0)
    f0 = [(0, 130.0), (0.07, pk), (d * 0.5, pk * r.uniform(0.85, 1.05)), (d, 140.0)]
    amp = [(0, 0), (0.02, 0.8), (0.07, 1.0), (d * 0.7, 0.8), (d, 0)]
    v = _hvoice(sr, r, d, f0, [(0, "ae"), (0.1, "a"), (d, "uh")], amp, rough=0.7, sub=r.uniform(0.45, 0.7), jitter=0.05,
                oq=0.33, tract=0.92, bw=1.25, wet=0.5, hollow=0.25, drive=3.8, tilt=7.0, rough_rate=dsp.vary(r, 62.0, 0.2))
    burst = dsp.breath(sr, 0.15, "a", [(0, 0), (0.01, 1.0), (0.15, 0)], r, hiss=0.6)
    dsp.place(y, dsp.normalize(burst), 0, 0.4)
    dsp.place(y, v, dsp.ns(0.02, sr), 1.0)
    sp = dsp.squelch(sr, r, 0.25, 2500.0, 900.0, q=3.0, stick=1.2, bub=0.4)
    dsp.place(y, dsp.normalize(sp), dsp.ns(d * 0.3, sr), 0.15)
    return y


@sound("voice/hollow_pain", variants=4, seed=9004, peak_db=-5.8)
def hollow_pain(seed, variant, sr):
    """Hit: a cracked yelp jumping up then collapsing into a wet choke."""
    r = dsp.rng(seed, "pain")
    d = r.uniform(0.45, 0.7)
    y = _buf(d + 0.6, sr)
    pk = r.uniform(300.0, 420.0)
    f0 = [(0, 200.0), (0.04, pk), (d * 0.45, pk * 0.75), (d, 130.0)]
    amp = [(0, 0), (0.015, 1.0), (d * 0.4, 0.8), (d * 0.8, 0.35), (d, 0)]
    v = _hvoice(sr, r, d, f0, [(0, "ae"), (d * 0.3, "a"), (d, "uh")], amp, rough=0.45, sub=0.3, jitter=0.04, oq=0.4,
                tract=0.95, bw=1.2, wet=0.4, hollow=0.3, drive=2.5, tilt=5.0)
    dsp.place(y, v, 0, 1.0)
    cd = r.uniform(0.35, 0.5)
    choke = dsp.breath(sr, cd, [(0, "uh"), (cd, "u")], [(0, 0), (0.03, 1.0), (cd, 0)], r, tract=0.85, wet=1.0, rattle=0.7,
                       rattle_hz=dsp.vary(r, 22.0, 0.2))
    dsp.place(y, dsp.normalize(choke), dsp.ns(d * 0.85, sr), 0.4)
    return y


@sound("voice/hollow_death", variants=4, seed=9005, peak_db=-5.2)
def hollow_death(seed, variant, sr):
    """Collapse: a falling groan breaking into an agonal, bubbling rattle and a last exhale."""
    r = dsp.rng(seed, "hdeath")
    d1 = r.uniform(0.8, 1.3)
    y = _buf(d1 + 2.2, sr)
    f0 = [(0, r.uniform(110.0, 140.0)), (0.1, r.uniform(120.0, 150.0)), (d1 * 0.6, 80.0), (d1, 45.0)]
    amp = [(0, 0), (0.04, 1.0), (d1 * 0.5, 0.8), (d1 * 0.9, 0.3), (d1, 0)]
    v = _hvoice(sr, r, d1, f0, [(0, "a"), (d1 * 0.4, "o"), (d1, "u")], amp, rough=0.5,
                sub=[(0, 0.2), (d1, 0.8)], jitter=0.06, oq=[(0, 0.4), (d1, 0.3)], tract=0.88, bw=1.6, wet=0.6, hollow=0.35,
                drive=2.0, tilt=2.0)
    dsp.place(y, v, 0, 1.0)
    t = d1 - 0.05
    for _ in range(int(r.integers(2, 4))):
        rd = r.uniform(0.35, 0.6)
        rat = dsp.breath(sr, rd, "uh", [(0, 0), (rd * 0.3, 1.0), (rd, 0)], r, tract=0.85, wet=1.2, rattle=0.85,
                         rattle_hz=dsp.vary(r, 20.0, 0.25))
        dsp.place(y, dsp.normalize(rat), dsp.ns(t, sr), r.uniform(0.35, 0.55))
        t += rd + r.uniform(0.05, 0.2)
    ex = dsp.breath(sr, 0.6, [(0, "uh"), (0.6, "h")], [(0, 0), (0.05, 1.0), (0.6, 0)], r, wet=0.4)
    dsp.place(y, dsp.normalize(ex), dsp.ns(t, sr), 0.2)
    return y


@sound("voice/hollow_sleep_breath", variants=4, seed=9006, peak_db=-10.0)
def hollow_sleep_breath(seed, variant, sr):
    """Dormant Hollowed: one slow wet breath cycle - a rattling snore-like intake, a gurgling exhale with a
    faint fry moan underneath."""
    r = dsp.rng(seed, "sleep")
    di = r.uniform(1.2, 1.7)
    pause = r.uniform(0.2, 0.45)
    de = r.uniform(1.4, 2.0)
    y = _buf(di + pause + de + 0.2, sr)
    inh = dsp.breath(sr, di, [(0, "uh"), (di, "o")], [(0, 0), (di * 0.6, 1.0), (di, 0.0)], r, tract=0.85, bw=1.4, hiss=0.2,
                     rattle=r.uniform(0.6, 0.85), rattle_hz=dsp.vary(r, 30.0, 0.2), wet=0.3)
    fry = dsp.voice(sr, di, [(0, 38.0), (di, 46.0)], "o", [(0, 0), (di * 0.6, 1.0), (di, 0)], r, oq=0.3, jitter=0.12, shimmer=0.3,
                    sub=0.5, breath=0.3, tract=0.85, bw=1.8)
    seg = dsp.normalize(inh) + 0.25 * dsp.normalize(fry)[::-1]
    dsp.place(y, seg, 0, 0.8)
    t = di + pause
    exh = dsp.breath(sr, de, [(0, "uh"), (de, "h")], [(0, 0), (0.15, 1.0), (de * 0.5, 0.6), (de, 0)], r, tract=0.85, bw=1.6,
                     hiss=0.1, wet=0.9, rattle=0.3)
    moan = _hvoice(sr, r, de, [(0, 62.0), (de, 48.0)], [(0, "m"), (de, "u")], [(0, 0), (0.2, 0.6), (de * 0.5, 0.4), (de, 0)],
                   rough=0.5, sub=0.5, jitter=0.08, oq=0.35, wet=0.3, hollow=0.4, drive=1.2)
    dsp.place(y, dsp.normalize(exh) + 0.3 * dsp.fit(dsp.normalize(moan), len(exh)), dsp.ns(t, sr), 0.9)
    return y


@sound("voice/lurcher_screech", variants=4, seed=9007, peak_db=-4.0)
def lurcher_screech(seed, variant, sr):
    """Lurcher (fast runner) screech: frantic high wail with a second, unrelated pitch (biphonation),
    tremor and voice breaks, piercing 2-4 kHz, overdriven."""
    r = dsp.rng(seed, "lurcher")
    d = r.uniform(1.0, 1.6)
    n = dsp.ns(d, sr)
    pk = r.uniform(820.0, 1100.0)
    pts = [(0, 420.0), (0.07, pk)]
    t = 0.2
    while t < d - 0.2:
        pts.append((t, pk * r.uniform(0.8, 1.25)))
        t += r.uniform(0.12, 0.3)
    pts.append((d, r.uniform(450.0, 600.0)))
    f0 = dsp.curve(pts, n, sr, "smooth") * dsp.vibrato(n, sr, dsp.vary(r, 11.0, 0.2), r.uniform(60.0, 120.0), r, 0.6)
    amp = [(0, 0), (0.03, 1.0), (d * 0.7, 0.85), (d, 0)]
    vow = [(0, "ae"), (d * 0.5, "a"), (d, "e")]
    a = dsp.voice(sr, d, f0, vow, amp, r, oq=0.35, sq=3.5, jitter=0.04, shimmer=0.12, sub=0.4, breath=0.15, asp=0.6,
                  tract=1.12, bw=1.1, rough=0.75, rough_rate=dsp.vary(r, 70.0, 0.2), tilt_db=8.0, os=4)
    ratio = r.uniform(1.37, 1.52)
    b = dsp.voice(sr, d, f0 * ratio, vow, amp, r, oq=0.4, sq=3.0, jitter=0.06, shimmer=0.15, breath=0.1, tract=1.15,
                  rough=0.4, tilt_db=6.0, os=4)
    hs = dsp.breath(sr, d, "a", amp, r, tract=1.1, hiss=0.8, hiss_f=2500.0)
    y = dsp.normalize(a) + 0.4 * dsp.normalize(b) + 0.3 * dsp.normalize(hs)
    y = dsp.asym(y / dsp.peak(y), 4.0, 0.2)
    y = dsp.peq(y, sr, 3000.0, 4.0, 1.0)
    y = _hollow(y, sr, r, 0.25, delay=r.uniform(0.0012, 0.002))
    return dsp.reverb(y, sr, "forest", 0.12, seed=seed)


@sound("voice/lurcher_pant", variants=2, seed=9008, peak_db=-6.0)
def lurcher_pant(seed, variant, sr):
    """Hunting breath: rapid ragged panting, half-voiced, wet, with a growl under it."""
    r = dsp.rng(seed, "pant")
    dur = 2.2
    y = _buf(dur + 0.3, sr)
    t = 0.0
    rate = r.uniform(3.6, 4.6)
    while t < dur:
        ed = r.uniform(0.09, 0.14)
        ex_v = dsp.voice(sr, ed, [(0, dsp.vary(r, 150.0, 0.15)), (ed, 110.0)], [(0, "a"), (ed, "uh")],
                         [(0, 0), (0.01, 1.0), (ed, 0)], r, oq=0.6, jitter=0.06, shimmer=0.2, breath=0.8, asp=0.6, rough=0.6,
                         sub=0.4, tract=0.95)
        ex_n = dsp.breath(sr, ed, "a", [(0, 0), (0.008, 1.0), (ed, 0)], r, hiss=0.5, wet=0.5)
        dsp.place(y, dsp.normalize(ex_v) * 0.6 + dsp.normalize(ex_n) * 0.7, dsp.ns(t, sr), r.uniform(0.7, 1.0))
        idd = r.uniform(0.07, 0.1)
        inh = dsp.breath(sr, idd, "ih", [(0, 0), (idd * 0.7, 1.0), (idd, 0)], r, hiss=0.9, hiss_f=2600.0, rattle=0.5)
        dsp.place(y, dsp.normalize(inh), dsp.ns(t + ed + 0.02, sr), r.uniform(0.3, 0.5))
        t += 1.0 / rate * r.uniform(0.85, 1.2)
    n = len(y)
    growl = _hvoice(sr, r, n / sr, dsp.vary(r, 70.0, 0.1), "uh", [(0, 0), (0.2, 1.0), (n / sr - 0.3, 1.0), (n / sr, 0)],
                    rough=0.8, sub=0.6, jitter=0.08, oq=0.35, wet=0.3, hollow=0.3, drive=2.0, rough_rate=dsp.vary(r, 30.0, 0.2))
    y = dsp.normalize(y) + 0.18 * dsp.fit(dsp.normalize(growl), n)
    return y


@sound("voice/keener_scream", variants=3, seed=9009, peak_db=-3.5)
def keener_scream(seed, variant, sr):
    """The Keener: a long (3-4 s) resonant keening wail. A sucked-in breath, then a rising cry sung by a
    'choir of one' - five detuned copies of the same throat beating against each other, an octave-down
    undertone, a piercing singer's-formant ring and a hollow cavity resonance; a voice break near the
    climax, collapsing into a wet sob. Baked forest tail."""
    r = dsp.rng(seed, "keener")
    d = r.uniform(3.0, 3.6)
    pre = r.uniform(0.3, 0.42)
    n = dsp.ns(d, sr)
    top = r.uniform(760.0, 920.0)
    contour = [(0, 330.0), (0.45, 520.0), (1.25, top), (2.2, top * r.uniform(1.0, 1.08)), (d - 0.55, top * 0.85),
               (d - 0.15, 420.0), (d, 300.0)]
    base = dsp.curve(contour, n, sr, "smooth")
    tb = r.uniform(1.55, 2.0)                                   # voice break: jump up a fifth for a moment
    brk = dsp.curve([(0, 1.0), (tb, 1.0), (tb + 0.03, 1.5), (tb + 0.22, 1.5), (tb + 0.27, 1.0), (d, 1.0)], n, sr)
    base = base * brk
    amp = [(0, 0), (0.2, 0.55), (1.0, 0.9), (2.2, 1.0), (d - 0.5, 0.85), (d - 0.12, 0.4), (d, 0)]
    vow = [(0, "i"), (0.6, "e"), (1.5, "a"), (2.5, "o"), (d, "u")]
    # vibrato that destabilizes into a warble around the climax / voice break
    wob = dsp.curve([(0, 0.0), (0.7, 0.5), (tb - 0.4, 1.0), (tb + 0.4, 1.8), (d, 1.2)], n, sr, "smooth")
    rasp = [(0, 0.0), (1.0, 0.05), (tb, 0.35), (d - 0.4, 0.5), (d, 0.3)]          # throat tearing as it goes on
    choir = np.zeros(n)
    for k, c in enumerate((0.0, -9.0, 8.0, -17.0, 19.0)):
        vib = dsp.vibrato(n, sr, dsp.vary(r, 5.4, 0.1), r.uniform(55.0, 90.0), r, 0.7, onset=0.7)
        f0 = base * dsp.cents(c + r.uniform(-3, 3)) * vib ** wob
        v = dsp.voice(sr, d, f0, vow, amp, r, oq=0.5, sq=2.6, jitter=0.012, shimmer=0.05, breath=0.06, asp=0.3, tract=1.18,
                      bw=1.0, wander=0.03, os=4, tilt_db=3.0, rough=rasp, rough_rate=dsp.vary(r, 55.0, 0.2))
        choir += dsp.normalize(v) * (1.0 if k == 0 else 0.6)
    under = dsp.voice(sr, d, base * 0.5 * dsp.drift(n, sr, r, 15.0, 1.0), [(0, "o"), (d, "u")],
                      [(0, 0), (1.0, 0.0), (1.6, 0.8), (d - 0.3, 0.6), (d, 0)], r, oq=0.4, jitter=0.03, sub=0.4, rough=0.3,
                      tract=0.95, bw=1.4)
    # a second throat a tritone above, creeping in late (wrong, dissonant)
    trit = dsp.voice(sr, d, base * dsp.semis(6) * dsp.cents(r.uniform(-12, 12)) * dsp.vibrato(n, sr, 6.3, 70.0, r, 0.8),
                     vow, [(0, 0), (1.3, 0.0), (2.2, 0.7), (d - 0.3, 0.5), (d, 0)], r, oq=0.45, jitter=0.02, breath=0.1,
                     tract=1.2, os=4, tilt_db=2.0)
    y = dsp.normalize(choir) + 0.22 * dsp.normalize(under) + 0.2 * dsp.normalize(trit)
    ring = dsp.bp(y, sr, dsp.curve([(0, 2600.0), (d, 3100.0)], n, sr), 14.0) + 0.6 * dsp.bp(y, sr, dsp.vary(r, 1400.0, 0.1), 10.0)
    y = y + 0.9 * dsp.normalize(ring) * dsp.peak(y)
    y = _hollow(y, sr, r, 0.3, delay=r.uniform(0.0018, 0.0026), fb=0.55)
    y = dsp.asym(y / dsp.peak(y), 1.8, 0.1)
    # intake before, sob after
    out = _buf(pre + d + 0.9, sr)
    gasp = dsp.breath(sr, pre + 0.05, [(0, "i"), (pre, "ih")], [(0, 0), (pre * 0.7, 1.0), (pre + 0.05, 0.0)], r, tract=1.15,
                      hiss=1.0, hiss_f=2800.0, wet=0.3)
    dsp.place(out, dsp.normalize(dsp.hp(gasp, sr, 500.0)), 0, 0.35)
    dsp.place(out, y, dsp.ns(pre, sr), 1.0)
    sd = 0.7
    sob = dsp.breath(sr, sd, [(0, "uh"), (sd, "h")], [(0, 0), (0.05, 1.0), (0.2, 0.3), (0.3, 0.8), (sd, 0)], r, tract=1.1,
                     wet=0.8, rattle=0.5)
    dsp.place(out, dsp.normalize(sob), dsp.ns(pre + d - 0.1, sr), 0.3)
    return dsp.reverb(out, sr, "forest", 0.2, seed=seed)


@sound("voice/dragger_drag", variants=4, seed=9010, peak_db=-6.7)
def dragger_drag(seed, variant, sr):
    """Dragger (crawler) pulling itself along: hand slaps down, the body scrapes and smears forward,
    strained wet groan with the pull."""
    r = dsp.rng(seed, "dragger")
    dur = r.uniform(1.4, 1.8)
    y = _buf(dur, sr)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 140.0, 0.15), 0.15, contact_ms=6.0, t60=0.03, noise=0.6, knock=0.7,
                          knock_f=dsp.vary(r, 500.0, 0.2)), 0, 0.8)
    dsp.place(y, dsp.normalize(dsp.squelch(sr, r, 0.12, 1800.0, 600.0, q=3.0, stick=1.0, bub=0.2)), 0, 0.3)
    t0 = r.uniform(0.1, 0.2)
    dd = r.uniform(0.7, 1.0)
    pull = [(0, 0), (dd * 0.15, 1.0), (dd * 0.4, r.uniform(0.4, 0.7)), (dd * 0.6, 0.9), (dd, 0)]
    sc = dsp.scrape(sr, dd, r, pull, f_lo=180.0, f_hi=3500.0, grit=0.7, grit_rate=600.0, rough_hz=dsp.vary(r, 35.0, 0.2))
    clo = dsp.cloth(sr, dd, r, pull, heavy=0.9)
    smear = dsp.squelch(sr, r, dd, 900.0, 380.0, q=2.5, stick=0.6, bub=0.3, attack=0.1)
    dsp.place(y, dsp.normalize(sc) * 0.6 + dsp.normalize(clo) * 0.35 + dsp.normalize(smear) * 0.2, dsp.ns(t0, sr))
    gd = dd + 0.2
    g = _hvoice(sr, r, gd, [(0, 72.0), (gd * 0.3, 95.0), (gd, 62.0)], [(0, "uh"), (gd * 0.5, "ng"), (gd, "uh")],
                [(0, 0), (gd * 0.25, 1.0), (gd * 0.7, 0.6), (gd, 0)], rough=0.55, sub=0.5, jitter=0.07, oq=0.35, wet=0.6,
                hollow=0.35, drive=1.8)
    dsp.place(y, g, dsp.ns(t0 + 0.05, sr), 0.55)
    return y
