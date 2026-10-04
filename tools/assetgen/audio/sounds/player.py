"""Player body: pain grunts, death, exertion breaths (adult male voice via glottal source + formants) and
heartbeat loops (low-health / fear). Voices: fast glottal attack, pressed voice at the peak, f0 falling
with a creaky, breathy release - never a steady synthetic tone."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _grunt(sr, r, dur, f0, vowel, *, rough=0.15, oq=0.45, breath_in=0.0, tail_breath=0.5, tilt=0.0, sub=0.0):
    """One pained vocalization with breathy onset/release and a fry tail as pressure drops."""
    n = dsp.ns(dur, sr)
    amp = [(0.0, 0.0), (0.01, 0.85), (0.03, 1.0), (dur * 0.35, 0.55), (dur * 0.7, 0.18), (dur, 0.0)]
    oqc = [(0.0, oq), (dur * 0.6, oq + 0.1), (dur, 0.85)]
    jit = 0.02 + 0.02 * rough
    v = dsp.voice(sr, dur, f0, vowel, amp, r, oq=oqc, sq=3.0, jitter=jit, shimmer=0.07, drift=0.01,
                  breath=[(0, 0.15), (0.05, 0.05), (dur, 0.6)], asp=0.3, rough=rough, rough_rate=dsp.vary(r, 34.0, 0.2),
                  sub=sub, tilt_db=tilt + 4.0, wander=0.03, tract=dsp.vary(r, 1.0, 0.03))
    y = dsp.normalize(v)
    if tail_breath:
        bd = dur * 0.6
        b = dsp.breath(sr, bd, "h", [(0.0, 0.0), (0.06, 1.0), (bd, 0.0)], r, hiss=0.15)
        y = dsp.fit(y, n + dsp.ns(bd * 0.6, sr))
        dsp.place(y, dsp.normalize(b) * tail_breath * 0.35, dsp.ns(dur * 0.65, sr))
    if breath_in:
        pre = dsp.breath(sr, 0.12, "ih", [(0, 0), (0.08, 1.0), (0.12, 0.0)], r, hiss=0.6, hiss_f=2500.0)
        y = np.concatenate([dsp.normalize(pre) * breath_in * 0.3, y])
    return dsp.sat(y, 1.3)


@sound("voice/player_hurt", variants=5, seed=7001, peak_db=-5.6)
def player_hurt(seed, variant, sr):
    r = dsp.rng(seed, "hurt")
    if variant == 0:      # "uh!"
        d = r.uniform(0.22, 0.28)
        return _grunt(sr, r, d, [(0, 150.0), (0.03, 175.0), (d, 118.0)], [(0, "uh"), (d, "schwa")], rough=0.2)
    if variant == 1:      # "agh!" harsh
        d = r.uniform(0.38, 0.46)
        return _grunt(sr, r, d, [(0, 170.0), (0.05, 205.0), (0.2, 180.0), (d, 128.0)], [(0, "ae"), (0.1, "a"), (d, "uh")],
                      rough=0.45, oq=0.4, tilt=3.0, sub=0.15)
    if variant == 2:      # "hnngh" through the teeth
        d = r.uniform(0.33, 0.4)
        return _grunt(sr, r, d, [(0, 135.0), (0.06, 158.0), (d, 108.0)], [(0, "ng"), (d * 0.6, "ng"), (d, "uh")],
                      rough=0.3, oq=0.38, tail_breath=0.8)
    if variant == 3:      # "ugh" with fry
        d = r.uniform(0.3, 0.36)
        return _grunt(sr, r, d, [(0, 145.0), (0.04, 160.0), (d * 0.7, 112.0), (d, 70.0)], [(0, "oo"), (d * 0.5, "uh")],
                      rough=0.3, sub=[(0, 0.0), (d * 0.6, 0.0), (d, 0.5)])
    d = r.uniform(0.2, 0.26)  # sharp "ah!"
    return _grunt(sr, r, d, [(0, 200.0), (0.025, 235.0), (d, 165.0)], [(0, "ae"), (d, "a")], rough=0.25, oq=0.42,
                  tilt=2.0, breath_in=1.0)


@sound("voice/player_death", variants=2, seed=7002, peak_db=-7.3)
def player_death(seed, variant, sr):
    """Cry of pain, a choking gasp, a long falling groan into creak, the last breath out."""
    r = dsp.rng(seed, "death")
    y = _buf(3.4, sr)
    d1 = r.uniform(0.5, 0.65) if variant == 0 else r.uniform(0.35, 0.45)
    cry = _grunt(sr, r, d1, [(0, 190.0), (0.06, 230.0), (d1 * 0.5, 200.0), (d1, 150.0)], [(0, "ae"), (0.12, "a"), (d1, "uh")],
                 rough=0.4, oq=0.4, tilt=3.0, tail_breath=0.0, sub=0.1)
    dsp.place(y, cry, 0, 1.0)
    t = d1 + 0.05
    for _ in range(1 if variant == 0 else 2):
        gd = r.uniform(0.25, 0.35)
        gasp = dsp.breath(sr, gd, [(0, "ih"), (gd, "uh")], [(0, 0), (gd * 0.25, 1.0), (gd * 0.6, 0.7), (gd, 0)], r, hiss=0.8,
                          hiss_f=2200.0, rattle=0.45, rattle_hz=dsp.vary(r, 26.0, 0.2), wet=0.4)
        gasp = dsp.hp(gasp, sr, 450.0)
        dsp.place(y, dsp.normalize(gasp), dsp.ns(t, sr), 0.35)
        t += gd + r.uniform(0.05, 0.12)
    d3 = r.uniform(1.1, 1.4)
    groan = dsp.voice(sr, d3, [(0, 135.0), (0.15, 125.0), (d3 * 0.6, 95.0), (d3, 62.0)], [(0, "uh"), (d3 * 0.5, "o"), (d3, "m")],
                      [(0, 0), (0.06, 0.9), (d3 * 0.5, 0.65), (d3 * 0.85, 0.25), (d3, 0)], r,
                      oq=[(0, 0.5), (d3, 0.3)], sq=2.5, jitter=0.025, shimmer=0.1, breath=0.12, asp=0.4, rough=0.35,
                      sub=[(0, 0.0), (d3 * 0.5, 0.2), (d3, 0.6)], drift=0.02)
    dsp.place(y, dsp.normalize(groan), dsp.ns(t, sr), 0.6)
    t += d3 - 0.1
    fd = r.uniform(0.6, 0.8)
    last = dsp.breath(sr, fd, [(0, "uh"), (fd, "h")], [(0, 0), (0.08, 1.0), (fd, 0)], r, hiss=0.15, wet=0.3, rattle=0.3)
    dsp.place(y, dsp.normalize(last), dsp.ns(t, sr), 0.28)
    return dsp.sat(y, 1.2)


@sound("voice/breath_exert", variants=4, seed=7003, peak_db=-6.9)
def breath_exert(seed, variant, sr):
    """Effort breaths: 0 swing exhale 'hhuh', 1 double 'huh-huh', 2 lifting strain 'hnnh-hah', 3 winded in/out."""
    r = dsp.rng(seed, "exert")
    y = _buf(1.2, sr)
    ind = r.uniform(0.18, 0.26)
    inh = dsp.breath(sr, ind, [(0, "ih"), (ind, "uh")], [(0, 0), (ind * 0.7, 1.0), (ind, 0.0)], r, hiss=0.7, hiss_f=2400.0)
    t = 0.0
    if variant in (0, 3):
        dsp.place(y, dsp.normalize(inh), 0, 0.3)
        t = ind
    reps = 2 if variant == 1 else 1
    for k in range(reps):
        d = r.uniform(0.22, 0.32)
        if variant == 2:
            st = r.uniform(0.3, 0.4)
            strain = dsp.voice(sr, st, [(0, 120.0), (st, 138.0)], "ng", [(0, 0), (0.04, 0.8), (st * 0.85, 1.0), (st, 0.0)], r, oq=0.35, sq=3.0,
                               jitter=0.03, shimmer=0.08, breath=0.05, rough=0.4)
            dsp.place(y, dsp.normalize(strain), dsp.ns(t, sr), 0.6)
            t += st
        vo = dsp.voice(sr, d, [(0, 145.0), (d, 112.0)], [(0, "a"), (d, "uh")], [(0, 0), (0.015, 1.0), (d * 0.4, 0.5), (d, 0)], r,
                       oq=0.7, sq=2.0, jitter=0.02, shimmer=0.06, breath=0.6, asp=0.5)
        ex = dsp.breath(sr, d, [(0, "a"), (d, "h")], [(0, 0), (0.01, 1.0), (d, 0)], r, hiss=0.25)
        seg = dsp.normalize(vo) * (0.55 if variant != 3 else 0.2) + dsp.normalize(ex) * 0.6
        dsp.place(y, seg, dsp.ns(t, sr), 1.0 if k == 0 else 0.8)
        t += d + r.uniform(0.08, 0.14)
    return y


def _heart(sr, r, period, beats, s1_f=48.0, intensity=1.0):
    """Muffled heartbeat heard from inside: S1 'lub' (lower, longer) and S2 'dub' (shorter, higher) on a
    circular buffer so the loop is seamless."""
    n = dsp.ns(period * beats, sr)
    y = np.zeros(n)
    gap = min(0.34 * period ** 0.5, period * 0.42)
    for b in range(beats):
        t = b * period + r.uniform(-0.004, 0.004)
        a = intensity * r.uniform(0.85, 1.0)
        for f, d, g, dt in ((s1_f, 0.13, 1.0, 0.0), (s1_f * 1.35, 0.09, 0.7, gap)):
            m = dsp.ns(d + 0.12, sr)
            f_curve = dsp.curve([(0, f * 1.25), (d, f * 0.9)], m, sr)
            tone = dsp.sine(f_curve, m, sr) * dsp.env_ar(m, sr, 0.012, d)
            tone += 0.35 * dsp.sine(f_curve * 2.02, m, sr) * dsp.env_ar(m, sr, 0.008, d * 0.6)
            thump = dsp.lp(dsp.white(m, r), sr, 180.0, order=4) * dsp.env_ar(m, sr, 0.004, d * 0.5)
            ev = dsp.normalize(tone) + 0.35 * dsp.normalize(thump)
            dsp.loop_place(y, ev, dsp.ns(t + dt, sr) % n, a * g)
    y = dsp.circular(lambda x: dsp.lp(x, sr, 240.0, order=4), y, sr, 0.5)
    return y


@sound("sfx/heartbeat_slow", variants=1, seed=7004, peak_db=-4.0, loop=True)
def heartbeat_slow(seed, variant, sr):
    r = dsp.rng(seed, "hbslow")
    return _heart(sr, r, 1.0, 4, 46.0, 1.0)            # 60 bpm, 4 s loop


@sound("sfx/heartbeat_fast", variants=1, seed=7005, peak_db=-3.0, loop=True)
def heartbeat_fast(seed, variant, sr):
    r = dsp.rng(seed, "hbfast")
    return _heart(sr, r, 0.46, 8, 52.0, 1.0)           # ~130 bpm, 3.68 s loop
