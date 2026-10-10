"""The new-game intro's crash (ADR-0064, TD-379): Lift 3 going into the trees short of the drop.

sfx/lift3_crash   the impact card's one sound, cut in on its white flash: the airframe hits the
                  canopy (a deep body blow and torn sheet metal); the rotor, still under power,
                  chops into the trunks, its blade strikes coming slower as it is beaten down; the
                  trees it cuts snap and fall; the turbine, its load gone, shrieks and winds down
                  through its whole range, coughing (compressor stalls) as it goes; then the
                  debris settles and the hull groans. About six seconds: the tail runs under the
                  next radio card ("Lift Three, Control.").
sfx/lift3_engine_failure   the bed under the last radio call (IntroPlayer's card `bed`, from
                  "Losing number two"): engine two stalls and runs down while engine one strains,
                  the rotor droops, the caution chime and then the low-rotor horn sound, and the
                  wind rises as the Lift sinks. Ten seconds with no end of its own: the impact
                  card cuts it.
Dry and mono: the intro plays it flat (Audio.play_2d)."""
from __future__ import annotations

import numpy as np

from .. import dsp
from ..registry import sound

DUR = 6.2


def _turbine(n: int, sr: int, r: np.random.Generator) -> np.ndarray:
    """The turbine spooling down: a whine falling from ~2.4 kHz to ~140 Hz over five seconds, with
    its shaft harmonics, a rough surge, and two compressor stalls (sharp pops with a cough)."""
    t = np.arange(n) / sr
    f = 140.0 + (2400.0 - 140.0) * np.exp(-t / 1.25)
    surge = 1.0 + 0.035 * dsp.smooth_noise(n, sr, r, 6.0) + 0.012 * dsp.smooth_noise(n, sr, r, 40.0)
    f = f * surge
    ph = 2.0 * np.pi * np.cumsum(f) / sr
    whine = np.sin(ph) + 0.45 * np.sin(2.0 * ph + 0.3) + 0.15 * np.sin(3.0 * ph + 1.1) + 0.05 * np.sin(5.0 * ph)
    # A damaged spool: the whine flutters (a bent blade's once-per-rev beat) rather than singing clean.
    whine *= 1.0 + 0.35 * np.sin(ph / 7.0) * dsp.smooth_noise(n, sr, r, 3.0)
    # Rough burning: the combustor's roar, band-limited noise that falls with the shaft.
    roar = dsp.band_noise(n, sr, r, 120.0, 3200.0, slope_db_oct=-3.0)
    level = np.exp(-t / 1.6) * (0.85 + 0.15 * dsp.smooth_noise(n, sr, r, 9.0))
    y = 0.55 * dsp.normalize(whine) * level + 0.45 * dsp.normalize(roar) * np.exp(-t / 1.4)
    for at in (0.55 + r.uniform(-0.05, 0.05), 1.7 + r.uniform(-0.1, 0.1)):
        pop = dsp.thud(sr, r, f=dsp.vary(r, 70.0, 0.1), dur=0.5, contact_ms=3.0, t60=0.12, noise=0.9, noise_lp=2500.0)
        cough = dsp.band_noise(dsp.ns(0.35, sr), sr, r, 200.0, 2500.0) * dsp.env_ar(dsp.ns(0.35, sr), sr, 0.004, 0.25)
        dsp.place(y, pop, dsp.ns(at, sr), 0.9 * np.exp(-at / 2.5))
        dsp.place(y, cough, dsp.ns(at + 0.01, sr), 0.5 * np.exp(-at / 2.5))
    return y


def _blade_strikes(n: int, sr: int, r: np.random.Generator) -> np.ndarray:
    """The rotor chopping into the trunks: a wood crack and a steel ring a strike, the interval
    stretching from 70 ms to 300 ms as the blades are beaten down, softer as they shatter."""
    y = np.zeros(n)
    at = 0.04
    gap = 0.07
    while at < 2.3:
        g = np.exp(-at / 0.9) * dsp.vary(r, 1.0, 0.25)
        wood = dsp.crack(sr, r, dur=0.3, n_clicks=4, spread=0.012, body_f=dsp.vary(r, 420.0, 0.3), body_amt=0.8, tail=0.3)
        steel = dsp.impact(sr, r, "metal_bar", dsp.vary(r, 340.0, 0.2), 0.45, contact_ms=0.4, t60=0.35, click=0.4,
                           click_hz=2600.0)
        dsp.place(y, wood, dsp.ns(at, sr), g)
        dsp.place(y, steel, dsp.ns(at + 0.003, sr), 0.45 * g)
        at += gap * dsp.vary(r, 1.0, 0.12)
        gap = min(0.3, gap * 1.17)
    return y


def _airframe(n: int, sr: int, r: np.random.Generator) -> np.ndarray:
    """The hull into the canopy and the ground: a deep body blow, sheet metal crumpling and tearing,
    loose panels clattering down after."""
    y = np.zeros(n)
    blow = dsp.thud(sr, r, f=38.0, dur=2.0, contact_ms=22.0, t60=0.6, noise=1.0, noise_lp=500.0, force=1.0)
    dsp.place(y, blow, 0, 1.0)
    second = dsp.thud(sr, r, f=52.0, dur=1.4, contact_ms=15.0, t60=0.4, noise=0.8, noise_lp=700.0)
    dsp.place(y, second, dsp.ns(0.62, sr), 0.7)
    rumble = dsp.lp(dsp.brown(dsp.ns(2.5, sr), r, sr), sr, 300.0) * dsp.env_ar(dsp.ns(2.5, sr), sr, 0.005, 1.6)
    dsp.place(y, dsp.normalize(rumble), 0, 0.6)
    # Crumpling skin: a burst of sheet-metal impacts over the first half second.
    for _ in range(14):
        at = abs(r.normal(0.0, 0.22))
        hit = dsp.impact(sr, r, "metal_sheet", dsp.loguni(r, 110.0, 520.0), 0.9, contact_ms=dsp.vary(r, 1.2, 0.4),
                         t60=dsp.vary(r, 0.5, 0.3), noise=0.4)
        dsp.place(y, hit, dsp.ns(at, sr), dsp.vary(r, 0.35, 0.4) * np.exp(-at / 0.8))
    rip = dsp.tear(sr, 1.4, r, [(0.0, 0.0), (0.05, 1.0), (0.5, 0.7), (1.4, 0.0)], f_lo=700.0, f_hi=7000.0, rate=900.0)
    rip = rip + 0.6 * dsp.bp(rip, sr, 1900.0, 3.0)
    dsp.place(y, dsp.normalize(rip), dsp.ns(0.08, sr), 0.4)
    # Panels and parts clattering down, fewer and quieter.
    for at in np.sort(r.uniform(0.9, 5.0, 11)):
        part = dsp.impact(sr, r, dsp.pick(r, ["metal_sheet", "metal_bar"]), dsp.loguni(r, 250.0, 900.0), 0.6,
                          contact_ms=0.8, t60=dsp.vary(r, 0.4, 0.3), click=0.3)
        dsp.place(y, part, dsp.ns(at, sr), 0.22 * np.exp(-(at - 0.9) / 2.2) * dsp.vary(r, 1.0, 0.4))
    return y


def _trees(n: int, sr: int, r: np.random.Generator) -> np.ndarray:
    """Trunks the rotor and the hull cut through: big snaps, then their crowns crashing down."""
    y = np.zeros(n)
    for at in (0.12, 0.48, 1.05, 1.9):
        at = at + r.uniform(-0.04, 0.04)
        snap = dsp.crack(sr, r, dur=0.7, n_clicks=7, spread=0.05, body_f=dsp.vary(r, 260.0, 0.2), body_amt=0.9,
                         tail=0.6, tail_rate=500.0)
        dsp.place(y, snap, dsp.ns(at, sr), 0.8 * np.exp(-at / 2.4))
        fall_at = at + dsp.vary(r, 0.9, 0.2)
        crown = dsp.rustle(sr, 1.3, r, [(0.0, 0.0), (0.15, 1.0), (1.3, 0.0)], f_lo=500.0, f_hi=6000.0, density=1800.0)
        dsp.place(y, dsp.normalize(crown), dsp.ns(fall_at, sr), 0.3 * np.exp(-at / 2.4))
        land = dsp.thud(sr, r, f=dsp.vary(r, 60.0, 0.15), dur=0.6, contact_ms=12.0, t60=0.15, noise=0.7)
        dsp.place(y, land, dsp.ns(fall_at + 0.5, sr), 0.4 * np.exp(-at / 2.4))
    return y


def _settle(n: int, sr: int, r: np.random.Generator) -> np.ndarray:
    """The wreck settling: the hull's long groan under its own weight, and a last tick of debris."""
    y = np.zeros(n)
    groan = dsp.creak(sr, 2.2, r, [(0.0, 40.0), (1.2, 90.0), (2.2, 25.0)], [(0.0, 0.0), (0.3, 1.0), (2.2, 0.0)],
                      res=[(dsp.vary(r, 180.0, 0.1), 7.0, 1.0), (dsp.vary(r, 390.0, 0.1), 9.0, 0.6),
                           (dsp.vary(r, 820.0, 0.1), 11.0, 0.35)], bright=2500.0)
    dsp.place(y, dsp.normalize(groan), dsp.ns(3.4, sr), 0.28)
    tick = dsp.impact(sr, r, "metal_sheet", 700.0, 0.4, contact_ms=0.5, t60=0.3)
    dsp.place(y, tick, dsp.ns(5.3, sr), 0.12)
    return y


@sound("sfx/lift3_crash", seed=18101, peak_db=-1.0)
def lift3_crash(seed, variant, sr):
    r = dsp.rng(seed)
    n = dsp.ns(DUR, sr)
    y = (0.95 * dsp.normalize(_airframe(n, sr, r))
         + 0.7 * dsp.normalize(_blade_strikes(n, sr, r))
         + 0.55 * dsp.normalize(_turbine(n, sr, r))
         + 0.55 * dsp.normalize(_trees(n, sr, r))
         + _settle(n, sr, r))
    # Heard through the drop bay's floor and a headset: the very top is dulled.
    y = dsp.lp(y, sr, 9000.0)
    return dsp.peq(y, sr, 60.0, 3.0, 0.9)


BED_DUR = 10.0


def _rotor_chop(n: int, sr: int, r: np.random.Generator, f_bp: np.ndarray) -> np.ndarray:
    """The rotor heard from the cabin: air-wash noise chopped at the blade pass (f_bp per sample),
    with the blade-pass tone itself under it."""
    ph = 2.0 * np.pi * np.cumsum(f_bp) / sr
    chop = np.abs(np.sin(0.5 * ph)) ** 8
    wash = dsp.band_noise(n, sr, r, 70.0, 1800.0, slope_db_oct=-3.0)
    tone = np.sin(ph) + 0.5 * np.sin(2.0 * ph + 0.4) + 0.25 * np.sin(3.0 * ph + 1.0)
    return 0.6 * dsp.normalize(wash * (0.3 + chop)) + 0.4 * dsp.normalize(tone)


@sound("sfx/lift3_engine_failure", seed=18102, peak_db=-2.0)
def lift3_engine_failure(seed, variant, sr):
    """Under the last radio call: engine two dies, engine one strains on, the rotor droops, the
    caution tone and then the low-rotor horn sound, and the wind rises as the Lift sinks. No
    natural end: the impact card cuts it (IntroPlayer's bed); its last seconds hold at full
    distress in case the call types slowly."""
    r = dsp.rng(seed)
    n = dsp.ns(BED_DUR, sr)
    t = np.arange(n) / sr
    # Rotor: ~17 Hz blade pass at cruise, drooping to ~12.5 Hz as one engine can't hold it.
    f_bp = 17.0 - 4.5 * dsp.smoothstep(np.clip(t / 6.0, 0.0, 1.0)) + 0.25 * dsp.smooth_noise(n, sr, r, 1.5)
    rotor = _rotor_chop(n, sr, r, f_bp)
    # Engine one: a steady turbine whine, straining higher and rougher as it takes the load.
    f1 = 1650.0 + 140.0 * dsp.smoothstep(np.clip((t - 0.6) / 3.0, 0.0, 1.0)) + 18.0 * dsp.smooth_noise(n, sr, r, 5.0)
    p1 = 2.0 * np.pi * np.cumsum(f1) / sr
    eng1 = (np.sin(p1) + 0.3 * np.sin(2.0 * p1)) * (1.0 + 0.25 * dsp.smoothstep(np.clip((t - 0.6) / 3.0, 0.0, 1.0)) * dsp.smooth_noise(n, sr, r, 22.0))
    # Engine two: in tune with one at first, then surging and running down (its stalls are pops).
    fail_at = 0.35
    k2 = np.clip((t - fail_at) / 3.2, 0.0, 1.0)
    f2 = 1640.0 * (1.0 - 0.82 * k2 ** 0.7) * (1.0 + 0.05 * dsp.smooth_noise(n, sr, r, 3.0) * (k2 > 0))
    p2 = 2.0 * np.pi * np.cumsum(f2) / sr
    eng2 = (np.sin(p2) + 0.35 * np.sin(2.0 * p2 + 0.5)) * (1.0 - dsp.smoothstep(np.clip((t - 2.4) / 1.6, 0.0, 1.0)))
    y = 0.55 * rotor + 0.16 * dsp.normalize(eng1) + 0.16 * dsp.normalize(eng2)
    for at in (fail_at + 0.05, fail_at + 0.9 + r.uniform(-0.1, 0.1), fail_at + 1.7 + r.uniform(-0.1, 0.1)):
        pop = dsp.thud(sr, r, f=dsp.vary(r, 75.0, 0.1), dur=0.45, contact_ms=2.5, t60=0.1, noise=1.0, noise_lp=2600.0)
        dsp.place(y, pop, dsp.ns(at, sr), 0.55)
    # Master caution: a two-tone chime every 0.9 s from just after the failure.
    chime_n = dsp.ns(0.32, sr)
    chime = np.zeros(chime_n)
    half = chime_n // 2
    tc = np.arange(chime_n) / sr
    chime[:half] = np.sign(np.sin(2.0 * np.pi * 880.0 * tc[:half])) * 0.6 + np.sin(2.0 * np.pi * 880.0 * tc[:half])
    chime[half:] = np.sign(np.sin(2.0 * np.pi * 660.0 * tc[half:])) * 0.6 + np.sin(2.0 * np.pi * 660.0 * tc[half:])
    chime = dsp.lp(chime, sr, 3000.0) * dsp.env_ar(chime_n, sr, 0.004, 1.0)
    at = fail_at + 0.4
    while at < 4.2:
        dsp.place(y, dsp.normalize(chime), dsp.ns(at, sr), 0.16)
        at += 0.9
    # Low rotor RPM: a continuous warbling horn once the rotor has drooped.
    horn_f = 600.0 + 60.0 * np.sign(np.sin(2.0 * np.pi * 4.0 * t))
    horn = np.sign(np.sin(2.0 * np.pi * np.cumsum(horn_f) / sr)) * 0.5 + np.sin(2.0 * np.pi * np.cumsum(horn_f) / sr)
    horn = dsp.lp(horn, sr, 2500.0) * dsp.smoothstep(np.clip((t - 4.2) / 0.15, 0.0, 1.0))
    y += 0.12 * dsp.normalize(horn)
    # Sinking: the wind over the hull rises, and the airframe shudders at two per rev.
    wind = dsp.band_noise(n, sr, r, 150.0, 5000.0, slope_db_oct=-2.0) * (0.15 + 0.85 * dsp.smoothstep(np.clip((t - 1.5) / 6.0, 0.0, 1.0)))
    wind *= 1.0 + 0.3 * dsp.smooth_noise(n, sr, r, 2.0)
    shudder = dsp.lp(dsp.brown(n, r, sr), sr, 90.0) * (1.0 + np.sin(2.0 * np.pi * np.cumsum(f_bp * 2.0) / sr)) * dsp.smoothstep(np.clip((t - 2.0) / 4.0, 0.0, 1.0))
    y += 0.3 * dsp.normalize(wind) + 0.25 * dsp.normalize(shudder)
    # Heard from inside the cabin: the top end dulled, the low end full.
    y = dsp.lp(y, sr, 7000.0)
    return dsp.lshelf(y, sr, 150.0, 3.0)
