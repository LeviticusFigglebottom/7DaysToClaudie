"""Hollowmere procedural audio toolkit (numpy + scipy). Every sound in the game is synthesized here.

Contract with audio/catalog.py
    finish(sig, sr, peak_db=-1.0, loop=False) -> float32, (N,) mono or (N, 2) stereo
    write_wav(path, sig, sr)                  -> 16-bit PCM WAV (mono or stereo)

Conventions
    * Processing is float64; mono = shape (N,), stereo = shape (N, 2). Generators return roughly
      [-1, 1]; finish() removes DC, trims/fades one-shots, makes loop seams continuous and
      peak-normalizes to `peak_db` (per-family loudness is chosen with @sound(peak_db=...)).
    * Determinism: every random draw goes through rng(seed, *salt). No clocks, no global RNG.
    * "Curve" parameters accept a scalar, a per-sample array or [(t_sec, value), ...] breakpoints
      (see curve()). Times are seconds, frequencies Hz, levels linear unless named *_db.
    * One-shot SFX are generated dry (the game adds interior/cave reverb buses at runtime); big
      outdoor events and ambience beds bake their own space with reverb().

Sections
    RNG & utils . curves & envelopes . oscillators . noise . filters (static, time-varying, FFT) .
    resonators & modal synthesis . impulses & granular . physical recipes (impact, crack, creak,
    scrape, rustle, whoosh, thud, liquids, fire) . voice (glottal source + formant cascade, breath) .
    nonlinear & dynamics . modulation & time . stereo . reverb (synthetic IRs) . loops . finish/write
"""
from __future__ import annotations

import math
import pathlib
import wave

import numpy as np
from scipy import fft as _sfft
from scipy import ndimage as _nd
from scipy import signal as _ss

SR = 44100
TAU = 2.0 * math.pi
LN1000 = math.log(1000.0)  # exp(-LN1000 * t / t60) reaches -60 dB at t = t60


# =====================================================================================================
# RNG & small utilities
# =====================================================================================================

def _fnv64(s: str) -> int:
    h = 0xCBF29CE484222325
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def rng(seed: int, *salt) -> np.random.Generator:
    """Deterministic numpy Generator. `salt` (ints or strings) derives independent sub-streams:
    rng(seed, "grains") and rng(seed, "tail") never share draws."""
    s = int(seed) & 0xFFFFFFFFFFFFFFFF
    words = [s & 0xFFFFFFFF, s >> 32]
    for x in salt:
        v = _fnv64(x) if isinstance(x, str) else int(x) & 0xFFFFFFFFFFFFFFFF
        words += [v & 0xFFFFFFFF, v >> 32]
    return np.random.default_rng(np.random.SeedSequence(words))


def vary(r: np.random.Generator, x: float, pct: float) -> float:
    """x scaled by a uniform random factor in [1 - pct, 1 + pct]."""
    return float(x) * (1.0 + float(r.uniform(-pct, pct)))


def loguni(r: np.random.Generator, lo: float, hi: float, size=None):
    """Log-uniform draw(s) in [lo, hi] (frequencies, sizes)."""
    return np.exp(r.uniform(math.log(lo), math.log(hi), size))


def pick(r: np.random.Generator, seq):
    return seq[int(r.integers(len(seq)))]


def cents(c) -> float | np.ndarray:
    return 2.0 ** (np.asarray(c, dtype=np.float64) / 1200.0)


def semis(s) -> float | np.ndarray:
    return 2.0 ** (np.asarray(s, dtype=np.float64) / 12.0)


def midi_hz(m) -> float | np.ndarray:
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def ns(sec: float, sr: int = SR) -> int:
    """Seconds -> sample count."""
    return max(0, int(round(float(sec) * sr)))


def tvec(n: int, sr: int = SR) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / sr


def undb(d) -> float | np.ndarray:
    return 10.0 ** (np.asarray(d, dtype=np.float64) / 20.0)


def todb(x) -> float | np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(np.asarray(x, dtype=np.float64)), 1e-12))


def peak(x) -> float:
    x = np.asarray(x)
    return float(np.max(np.abs(x))) if x.size else 0.0


def rms(x) -> float:
    x = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


def normalize(x, level: float = 1.0) -> np.ndarray:
    p = peak(x)
    return np.asarray(x, dtype=np.float64) * (level / p) if p > 0 else np.asarray(x, dtype=np.float64)


def fit(x, n: int) -> np.ndarray:
    """Zero-pad or truncate along time to exactly n samples."""
    x = np.asarray(x, dtype=np.float64)
    if x.shape[0] >= n:
        return x[:n].copy()
    pad = [(0, n - x.shape[0])] + [(0, 0)] * (x.ndim - 1)
    return np.pad(x, pad)


def place(dst: np.ndarray, src, at: int, gain: float = 1.0) -> np.ndarray:
    """Adds src into dst starting at sample `at` (clipped to dst bounds, mono src into stereo dst ok)."""
    src = np.asarray(src, dtype=np.float64)
    n = dst.shape[0]
    s0 = 0
    if at < 0:
        s0, at = -at, 0
    if at >= n or s0 >= src.shape[0]:
        return dst
    m = min(src.shape[0] - s0, n - at)
    seg = src[s0:s0 + m] * gain
    if dst.ndim == 2 and seg.ndim == 1:
        seg = seg[:, None]
    dst[at:at + m] += seg
    return dst


def mix(n: int, sr: int, parts, stereo: bool = False) -> np.ndarray:
    """Sum of parts [(t_sec, signal, gain), ...] into a new buffer of n samples."""
    out = np.zeros((n, 2) if stereo else n)
    for t, s, g in parts:
        place(out, s, ns(t, sr), g)
    return out


def cat(*xs) -> np.ndarray:
    return np.concatenate([np.asarray(x, dtype=np.float64) for x in xs], axis=0)


def mono(x) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return x.mean(axis=1) if x.ndim == 2 else x


def _per_channel(fn, x, *a, **k):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        return np.stack([fn(x[:, c], *a, **k) for c in range(x.shape[1])], axis=1)
    return fn(x, *a, **k)


# =====================================================================================================
# Curves & envelopes
# =====================================================================================================

def smoothstep(x) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def curve(spec, n: int, sr: int = SR, kind: str = "linear") -> np.ndarray:
    """Control curve of n samples from a scalar, an array (resampled if its length differs) or
    breakpoints [(t_sec, value), ...]. kind: linear | smooth (smoothstep segments) | exp (geometric,
    values > 0) | step."""
    if np.isscalar(spec):
        return np.full(n, float(spec))
    if isinstance(spec, np.ndarray):
        a = spec.astype(np.float64)
        if a.shape[0] == n:
            return a
        if a.shape[0] == 1:
            return np.full(n, float(a[0]))
        return np.interp(np.linspace(0.0, a.shape[0] - 1.0, n), np.arange(a.shape[0]), a)
    pts = sorted(((float(t), float(v)) for t, v in spec), key=lambda p: p[0])
    ts = np.array([p[0] for p in pts])
    vs = np.array([p[1] for p in pts])
    t = np.arange(n) / sr
    if len(pts) == 1:
        return np.full(n, vs[0])
    if kind == "exp":
        return np.exp(np.interp(t, ts, np.log(np.maximum(vs, 1e-12))))
    if kind == "step":
        idx = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 1)
        return vs[idx]
    if kind == "smooth":
        idx = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2)
        t0, t1 = ts[idx], ts[idx + 1]
        f = smoothstep((t - t0) / np.maximum(t1 - t0, 1e-12))
        out = vs[idx] + (vs[idx + 1] - vs[idx]) * f
        out[t < ts[0]] = vs[0]
        out[t >= ts[-1]] = vs[-1]
        return out
    return np.interp(t, ts, vs)


def env_exp(n: int, sr: int, t60: float, delay: float = 0.0) -> np.ndarray:
    """Exponential decay reaching -60 dB after t60 seconds (flat 1.0 during `delay`)."""
    t = np.maximum(np.arange(n) / sr - delay, 0.0)
    return np.exp(-LN1000 * t / max(t60, 1e-6))


def env_ar(n: int, sr: int, attack: float, t60: float, hold: float = 0.0, power: float = 1.0) -> np.ndarray:
    """Raised-cosine attack, optional hold, exponential release (t60). power>1 sharpens the decay knee."""
    t = np.arange(n) / sr
    a = max(attack, 1e-5)
    rise = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / a, 0.0, 1.0))
    dec = np.exp(-LN1000 * np.maximum(t - a - hold, 0.0) / max(t60, 1e-6))
    return rise * dec ** power


def env_adsr(n: int, sr: int, a: float, d: float, s: float, rel: float, gate: float) -> np.ndarray:
    """Classic ADSR; `gate` = time the key is held (release starts there). Exponential segments."""
    t = np.arange(n) / sr
    e = np.zeros(n)
    att = t < a
    e[att] = 0.5 - 0.5 * np.cos(np.pi * t[att] / max(a, 1e-6))
    dec = (t >= a) & (t < gate)
    e[dec] = s + (1.0 - s) * np.exp(-5.0 * (t[dec] - a) / max(d, 1e-6))
    lvl = s + (1.0 - s) * math.exp(-5.0 * max(gate - a, 0.0) / max(d, 1e-6)) if gate > a else \
        0.5 - 0.5 * math.cos(math.pi * min(gate / max(a, 1e-6), 1.0))
    rl = t >= gate
    e[rl] = lvl * np.exp(-LN1000 * (t[rl] - gate) / max(rel, 1e-6))
    return e


def fade(x, sr: int, fin: float = 0.0, fout: float = 0.0) -> np.ndarray:
    """Raised-cosine fade in/out (seconds)."""
    x = np.array(x, dtype=np.float64, copy=True)
    n = x.shape[0]
    a, b = min(ns(fin, sr), n), min(ns(fout, sr), n)
    if a > 0:
        w = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
        x[:a] *= w if x.ndim == 1 else w[:, None]
    if b > 0:
        w = 0.5 + 0.5 * np.cos(np.pi * (np.arange(b) + 1) / b)
        x[n - b:] *= w if x.ndim == 1 else w[:, None]
    return x


def hann(n: int) -> np.ndarray:
    return 0.5 - 0.5 * np.cos(TAU * (np.arange(n) + 0.5) / n) if n > 0 else np.zeros(0)


# =====================================================================================================
# Oscillators
# =====================================================================================================

def phase(freq, n: int, sr: int = SR, phase0: float = 0.0) -> np.ndarray:
    """Running phase in cycles for a (possibly time-varying) frequency; phase[0] = phase0."""
    f = curve(freq, n, sr)
    ph = np.cumsum(f) / sr
    return ph - (ph[0] if n else 0.0) + phase0


def sine(freq, n: int, sr: int = SR, phase0: float = 0.0) -> np.ndarray:
    return np.sin(TAU * phase(freq, n, sr, phase0))


def _polyblep(p: np.ndarray, dt: np.ndarray) -> np.ndarray:
    out = np.zeros_like(p)
    m = p < dt
    t = p[m] / dt[m]
    out[m] = t + t - t * t - 1.0
    m = p > 1.0 - dt
    t = (p[m] - 1.0) / dt[m]
    out[m] = t * t + t + t + 1.0
    return out


def saw(freq, n: int, sr: int = SR, phase0: float = 0.0) -> np.ndarray:
    """PolyBLEP band-limited sawtooth (rising), amplitude ~[-1, 1]."""
    f = curve(freq, n, sr)
    p = np.mod(phase(f, n, sr, phase0), 1.0)
    dt = np.clip(f / sr, 1e-9, 0.5)
    return 2.0 * p - 1.0 - _polyblep(p, dt)


def square(freq, n: int, sr: int = SR, pw: float = 0.5, phase0: float = 0.0) -> np.ndarray:
    """PolyBLEP pulse wave with pulse width pw (difference of two saws)."""
    f = curve(freq, n, sr)
    ph = phase(f, n, sr, phase0)
    dt = np.clip(f / sr, 1e-9, 0.5)
    p1 = np.mod(ph, 1.0)
    p2 = np.mod(ph + pw, 1.0)
    s1 = 2.0 * p1 - 1.0 - _polyblep(p1, dt)
    s2 = 2.0 * p2 - 1.0 - _polyblep(p2, dt)
    return 0.5 * (s1 - s2)


def triangle(freq, n: int, sr: int = SR, phase0: float = 0.0) -> np.ndarray:
    p = np.mod(phase(freq, n, sr, phase0) + 0.25, 1.0)
    return 1.0 - 4.0 * np.abs(p - 0.5)


def fm(carrier, ratio, index, n: int, sr: int = SR, feedback: float = 0.0) -> np.ndarray:
    """2-operator FM: sin(2pi*phi_c + index * sin(2pi*phi_m)), modulator = carrier * ratio.
    `index` may be a curve (bright attack -> mellow decay)."""
    fc = curve(carrier, n, sr)
    pm = phase(fc * curve(ratio, n, sr), n, sr)
    mod = np.sin(TAU * pm)
    if feedback:
        mod = np.sin(TAU * pm + feedback * mod)
    return np.sin(TAU * phase(fc, n, sr) + curve(index, n, sr) * mod)


def partials(n: int, sr: int, freqs, amps, t60s=None, phases=None, attack: float = 0.0) -> np.ndarray:
    """Additive sum of (optionally decaying) sinusoids: amps[k] * sin(2pi f_k t + phi_k) * env_k."""
    freqs = np.asarray(freqs, dtype=np.float64)
    amps = np.asarray(amps, dtype=np.float64)
    keep = (freqs > 0) & (freqs < 0.48 * sr)
    freqs, amps = freqs[keep], amps[keep]
    t60s = None if t60s is None else np.asarray(t60s, dtype=np.float64)[keep]
    phases = np.zeros(len(freqs)) if phases is None else np.asarray(phases, dtype=np.float64)[keep]
    t = np.arange(n) / sr
    out = np.zeros(n)
    for i0 in range(0, len(freqs), 16):
        sl = slice(i0, i0 + 16)
        arg = TAU * freqs[sl, None] * t[None, :] + phases[sl, None]
        blk = np.sin(arg) * amps[sl, None]
        if t60s is not None:
            blk *= np.exp(-LN1000 * t[None, :] / np.maximum(t60s[sl, None], 1e-6))
        out += blk.sum(axis=0)
    if attack > 0:
        out *= 0.5 - 0.5 * np.cos(np.pi * np.clip(t / attack, 0.0, 1.0))
    return out


# =====================================================================================================
# Noise
# =====================================================================================================

def white(n: int, r: np.random.Generator) -> np.ndarray:
    return r.standard_normal(n)


def _spec_shape(n: int, r: np.random.Generator, gain_fn, sr: int = SR) -> np.ndarray:
    """Gaussian noise shaped in the frequency domain (periodic over n samples), unit RMS."""
    if n <= 1:
        return np.zeros(n)
    X = np.fft.rfft(r.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / sr)
    X *= gain_fn(np.maximum(f, 1e-3))
    X[0] = 0.0
    y = np.fft.irfft(X, n)
    s = np.std(y)
    return y / s if s > 0 else y


def colored(n: int, r: np.random.Generator, slope_db_oct: float, sr: int = SR, f_ref: float = 1000.0) -> np.ndarray:
    """Noise with a constant spectral slope (dB/octave): 0 white, -3 pink, -6 brown, +3 blue."""
    k = slope_db_oct / (20.0 * math.log10(2.0))
    lo = 10.0
    return _spec_shape(n, r, lambda f: (np.maximum(f, lo) / f_ref) ** k, sr)


def pink(n: int, r: np.random.Generator, sr: int = SR) -> np.ndarray:
    return colored(n, r, -3.0, sr)


def brown(n: int, r: np.random.Generator, sr: int = SR) -> np.ndarray:
    return colored(n, r, -6.0, sr)


def spectral_noise(n: int, sr: int, r: np.random.Generator, points) -> np.ndarray:
    """Noise with an arbitrary spectral envelope [(f_hz, db), ...] (log-frequency interpolation)."""
    fp = np.log2(np.array([max(p[0], 1.0) for p in points]))
    dp = np.array([p[1] for p in points], dtype=np.float64)
    return _spec_shape(n, r, lambda f: undb(np.interp(np.log2(f), fp, dp)), sr)


def band_noise(n: int, sr: int, r: np.random.Generator, lo: float, hi: float, slope_db_oct: float = 0.0,
               edge: float = 0.25) -> np.ndarray:
    """Band-limited noise between lo..hi Hz (soft raised-cosine edges `edge` octaves wide), unit RMS."""
    k = slope_db_oct / (20.0 * math.log10(2.0))

    def g(f):
        lf = np.log2(f)
        a = smoothstep((lf - (math.log2(lo) - edge)) / (2 * edge))
        b = 1.0 - smoothstep((lf - (math.log2(hi) - edge)) / (2 * edge))
        return a * b * (f / math.sqrt(lo * hi)) ** k
    return _spec_shape(n, r, g, sr)


def smooth_noise(n: int, sr: int, r: np.random.Generator, rate: float, periodic: bool = False) -> np.ndarray:
    """Smooth random control signal in about [-1, 1] with `rate` random knots per second (Catmull-Rom).
    periodic=True makes it loop exactly over n samples."""
    if n <= 0:
        return np.zeros(0)
    # evaluate the spline on a coarse grid (>= 48 points per knot) and interpolate: identical shape, far cheaper
    step = int(max(1, min(256, sr / max(rate, 1e-6) / 48.0)))
    m = (n + step - 1) // step + 1
    pos = np.arange(m) * step
    if periodic:
        k = max(2, int(round(n * rate / sr)))
        vals = r.uniform(-1.0, 1.0, k)
        u = pos * (k / n)
        i = np.floor(u).astype(np.int64)
        f = u - i
        p0, p1, p2, p3 = vals[(i - 1) % k], vals[i % k], vals[(i + 1) % k], vals[(i + 2) % k]
    else:
        k = int(n * rate / sr) + 4
        vals = r.uniform(-1.0, 1.0, k + 3 + int(step * rate / sr) + 2)
        u = pos * (rate / sr) + 1.0
        i = np.floor(u).astype(np.int64)
        f = u - i
        p0, p1, p2, p3 = vals[i - 1], vals[i], vals[i + 1], vals[i + 2]
    c = 0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
               + (-p0 + 3 * p1 - 3 * p2 + p3) * f * f * f)
    if step == 1:
        return c[:n]
    return np.interp(np.arange(n), pos, c)


def velvet(n: int, sr: int, r: np.random.Generator, density: float) -> np.ndarray:
    """Velvet noise: sparse random +-1 impulses, `density` per second (one per grid cell)."""
    out = np.zeros(n)
    step = max(1.0, sr / max(density, 1e-3))
    cells = int(n / step)
    if cells <= 0:
        return out
    pos = (np.arange(cells) * step + r.uniform(0, step, cells)).astype(np.int64)
    pos = pos[pos < n]
    out[pos] = r.choice((-1.0, 1.0), len(pos))
    return out


# =====================================================================================================
# Filters
# =====================================================================================================

def _rbj(kind: str, f, q, gain_db, sr: int):
    """RBJ cookbook biquads, vectorized over f/q/gain. kinds: lp hp bp(0 dB peak) notch ap peak ls hs."""
    f = np.clip(np.asarray(f, dtype=np.float64), 1.0, 0.4999 * sr)
    q = np.maximum(np.asarray(q, dtype=np.float64), 1e-4)
    A = 10.0 ** (np.asarray(gain_db, dtype=np.float64) / 40.0)
    w = TAU * f / sr
    c, s = np.cos(w), np.sin(w)
    al = s / (2.0 * q)
    one = np.ones_like(w)
    zero = np.zeros_like(w)
    if kind == "lp":
        b, a = ((1 - c) / 2, 1 - c, (1 - c) / 2), (1 + al, -2 * c, 1 - al)
    elif kind == "hp":
        b, a = ((1 + c) / 2, -(1 + c), (1 + c) / 2), (1 + al, -2 * c, 1 - al)
    elif kind == "bp":
        b, a = (al, zero, -al), (1 + al, -2 * c, 1 - al)
    elif kind == "notch":
        b, a = (one, -2 * c, one), (1 + al, -2 * c, 1 - al)
    elif kind == "ap":
        b, a = (1 - al, -2 * c, 1 + al), (1 + al, -2 * c, 1 - al)
    elif kind == "peak":
        b, a = (1 + al * A, -2 * c, 1 - al * A), (1 + al / A, -2 * c, 1 - al / A)
    elif kind == "ls":
        sq = 2 * np.sqrt(A) * al
        b = (A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq))
        a = ((A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq)
    elif kind == "hs":
        sq = 2 * np.sqrt(A) * al
        b = (A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq))
        a = ((A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq)
    else:
        raise ValueError(f"unknown biquad kind {kind}")
    b = np.stack(np.broadcast_arrays(*b), axis=-1)
    a = np.stack(np.broadcast_arrays(*a), axis=-1)
    return b / a[..., :1], a / a[..., :1]


def _is_const(spec) -> bool:
    return np.isscalar(spec) or (isinstance(spec, np.ndarray) and spec.size == 1)


def _tv_biquad(x: np.ndarray, sr: int, kind: str, f, q, g, block: int) -> np.ndarray:
    n = x.shape[0]
    nb = (n + block - 1) // block
    centers = np.minimum(np.arange(nb) * block + block // 2, n - 1)
    fv = curve(f, n, sr)[centers]
    qv = curve(q, n, sr)[centers]
    gv = curve(g, n, sr)[centers]
    B, A = _rbj(kind, fv, qv, gv, sr)
    y = np.empty_like(x)
    zi = np.zeros((2,) + x.shape[1:])
    for i in range(nb):
        s = i * block
        e = min(n, s + block)
        y[s:e], zi = _ss.lfilter(B[i], A[i], x[s:e], axis=0, zi=zi)
    return y


def biquad(x, sr: int, kind: str, f, q=0.7071, gain_db=0.0, block: int = 64) -> np.ndarray:
    """One RBJ biquad. If f/q/gain_db are curves (arrays/breakpoints) the filter is time-varying
    (coefficients updated every `block` samples, state carried across)."""
    x = np.asarray(x, dtype=np.float64)
    if x.shape[0] == 0:
        return x.copy()
    if _is_const(f) and _is_const(q) and _is_const(gain_db):
        b, a = _rbj(kind, float(np.asarray(f).ravel()[0]), float(np.asarray(q).ravel()[0]),
                    float(np.asarray(gain_db).ravel()[0]), sr)
        return _ss.lfilter(b, a, x, axis=0)
    return _tv_biquad(x, sr, kind, f, q, gain_db, block)


def _butter_qs(order: int) -> list[float]:
    k = order // 2
    return [1.0 / (2.0 * math.cos((2 * i - 1) * math.pi / (4 * k))) for i in range(1, k + 1)]


def lp(x, sr: int, f, q=0.7071, order: int = 2) -> np.ndarray:
    """Low-pass. order 1 = one-pole; 2 = biquad with q; 4/6/8 = Butterworth cascade (q ignored)."""
    if order == 1:
        return lp1(x, sr, f)
    if order == 2:
        return biquad(x, sr, "lp", f, q)
    y = np.asarray(x, dtype=np.float64)
    for qq in _butter_qs(order):
        y = biquad(y, sr, "lp", f, qq)
    return y


def hp(x, sr: int, f, q=0.7071, order: int = 2) -> np.ndarray:
    """High-pass (see lp for `order`)."""
    if order == 1:
        return hp1(x, sr, f)
    if order == 2:
        return biquad(x, sr, "hp", f, q)
    y = np.asarray(x, dtype=np.float64)
    for qq in _butter_qs(order):
        y = biquad(y, sr, "hp", f, qq)
    return y


def bp(x, sr: int, f, q=1.0) -> np.ndarray:
    """Band-pass, 0 dB at the centre frequency."""
    return biquad(x, sr, "bp", f, q)


def band(x, sr: int, lo, hi, order: int = 2) -> np.ndarray:
    """High-pass at lo then low-pass at hi (Butterworth of the given order)."""
    return lp(hp(x, sr, lo, order=order), sr, hi, order=order)


def notch(x, sr: int, f, q=4.0) -> np.ndarray:
    return biquad(x, sr, "notch", f, q)


def peq(x, sr: int, f, gain_db, q=1.0) -> np.ndarray:
    """Peaking EQ bell."""
    return biquad(x, sr, "peak", f, q, gain_db)


def lshelf(x, sr: int, f, gain_db, q=0.7071) -> np.ndarray:
    return biquad(x, sr, "ls", f, q, gain_db)


def hshelf(x, sr: int, f, gain_db, q=0.7071) -> np.ndarray:
    return biquad(x, sr, "hs", f, q, gain_db)


def eq(x, sr: int, *bands) -> np.ndarray:
    """Chain of bands: ("peak", f, gain_db, q) | ("ls"/"hs", f, gain_db) | ("lp"/"hp", f[, q]) | ("bp", f, q)."""
    y = np.asarray(x, dtype=np.float64)
    for bnd in bands:
        k = bnd[0]
        if k == "peak":
            y = peq(y, sr, bnd[1], bnd[2], bnd[3] if len(bnd) > 3 else 1.0)
        elif k in ("ls", "hs"):
            y = biquad(y, sr, k, bnd[1], 0.7071, bnd[2])
        elif k in ("lp", "hp"):
            y = biquad(y, sr, k, bnd[1], bnd[2] if len(bnd) > 2 else 0.7071)
        elif k == "bp":
            y = bp(y, sr, bnd[1], bnd[2])
        else:
            raise ValueError(k)
    return y


def lp1(x, sr: int, f) -> np.ndarray:
    """One-pole low-pass (6 dB/oct). f may be a curve."""
    x = np.asarray(x, dtype=np.float64)
    if _is_const(f):
        a = math.exp(-TAU * float(np.asarray(f).ravel()[0]) / sr)
        return _ss.lfilter([1.0 - a], [1.0, -a], x, axis=0)
    n = x.shape[0]
    fv = np.clip(curve(f, n, sr), 1.0, 0.45 * sr)
    block = 64
    y = np.empty_like(x)
    zi = np.zeros((1,) + x.shape[1:])
    for s in range(0, n, block):
        e = min(n, s + block)
        a = math.exp(-TAU * fv[min(n - 1, s + block // 2)] / sr)
        y[s:e], zi = _ss.lfilter([1.0 - a], [1.0, -a], x[s:e], axis=0, zi=zi * 1.0)
    return y


def hp1(x, sr: int, f) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return x - lp1(x, sr, f)


def fft_eq(x, sr: int, points, circular: bool = False) -> np.ndarray:
    """Zero-phase arbitrary EQ from [(f_hz, gain_db), ...] (log-frequency interpolation).
    circular=True filters a loop in place (no padding, seam preserved)."""
    x = np.asarray(x, dtype=np.float64)
    n0 = x.shape[0]
    pad = 0 if circular else _sfft.next_fast_len(n0 + min(n0, sr // 2) + 64, real=True) - n0
    xp = np.pad(x, [(0, pad)] + [(0, 0)] * (x.ndim - 1)) if pad else x
    n = xp.shape[0]
    X = np.fft.rfft(xp, axis=0)
    f = np.maximum(np.fft.rfftfreq(n, 1.0 / sr), 1.0)
    fp = np.log2(np.array([max(p[0], 1.0) for p in points]))
    g = undb(np.interp(np.log2(f), fp, np.array([p[1] for p in points], dtype=np.float64)))
    X *= g if x.ndim == 1 else g[:, None]
    return np.fft.irfft(X, n, axis=0)[:n0]


def tilt(x, sr: int, db_per_oct: float, pivot: float = 1000.0, circular: bool = False) -> np.ndarray:
    """Spectral tilt around `pivot` Hz (zero-phase)."""
    pts = [(f, db_per_oct * math.log2(f / pivot)) for f in (20.0, 40, 80, 160, 320, 640, 1280, 2560, 5120, 10240, 20480)]
    return fft_eq(x, sr, pts, circular)


def dc_block(x, sr: int, f: float = 12.0) -> np.ndarray:
    return hp(x, sr, f, order=2)


def comb(x, sr: int, delay: float, fb: float = 0.6, damp: float = 0.2) -> np.ndarray:
    """Feedback comb y[n] = x[n] + fb*((1-damp) y[n-D] + damp y[n-D-1]): hollow/tubular resonance at
    multiples of 1/delay."""
    D = max(1, int(round(delay * sr)))
    a = np.zeros(D + 2)
    a[0] = 1.0
    a[D] = -fb * (1.0 - damp)
    a[D + 1] = -fb * damp
    return _ss.lfilter([1.0], a, np.asarray(x, dtype=np.float64), axis=0)


def allpass(x, sr: int, delay: float, g: float = 0.6) -> np.ndarray:
    """Schroeder all-pass diffuser."""
    D = max(1, int(round(delay * sr)))
    b = np.zeros(D + 1)
    a = np.zeros(D + 1)
    b[0], b[D] = -g, 1.0
    a[0], a[D] = 1.0, -g
    return _ss.lfilter(b, a, np.asarray(x, dtype=np.float64), axis=0)


def fir_echo(x, sr: int, taps) -> np.ndarray:
    """Discrete echoes [(delay_s, gain), ...] (multi-tap delay via FFT convolution)."""
    L = ns(max(t for t, _ in taps), sr) + 1
    h = np.zeros(L)
    for t, g in taps:
        h[ns(t, sr)] += g
    return _conv(np.asarray(x, dtype=np.float64), h)


# =====================================================================================================
# Resonators & modal synthesis
# =====================================================================================================

def reson(x, sr: int, f: float, t60: float | None = None, bw: float | None = None, gain: float = 1.0,
          dc: bool = False) -> np.ndarray:
    """Two-pole resonator ringing at f with decay t60 (or bandwidth bw); a unit impulse rings with ~unit
    amplitude. Default form has a zero at DC (b = g/2 [1, 0, -1]): a smooth contact pulse excites only the
    mode, with no low-frequency leak. dc=True uses b = g sin(w) (passes DC: the pulse's own low-passed shape
    comes through too - wanted for body thumps)."""
    if t60 is not None:
        rr = math.exp(-LN1000 / (max(t60, 1e-5) * sr))
    else:
        rr = math.exp(-math.pi * float(bw or 50.0) / sr)
    w = TAU * min(f, 0.49 * sr) / sr
    b = [gain * math.sin(w)] if dc else [0.5 * gain, 0.0, -0.5 * gain]
    return _ss.lfilter(b, [1.0, -2.0 * rr * math.cos(w), rr * rr], np.asarray(x, dtype=np.float64), axis=0)


def modal_bank(exc, sr: int, freqs, t60s, amps) -> np.ndarray:
    """Parallel resonators driven by an excitation signal (impacts, scrapes, rolls)."""
    exc = np.asarray(exc, dtype=np.float64)
    y = np.zeros_like(exc)
    for f, t, a in zip(np.asarray(freqs, dtype=np.float64), np.asarray(t60s, dtype=np.float64),
                       np.asarray(amps, dtype=np.float64)):
        if 20.0 < f < 0.47 * sr and a != 0:
            y += reson(exc, sr, f, t60=t, gain=a)
    return y


def modal(n: int, sr: int, freqs, t60s, amps, phases=None) -> np.ndarray:
    """Direct modal synthesis (sum of exponentially decaying sines)."""
    return partials(n, sr, freqs, amps, t60s, phases)


_PLATE_CACHE: dict = {}


def _plate_ratios(aspect: float, count: int) -> np.ndarray:
    m = np.arange(1, 10)
    vals = (m[:, None] ** 2 + (m[None, :] / aspect) ** 2).ravel()
    vals = np.unique(np.round(vals / vals.min(), 5))
    return vals[:count]


# material presets: spread = random ratio step range (when no explicit ratios), t60 at f0, tilt: t60 ~ (f/f0)^-tilt,
# amp_tilt: amp ~ (f/f0)^-amp_tilt, doublet: split modes into beating pairs (relative detune)
MATERIALS = {
    "wood": dict(spread=(1.16, 1.62), count=18, t60=0.16, tilt=0.8, amp_tilt=0.35),
    "wood_hollow": dict(spread=(1.10, 1.45), count=24, t60=0.30, tilt=0.7, amp_tilt=0.45),
    "wood_small": dict(spread=(1.2, 1.7), count=12, t60=0.07, tilt=0.6, amp_tilt=0.25),
    "metal": dict(ratios="plate", count=28, t60=1.4, tilt=0.35, amp_tilt=0.15, doublet=0.0025),
    "metal_sheet": dict(ratios="plate", count=36, t60=0.9, tilt=0.25, amp_tilt=0.05, doublet=0.004),
    "metal_bar": dict(ratios=[1.0, 2.756, 5.404, 8.933, 13.344, 18.64, 24.81], t60=2.2, tilt=0.3,
                      amp_tilt=0.3, doublet=0.003),
    "pipe": dict(ratios=[1.0, 2.756, 5.404, 8.933, 13.344, 18.64], t60=1.6, tilt=0.4, amp_tilt=0.2,
                 doublet=0.006, extra=6),
    "bell": dict(ratios=[0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166, 5.433, 6.796],
                 t60=4.0, tilt=0.55, amp_tilt=0.25, doublet=0.0015),
    "stone": dict(spread=(1.22, 1.85), count=12, t60=0.045, tilt=0.45, amp_tilt=0.1),
    "rock_big": dict(spread=(1.15, 1.6), count=16, t60=0.09, tilt=0.6, amp_tilt=0.3),
    "glass": dict(ratios=[1.0, 2.32, 4.25, 6.63, 9.38, 12.6], t60=0.8, tilt=0.4, amp_tilt=0.25,
                  doublet=0.002, extra=6),
    "ceramic": dict(ratios=[1.0, 2.1, 3.6, 5.5, 7.8], t60=0.18, tilt=0.5, amp_tilt=0.2, extra=6),
    "plastic": dict(spread=(1.2, 1.7), count=10, t60=0.05, tilt=0.6, amp_tilt=0.4),
    "soft": dict(spread=(1.3, 2.0), count=6, t60=0.06, tilt=0.9, amp_tilt=1.0),
}


def modes(material: str, f0: float, r: np.random.Generator, count: int | None = None, t60: float | None = None,
          amp_jitter: float = 0.6, detune: float = 0.03, sr: int = SR):
    """(freqs, t60s, amps) for a material preset rooted at f0. Random per call (strike position, size)."""
    p = MATERIALS[material]
    rat = p.get("ratios")
    if rat is None:
        cnt = count or p["count"]
        steps = r.uniform(p["spread"][0], p["spread"][1], cnt - 1)
        ratios = np.concatenate([[1.0], np.cumprod(steps)])
    elif isinstance(rat, str):
        aspect = float(r.uniform(1.1, 1.9))
        ratios = _plate_ratios(aspect, count or p["count"])
    else:
        ratios = np.asarray(rat, dtype=np.float64)
        if count:
            ratios = ratios[:count]
        if p.get("extra"):
            ex = r.uniform(ratios[0] * 1.3, ratios[-1], p["extra"])
            ratios = np.sort(np.concatenate([ratios, ex]))
    ratios = ratios * (1.0 + detune * r.uniform(-1.0, 1.0, len(ratios)) * (np.arange(len(ratios)) > 0))
    freqs = f0 * ratios
    base_t60 = t60 if t60 is not None else p["t60"]
    t60s = base_t60 * (freqs / f0) ** (-p["tilt"]) * r.uniform(0.75, 1.25, len(freqs))
    amps = (freqs / f0) ** (-p["amp_tilt"]) * (1.0 - amp_jitter * r.random(len(freqs)))
    if p.get("doublet"):
        d = p["doublet"] * r.uniform(0.3, 1.0, len(freqs))
        freqs = np.concatenate([freqs * (1 - d / 2), freqs * (1 + d / 2)])
        t60s = np.concatenate([t60s, t60s * r.uniform(0.85, 1.15, len(t60s))])
        amps = np.concatenate([amps, amps * r.uniform(0.4, 1.0, len(amps))]) * 0.7
    keep = freqs < 0.45 * sr
    return freqs[keep], t60s[keep], amps[keep]


def pulse(sr: int, ms: float) -> np.ndarray:
    """Raised-cosine contact pulse of the given duration (hammer/contact force profile)."""
    L = max(2, ns(ms / 1000.0, sr))
    return np.sin(np.pi * (np.arange(L) + 0.5) / L) ** 2


# =====================================================================================================
# Impulses & granular textures
# =====================================================================================================

def poisson(r: np.random.Generator, dur: float, rate, sr: int = SR, t0: float = 0.0) -> np.ndarray:
    """Event times (s) of a Poisson process over [t0, t0+dur). `rate` (events/s) may be a scalar or a curve
    (time-varying intensity, sampled by thinning)."""
    if _is_const(rate):
        lam = float(np.asarray(rate).ravel()[0])
        if lam <= 0 or dur <= 0:
            return np.zeros(0)
        cnt = int(r.poisson(lam * dur))
        return np.sort(r.uniform(0.0, dur, cnt)) + t0
    n = max(2, ns(dur, sr))
    rc = np.maximum(curve(rate, n, sr), 0.0)
    lam = float(rc.max())
    if lam <= 0:
        return np.zeros(0)
    cnt = int(r.poisson(lam * dur))
    t = np.sort(r.uniform(0.0, dur, cnt))
    keep = r.random(cnt) * lam < rc[np.minimum((t * sr).astype(np.int64), n - 1)]
    return t[keep] + t0


def impulses(n: int, sr: int, times, amps) -> np.ndarray:
    """Sparse impulse train (fractional positions split linearly between neighbours)."""
    out = np.zeros(n + 2)
    pos = np.asarray(times, dtype=np.float64) * sr
    amps = np.broadcast_to(np.asarray(amps, dtype=np.float64), pos.shape)
    ok = (pos >= 0) & (pos < n)
    pos, amps = pos[ok], amps[ok]
    i = np.floor(pos).astype(np.int64)
    fr = pos - i
    np.add.at(out, i, amps * (1 - fr))
    np.add.at(out, i + 1, amps * fr)
    return out[:n]


def scatter(n: int, sr: int, times, grains, gains=None) -> np.ndarray:
    """Places grain arrays at times (s). `grains` is a list or a callable(i) -> array."""
    out = np.zeros(n)
    for i, t in enumerate(times):
        g = grains(i) if callable(grains) else grains[i]
        place(out, g, ns(t, sr), 1.0 if gains is None else float(gains[i]))
    return out


def power_amps(r: np.random.Generator, count: int, alpha: float = 1.8, cap: float = 30.0) -> np.ndarray:
    """Heavy-tailed (Pareto) amplitudes in (0, 1]: many small grains, a few loud ones (crackle statistics)."""
    a = (1.0 - r.random(count)) ** (-1.0 / alpha)
    return np.minimum(a, cap) / cap


def grain_bank(x_imp: np.ndarray, sr: int, r: np.random.Generator, centers, q=3.0, groups: int | None = None,
               weights=None) -> np.ndarray:
    """Distributes the impulses of x_imp over band-pass 'grain colours' (centres Hz, Q) and sums.
    Cheap dense textures: each impulse rings as a short filtered click."""
    centers = list(centers)
    G = len(centers)
    idx = np.nonzero(x_imp)[0]
    which = r.integers(0, G, len(idx)) if weights is None else r.choice(G, len(idx), p=np.asarray(weights) / np.sum(weights))
    out = np.zeros_like(x_imp)
    qs = np.broadcast_to(np.asarray(q, dtype=np.float64), (G,))
    for g in range(G):
        sel = idx[which == g]
        if len(sel) == 0:
            continue
        tr = np.zeros_like(x_imp)
        tr[sel] = x_imp[sel]
        out += bp(tr, sr, centers[g], qs[g]) * math.sqrt(qs[g])
    return out


def clicks(n: int, sr: int, r: np.random.Generator, rate, f_lo: float = 1500.0, f_hi: float = 8000.0, q=2.5,
           alpha: float = 1.8, groups: int = 12, dur: float | None = None, follow: float = 0.6) -> np.ndarray:
    """Poisson cloud of tiny band-passed clicks with heavy-tailed amplitudes (crackle, crunch, rustle).
    When `rate` is a curve, grain amplitudes also scale with (rate/max)**follow (texture settles naturally)."""
    times = poisson(r, n / sr if dur is None else dur, rate, sr)
    amps = power_amps(r, len(times), alpha) * r.choice((-1.0, 1.0), len(times))
    if follow and not _is_const(rate) and len(times):
        rc = np.maximum(curve(rate, n, sr), 0.0)
        amps = amps * (rc[np.minimum((times * sr).astype(np.int64), n - 1)] / max(float(rc.max()), 1e-9)) ** follow
    imp = impulses(n, sr, times, amps)
    cents_ = np.exp(np.linspace(math.log(f_lo), math.log(f_hi), groups) + r.uniform(-0.12, 0.12, groups))
    return grain_bank(imp, sr, r, cents_, q)


# =====================================================================================================
# Physical recipes (shared by several families)
# =====================================================================================================

def impact(sr: int, r: np.random.Generator, material: str = "wood", f0: float = 300.0, dur: float | None = None, *,
           contact_ms: float = 0.6, force: float = 1.0, damp: float = 1.0, count: int | None = None,
           noise: float = 0.15, click: float = 0.15, click_hz: float = 3000.0, modes_=None,
           amp_jitter: float = 0.6, t60: float | None = None, tilt: float = 0.0) -> np.ndarray:
    """Modal impact: raised-cosine contact pulse (+ contact roughness noise) driving a material's resonator
    bank, plus a short broadband contact click. Peak ~= force. Shorter contact = brighter (more high modes);
    tilt > 0 additionally darkens (mode amplitude * (f/f_lowest)^-tilt)."""
    fr, tt, aa = modes_ if modes_ is not None else modes(material, f0, r, count=count, t60=t60, amp_jitter=amp_jitter, sr=sr)
    if tilt and len(fr):
        aa = np.asarray(aa) * (np.asarray(fr) / float(np.min(fr))) ** (-tilt)
    tt = np.asarray(tt) / max(damp, 1e-3)
    if dur is None:
        dur = min(6.0, float(np.max(tt)) * 1.05 + 0.02)
    n = max(ns(dur, sr), 8)
    exc = np.zeros(n)
    p = pulse(sr, contact_ms)
    place(exc, p, 0)
    if noise:
        L = min(n, max(len(p) * 3, 16))
        exc[:L] += noise * r.standard_normal(L) * np.exp(-np.arange(L) / (L / 3.0)) * 0.5
    y = modal_bank(exc, sr, fr, tt, aa)
    y = normalize(y, 1.0)
    if click:
        L = max(8, ns(0.0012, sr))
        c = hp(r.standard_normal(L) * np.exp(-np.arange(L) / (L / 4.0)), sr, click_hz)
        c = normalize(c, 1.0)
        place(y, c, 0, click)
    return normalize(y, force)


def thud(sr: int, r: np.random.Generator, f: float = 80.0, dur: float = 0.25, *, contact_ms: float = 8.0,
         t60: float = 0.05, noise: float = 0.3, noise_lp: float = 600.0, force: float = 1.0,
         knock: float = 0.0, knock_f: float = 450.0) -> np.ndarray:
    """Low body thump (foot on ground, body fall, heavy soft object): smoothed contact pulse into a
    low-Q resonance (t60 ~ 0.03-0.06 s keeps it tight, longer = boomy), low-passed contact noise and an
    optional mid 'knock' (sole/shoe body, 250-800 Hz)."""
    n = ns(dur, sr)
    exc = np.zeros(n)
    place(exc, pulse(sr, contact_ms), 0)
    y = reson(exc, sr, f, t60=t60, dc=True) + 0.5 * reson(exc, sr, f * vary(r, 1.9, 0.15), t60=t60 * 0.5, dc=True)
    y = normalize(y)
    if noise:
        L = min(n, ns(contact_ms * 4 / 1000.0, sr) + 8)
        nz = np.zeros(n)
        nz[:L] = r.standard_normal(L) * env_ar(L, sr, contact_ms / 3000.0, contact_ms * 3.0 / 1000.0)
        nz = normalize(lp(nz, sr, noise_lp, order=4))
        y = y + noise * nz
    if knock:
        L = min(n, ns(0.03, sr))
        kn = np.zeros(n)
        kn[:L] = r.standard_normal(L) * env_ar(L, sr, 0.0006, 0.018)
        kn = bp(kn, sr, knock_f, 1.4) + 0.5 * bp(kn, sr, knock_f * vary(r, 2.3, 0.15), 2.0)
        y = y + knock * normalize(kn)
    return normalize(y, force)


def crack(sr: int, r: np.random.Generator, dur: float = 0.4, *, n_clicks: int = 5, spread: float = 0.035,
          body: str = "wood", body_f: float = 600.0, body_amt: float = 0.6, bright: float = 4000.0,
          tail: float = 0.4, tail_rate: float = 300.0, force: float = 1.0) -> np.ndarray:
    """Brittle fracture (twig/branch/bone/plank snap): a cluster of very sharp broadband clicks (first one
    loudest) exciting a resonant body, followed by a short fibrous crackle tail."""
    n = ns(dur, sr)
    times = np.concatenate([[0.0], np.sort(r.exponential(spread / 2.0, max(0, n_clicks - 1)))])
    times = np.minimum(times, spread * 3)
    amps = np.concatenate([[1.0], r.uniform(0.15, 0.8, max(0, n_clicks - 1))])
    exc = impulses(n, sr, times + 0.0005, amps * r.choice((-1.0, 1.0), len(amps)))
    sharp = hp(exc, sr, bright * 0.5) + 0.4 * bp(exc, sr, bright, 1.2)
    fr, tt, aa = modes(body, body_f, r)
    res = modal_bank(lp(exc, sr, 6000.0), sr, fr, tt, aa)
    y = normalize(sharp) + body_amt * normalize(res)
    if tail:
        k = ns(min(dur, spread * 4 + 0.15), sr)
        rate = curve([(0.0, tail_rate), (k / sr, 0.0)], k, sr)
        cr = clicks(k, sr, r, rate, 1200.0, 7000.0, q=2.0, alpha=1.5, groups=6)
        place(y, normalize(cr) * tail, ns(0.002, sr))
    return normalize(y, force)


def creak(sr: int, dur: float, r: np.random.Generator, rate, amp=1.0, *, res=None, jitter: float = 0.12,
          pulse_ms: float = 0.35, body: float = 0.15, roughness: float = 0.3, bright: float = 3500.0) -> np.ndarray:
    """Stick-slip friction (hinges, timber under strain, rope, leather): a jittered train of slip impulses at
    `rate` events/s (curve; ~10-40/s ticks, 50-300/s groan, >300/s squeal) exciting resonances
    res=[(f, q, gain), ...]. Amplitude follows `amp` (curve). `bright` low-passes the slip pulses (a real
    slip is not an ideal spike; keeps the pitched harmonics clear of broadband fizz)."""
    n = ns(dur, sr)
    rc = np.maximum(curve(rate, n, sr), 0.0)
    wob = 1.0 + jitter * smooth_noise(n, sr, r, 25.0) + 0.5 * jitter * smooth_noise(n, sr, r, 180.0)
    ph = np.cumsum(rc * np.maximum(wob, 0.05)) / sr
    k = np.floor(ph)
    idx = np.nonzero(np.diff(k, prepend=k[0]) > 0)[0]
    a = curve(amp, n, sr)
    amps = a[idx] * np.exp(roughness * r.standard_normal(len(idx)))
    imp = np.zeros(n)
    imp[idx] = amps
    dec = math.exp(-1.0 / max(pulse_ms * sr / 1000.0, 0.5))
    pul = _ss.lfilter([1.0, -1.0], [1.0, -dec], imp)  # sharp slip then relaxation (saw-like pulse)
    if bright:
        pul = lp(pul, sr, bright, q=0.6)
    if res is None:
        res = [(vary(r, 420.0, 0.2), 9.0, 1.0), (vary(r, 860.0, 0.2), 11.0, 0.7), (vary(r, 1650.0, 0.2), 13.0, 0.45),
               (vary(r, 2700.0, 0.2), 15.0, 0.3)]
    y = np.zeros(n)
    for f, q, g in res:
        y += bp(pul, sr, f, q) * g
    y += body * hp(pul, sr, 300.0)
    return y


def scrape(sr: int, dur: float, r: np.random.Generator, speed=1.0, *, f_lo: float = 400.0, f_hi: float = 5000.0,
           grit: float = 0.5, grit_rate: float = 600.0, res=None, rough_hz: float = 60.0) -> np.ndarray:
    """Rough sliding contact (stone/metal/wood dragged): band-limited noise with jittery micro-AM, Poisson
    grit clicks whose rate follows speed, optional resonances res=[(f, q, gain)]."""
    n = ns(dur, sr)
    sp = np.maximum(curve(speed, n, sr), 0.0)
    nz = band_noise(n, sr, r, f_lo, f_hi)
    am = np.maximum(0.0, 1.0 + 0.8 * smooth_noise(n, sr, r, rough_hz) + 0.4 * smooth_noise(n, sr, r, rough_hz * 4))
    y = nz * am * sp ** 1.5
    if grit:
        g = clicks(n, sr, r, sp * grit_rate, f_lo * 1.5, min(f_hi * 1.5, 0.45 * sr), q=2.0, alpha=1.6)
        y = normalize(y) + grit * normalize(g) * 0.8
    if res:
        z = np.zeros(n)
        for f, q, gg in res:
            z += bp(y, sr, f, q) * gg
        y = y + z
    return y


def rustle(sr: int, dur: float, r: np.random.Generator, intensity=1.0, *, f_lo: float = 1500.0, f_hi: float = 9000.0,
           density: float = 1200.0, q=2.5, alpha: float = 1.7, swish: float = 0.35, swish_lo: float | None = None,
           groups: int = 8) -> np.ndarray:
    """Foliage/paper/cloth texture: heavy-tailed crinkle grains (rate density*intensity) over a smooth
    band-passed swish whose level follows intensity**1.5."""
    n = ns(dur, sr)
    it = np.maximum(curve(intensity, n, sr), 0.0)
    cr = clicks(n, sr, r, it * density, f_lo, f_hi, q=q, alpha=alpha, groups=groups)
    y = normalize(cr)
    if swish:
        sw = band_noise(n, sr, r, swish_lo or f_lo * 0.6, f_hi) * it ** 1.5
        y = y + swish * normalize(sw)
    return y


def whoosh(sr: int, dur: float, r: np.random.Generator, *, peak_t: float = 0.5, width: float = 0.18,
           f_lo: float = 250.0, f_hi: float = 1400.0, q: float = 1.3, power: float = 2.2, tone: float = 0.0,
           tone_q: float = 18.0, skew: float = 1.4) -> np.ndarray:
    """Air rush of a swung object: a skewed velocity bell drives band-pass centre (doppler-ish rise/fall) and
    amplitude (~v^power). Optional whistling vortex tone (narrow band)."""
    n = ns(dur, sr)
    t = np.arange(n) / sr / max(dur, 1e-6)
    u = (t - peak_t) / width
    u = np.where(u < 0, u, u / skew)            # slower decay than attack
    v = np.exp(-u * u)
    fc = f_lo + (f_hi - f_lo) * v
    src = pink(n, r, sr)
    y = bp(src, sr, fc, q) * v ** power
    y = y + 0.35 * bp(src, sr, fc * 2.3, q * 0.8) * v ** (power + 1)
    if tone:
        y = y + tone * bp(white(n, r), sr, fc * 1.8, tone_q) * v ** (power + 1) * 3.0
    return y


def squelch(sr: int, r: np.random.Generator, dur: float = 0.18, f0: float = 2200.0, f1: float = 600.0, q: float = 5.0,
            stick: float = 0.5, bub: float = 0.35, attack: float = 0.004) -> np.ndarray:
    """Wet squelch (soft tissue, mud, gore, chewing): resonant noise whose centre sweeps f0 -> f1 (a cavity
    changing size), sticky micro-pops of liquid films separating, and a few bubbles."""
    n = ns(dur, sr)
    env = env_ar(n, sr, attack, dur * 0.85)
    fc = curve([(0.0, f0), (dur, f1)], n, sr, "exp")
    src = white(n, r)
    y = bp(src, sr, fc, q) * env + 0.5 * bp(src, sr, fc * vary(r, 1.8, 0.1), q * 1.3) * env
    y = normalize(y)
    if stick:
        y = y + stick * normalize(clicks(n, sr, r, env * 1800.0, 500.0, 5000.0, q=3.0, alpha=1.5, groups=8))
    if bub:
        y = y + bub * normalize(bubbles(n, sr, r, env * 70.0 + 1e-3, 350.0, 2400.0, 2.0, rise=(0.0, 0.2)))
    return y


def cloth(sr: int, dur: float, r: np.random.Generator, motion=1.0, *, heavy: float = 0.5) -> np.ndarray:
    """Clothing/fabric movement: soft broadband swish with fibrous micro-crackle; heavy -> lower, denser."""
    lo = 300.0 + 500.0 * (1 - heavy)
    return rustle(sr, dur, r, motion, f_lo=lo * 1.5, f_hi=6000.0 - 2500.0 * heavy, density=400.0 + 600 * heavy,
                  q=1.3, alpha=2.2, swish=1.0, swish_lo=lo)


def tear(sr: int, dur: float, r: np.random.Generator, intensity=1.0, *, f_lo: float = 500.0, f_hi: float = 6000.0,
         wet: float = 0.0, rate: float = 1800.0) -> np.ndarray:
    """Tearing (fabric, flesh, bark, paper): bursts of densely packed fibre snaps under a jerky pull."""
    n = ns(dur, sr)
    it = np.maximum(curve(intensity, n, sr), 0.0)
    jerk = np.maximum(0.0, 0.6 + 0.6 * smooth_noise(n, sr, r, 18.0))
    y = normalize(clicks(n, sr, r, it * jerk * rate, f_lo, f_hi, q=1.8, alpha=1.6)) + \
        0.35 * normalize(band_noise(n, sr, r, f_lo, f_hi) * it * jerk)
    if wet:
        y = y + wet * normalize(squelch(sr, r, dur, f_hi * 0.4, f_lo, 4.0, stick=1.0, bub=0.5))
    return y


def bubble(sr: int, r: np.random.Generator, f0: float, amp: float = 1.0, rise: float | None = None,
           dur: float | None = None) -> np.ndarray:
    """One bubble (van den Doel): sine chirp f(t)=f0(1+sigma t) with damping d = 0.13 f0 + 0.0072 f0^1.5."""
    d = 0.13 * f0 + 0.0072 * f0 ** 1.5
    sig = (r.uniform(0.0, 0.25) if rise is None else rise) * d
    L = max(8, ns(dur if dur else min(0.5, 6.9 / d), sr))
    t = np.arange(L) / sr
    y = np.sin(TAU * (f0 * t + 0.5 * f0 * sig * t * t)) * np.exp(-d * t)
    a = min(L, max(2, ns(0.0004, sr)))
    y[:a] *= np.linspace(0, 1, a)
    return y * amp


def bubbles(n: int, sr: int, r: np.random.Generator, rate, f_lo: float = 300.0, f_hi: float = 2500.0,
            alpha: float = 2.0, rise: tuple = (0.0, 0.4)) -> np.ndarray:
    """Cloud of bubbles (streams, pours, gore, gulps) with log-uniform pitch and Pareto amplitude."""
    times = poisson(r, n / sr, rate, sr)
    if len(times) == 0:
        return np.zeros(n)
    fs = loguni(r, f_lo, f_hi, len(times))
    am = power_amps(r, len(times), alpha)
    rs = r.uniform(rise[0], rise[1], len(times))
    return scatter(n, sr, times, lambda i: bubble(sr, r, fs[i], am[i], rs[i]))


def drip(sr: int, r: np.random.Generator, f0: float = 1400.0, *, plink: float = 1.0, splat: float = 0.3,
         room: float = 0.0) -> np.ndarray:
    """Water drop into water: tiny impact click + rising 'plink' bubble resonance."""
    b = bubble(sr, r, f0, 1.0, rise=r.uniform(0.6, 1.6), dur=0.25)
    c = hp(r.standard_normal(ns(0.002, sr)) * np.exp(-np.arange(ns(0.002, sr)) / 20.0), sr, 2000.0)
    y = np.zeros(len(b) + 64)
    place(y, normalize(c), 0, splat)
    place(y, b, ns(0.0015, sr), plink)
    return y


def splash(sr: int, r: np.random.Generator, size: float = 1.0, dur: float = 0.7) -> np.ndarray:
    """Object/foot entering water: slap transient, spray of droplets, bubbles, low slosh."""
    n = ns(dur, sr)
    t = np.arange(n) / sr
    slap = band_noise(n, sr, r, 300.0, 6000.0) * env_ar(n, sr, 0.003, 0.09 * size)
    spray_env = env_ar(n, sr, 0.02, 0.35 * size) * (0.6 + 0.4 * smooth_noise(n, sr, r, 30.0))
    spray = clicks(n, sr, r, 2500.0 * size * spray_env + 1.0, 1500.0, 9000.0, q=4.0, alpha=1.6)
    bub = bubbles(n, sr, r, 90.0 * size * env_ar(n, sr, 0.03, 0.4 * size), 500.0 / size ** 0.3, 3500.0, 2.4,
                  rise=(0.0, 0.12))
    slosh = lp(brown(n, r, sr), sr, 400.0) * env_ar(n, sr, 0.03, 0.4 * size) * (1 + 0.5 * np.sin(TAU * 7 * t))
    return (0.9 * normalize(slap) + 0.55 * normalize(spray) + 0.6 * normalize(bub) + 0.5 * normalize(slosh))


def fire(n: int, sr: int, r: np.random.Generator, *, intensity=1.0, crackle_rate: float = 8.0, roar: float = 0.6,
         hiss: float = 0.25, pops: float = 1.0, periodic: bool = False, size: float = 1.0) -> np.ndarray:
    """Burning wood: low turbulent roar with flicker, airy hiss, clustered crackles and resonant pops
    (sap bursts). periodic=True keeps the beds loopable (events must still be wrapped by the caller)."""
    it = curve(intensity, n, sr)
    fl = 0.65 + 0.35 * smooth_noise(n, sr, r, 3.0 / size, periodic) + 0.15 * smooth_noise(n, sr, r, 11.0, periodic)
    ro = _spec_shape(n, r, lambda f: (np.maximum(f, 30.0) / 100.0) ** -1.0 * smoothstep((f - 30.0) / 40.0)
                     * 1.0 / (1.0 + (f / (420.0 / size ** 0.4)) ** 3), sr) * fl * it
    hs = _spec_shape(n, r, lambda f: smoothstep((np.log2(f) - 10.5) / 2.0) * 1.0 / (1.0 + (f / 9000.0) ** 2), sr)
    hs = hs * (0.4 + 0.6 * np.maximum(fl, 0.0) ** 2) * it
    y = roar * ro / 3.0 + hiss * hs * 0.12
    if pops:
        y = y + pops * crackles(n, sr, r, crackle_rate * it, size=size) * 0.9
    return y


def crackles(n: int, sr: int, r: np.random.Generator, rate, size: float = 1.0) -> np.ndarray:
    """Clustered fire crackle: parent events (rate/s) spawning bursts of 1-7 snaps within ~60 ms; each snap is
    a sharp click through a random resonance (bright ticks to woody pops)."""
    parents = poisson(r, n / sr, rate, sr)
    times, amps = [], []
    for t in parents:
        k = int(r.integers(1, 8))
        base = float(power_amps(r, 1, 1.4)[0])
        ts = t + np.concatenate([[0.0], np.sort(r.exponential(0.018, k - 1))])
        times += list(ts)
        amps += list(base * np.concatenate([[1.0], r.uniform(0.1, 0.6, k - 1)]))
    times = np.asarray(times)
    amps = np.asarray(amps) * r.choice((-1.0, 1.0), len(amps))
    imp = impulses(n, sr, times % (n / sr), amps)
    cen = [700.0 / size, 1100.0, 1700.0, 2600.0, 3800.0, 5500.0, 8000.0]
    y = grain_bank(imp, sr, r, cen, q=[4.0, 3.5, 3.0, 2.5, 2.0, 2.0, 1.5])
    y = y + 0.6 * hp(imp, sr, 3000.0)
    return y


# =====================================================================================================
# Voice: glottal source + formant cascade
# =====================================================================================================

# (F1..F5), (B1..B5) in Hz for an adult male tract (Peterson & Barney / Klatt); scale with tract=...
VOWELS = {
    "a": ((730, 1090, 2440, 3400, 4300), (90, 110, 140, 220, 260)),
    "o": ((570, 840, 2410, 3300, 4200), (80, 90, 130, 200, 250)),
    "u": ((300, 870, 2240, 3300, 4200), (60, 90, 120, 200, 250)),
    "oo": ((440, 1020, 2240, 3300, 4200), (70, 90, 120, 200, 250)),
    "uh": ((640, 1190, 2390, 3400, 4300), (90, 100, 130, 200, 250)),
    "e": ((530, 1840, 2480, 3500, 4400), (70, 100, 140, 200, 250)),
    "ae": ((660, 1720, 2410, 3400, 4400), (90, 110, 140, 200, 250)),
    "i": ((270, 2290, 3010, 3600, 4500), (50, 100, 150, 200, 250)),
    "ih": ((390, 1990, 2550, 3500, 4400), (60, 100, 140, 200, 250)),
    "er": ((490, 1350, 1690, 3300, 4200), (70, 90, 110, 200, 250)),
    "schwa": ((500, 1500, 2500, 3500, 4400), (80, 100, 140, 200, 250)),
    "m": ((260, 1100, 2300, 3300, 4200), (120, 300, 350, 350, 400)),
    "ng": ((300, 1500, 2400, 3300, 4200), (120, 280, 320, 350, 400)),
    "h": ((600, 1400, 2500, 3500, 4400), (220, 260, 320, 360, 420)),
}


def _nkeys(n: int, hop: int) -> int:
    return (max(n, 1) - 1 + hop - 1) // hop + 1


def formant_tracks(vowel, n: int, sr: int = SR, *, tract=1.0, bw=1.0, wander: float = 0.0,
                   r: np.random.Generator | None = None, kind: str = "smooth", hop: int = 1):
    """Formant tracks F (5, K) and B (5, K) from a vowel name, an (F, B) tuple, or [(t, vowel), ...] targets,
    sampled every `hop` samples (K = keyframes covering n samples; hop=1 gives per-sample tracks).
    tract scales frequencies (<1 longer/bigger throat), bw scales bandwidths (>1 wetter/muffled)."""
    pts = [(0.0, vowel)] if isinstance(vowel, (str, tuple)) else list(vowel)
    K = _nkeys(n, hop)
    ksr = sr / hop

    def fb(v):
        return VOWELS[v] if isinstance(v, str) else v
    F = np.zeros((5, K))
    B = np.zeros((5, K))
    for k in range(5):
        F[k] = np.exp(curve([(t, math.log(fb(v)[0][k])) for t, v in pts], K, ksr, kind))
        B[k] = curve([(t, fb(v)[1][k]) for t, v in pts], K, ksr, kind)
    F *= _ctl(tract, K, ksr)[None, :]
    B *= _ctl(bw, K, ksr)[None, :]
    if wander and r is not None:
        for k in range(5):
            F[k] *= 1.0 + wander * smooth_noise(K, ksr, r, 4.0 + 2 * k)
    F[0] = np.maximum(F[0], 120.0)
    for k in range(1, 5):
        F[k] = np.maximum(F[k], F[k - 1] * 1.12)
    F = np.minimum(F, 0.45 * sr)
    return F, B


def _ctl(spec, K: int, ksr: float) -> np.ndarray:
    """A control (scalar, per-sample array, or [(t, v)] breakpoints) sampled at K keyframes (rate ksr)."""
    if np.isscalar(spec):
        return np.full(K, float(spec))
    if isinstance(spec, np.ndarray):
        return np.interp(np.linspace(0.0, 1.0, K), np.linspace(0.0, 1.0, len(spec)), spec.astype(np.float64))
    return curve(spec, K, ksr)


def formant_filter(src, sr: int, F: np.ndarray, B: np.ndarray, hop: int | None = None) -> np.ndarray:
    """Time-varying cascade of unity-DC-gain (Klatt) formant resonators, as an overlap-add of LTI filters:
    the input is split by triangular windows (summing to 1) centred on keyframes every `hop` samples;
    each window is filtered (with its ringing tail) by the cascade frozen at that keyframe.
    F/B are (5, K) keyframe tracks from formant_tracks(..., hop=hop), or per-sample (5, n) tracks."""
    x = np.asarray(src, dtype=np.float64)
    n = x.shape[0]
    if hop is None or F.shape[1] == n and hop != 1:
        hop = max(32, ns(0.01, sr))
        idx = np.minimum(np.arange(_nkeys(n, hop)) * hop, n - 1)
        F, B = F[:, idx], B[:, idx]
    K = F.shape[1]
    rr = np.exp(-np.pi * B / sr)
    C = -rr * rr
    Bc = 2.0 * rr * np.cos(TAU * F / sr)
    A = 1.0 - Bc - C
    sos = np.zeros((K, F.shape[0], 6))
    sos[:, :, 0] = A.T
    sos[:, :, 3] = 1.0
    sos[:, :, 4] = -Bc.T
    sos[:, :, 5] = -C.T
    bmin = max(25.0, float(np.min(B)))
    margin = min(ns(0.09, sr), ns(1.2 * LN1000 / (math.pi * bmin), sr))
    y = np.zeros(n + margin + 2 * hop + 2)
    tri = 1.0 - np.abs(np.arange(-hop, hop + 1)) / hop
    pad = np.zeros(margin)
    for k in range(K):
        c = k * hop
        a, b = c - hop, c + hop + 1
        a0, b0 = max(a, 0), min(b, n)
        if a0 >= b0:
            continue
        seg = x[a0:b0] * tri[a0 - a:b0 - a]
        if not seg.any():
            continue
        out = _ss.sosfilt(sos[k], np.concatenate([seg, pad]))
        y[a0:a0 + out.shape[0]] += out
    return y[:n]


def glottal(f0, n: int, sr: int, r: np.random.Generator, *, oq=0.6, sq=2.5, jitter: float = 0.01,
            shimmer: float = 0.04, sub=0.0, drift: float = 0.0, os: int = 2):
    """Rosenberg-style glottal flow pulses with jitter/shimmer/period-doubling.
    Returns (dflow, flow): dflow ~ flow derivative (+ lip radiation) = the voiced source, roughly unit
    amplitude independent of f0; flow (0..1) for modulating aspiration noise.
    oq: open quotient (0.3 pressed/creaky .. 0.9 breathy); sq: opening/closing time ratio (higher = brighter);
    sub: alternate-cycle attenuation (0..1) -> subharmonic growl; os: oversampling against aliasing."""
    m = n * os
    srs = sr * os
    f = np.repeat(curve(f0, n, sr), os)
    if jitter:
        f = f * (1.0 + jitter * smooth_noise(m, srs, r, max(20.0, float(np.median(f)) * 0.6)))
    if drift:
        f = f * (1.0 + drift * smooth_noise(m, srs, r, 2.5))
    f = np.maximum(f, 4.0)
    ph = np.cumsum(f) / srs
    k = np.floor(ph)
    p = ph - k
    ki = (k - k[0]).astype(np.int64)
    oqv = np.clip(np.repeat(curve(oq, n, sr), os), 0.15, 0.98)
    sqv = np.maximum(np.repeat(curve(sq, n, sr), os), 0.3)
    tp = oqv * sqv / (1.0 + sqv)
    tn = oqv / (1.0 + sqv)
    g = np.zeros(m)
    m1 = p < tp
    g[m1] = 0.5 - 0.5 * np.cos(np.pi * p[m1] / tp[m1])
    m2 = (~m1) & (p < tp + tn)
    g[m2] = np.cos(0.5 * np.pi * (p[m2] - tp[m2]) / tn[m2])
    nper = int(ki[-1]) + 2 if m else 1
    amp = np.maximum(1.0 + shimmer * r.standard_normal(nper), 0.05)
    g *= amp[ki]
    subv = np.repeat(curve(sub, n, sr), os)
    if np.any(subv):
        g *= 1.0 - np.clip(subv, 0.0, 1.0) * (ki % 2)
    d = np.diff(g, prepend=0.0) * srs / (f * 5.0)
    if os > 1:
        d = _ss.resample_poly(d, 1, os)[:n]
        g = _ss.resample_poly(g, 1, os)[:n]
    return d, g


def voice(sr: int, dur: float, f0, vowel="a", amp=1.0, r: np.random.Generator | None = None, *, oq=0.6, sq=2.5,
          jitter: float = 0.012, shimmer: float = 0.04, sub=0.0, drift: float = 0.0, breath=0.04, asp=0.0,
          tract=1.0, bw=1.0, wander: float = 0.02, rough=0.0, rough_rate: float = 32.0, os: int = 2,
          block: int = 64, tilt_db: float = 0.0) -> np.ndarray:
    """Voiced sound: glottal source (+ aspiration noise: `breath` steady, `asp` flow-modulated), optional
    roughness (random AM at rough_rate -> growl/rattle), through a formant cascade. amp (curve) shapes
    the source so formants ring naturally after stops."""
    r = r if r is not None else rng(0)
    n = ns(dur, sr)
    src, flow = glottal(f0, n, sr, r, oq=oq, sq=sq, jitter=jitter, shimmer=shimmer, sub=sub, drift=drift, os=os)
    rv = curve(rough, n, sr)
    if np.any(rv):
        mod = 0.5 + 0.5 * smooth_noise(n, sr, r, rough_rate)
        src = src * (1.0 - np.clip(rv, 0, 1) * mod)
    nz = hp(white(n, r), sr, 400.0) * 0.25
    br = curve(breath, n, sr)
    asv = curve(asp, n, sr)
    exc = src + nz * (br + asv * flow)
    if tilt_db:
        exc = hshelf(exc, sr, 2500.0, tilt_db)
    exc = exc * curve(amp, n, sr)
    hop = max(32, ns(0.008, sr))
    F, B = formant_tracks(vowel, n, sr, tract=tract, bw=bw, wander=wander, r=r, hop=hop)
    return formant_filter(exc, sr, F, B, hop)


def breath(sr: int, dur: float, vowel="h", amp=1.0, r: np.random.Generator | None = None, *, tract=1.0, bw=1.6,
           hiss: float = 0.3, hiss_f: float = 3500.0, wet: float = 0.0, rattle: float = 0.0,
           rattle_hz: float = 28.0) -> np.ndarray:
    """Unvoiced breath through the tract (exhale 'hhh', inhale with hiss), optional wet gurgle bubbles and
    soft-palate rattle (snore/fluid flutter)."""
    r = r if r is not None else rng(0)
    n = ns(dur, sr)
    a = curve(amp, n, sr)
    src = white(n, r)
    if rattle:
        src = src * (1.0 - rattle * (0.5 + 0.5 * np.sin(TAU * phase(rattle_hz * (1 + 0.15 * smooth_noise(n, sr, r, 3.0)), n, sr))))
    hop = max(32, ns(0.01, sr))
    F, B = formant_tracks(vowel, n, sr, tract=tract, bw=bw, wander=0.03, r=r, hop=hop)
    y = formant_filter(src * a, sr, F, B, hop) * 0.15
    if hiss:
        y = y + hiss * lp(hp(white(n, r), sr, hiss_f), sr, max(hiss_f * 2.5, 8500.0)) * a * 0.25
    if wet:
        bb = bubbles(n, sr, r, 60.0 * wet * a / max(float(a.max()), 1e-9), 250.0, 1400.0, 2.0)
        y = y + wet * 0.5 * normalize(bb) * peak(y)
    return y


# =====================================================================================================
# Nonlinear & dynamics
# =====================================================================================================

def sat(x, drive: float = 1.0) -> np.ndarray:
    """tanh saturation normalized so that +-1 stays +-1."""
    x = np.asarray(x, dtype=np.float64)
    return np.tanh(drive * x) / math.tanh(drive) if drive > 1e-6 else x


def asym(x, drive: float = 2.0, bias: float = 0.25) -> np.ndarray:
    """Asymmetric saturation (adds even harmonics: overdriven throat, blown speakers)."""
    x = np.asarray(x, dtype=np.float64)
    return (np.tanh(drive * (x + bias)) - math.tanh(drive * bias)) / max(math.tanh(drive * (1 + bias)) - math.tanh(drive * bias), 1e-9)


def fold(x, amount: float = 1.5) -> np.ndarray:
    """Sine wavefolder (metallic, gnarly harmonics)."""
    return np.sin(0.5 * np.pi * amount * np.asarray(x, dtype=np.float64))


def env_follow(x, sr: int, attack_ms: float = 2.0, release_ms: float = 60.0) -> np.ndarray:
    """Peak envelope: max-filter over the attack window then one-pole release smoothing."""
    a = np.abs(mono(x))
    w = max(1, ns(attack_ms / 1000.0, sr))
    a = _nd.maximum_filter1d(a, 2 * w + 1)
    c = math.exp(-1.0 / max(1.0, release_ms * sr / 1000.0))
    return _ss.lfilter([1 - c], [1, -c], a)


def compress(x, sr: int, thresh_db: float = -18.0, ratio: float = 3.0, attack_ms: float = 3.0,
             release_ms: float = 80.0, makeup_db: float = 0.0, knee_db: float = 6.0) -> np.ndarray:
    """Feed-forward soft-knee compressor."""
    x = np.asarray(x, dtype=np.float64)
    e = todb(env_follow(x, sr, attack_ms, release_ms))
    o = e - thresh_db
    gr = np.where(o <= -knee_db / 2, 0.0,
                  np.where(o >= knee_db / 2, o * (1 - 1 / ratio), (1 - 1 / ratio) * (o + knee_db / 2) ** 2 / (2 * knee_db)))
    g = undb(makeup_db - gr)
    return x * (g if x.ndim == 1 else g[:, None])


def limit(x, sr: int, ceiling: float = 0.98, window_ms: float = 3.0) -> np.ndarray:
    """Look-ahead brickwall limiter (min-filter + box smoothing; never overshoots the ceiling)."""
    x = np.asarray(x, dtype=np.float64)
    a = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    g = np.minimum(1.0, ceiling / np.maximum(a, 1e-12))
    w = 2 * max(1, ns(window_ms / 1000.0, sr)) + 1
    g = _nd.uniform_filter1d(_nd.minimum_filter1d(g, w), w)
    return x * (g if x.ndim == 1 else g[:, None])


# =====================================================================================================
# Modulation & time
# =====================================================================================================

def varispeed(x, rate) -> np.ndarray:
    """Tape-style playback at `rate` (scalar or per-output-sample curve array): pitch and time change together."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    if _is_const(rate):
        rt = float(np.asarray(rate).ravel()[0])
        pos = np.arange(0.0, n - 1, rt)
    else:
        rc = np.asarray(rate, dtype=np.float64)
        pos = np.concatenate([[0.0], np.cumsum(rc)[:-1]])
        pos = pos[pos < n - 1]
    return _per_channel(lambda c: np.interp(pos, np.arange(n), c), x)


def resample(x, ratio: float) -> np.ndarray:
    """High-quality fixed pitch/time change by `ratio` (>1 = higher & shorter) via polyphase resampling."""
    from fractions import Fraction
    fr = Fraction(1.0 / ratio).limit_denominator(200)
    return _per_channel(lambda c: _ss.resample_poly(c, fr.numerator, fr.denominator), np.asarray(x, dtype=np.float64))


def vdelay(x, sr: int, delay) -> np.ndarray:
    """Variable delay line (seconds, curve) with linear interpolation (chorus, doppler, flanging)."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    d = curve(delay, n, sr) * sr
    idx = np.arange(n) - d
    return _per_channel(lambda c: np.interp(idx, np.arange(n), c, left=0.0, right=0.0), x)


def chorus(x, sr: int, r: np.random.Generator, voices: int = 3, depth_ms: float = 4.0, base_ms: float = 14.0,
           rate: float = 0.3, mix: float = 0.5) -> np.ndarray:
    """Multi-voice chorus with randomized slow LFOs (ensemble beating, thickening)."""
    x = mono(x)
    n = len(x)
    out = x * (1.0 - mix)
    for v in range(voices):
        lfo = 0.6 * np.sin(TAU * phase(rate * r.uniform(0.7, 1.4), n, sr, r.random())) + \
            0.4 * smooth_noise(n, sr, r, rate * 2)
        out += vdelay(x, sr, (base_ms + depth_ms * lfo) / 1000.0) * (mix / voices) * 1.4
    return out


def tremolo(x, sr: int, rate, depth: float = 0.5, r: np.random.Generator | None = None, rnd: float = 0.0) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    m = 0.5 + 0.5 * np.sin(TAU * phase(rate, n, sr))
    if rnd and r is not None:
        m = np.clip(m + rnd * smooth_noise(n, sr, r, float(np.mean(curve(rate, 4, sr))) * 2), 0, 1)
    g = 1.0 - depth * m
    return x * (g if x.ndim == 1 else g[:, None])


def vibrato(n: int, sr: int, rate: float = 5.0, depth_cents: float = 25.0, r: np.random.Generator | None = None,
            irregular: float = 0.3, onset: float = 0.0) -> np.ndarray:
    """Pitch multiplier curve for vibrato (irregular rate/depth when r given; fades in over `onset` s)."""
    ph = phase(rate * (1.0 + (irregular * 0.3 * smooth_noise(n, sr, r, 1.5) if r is not None else 0.0)), n, sr)
    dep = depth_cents * (1.0 + (irregular * smooth_noise(n, sr, r, 1.0) if r is not None else 0.0))
    if onset > 0:
        dep = dep * smoothstep(np.arange(n) / sr / onset)
    return cents(dep * np.sin(TAU * ph))


def drift(n: int, sr: int, r: np.random.Generator, depth_cents: float = 10.0, rate: float = 0.7,
          periodic: bool = False) -> np.ndarray:
    """Slow random pitch-wander multiplier."""
    return cents(depth_cents * smooth_noise(n, sr, r, rate, periodic))


def ring(x, sr: int, f) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return x * sine(f, x.shape[0], sr)


# =====================================================================================================
# Stereo
# =====================================================================================================

def pan(x, p=0.0) -> np.ndarray:
    """Equal-power pan of a mono signal; p in [-1 (left), 1 (right)], scalar or curve array."""
    x = np.asarray(x, dtype=np.float64)
    pv = np.clip(curve(p, len(x)) if not np.isscalar(p) else p, -1.0, 1.0)
    a = (pv + 1.0) * np.pi / 4.0
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1) * math.sqrt(2.0)


def stereo(left, right=None) -> np.ndarray:
    left = np.asarray(left, dtype=np.float64)
    right = left if right is None else np.asarray(right, dtype=np.float64)
    n = max(len(left), len(right))
    return np.stack([fit(left, n), fit(right, n)], axis=1)


def widen(x, width: float = 1.3) -> np.ndarray:
    """Mid/side width (1 = unchanged, 0 = mono)."""
    x = np.asarray(x, dtype=np.float64)
    m = 0.5 * (x[:, 0] + x[:, 1])
    s = 0.5 * (x[:, 0] - x[:, 1]) * width
    return np.stack([m + s, m - s], axis=1)


def decorrelate(x, sr: int, r: np.random.Generator, amount: float = 0.7, ms: float = 18.0) -> np.ndarray:
    """Mono -> stereo with two different short diffusing FIRs (spacious, still mono-compatible)."""
    x = mono(x)
    L = max(16, ns(ms / 1000.0, sr))
    out = []
    for _ in range(2):
        h = r.standard_normal(L) * np.exp(-np.arange(L) / (L / 5.0))
        h /= math.sqrt(np.sum(h * h))
        out.append((1.0 - amount) * x + amount * _conv(x, h)[:len(x)])
    return np.stack(out, axis=1)


# =====================================================================================================
# Reverb (synthetic impulse responses)
# =====================================================================================================

# rt: RT60 (s) for low (<300 Hz) / mid / high (>3 kHz) bands; pre: predelay ms; er: (count, start ms, end ms);
# dens: echo density (/s) of the sparse early tail; build: seconds until the tail is fully diffuse;
# er_gain: early reflections vs tail; lp: brightness of reflections; slaps: discrete distant echoes.
ROOMS = {
    "small_room": dict(rt=(0.42, 0.34, 0.2), pre=1.5, er=(14, 2, 22), dens=2500, build=0.012, er_gain=0.8, lp=9000),
    "house": dict(rt=(0.75, 0.6, 0.32), pre=3.0, er=(18, 3, 40), dens=2000, build=0.02, er_gain=0.7, lp=8000),
    "forest": dict(rt=(1.5, 1.15, 0.45), pre=10.0, er=(45, 8, 260), dens=500, build=0.25, er_gain=0.45, lp=5500),
    "valley": dict(rt=(3.2, 2.6, 0.9), pre=40.0, er=(30, 20, 400), dens=300, build=0.6, er_gain=0.35, lp=3500,
                   slaps=((0.42, 0.55), (0.9, 0.4), (1.45, 0.28), (2.1, 0.16))),
    "cave": dict(rt=(4.0, 3.1, 1.4), pre=16.0, er=(36, 6, 140), dens=2500, build=0.06, er_gain=0.6, lp=7000),
    "hall": dict(rt=(2.8, 2.3, 1.3), pre=24.0, er=(26, 10, 90), dens=3000, build=0.07, er_gain=0.4, lp=9000),
    "town": dict(rt=(1.6, 1.3, 0.55), pre=14.0, er=(40, 10, 300), dens=700, build=0.2, er_gain=0.5, lp=6000,
                 slaps=((0.18, 0.35), (0.31, 0.25), (0.52, 0.18))),
}


def _conv(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    if x.ndim == 2:
        return np.stack([_ss.oaconvolve(x[:, c], h if h.ndim == 1 else h[:, c]) for c in range(x.shape[1])], axis=1)
    return _ss.oaconvolve(x, h)


def make_ir(sr: int, room: str = "house", r: np.random.Generator | None = None, *, stereo_: bool = False,
            rt=None, pre_ms: float | None = None, length: float | None = None) -> np.ndarray:
    """Synthetic IR: early reflections + tail of sparse->dense noise with 3-band exponential decay.
    Unit energy (convolving white noise keeps its RMS)."""
    p = dict(ROOMS[room])
    r = r if r is not None else rng(1234, room)
    rts = p["rt"] if rt is None else ((rt * 1.2, rt, rt * 0.5) if np.isscalar(rt) else rt)
    pre = p["pre"] if pre_ms is None else pre_ms
    L = ns(length if length else max(rts) * 1.1 + pre / 1000.0, sr)
    chans = []
    for ch in range(2 if stereo_ else 1):
        t = np.arange(L) / sr
        dense = r.standard_normal(L)
        sparse = velvet(L, sr, r, p["dens"]) * math.sqrt(sr / p["dens"]) * 0.7
        mixw = smoothstep(t / max(p["build"], 1e-3))
        tail = sparse * (1 - mixw) + dense * mixw
        bands = [lp(tail, sr, 300.0, order=4), band(tail, sr, 300.0, 3000.0, order=4), hp(tail, sr, 3000.0, order=4)]
        y = np.zeros(L)
        for b, rtb in zip(bands, rts):
            y += b * np.exp(-LN1000 * t / rtb)
        y *= smoothstep(t / max(p["build"] * 0.5, 0.002)) * 0.6 + 0.4 * (t > 0.002)
        er = np.zeros(L)
        cnt, a0, a1 = p["er"]
        ets = np.sort(r.uniform(a0, a1, cnt)) / 1000.0
        eam = r.uniform(0.3, 1.0, cnt) * (a0 / 1000.0 + 0.01) / (ets + 0.01) * r.choice((-1.0, 1.0), cnt)
        er = impulses(L, sr, ets, eam)
        er = lp(er, sr, p["lp"])
        for dt, g in p.get("slaps", ()):
            k = ns(dt * r.uniform(0.92, 1.08), sr)
            if k < L - 64:
                w = ns(r.uniform(0.02, 0.06), sr)
                smear = r.standard_normal(w) * hann(w)
                place(er, lp(smear, sr, p["lp"] * 0.6) * g * 3.0, k)
        y = y / math.sqrt(np.sum(y * y) + 1e-12)
        er = er / math.sqrt(np.sum(er * er) + 1e-12)
        h = y * (1 - p["er_gain"] * 0.5) + er * p["er_gain"]
        d = ns(pre / 1000.0, sr)
        h = np.concatenate([np.zeros(d), h])[:L]
        h /= math.sqrt(np.sum(h * h) + 1e-12)
        chans.append(h)
    return np.stack(chans, axis=1) if stereo_ else chans[0]


def reverb(x, sr: int, room: str = "house", mix: float = 0.25, *, seed: int = 0, stereo_: bool = False,
           dry: float = 1.0, circular: bool = False, rt=None, pre_ms: float | None = None, tail: bool = True,
           ir: np.ndarray | None = None) -> np.ndarray:
    """dry*x + mix*(x conv IR). stereo_=True returns (N, 2) with a decorrelated stereo IR.
    circular=True wraps the tail onto the start (seamless loops; output keeps len(x)).
    tail=False truncates to len(x)."""
    x = np.asarray(x, dtype=np.float64)
    h = ir if ir is not None else make_ir(sr, room, rng(seed, "ir", room), stereo_=stereo_, rt=rt, pre_ms=pre_ms)
    if stereo_ and x.ndim == 1:
        x = np.stack([x, x], axis=1)
    n = x.shape[0]
    if circular:
        L = n
        if h.shape[0] > L:
            h = h[:L]
        X = np.fft.rfft(x, n=L, axis=0)
        Hh = np.fft.rfft(h, n=L, axis=0)
        if X.ndim == 2 and Hh.ndim == 1:
            Hh = Hh[:, None]
        wet = np.fft.irfft(X * Hh, L, axis=0)
        return dry * x + mix * wet
    if x.ndim == 2 and h.ndim == 1:
        h = np.stack([h, h], axis=1)
    if x.ndim == 1 and h.ndim == 2:
        h = h[:, 0]
    wet = _conv(x, h)
    out = mix * wet
    out[:n] += dry * x
    return out if tail else out[:n]


def air(x, sr: int, dist_m: float, foliage: float = 0.0) -> np.ndarray:
    """Distance colouring: air absorption (~f^2) plus optional foliage scattering loss of highs."""
    pts = []
    for f in (100.0, 500, 1000, 2000, 4000, 8000, 12000, 20000):
        a = dist_m * 1.2e-9 * f * f * 1.0 + foliage * dist_m * 0.02 * math.log2(max(f / 500.0, 1.0))
        pts.append((f, -min(a, 60.0)))
    return fft_eq(x, sr, pts)


# =====================================================================================================
# Loops
# =====================================================================================================

def make_loop(x, sr: int, xfade: float = 2.0, power: bool = True) -> np.ndarray:
    """Seamless loop from a render that runs `xfade` seconds past the loop end: the overhang is crossfaded
    onto the head (equal-power for uncorrelated material, linear when power=False)."""
    x = np.asarray(x, dtype=np.float64)
    X = ns(xfade, sr)
    N = x.shape[0] - X
    if N <= X:
        raise ValueError("make_loop: signal too short for crossfade")
    out = x[:N].copy()
    t = (np.arange(X) + 0.5) / X
    fi, fo = (np.sin(0.5 * np.pi * t), np.cos(0.5 * np.pi * t)) if power else (t, 1.0 - t)
    if x.ndim == 2:
        fi, fo = fi[:, None], fo[:, None]
    out[:X] = x[:X] * fi + x[N:N + X] * fo
    return out


def loop_place(dst: np.ndarray, src, at: int, gain: float = 1.0) -> np.ndarray:
    """Adds src into a loop buffer at `at`, wrapping whatever runs past the end onto the start."""
    src = np.asarray(src, dtype=np.float64) * gain
    n = dst.shape[0]
    at %= n
    pos = 0
    while pos < src.shape[0]:
        m = min(src.shape[0] - pos, n - at)
        seg = src[pos:pos + m]
        if dst.ndim == 2 and seg.ndim == 1:
            seg = seg[:, None]
        dst[at:at + m] += seg
        pos += m
        at = 0
    return dst


def circular(fn, x, sr: int, preroll: float = 1.0):
    """Runs a causal process on a loop so its state wraps: fn applied to [tail(x), x], tail dropped."""
    x = np.asarray(x, dtype=np.float64)
    P = min(ns(preroll, sr), x.shape[0])
    y = fn(np.concatenate([x[-P:], x], axis=0))
    return y[P:P + x.shape[0]]


# =====================================================================================================
# Finish & write (catalog contract)
# =====================================================================================================

def _seam_fix(x: np.ndarray, sr: int) -> np.ndarray:
    """Spreads the residual loop-seam discontinuity over the last 12 ms (inaudible ramp)."""
    K = min(ns(0.012, sr), x.shape[0] // 4)
    if K < 4:
        return x
    pred = 2 * x[-1] - x[-2]
    err = x[0] - pred
    w = smoothstep(np.arange(1, K + 1) / K)
    x = x.copy()
    x[-K:] += (w[:, None] * err[None, :]) if x.ndim == 2 else w * err
    return x


def _circ_hp(x: np.ndarray, sr: int, fc: float = 12.0) -> np.ndarray:
    n = x.shape[0]
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    g = 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-6)) ** 8)
    g[0] = 0.0
    X *= g if x.ndim == 1 else g[:, None]
    return np.fft.irfft(X, n, axis=0)


def finish(sig, sr: int = SR, peak_db: float = -1.0, loop: bool = False) -> np.ndarray:
    """Final mastering for every sound: sanitize, DC/subsonic removal (circular for loops), trim trailing
    silence + raised-cosine fades (one-shots) or seam smoothing (loops), peak-normalize to peak_db."""
    x = np.asarray(sig, dtype=np.float64)
    if x.ndim == 2 and x.shape[1] == 1:
        x = x[:, 0]
    if x.ndim == 2 and x.shape[0] == 2 and x.shape[1] != 2:
        x = x.T
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    if x.shape[0] < 16:
        x = fit(x, 16)
    if loop:
        x = _circ_hp(x, sr)
        x = _seam_fix(x, sr)
    else:
        x = hp(x, sr, 14.0, order=2)
        a = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
        pk = float(a.max())
        if pk > 0:
            above = np.nonzero(a > pk * undb(-70.0))[0]
            end = min(x.shape[0], int(above[-1]) + ns(0.02, sr)) if len(above) else x.shape[0]
            x = x[:max(end, 16)]
        fo = min(0.03, 0.12 * x.shape[0] / sr)
        x = fade(x, sr, fin=0.001, fout=fo)
    pk = peak(x)
    if pk > 0:
        x = x * (undb(peak_db) / pk)
    return x.astype(np.float32)


def write_wav(path, sig, sr: int = SR) -> None:
    """16-bit PCM WAV (mono or interleaved stereo); deterministic bytes."""
    x = np.asarray(sig, dtype=np.float64)
    ch = 1 if x.ndim == 1 else x.shape[1]
    pcm = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())
