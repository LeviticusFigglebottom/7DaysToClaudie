"""Buildings, doors and containers: timber strain, breakage, glass, hinges, latches, drawers, rummaging,
metal clangs and the Hollowed pounding on doors. Dry (interior reverb is a runtime bus)."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound


def _punch(y, sr, ceiling):
    """Transient limiting (~1 ms look-ahead): trims only the initial spike so the body reads louder."""
    return dsp.limit(dsp.normalize(y), sr, ceiling, window_ms=1.0)


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


def _latch(sr, r, gain=1.0):
    """Door latch / handle mechanism: two quick steel clicks over a small wood knock."""
    y = _buf(0.12, sr)
    a = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 2600.0, 0.2), 0.1, contact_ms=0.1, t60=0.05, click=0.6, click_hz=4000.0)
    b = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 3300.0, 0.2), 0.08, contact_ms=0.1, t60=0.04, click=0.6)
    dsp.place(y, a, 0, 1.0)
    dsp.place(y, b, dsp.ns(r.uniform(0.012, 0.03), sr), 0.6)
    dsp.place(y, dsp.impact(sr, r, "wood", dsp.vary(r, 400.0, 0.2), 0.08, contact_ms=0.6, t60=0.05, click=0.0), 0, 0.4)
    return y * gain


def _door_res(r, f0=115.0, squeal=True):
    md = dsp.modes("wood_hollow", dsp.vary(r, f0, 0.15), r, count=10)
    res = [(float(f), dsp.vary(r, 14.0, 0.3), float(a)) for f, a in zip(md[0][:8], md[2][:8])]
    if squeal:
        res += [(dsp.vary(r, 1700.0, 0.2), 25.0, 0.8), (dsp.vary(r, 2900.0, 0.2), 30.0, 0.6), (dsp.vary(r, 4300.0, 0.2), 30.0, 0.35)]
    return res


def _hinge_creak(sr, r, dur, lo=40.0, hi=600.0, squeal=True, f0=115.0):
    k = int(r.integers(4, 9))
    ts = np.sort(r.uniform(0.05, dur - 0.05, k))
    rate = [(0.0, lo)] + [(t, dsp.loguni(r, lo * 1.5, hi)) for t in ts] + [(dur, lo)]
    amp = [(0.0, 0.0), (0.06, 0.6)] + [(t, r.uniform(0.5, 1.0)) for t in ts] + [(dur - 0.05, 0.4), (dur, 0.0)]
    y = dsp.creak(sr, dur, r, rate, amp, res=_door_res(r, f0, squeal), jitter=0.12, pulse_ms=0.25, roughness=0.35, body=0.04,
                  bright=2500.0 if squeal else 1500.0)
    return dsp.normalize(y)


@sound("sfx/structure_creak", variants=4, seed=5001, peak_db=-3.6)
def structure_creak(seed, variant, sr):
    r = dsp.rng(seed, "structcreak")
    dur = r.uniform(1.3, 2.2)
    k = int(r.integers(3, 7))
    ts = np.sort(r.uniform(0.1, dur - 0.1, k))
    rate = [(0.0, 18.0)] + [(t, dsp.loguni(r, 18.0, 260.0)) for t in ts] + [(dur, 22.0)]
    amp = [(0.0, 0.0), (0.15, 0.7)] + [(t, r.uniform(0.3, 1.0)) for t in ts] + [(dur, 0.0)]
    res = [(dsp.vary(r, 230.0, 0.2), 7.0, 1.0), (dsp.vary(r, 470.0, 0.2), 9.0, 0.8), (dsp.vary(r, 900.0, 0.2), 11.0, 0.5),
           (dsp.vary(r, 1700.0, 0.2), 12.0, 0.3)]
    n = dsp.ns(dur, sr)
    stick = np.clip(0.55 + 0.6 * dsp.smooth_noise(n, sr, r, 3.0), 0.0, 1.0) ** 1.5      # catches and releases
    y = dsp.creak(sr, dur, r, dsp.curve(rate, n, sr, "smooth") * (0.6 + 0.4 * stick), dsp.curve(amp, n, sr) * stick,
                  res=res, jitter=0.4, pulse_ms=0.6, roughness=0.7, bright=2200.0)
    y = dsp.normalize(y) + 0.3 * dsp.normalize(dsp.lp(y, sr, 250.0))
    for _ in range(int(r.integers(1, 4))):
        tk = dsp.impact(sr, r, "wood", dsp.vary(r, 450.0, 0.3), 0.1, contact_ms=0.5, t60=0.06, click=0.4)
        dsp.place(y, tk, dsp.ns(r.uniform(0.1, dur - 0.1), sr), r.uniform(0.1, 0.25))
    return y


def _wood_break(sr, r, dur, scale=1.0):
    """Planks splintering and the pieces clattering down."""
    y = _buf(dur, sr)
    panel = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 100.0, 0.2), 0.6, contact_ms=2.0, t60=0.3, noise=0.5, click=0.0)
    dsp.place(y, panel, 0, 0.8)
    dsp.place(y, dsp.thud(sr, r, 75.0, 0.4, contact_ms=5.0, t60=0.08, noise=0.5, knock=0.6, knock_f=280.0), 0, 0.7)
    t = 0.0
    for i in range(int(r.integers(3, 6) * scale)):
        c = dsp.crack(sr, r, 0.25, n_clicks=int(r.integers(2, 6)), spread=0.015, body="wood", body_f=dsp.loguni(r, 250.0, 900.0),
                      body_amt=0.7, bright=dsp.vary(r, 3500.0, 0.3), tail=0.35, tail_rate=600.0)
        dsp.place(y, c, dsp.ns(t, sr), 1.0 if i == 0 else r.uniform(0.3, 0.8))
        t += r.exponential(0.05)
    # pieces landing and clattering
    t = r.uniform(0.25, 0.4)
    a = 0.7
    while t < dur - 0.3:
        p = dsp.impact(sr, r, "wood", dsp.loguni(r, 180.0, 700.0), 0.3, contact_ms=r.uniform(0.8, 2.5), t60=0.12,
                       click=0.3, noise=0.4)
        dsp.place(y, p, dsp.ns(t, sr), a * r.uniform(0.4, 1.0))
        t += r.exponential(0.09)
        a *= 0.85
    for _ in range(int(r.integers(1, 4))):
        nl = dsp.impact(sr, r, "metal_bar", dsp.loguni(r, 2000.0, 4000.0), 0.25, contact_ms=0.15, t60=0.15, click=0.4)
        dsp.place(y, nl, dsp.ns(r.uniform(0.3, dur - 0.4), sr), r.uniform(0.05, 0.15))
    n = len(y)
    dust = dsp.clicks(n, sr, r, dsp.env_ar(n, sr, 0.05, dur * 0.7) * 700.0, 1200.0, 8000.0, q=2.0, alpha=1.7)
    y += 0.08 * dsp.normalize(dust)
    return y


@sound("sfx/structure_break_wood", variants=4, seed=5002, peak_db=-2.0)
def structure_break_wood(seed, variant, sr):
    r = dsp.rng(seed, "structbreak")
    return _wood_break(sr, r, r.uniform(1.4, 1.8))


@sound("sfx/barricade_break", variants=3, seed=5003, peak_db=-1.0)
def barricade_break(seed, variant, sr):
    """Heavier than a wall plank: double impact, nails shrieking out of the posts, crash of several planks."""
    r = dsp.rng(seed, "barricade")
    dur = 2.4
    y = _wood_break(sr, r, dur, scale=1.6)
    t2 = r.uniform(0.08, 0.16)
    dsp.place(y, _wood_break(sr, r, dur - t2, scale=0.8), dsp.ns(t2, sr), 0.6)
    for _ in range(int(r.integers(1, 3))):
        d = r.uniform(0.15, 0.3)
        sq = dsp.creak(sr, d, r, [(0, r.uniform(700, 1100)), (d, r.uniform(1300, 2200))], [(0, 0), (0.02, 1.0), (d, 0)],
                       res=[(dsp.vary(r, 2400.0, 0.15), 30.0, 1.0), (dsp.vary(r, 4100.0, 0.15), 35.0, 0.7),
                            (dsp.vary(r, 6000.0, 0.15), 30.0, 0.4)], jitter=0.08, pulse_ms=0.15)
        dsp.place(y, dsp.normalize(sq), dsp.ns(r.uniform(0.02, 0.2), sr), r.uniform(0.15, 0.3))
    return dsp.sat(y / dsp.peak(y), 1.4)


def _shard(sr, r, f0, t60, gain=1.0):
    """One glass fragment ringing: a few inharmonic modes, very hard contact."""
    fr, tt, aa = dsp.modes("glass", f0, r, t60=t60)
    dur = min(0.6, float(np.max(tt)) + 0.01)
    n = dsp.ns(dur, sr)
    y = dsp.partials(n, sr, fr, aa * r.uniform(0.2, 1.0, len(aa)), tt, r.uniform(0, 6.28, len(fr)))
    a = dsp.ns(0.0003, sr)
    y[:a] *= np.linspace(0, 1, a)
    c = dsp.hp(r.standard_normal(dsp.ns(0.001, sr)), sr, 5000.0)
    dsp.place(y, c * 0.3 * dsp.peak(y) / max(dsp.peak(c), 1e-9), 0)
    return y * gain


@sound("sfx/glass_break", variants=4, seed=5004, peak_db=-2.0)
def glass_break(seed, variant, sr):
    """Window pane: hard strike and crack, shatter burst of shards, fragments raining on the floor."""
    r = dsp.rng(seed, "glass")
    dur = 2.0
    y = _buf(dur, sr)
    pane = dsp.impact(sr, r, "glass", dsp.vary(r, 1250.0, 0.2), 0.4, contact_ms=0.05, t60=0.25, click=0.9, click_hz=3000.0,
                      noise=0.7)
    dsp.place(y, pane, 0, 0.8)
    L = dsp.ns(0.12, sr)
    crash = dsp.band_noise(L, sr, r, 1500.0, 16000.0) * dsp.env_ar(L, sr, 0.0003, 0.07)
    dsp.place(y, dsp.normalize(crash), 0, 0.9)
    dsp.place(y, dsp.thud(sr, r, 160.0, 0.1, contact_ms=1.5, t60=0.03, noise=0.6, knock=0.5, knock_f=600.0), 0, 0.35)
    # shatter burst
    times = np.sort(r.exponential(0.035, int(r.integers(70, 120))))
    for t in times[times < 0.3]:
        dsp.place(y, _shard(sr, r, dsp.loguni(r, 2500.0, 11000.0), r.uniform(0.04, 0.25)), dsp.ns(t, sr),
                  r.uniform(0.05, 0.35) * np.exp(-t / 0.15))
    # rain of fragments on the floor (with bounces)
    t = r.uniform(0.25, 0.35)
    a = 0.45
    while t < dur - 0.4:
        f = dsp.loguni(r, 2000.0, 9000.0)
        dsp.place(y, _shard(sr, r, f, r.uniform(0.05, 0.3)), dsp.ns(t, sr), a * r.uniform(0.3, 1.0))
        if r.random() < 0.4:
            dsp.place(y, _shard(sr, r, f, 0.1), dsp.ns(t + r.uniform(0.03, 0.07), sr), a * 0.25)
        t += r.exponential(0.035 + 0.12 * (t / dur))
        a *= 0.96
    for _ in range(int(r.integers(1, 3))):
        dsp.place(y, dsp.impact(sr, r, "glass", dsp.loguni(r, 900.0, 1800.0), 0.3, contact_ms=0.1, t60=0.15, click=0.6),
                  dsp.ns(r.uniform(0.3, 0.6), sr), r.uniform(0.2, 0.4))
    return y


@sound("sfx/door_open_creak", variants=3, seed=5005, peak_db=-6.7)
def door_open_creak(seed, variant, sr):
    """Latch, then hinges: 0 squealing hinge, 1 low groaning door, 2 stuttering creak."""
    r = dsp.rng(seed, "dooropen")
    dur = r.uniform(1.5, 2.1)
    y = _buf(dur + 0.2, sr)
    dsp.place(y, _latch(sr, r), 0, 0.6)
    t0 = r.uniform(0.08, 0.15)
    if variant == 0:
        cr = _hinge_creak(sr, r, dur - t0, 60.0, 800.0, True)
    elif variant == 1:
        cr = _hinge_creak(sr, r, dur - t0, 20.0, 160.0, False, f0=95.0)
    else:
        cr = _hinge_creak(sr, r, dur - t0, 25.0, 450.0, True)
        m = len(cr)
        gate = np.zeros(m)
        t = 0.0
        while t < (dur - t0):   # irregular stick/release segments as the door is pushed in jerks
            on = r.uniform(0.12, 0.35)
            k0, k1 = dsp.ns(t, sr), dsp.ns(t + on, sr)
            if k1 > k0:
                gate[k0:min(k1, m)] = dsp.hann(k1 - k0)[:max(0, min(k1, m) - k0)] ** 0.3
            t += on + r.uniform(0.05, 0.2)
        cr = cr * gate
    dsp.place(y, cr, dsp.ns(t0, sr), 1.0)
    n = len(y)
    air = dsp.lp(dsp.pink(n, r), sr, 400.0) * dsp.curve([(0, 0), (0.4, 0.5), (dur, 0.0)], n, sr)
    y += 0.08 * dsp.normalize(air)
    return y


@sound("sfx/door_close", variants=3, seed=5006, peak_db=-3.0)
def door_close(seed, variant, sr):
    r = dsp.rng(seed, "doorclose")
    y = _buf(1.0, sr)
    tsl = r.uniform(0.07, 0.11)
    sw = dsp.lp(dsp.pink(dsp.ns(tsl, sr), r), sr, 350.0) * dsp.curve([(0, 0), (tsl, 1.0)], dsp.ns(tsl, sr), sr) ** 2
    dsp.place(y, dsp.normalize(sw), 0, 0.15)
    k = dsp.ns(tsl, sr)
    panel = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 110.0, 0.15), 0.7, contact_ms=2.5, t60=dsp.vary(r, 0.3, 0.2),
                       noise=0.5, click=0.2, click_hz=1500.0)
    dsp.place(y, panel, k, 1.0)
    frame = dsp.impact(sr, r, "wood", dsp.vary(r, 300.0, 0.2), 0.3, contact_ms=0.8, t60=0.1, click=0.5, click_hz=2000.0)
    dsp.place(y, frame, k, 0.9)
    dsp.place(y, dsp.thud(sr, r, 80.0, 0.3, contact_ms=5.0, t60=0.05, noise=0.5, knock=0.5, knock_f=300.0), k, 0.6)
    dsp.place(y, _latch(sr, r), k + dsp.ns(r.uniform(0.004, 0.015), sr), 0.7)
    for _ in range(int(r.integers(1, 3))):
        rt = dsp.impact(sr, r, "metal_bar", dsp.loguni(r, 1800.0, 3500.0), 0.1, contact_ms=0.2, t60=0.06, click=0.3)
        dsp.place(y, rt, k + dsp.ns(r.uniform(0.02, 0.08), sr), r.uniform(0.05, 0.12))
    return _punch(y, sr, 0.7)


@sound("sfx/door_bash", variants=4, seed=5007, peak_db=-2.0)
def door_bash(seed, variant, sr):
    """Shoulder/kick against a closed door: panel boom, frame and hinge rattle, strain creak, dust."""
    r = dsp.rng(seed, "doorbash")
    y = _buf(1.0, sr)
    panel = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 85.0, 0.15), 0.8, contact_ms=dsp.vary(r, 5.0, 0.3), t60=0.4,
                       noise=0.6, click=0.15)
    dsp.place(y, panel, 0, 1.0)
    dsp.place(y, dsp.thud(sr, r, 65.0, 0.4, contact_ms=10.0, t60=0.07, noise=0.6, knock=0.6, knock_f=250.0), 0, 0.8)
    t = r.uniform(0.008, 0.02)
    for _ in range(int(r.integers(3, 7))):
        if r.random() < 0.5:
            c = dsp.impact(sr, r, "metal_bar", dsp.loguni(r, 1500.0, 3500.0), 0.12, contact_ms=0.15, t60=0.08, click=0.4)
        else:
            c = dsp.impact(sr, r, "wood", dsp.loguni(r, 300.0, 700.0), 0.12, contact_ms=0.5, t60=0.07, click=0.3)
        dsp.place(y, c, dsp.ns(t, sr), r.uniform(0.1, 0.3))
        t += r.uniform(0.01, 0.04)
    cd = r.uniform(0.25, 0.45)
    cr = dsp.creak(sr, cd, r, [(0, 30.0), (cd * 0.4, r.uniform(80, 200)), (cd, 30.0)], [(0, 0), (0.03, 1), (cd, 0)],
                   res=_door_res(r, 100.0, False), jitter=0.2, pulse_ms=0.5)
    dsp.place(y, dsp.normalize(cr), dsp.ns(r.uniform(0.04, 0.1), sr), 0.25)
    n = len(y)
    dust = dsp.clicks(n, sr, r, dsp.env_ar(n, sr, 0.02, 0.5) * 500.0, 1500.0, 8000.0, q=2.0)
    y += 0.05 * dsp.normalize(dust)
    return dsp.sat(y / dsp.peak(y), 1.3)


@sound("sfx/door_locked_rattle", variants=2, seed=5008, peak_db=-6.0)
def door_locked_rattle(seed, variant, sr):
    r = dsp.rng(seed, "locked")
    y = _buf(1.0, sr)
    t = 0.0
    for i in range(int(r.integers(3, 6))):
        dsp.place(y, _latch(sr, r), dsp.ns(t, sr), r.uniform(0.6, 1.0))
        knock = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 130.0, 0.15), 0.25, contact_ms=1.5, t60=0.12, click=0.2)
        dsp.place(y, knock, dsp.ns(t + r.uniform(0.003, 0.012), sr), r.uniform(0.3, 0.6))
        t += r.uniform(0.1, 0.17)
        if t > 0.8:
            break
    return y


@sound("sfx/metal_clang", variants=4, seed=5009, peak_db=-2.0)
def metal_clang(seed, variant, sr):
    """Loose metal object falling (pipe, bucket/barrel, sheet, pan): first hit, bounces, ring-out."""
    r = dsp.rng(seed, "clang")
    kind = ["pipe", "metal", "metal_sheet", "metal"][variant]
    f0 = [420.0, 210.0, 160.0, 330.0][variant]
    md = dsp.modes(kind, dsp.vary(r, f0, 0.1), r, t60=[1.6, 1.3, 0.9, 1.0][variant])
    y = _buf(2.6, sr)
    t, a = 0.0, 1.0
    for i in range(int(r.integers(3, 6))):
        h = dsp.impact(sr, r, modes_=(md[0], md[1], md[2] * r.uniform(0.3, 1.0, len(md[2]))), contact_ms=0.3, noise=0.4,
                       click=0.5, dur=2.6 - t)
        dsp.place(y, h, dsp.ns(t, sr), a)
        t += r.uniform(0.18, 0.32) * (0.75 ** i)
        a *= r.uniform(0.35, 0.6)
    dsp.place(y, dsp.thud(sr, r, 120.0, 0.15, contact_ms=1.5, t60=0.03, noise=0.6), 0, 0.3)
    return y


@sound("sfx/container_open_wood", variants=4, seed=5010, peak_db=-4.7)
def container_open_wood(seed, variant, sr):
    r = dsp.rng(seed, "crateopen")
    y = _buf(1.0, sr)
    dsp.place(y, dsp.impact(sr, r, "wood", dsp.vary(r, 380.0, 0.2), 0.12, contact_ms=0.8, t60=0.06, click=0.3), 0, 0.4)
    cd = r.uniform(0.35, 0.6)
    cr = dsp.creak(sr, cd, r, [(0, 30.0), (cd * 0.5, r.uniform(90, 300)), (cd, 40.0)], [(0, 0), (0.05, 0.8), (cd, 0.3)],
                   res=_door_res(r, dsp.vary(r, 170.0, 0.2), r.random() < 0.5), jitter=0.15, pulse_ms=0.3)
    dsp.place(y, dsp.normalize(cr), dsp.ns(0.04, sr), 0.6)
    tk = dsp.ns(0.04 + cd, sr)
    lid = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 160.0, 0.2), 0.4, contact_ms=2.0, t60=0.18, click=0.2)
    dsp.place(y, lid, tk, 1.0)
    dsp.place(y, dsp.thud(sr, r, 110.0, 0.15, contact_ms=5.0, t60=0.04, knock=0.5, knock_f=350.0), tk, 0.4)
    return y


@sound("sfx/container_open_metal", variants=3, seed=5011, peak_db=-6.0)
def container_open_metal(seed, variant, sr):
    r = dsp.rng(seed, "lockeropen")
    y = _buf(1.2, sr)
    dsp.place(y, _latch(sr, r), 0, 0.8)
    cd = r.uniform(0.3, 0.5)
    cr = dsp.creak(sr, cd, r, [(0, 200.0), (cd * 0.5, r.uniform(600, 1100)), (cd, 300.0)], [(0, 0), (0.04, 1.0), (cd, 0.2)],
                   res=[(dsp.vary(r, 1400.0, 0.2), 25.0, 1.0), (dsp.vary(r, 2600.0, 0.2), 30.0, 0.7),
                        (dsp.vary(r, 4100.0, 0.2), 30.0, 0.4)], jitter=0.1, pulse_ms=0.15)
    dsp.place(y, dsp.normalize(cr), dsp.ns(0.06, sr), 0.4)
    md = dsp.modes("metal_sheet", dsp.vary(r, 140.0, 0.2), r, t60=0.6)
    n = dsp.ns(0.9, sr)
    exc = dsp.band_noise(n, sr, r, 200.0, 3000.0) * dsp.env_ar(n, sr, 0.05, 0.3) * 0.02
    wob = dsp.modal_bank(exc, sr, md[0], md[1], md[2])
    dsp.place(y, dsp.normalize(wob), dsp.ns(0.08, sr), 0.35)
    tk = dsp.ns(0.06 + cd, sr)
    stop = dsp.impact(sr, r, modes_=md, contact_ms=0.6, click=0.4, noise=0.4, dur=0.8)
    dsp.place(y, stop, tk, 0.9)
    return y


@sound("sfx/drawer_open", variants=4, seed=5012, peak_db=-8.8)
def drawer_open(seed, variant, sr):
    """Wooden drawer: juddering runner friction through the box resonance, contents shift, stop knock."""
    r = dsp.rng(seed, "drawer")
    y = _buf(0.9, sr)
    d = r.uniform(0.35, 0.55)
    box = dsp.modes("wood_hollow", dsp.vary(r, 210.0, 0.2), r, count=8)
    res = [(float(f), 6.0, float(a)) for f, a in zip(box[0][:6], box[2][:6])]
    fr = dsp.scrape(sr, d, r, [(0, 0), (0.04, 1.0), (d * 0.7, 0.8), (d, 0)], f_lo=150.0, f_hi=2500.0, grit=0.6, grit_rate=400.0,
                    res=res, rough_hz=dsp.vary(r, 28.0, 0.3))
    jud = dsp.creak(sr, d, r, dsp.vary(r, 35.0, 0.3), [(0, 0), (0.05, 1.0), (d, 0)], res=res, jitter=0.3, pulse_ms=1.0)
    dsp.place(y, dsp.normalize(fr) + 0.5 * dsp.normalize(jud), 0, 0.8)
    t = r.uniform(0.03, 0.1)
    for _ in range(int(r.integers(2, 6))):
        mat = dsp.pick(r, ["metal_bar", "wood_small", "plastic", "glass"])
        f0 = {"metal_bar": 2500.0, "wood_small": 1200.0, "plastic": 900.0, "glass": 2800.0}[mat]
        c = dsp.impact(sr, r, mat, dsp.vary(r, f0, 0.3), 0.1, contact_ms=0.3, t60=0.05, click=0.3)
        dsp.place(y, c, dsp.ns(t, sr), r.uniform(0.08, 0.25))
        t += r.uniform(0.04, 0.12)
    stop = dsp.impact(sr, r, "wood", dsp.vary(r, 260.0, 0.2), 0.25, contact_ms=1.2, t60=0.1, click=0.3, noise=0.3)
    dsp.place(y, stop, dsp.ns(d, sr), 0.7)
    dsp.place(y, dsp.thud(sr, r, 120.0, 0.12, contact_ms=3.0, t60=0.03, knock=0.6, knock_f=420.0), dsp.ns(d, sr), 0.4)
    return y


@sound("sfx/search_rummage", variants=4, seed=5013, peak_db=-11.0)
def search_rummage(seed, variant, sr):
    """Hands going through a container: cloth, paper, and small objects knocking."""
    r = dsp.rng(seed, "rummage")
    dur = r.uniform(1.1, 1.5)
    n = dsp.ns(dur, sr)
    motion = 0.35 + 0.65 * np.abs(dsp.smooth_noise(n, sr, r, 4.0))
    motion *= dsp.curve([(0, 0), (0.08, 1), (dur - 0.15, 1), (dur, 0)], n, sr)
    y = 0.6 * dsp.normalize(dsp.cloth(sr, dur, r, motion, heavy=0.5))
    y += 0.35 * dsp.normalize(dsp.rustle(sr, dur, r, motion ** 2, f_lo=2000.0, f_hi=10000.0, density=900.0, q=3.0))
    t = r.uniform(0.05, 0.2)
    while t < dur - 0.1:
        mat = dsp.pick(r, ["metal_bar", "wood_small", "plastic", "glass", "ceramic"])
        f0 = {"metal_bar": 2300.0, "wood_small": 1000.0, "plastic": 800.0, "glass": 2600.0, "ceramic": 1700.0}[mat]
        c = dsp.impact(sr, r, mat, dsp.vary(r, f0, 0.3), 0.15, contact_ms=0.4, t60=0.07, click=0.3)
        dsp.place(y, c, dsp.ns(t, sr), r.uniform(0.1, 0.35))
        t += r.exponential(0.16)
    return y


@sound("sfx/zombie_hit_door", variants=4, seed=5014, peak_db=-2.0)
def zombie_hit_door(seed, variant, sr):
    """Hollowed pounding a door with fists/forearms: soft fleshy contact on a booming panel, frame rattle,
    sometimes a double blow."""
    r = dsp.rng(seed, "zdoor")
    y = _buf(1.0, sr)
    hits = [0.0] + ([r.uniform(0.18, 0.3)] if variant % 2 == 1 else [])
    for i, t in enumerate(hits):
        k = dsp.ns(t, sr)
        panel = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 95.0, 0.15), 0.7, contact_ms=dsp.vary(r, 5.0, 0.25),
                           t60=0.24, noise=0.5, click=0.0)
        g = 1.0 if i == 0 else r.uniform(0.6, 0.85)
        dsp.place(y, panel, k, g)
        knock = dsp.impact(sr, r, "wood", dsp.vary(r, 330.0, 0.2), 0.3, contact_ms=2.5, t60=0.12, noise=0.4, click=0.1)
        dsp.place(y, knock, k, 0.55 * g)
        dsp.place(y, dsp.thud(sr, r, 75.0, 0.35, contact_ms=12.0, t60=0.04, noise=0.6, knock=0.6, knock_f=300.0), k, 0.6 * g)
        L = dsp.ns(0.04, sr)
        slap = dsp.band_noise(L, sr, r, 500.0, 4500.0) * dsp.env_ar(L, sr, 0.0015, 0.025)
        dsp.place(y, dsp.normalize(slap), k, 0.45 * g)
        for _ in range(int(r.integers(2, 5))):
            if r.random() < 0.5:
                c = dsp.impact(sr, r, "metal_bar", dsp.loguni(r, 1500.0, 3000.0), 0.1, contact_ms=0.2, t60=0.07, click=0.3)
            else:
                c = dsp.impact(sr, r, "wood", dsp.loguni(r, 350.0, 800.0), 0.1, contact_ms=0.6, t60=0.05, click=0.3)
            dsp.place(y, c, k + dsp.ns(r.uniform(0.008, 0.05), sr), r.uniform(0.08, 0.22) * g)
    return dsp.hp(dsp.sat(y / dsp.peak(y), 1.2), sr, 50.0)
