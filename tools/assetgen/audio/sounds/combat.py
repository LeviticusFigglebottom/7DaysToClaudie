"""Melee, tool strikes and body impacts: swings, chops, flesh hits, stone/metal/wood strikes, gore.

Layering rule for every hit: transient (contact click / bite / crack) + body (modal resonance of the
struck object or a meaty low thump) + tail (debris, chips, ring-out, wet residue). Dry: the game adds
room/cave reverb on its buses.
"""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound

HIT = -3.0      # heavy hits
MID = -5.0


def _punch(y, sr, ceiling):
    """Transient limiting (~1 ms look-ahead): trims only the initial spike so the body reads louder."""
    return dsp.limit(dsp.normalize(y), sr, ceiling, window_ms=1.0)


def _buf(sec, sr):
    return np.zeros(dsp.ns(sec, sr))


# ------------------------------------------------------------------------------------------- swings

@sound("sfx/swing_whoosh", variants=6, seed=2001, peak_db=-7.0)
def swing_whoosh(seed, variant, sr):
    """Light (knife), medium (axe: vortex whistle) and heavy (club/branch) swings, two of each."""
    r = dsp.rng(seed, "swing")
    kind = variant % 3
    if kind == 0:     # light, fast blade
        dur, f_lo, f_hi, q, width, tone = r.uniform(0.28, 0.36), 350.0, dsp.vary(r, 2600.0, 0.15), 1.6, 0.13, 0.0
    elif kind == 1:   # axe: edge whistle
        dur, f_lo, f_hi, q, width, tone = r.uniform(0.38, 0.48), 220.0, dsp.vary(r, 1500.0, 0.15), 1.3, 0.16, 0.35
    else:             # heavy blunt object: lower, broader, longer
        dur, f_lo, f_hi, q, width, tone = r.uniform(0.45, 0.55), 140.0, dsp.vary(r, 1000.0, 0.15), 1.1, 0.16, 0.0
    peak_t = r.uniform(0.5, 0.62)
    y = dsp.whoosh(sr, dur, r, peak_t=peak_t, width=width, f_lo=f_lo, f_hi=f_hi, q=q, tone=tone, skew=1.6)
    n = len(y)
    # weight: low air displacement of the mass
    t = np.arange(n) / sr / dur
    v = np.exp(-((t - peak_t) / (width * 1.3)) ** 2)
    low = dsp.lp(dsp.pink(n, r), sr, 260.0, order=4) * v ** 2
    y = dsp.normalize(y) + (0.25 + 0.2 * kind) * dsp.normalize(low)
    # arm/sleeve movement before the swing
    cl = dsp.cloth(sr, dur * 0.6, r, [(0, 0), (dur * 0.25, 1), (dur * 0.6, 0)], heavy=0.4)
    dsp.place(y, dsp.normalize(cl), 0, 0.12)
    return y


# ------------------------------------------------------------------------------------------- wood chopping

def _chop(r, sr, f_trunk, bite, chips, dur=0.75):
    y = _buf(dur, sr)
    # blade bite: sharp broadband 'thwack' of fibres crushed and split
    L = dsp.ns(0.014, sr)
    th_ = dsp.band_noise(L, sr, r, 1600.0, 10000.0) * dsp.env_ar(L, sr, 0.0004, dsp.vary(r, 0.009, 0.25))
    dsp.place(y, dsp.normalize(th_), 0, 0.65 * bite)
    cr = dsp.crack(sr, r, 0.25, n_clicks=int(r.integers(2, 5)), spread=0.006, body="wood", body_f=dsp.vary(r, 900.0, 0.2),
                   body_amt=0.5, bright=dsp.vary(r, 4500.0, 0.2), tail=0.25, tail_rate=500.0, force=1.0)
    dsp.place(y, cr, 0, 0.5 * bite)
    # trunk/log body: damped wood modes ('tock') + a little low thunk of the mass
    trunk = dsp.impact(sr, r, "wood", f_trunk, 0.4, contact_ms=dsp.vary(r, 0.7, 0.25), t60=dsp.vary(r, 0.15, 0.2),
                       noise=0.4, click=0.0, force=1.0)
    dsp.place(y, trunk, 0, 1.0)
    th = dsp.thud(sr, r, dsp.vary(r, 120.0, 0.15), 0.25, contact_ms=2.0, t60=0.035, noise=0.4, noise_lp=1500.0,
                  knock=1.0, knock_f=dsp.vary(r, 480.0, 0.15))
    dsp.place(y, th, 0, 0.4)
    # axe head: faint steel ring
    ring = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 2300.0, 0.25), 0.35, contact_ms=0.2, t60=dsp.vary(r, 0.25, 0.3),
                      click=0.0, force=1.0)
    dsp.place(y, ring, dsp.ns(0.0008, sr), r.uniform(0.04, 0.09))
    # chips flying and landing
    t = r.uniform(0.05, 0.12)
    for _ in range(chips):
        ch = dsp.impact(sr, r, "wood_small", dsp.loguni(r, 900.0, 2600.0), 0.08, contact_ms=0.3, click=0.5)
        dsp.place(y, ch, dsp.ns(t, sr), r.uniform(0.03, 0.09))
        t += r.uniform(0.04, 0.16)
    # bark/debris crumbs
    k = dsp.ns(0.25, sr)
    deb = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.01, 0.2) * 260.0, 1500.0, 7000.0, q=2.5, alpha=1.5)
    dsp.place(y, dsp.normalize(deb), dsp.ns(0.02, sr), 0.06)
    return dsp.hp(y, sr, 75.0)


@sound("sfx/axe_chop_wood", variants=8, seed=2002, peak_db=HIT)
def axe_chop_wood(seed, variant, sr):
    r = dsp.rng(seed, "chop")
    f_trunk = dsp.vary(r, [260.0, 310.0, 360.0, 290.0][variant % 4], 0.08)
    return _punch(_chop(r, sr, f_trunk, bite=r.uniform(0.7, 1.15), chips=int(r.integers(0, 4))), sr, 0.7)


# ------------------------------------------------------------------------------------------- flesh

def _slice(sr, r, dur=0.05, lo=2500.0, hi=10000.0):
    n = dsp.ns(dur, sr)
    fc = dsp.curve([(0, hi * 0.7), (dur, lo)], n, sr, "exp")
    return dsp.bp(dsp.white(n, r), sr, fc, 1.2) * dsp.env_ar(n, sr, 0.001, dur * 0.7)


@sound("sfx/axe_hit_flesh", variants=6, seed=2003, peak_db=HIT)
def axe_hit_flesh(seed, variant, sr):
    r = dsp.rng(seed, "axeflesh")
    y = _buf(0.7, sr)
    th = dsp.thud(sr, r, dsp.vary(r, 85.0, 0.15), 0.3, contact_ms=dsp.vary(r, 4.0, 0.2), t60=0.06, noise=0.6,
                  noise_lp=1600.0, knock=0.8, knock_f=dsp.vary(r, 380.0, 0.2))
    dsp.place(y, th, 0, 1.0)
    dsp.place(y, dsp.normalize(_slice(sr, r, 0.04)), 0, 0.35)
    sq = dsp.squelch(sr, r, r.uniform(0.18, 0.28), dsp.vary(r, 2000.0, 0.2), dsp.vary(r, 450.0, 0.2), q=r.uniform(3.0, 6.0),
                     stick=0.7, bub=0.4)
    dsp.place(y, dsp.normalize(sq), dsp.ns(0.004, sr), 0.55)
    if variant % 2 == 0:   # through bone
        bc = dsp.crack(sr, r, 0.2, n_clicks=int(r.integers(2, 5)), spread=0.012, body="wood_small",
                       body_f=dsp.vary(r, 1000.0, 0.2), body_amt=0.6, bright=3500.0, tail=0.3)
        dsp.place(y, dsp.lp(bc, sr, 5000.0), dsp.ns(0.006, sr), 0.45)
    ring = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 2100.0, 0.2), 0.2, contact_ms=0.4, t60=0.15, click=0.0)
    dsp.place(y, ring, 0, 0.04)
    # spatter
    k = dsp.ns(0.3, sr)
    sp = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.02, 0.2) * 400.0, 800.0, 5000.0, q=3.0, alpha=1.7)
    dsp.place(y, dsp.normalize(sp), dsp.ns(0.04, sr), 0.08)
    return _punch(y, sr, 0.8)


@sound("sfx/blunt_hit_flesh", variants=6, seed=2004, peak_db=HIT)
def blunt_hit_flesh(seed, variant, sr):
    """Club/fist into a body: meaty thump + skin/cloth smack + muffled squish (+ rib crunch on heavy hits)."""
    r = dsp.rng(seed, "blunt")
    heavy = variant >= 3
    y = _buf(0.45, sr)
    th = dsp.thud(sr, r, dsp.vary(r, 75.0 if heavy else 95.0, 0.12), 0.3, contact_ms=dsp.vary(r, 7.0 if heavy else 5.0, 0.2),
                  t60=0.04, noise=0.7, noise_lp=1800.0, knock=1.0, knock_f=dsp.vary(r, 420.0, 0.2))
    dsp.place(y, th, 0, 1.0)
    L = dsp.ns(0.035, sr)
    slap = dsp.band_noise(L, sr, r, 700.0, 7000.0) * dsp.env_ar(L, sr, 0.0005, dsp.vary(r, 0.022, 0.2))
    dsp.place(y, dsp.normalize(slap), 0, 0.6)
    smack = dsp.crack(sr, r, 0.06, n_clicks=2, spread=0.003, body="soft", body_f=dsp.vary(r, 650.0, 0.2), body_amt=0.4,
                      bright=2500.0, tail=0.0)
    dsp.place(y, smack, 0, 0.3)
    sq = dsp.squelch(sr, r, 0.12, 1600.0, 500.0, q=3.0, stick=0.5, bub=0.1)
    dsp.place(y, dsp.normalize(sq), dsp.ns(0.003, sr), 0.22)
    if heavy and r.random() < 0.7:
        bc = dsp.crack(sr, r, 0.15, n_clicks=3, spread=0.01, body="wood_small", body_f=dsp.vary(r, 800.0, 0.2), tail=0.2)
        dsp.place(y, dsp.lp(bc, sr, 3500.0), dsp.ns(0.004, sr), 0.3)
    return _punch(dsp.hp(y, sr, 55.0), sr, 0.8)


@sound("sfx/blade_hit_flesh", variants=6, seed=2005, peak_db=-3.0)
def blade_hit_flesh(seed, variant, sr):
    r = dsp.rng(seed, "blade")
    y = _buf(0.45, sr)
    w = dsp.whoosh(sr, 0.12, r, peak_t=0.75, width=0.25, f_lo=600.0, f_hi=3200.0, q=1.6)
    dsp.place(y, dsp.normalize(w), 0, 0.3)
    hit = dsp.ns(0.075, sr)
    dsp.place(y, dsp.normalize(_slice(sr, r, r.uniform(0.05, 0.09), 1800.0, 11000.0)), hit, 0.75)
    sq = dsp.squelch(sr, r, r.uniform(0.12, 0.2), dsp.vary(r, 3000.0, 0.2), dsp.vary(r, 900.0, 0.2), q=4.0, stick=0.9,
                     bub=0.3)
    dsp.place(y, dsp.normalize(sq), hit + dsp.ns(0.004, sr), 0.6)
    th = dsp.thud(sr, r, dsp.vary(r, 130.0, 0.15), 0.15, contact_ms=3.0, t60=0.04, noise=0.5, knock=0.5, knock_f=500.0)
    dsp.place(y, th, hit, 0.45)
    return y


@sound("sfx/spear_stab", variants=4, seed=2006, peak_db=-3.0)
def spear_stab(seed, variant, sr):
    r = dsp.rng(seed, "spear")
    y = _buf(0.75, sr)
    w = dsp.whoosh(sr, 0.16, r, peak_t=0.8, width=0.3, f_lo=300.0, f_hi=1700.0, q=1.4)
    dsp.place(y, dsp.normalize(w), 0, 0.35)
    hit = dsp.ns(0.13, sr)
    th = dsp.thud(sr, r, dsp.vary(r, 95.0, 0.15), 0.25, contact_ms=3.0, t60=0.05, noise=0.6, noise_lp=2000.0, knock=0.7,
                  knock_f=dsp.vary(r, 420.0, 0.2))
    dsp.place(y, th, hit, 1.0)
    dsp.place(y, dsp.normalize(_slice(sr, r, 0.03, 2000.0, 8000.0)), hit, 0.3)
    sq = dsp.squelch(sr, r, r.uniform(0.15, 0.22), dsp.vary(r, 1800.0, 0.2), dsp.vary(r, 500.0, 0.2), q=5.0, stick=0.8,
                     bub=0.4)
    dsp.place(y, dsp.normalize(sq), hit + dsp.ns(0.006, sr), 0.6)
    shaft = dsp.impact(sr, r, "wood", dsp.vary(r, 320.0, 0.2), 0.25, contact_ms=0.8, t60=0.12, click=0.1)
    dsp.place(y, shaft, hit, 0.25)
    if variant % 2 == 1:   # wrench it back out
        out = dsp.squelch(sr, r, 0.2, 500.0, 1700.0, q=4.0, stick=1.0, bub=0.6, attack=0.04)
        dsp.place(y, dsp.normalize(out), hit + dsp.ns(r.uniform(0.25, 0.32), sr), 0.4)
    return _punch(y, sr, 0.8)


# ------------------------------------------------------------------------------------------- tool on material

@sound("sfx/hit_stone", variants=4, seed=2007, peak_db=HIT)
def hit_stone(seed, variant, sr):
    r = dsp.rng(seed, "stone")
    y = _buf(0.9, sr)
    crack = dsp.impact(sr, r, "stone", dsp.vary(r, 2600.0, 0.25), 0.15, contact_ms=0.18, t60=0.035, click=0.8,
                       click_hz=3500.0, noise=0.6)
    dsp.place(y, crack, 0, 0.9)
    body = dsp.impact(sr, r, "rock_big", dsp.vary(r, 420.0, 0.25), 0.3, contact_ms=0.5, t60=dsp.vary(r, 0.08, 0.2),
                      click=0.0, noise=0.4)
    dsp.place(y, body, 0, 0.75)
    dsp.place(y, dsp.thud(sr, r, 110.0, 0.2, contact_ms=2.0, t60=0.04, noise=0.4, noise_lp=2000.0), 0, 0.4)
    tool = dsp.impact(sr, r, "metal", dsp.vary(r, 1700.0, 0.25), 0.3, contact_ms=0.15, t60=dsp.vary(r, 0.18, 0.25),
                      click=0.0)
    dsp.place(y, tool, 0, r.uniform(0.08, 0.15))
    # flying chips & grit trickle
    t = r.uniform(0.04, 0.1)
    for _ in range(int(r.integers(3, 8))):
        ch = dsp.impact(sr, r, "stone", dsp.loguni(r, 2500.0, 6500.0), 0.05, contact_ms=0.15, t60=0.02, click=0.6)
        dsp.place(y, ch, dsp.ns(t, sr), r.uniform(0.03, 0.12))
        t += r.exponential(0.07)
    k = dsp.ns(0.5, sr)
    grit = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.03, 0.4) * 500.0, 2000.0, 9000.0, q=4.0, alpha=1.6)
    dsp.place(y, dsp.normalize(grit), dsp.ns(0.03, sr), 0.07)
    return _punch(y, sr, 0.55)


@sound("sfx/hit_metal", variants=4, seed=2008, peak_db=HIT)
def hit_metal(seed, variant, sr):
    """Tool against a metal object: 0 barrel/drum, 1 car panel, 2 pipe/post, 3 heavy plate."""
    r = dsp.rng(seed, "hitmetal")
    y = _buf(1.8, sr)
    if variant == 2:
        md = dsp.modes("pipe", dsp.vary(r, 520.0, 0.15), r, t60=1.4)
    elif variant == 1:
        md = dsp.modes("metal_sheet", dsp.vary(r, 170.0, 0.15), r, t60=0.7)
    else:
        md = dsp.modes("metal", dsp.vary(r, [190.0, 0, 0, 110.0][variant], 0.15), r, t60=[1.1, 0, 0, 0.9][variant])
    clang = dsp.impact(sr, r, modes_=md, contact_ms=0.3, noise=0.4, click=0.5, click_hz=3000.0, dur=1.8)
    dsp.place(y, clang, 0, 1.0)
    tool = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 1700.0, 0.2), 0.8, contact_ms=0.12, t60=0.5, click=0.0)
    dsp.place(y, tool, 0, 0.25)
    dsp.place(y, dsp.thud(sr, r, 140.0, 0.15, contact_ms=1.5, t60=0.03, noise=0.6, noise_lp=3000.0), 0, 0.35)
    if variant == 1:  # loose panel buzz
        n = len(y)
        buzz = 1.0 + 0.5 * np.sign(np.sin(dsp.TAU * dsp.phase(dsp.vary(r, 38.0, 0.2), n, sr))) * dsp.env_exp(n, sr, 0.4)
        y = y * buzz
    return _punch(y, sr, 0.85)


@sound("sfx/hit_wood_structure", variants=6, seed=2009, peak_db=HIT)
def hit_wood_structure(seed, variant, sr):
    """Weapon/tool against built wood (plank walls, crates, barricades): hollow panel boom, plank knock,
    loose-nail rattle, dust."""
    r = dsp.rng(seed, "woodstruct")
    y = _buf(0.9, sr)
    panel = dsp.impact(sr, r, "wood_hollow", dsp.vary(r, 115.0, 0.2), 0.6, contact_ms=dsp.vary(r, 1.4, 0.25),
                       t60=dsp.vary(r, 0.28, 0.2), noise=0.4, click=0.0)
    dsp.place(y, panel, 0, 0.9)
    plank = dsp.impact(sr, r, "wood", dsp.vary(r, 340.0, 0.2), 0.3, contact_ms=0.6, t60=0.12, click=0.5, click_hz=2500.0)
    dsp.place(y, plank, 0, 0.7)
    dsp.place(y, dsp.thud(sr, r, 90.0, 0.2, contact_ms=3.0, t60=0.05, noise=0.4, knock=0.5, knock_f=250.0), 0, 0.5)
    t = r.uniform(0.008, 0.02)
    for _ in range(int(r.integers(1, 4))):
        nail = dsp.impact(sr, r, "metal_bar", dsp.loguni(r, 1800.0, 3500.0), 0.2, contact_ms=0.2, t60=0.12, click=0.3)
        dsp.place(y, nail, dsp.ns(t, sr), r.uniform(0.04, 0.12))
        rattle = dsp.impact(sr, r, "wood", dsp.vary(r, 500.0, 0.3), 0.1, contact_ms=0.4, t60=0.06, click=0.3)
        dsp.place(y, rattle, dsp.ns(t + 0.003, sr), r.uniform(0.1, 0.25))
        t += r.uniform(0.02, 0.05)
    k = dsp.ns(0.5, sr)
    dust = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.05, 0.35) * 300.0, 1500.0, 7000.0, q=2.0, alpha=1.8)
    dsp.place(y, dsp.normalize(dust), dsp.ns(0.04, sr), 0.05)
    return _punch(y, sr, 0.8)


# ------------------------------------------------------------------------------------------- gore

@sound("sfx/gore_squelch", variants=4, seed=2010, peak_db=MID)
def gore_squelch(seed, variant, sr):
    r = dsp.rng(seed, "gore")
    dur = r.uniform(0.7, 0.95)
    y = _buf(dur, sr)
    t = 0.0
    for i in range(int(r.integers(2, 4))):
        d = r.uniform(0.15, 0.32)
        up = r.random() < 0.4
        f0, f1 = (dsp.vary(r, 500.0, 0.3), dsp.vary(r, 1800.0, 0.3)) if up else (dsp.vary(r, 2200.0, 0.3), dsp.vary(r, 420.0, 0.3))
        sq = dsp.squelch(sr, r, d, f0, f1, q=r.uniform(4.0, 9.0), stick=r.uniform(0.6, 1.2), bub=r.uniform(0.3, 0.7),
                         attack=r.uniform(0.003, 0.03))
        dsp.place(y, dsp.normalize(sq), dsp.ns(t, sr), 1.0 if i == 0 else r.uniform(0.5, 0.85))
        t += r.uniform(0.12, 0.25)
    n = len(y)
    slosh = dsp.lp(dsp.brown(n, r), sr, 350.0) * dsp.env_ar(n, sr, 0.02, dur * 0.7)
    y += 0.3 * dsp.normalize(slosh)
    return y


@sound("sfx/bone_crack", variants=4, seed=2011, peak_db=HIT)
def bone_crack(seed, variant, sr):
    r = dsp.rng(seed, "bone")
    y = _buf(0.45, sr)
    cr = dsp.crack(sr, r, 0.3, n_clicks=int(r.integers(3, 7)), spread=r.uniform(0.012, 0.04), body="wood_small",
                   body_f=dsp.vary(r, 1100.0, 0.25), body_amt=0.7, bright=dsp.vary(r, 3800.0, 0.2), tail=0.45,
                   tail_rate=600.0)
    dsp.place(y, dsp.lp(cr, sr, 6500.0), 0, 1.0)
    k = dsp.ns(0.08, sr)
    crunch = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.002, 0.06) * 3000.0, 700.0, 4500.0, q=2.0, alpha=1.5)
    dsp.place(y, dsp.normalize(crunch), 0, 0.4)
    dsp.place(y, dsp.thud(sr, r, 120.0, 0.15, contact_ms=4.0, t60=0.04, noise=0.5, knock=0.6, knock_f=350.0), 0, 0.45)
    sq = dsp.squelch(sr, r, 0.12, 1400.0, 500.0, q=3.0, stick=0.6, bub=0.2)
    dsp.place(y, dsp.normalize(sq), dsp.ns(0.01, sr), 0.15)
    return _punch(y, sr, 0.8)


@sound("sfx/limb_sever", variants=3, seed=2012, peak_db=HIT)
def limb_sever(seed, variant, sr):
    r = dsp.rng(seed, "sever")
    y = _buf(1.4, sr)
    th = dsp.thud(sr, r, dsp.vary(r, 80.0, 0.1), 0.3, contact_ms=4.0, t60=0.06, noise=0.6, noise_lp=1500.0, knock=0.8,
                  knock_f=360.0)
    dsp.place(y, th, 0, 1.0)
    dsp.place(y, dsp.normalize(_slice(sr, r, 0.05)), 0, 0.4)
    bc = dsp.crack(sr, r, 0.25, n_clicks=int(r.integers(3, 6)), spread=0.02, body="wood_small", body_f=dsp.vary(r, 950.0, 0.2),
                   body_amt=0.6, tail=0.4)
    dsp.place(y, dsp.lp(bc, sr, 5500.0), dsp.ns(0.008, sr), 0.6)
    td = r.uniform(0.25, 0.4)
    tr = dsp.tear(sr, td, r, [(0, 1.0), (td * 0.5, 0.7), (td, 0.0)], f_lo=400.0, f_hi=5000.0, wet=0.8, rate=1400.0)
    dsp.place(y, dsp.normalize(tr), dsp.ns(0.03, sr), 0.45)
    # limb hits the ground
    tf = r.uniform(0.5, 0.7)
    dsp.place(y, dsp.thud(sr, r, 95.0, 0.3, contact_ms=10.0, t60=0.05, noise=0.5, knock=0.4, knock_f=280.0), dsp.ns(tf, sr), 0.55)
    dsp.place(y, dsp.normalize(dsp.squelch(sr, r, 0.15, 1300.0, 400.0, 4.0, 0.8, 0.3)), dsp.ns(tf + 0.005, sr), 0.25)
    k = dsp.ns(0.5, sr)
    spl = dsp.clicks(k, sr, r, dsp.env_ar(k, sr, 0.03, 0.4) * 500.0, 900.0, 5000.0, q=3.0, alpha=1.7)
    dsp.place(y, dsp.normalize(spl), dsp.ns(0.08, sr), 0.1)
    return _punch(y, sr, 0.7)


@sound("sfx/body_fall", variants=4, seed=2013, peak_db=-2.1)
def body_fall(seed, variant, sr):
    """Body collapsing: knees, torso slam, arm/head flop, gear rattle, cloth and ground debris."""
    r = dsp.rng(seed, "bodyfall")
    dur = 1.3
    y = _buf(dur, sr)
    t_knee = 0.0
    t_torso = r.uniform(0.22, 0.38)
    t_arm = t_torso + r.uniform(0.08, 0.2)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 85.0, 0.1), 0.3, contact_ms=12.0, t60=0.05, noise=0.5, knock=0.4,
                          knock_f=300.0), dsp.ns(t_knee, sr), 0.55)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 62.0, 0.1), 0.4, contact_ms=18.0, t60=0.07, noise=0.6, noise_lp=700.0,
                          knock=0.5, knock_f=220.0), dsp.ns(t_torso, sr), 1.0)
    dsp.place(y, dsp.thud(sr, r, dsp.vary(r, 110.0, 0.1), 0.2, contact_ms=8.0, t60=0.04, noise=0.5, knock=0.5,
                          knock_f=400.0), dsp.ns(t_arm, sr), 0.4)
    n = len(y)
    env = np.zeros(n)
    for t, a in ((t_knee, 0.5), (t_torso, 1.0), (t_arm, 0.4)):
        k = dsp.ns(t, sr)
        env[k:] += a * dsp.env_ar(n - k, sr, 0.004, 0.25)
    ground = dsp.clicks(n, sr, r, env * 1400.0, 700.0, 7000.0, q=1.8, alpha=1.7)
    leaves = dsp.rustle(sr, dur, r, np.minimum(env, 1.0), f_lo=1500.0, f_hi=9000.0, density=900.0)
    y += 0.25 * dsp.normalize(ground) + 0.15 * dsp.normalize(leaves)
    clo = dsp.cloth(sr, dur, r, [(0, 0.3), (t_torso, 1.0), (t_torso + 0.4, 0.2), (dur, 0.0)], heavy=0.7)
    y += 0.15 * dsp.normalize(clo)
    if variant % 2 == 0:
        for _ in range(int(r.integers(2, 4))):
            ck = dsp.impact(sr, r, "metal", dsp.loguni(r, 1500.0, 3200.0), 0.15, contact_ms=0.25, t60=0.08, click=0.3)
            dsp.place(y, ck, dsp.ns(t_torso + r.uniform(0.0, 0.15), sr), r.uniform(0.05, 0.12))
    return y
