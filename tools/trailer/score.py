"""The trailer's score: the game's own cues (tools/assetgen/audio/sounds/music.py) arranged on the cut.

    python tools/trailer/score.py [--edit tools/trailer/edit.json] [--out build/trailer/score.wav]

Section times and card hits come from edit.json, so re-timing the cut re-times the music. The score
is a trailer deliverable, not a game asset: it is written under build/ and never imported by Godot.

    open     the menu theme's strings rising out of silence (after the tether beep)
    explore  the discovery stinger, then the menu theme under the walk and the town
    build    a D-minor piano ostinato over string chords, swelling towards the threat
    threat   the dread drone; at `hum` the Hum stinger, then impacts closing in and a riser
             that cuts dead on the last card
    dawn     dawn relief (G(add9) -> D major); a low bell under the title
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import wave

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assetgen.audio import dsp  # noqa: E402
from assetgen.audio.sounds import music  # noqa: E402

SR = 44100
SEED = 12001


def _cue(fn, seed: int) -> np.ndarray:
    """One of the game's cues, stereo, peak-normalized."""
    y = np.asarray(fn(seed, 0, SR), dtype=np.float64)
    if y.ndim == 1:
        y = np.stack([y, y], axis=1)
    return dsp.normalize(y)


def _place(dst: np.ndarray, src: np.ndarray, t: float, gain: float = 1.0) -> None:
    if src.ndim == 1:
        src = np.stack([src, src], axis=1)
    dsp.place(dst, src, dsp.ns(max(t, 0.0), SR), gain)


def _window(n: int, spec) -> np.ndarray:
    return dsp.curve(spec, n, SR)[:, None]


def build_ostinato(r: np.random.Generator, dur: float) -> np.ndarray:
    """Build section: eighth-note piano ostinato (D-A-F-A, lifting with the chords) at 96 bpm over
    Dm - Bb - F - C string chords, a soft low pulse on each bar, swelling throughout."""
    n = dsp.ns(dur, SR)
    out = np.zeros((n, 2))
    eighth = 60.0 / 96.0 / 2.0
    bar = eighth * 8
    chords = [(38, [50, 57, 62, 65], [62, 69, 65, 69]),     # Dm
              (34, [50, 53, 58, 62], [62, 70, 65, 70]),     # Bb
              (41, [53, 57, 60, 65], [65, 72, 69, 72]),     # F
              (36, [52, 55, 60, 64], [64, 72, 67, 72])]     # C
    t = 0.0
    k = 0
    while t < dur:
        bass, pad, figure = chords[(k // 2) % len(chords)]
        if k % 2 == 0:
            st = music.strings(SR, r, [bass + 12] + pad, bar * 2 + 0.5, attack=1.2, release=1.8, bright=0.4 + 0.2 * t / dur)
            _place(out, st, t - 0.2, 0.5)
            _place(out, music.piano(SR, bass, 0.45, 4.0), t, 0.8)
            _place(out, music.sub_boom(SR, r, 36.0, 1.6, 0.9), t, 0.18 + 0.2 * t / dur)
        for i in range(8):
            m = figure[i % 4] + (12 if (k >= 4 and i % 4 == 1) else 0)
            v = 0.3 + 0.12 * (i % 4 == 0) + 0.12 * t / dur
            _place(out, dsp.pan(music.piano(SR, m, v, 1.5), music._pan_for(m)), t + i * eighth, 0.55)
        t += bar
        k += 1
    out *= _window(n, [(0, 0.55), (dur * 0.6, 0.8), (dur, 1.0)])
    return dsp.reverb(out[:n], SR, "hall", 0.32, seed=SEED, stereo_=True)


def riser(r: np.random.Generator, dur: float) -> np.ndarray:
    """Tremolo string cluster climbing with an opening filter and rising noise; ends at full height."""
    n = dsp.ns(dur, SR)
    st = music.strings(SR, r, [62, 63, 68, 69, 74, 75], dur + 0.5, attack=dur * 0.8, release=0.3, bright=0.7, trem=0.8)
    st = st[:n]
    noise = dsp.band_noise(n, SR, r, 800.0, 9000.0) * dsp.curve([(0, 0), (dur, 1.0)], n, SR, "exp")
    out = dsp.normalize(st) * 0.8 + dsp.pan(dsp.normalize(noise), 0.0) * 0.18
    return out * _window(n, [(0, 0.0), (dur * 0.3, 0.3), (dur, 1.0)])


def score(edit: dict) -> np.ndarray:
    s = edit["sections"]
    end = float(s["end"])
    n = dsp.ns(end + 4.0, SR)       # a tail for the last reverb; trimmed to the cut by assemble.py
    out = np.zeros((n, 2))
    r = dsp.rng(SEED, "trailer")

    # open + explore: the menu theme out of silence, under everything up to the build
    menu = _cue(music.menu, 11006)
    m0, m1 = 1.5, float(s["build"])
    seg = menu[: dsp.ns(m1 - m0 + 2.0, SR)]
    seg = seg * dsp.curve([(0, 0.0), (3.0, 0.75), (s["explore"] - m0, 0.75), (s["explore"] - m0 + 1.0, 0.6),
                           (m1 - m0 - 1.0, 0.6), (m1 - m0 + 2.0, 0.0)], len(seg), SR)[:, None]
    _place(out, seg, m0)
    _place(out, _cue(music.discovery, 11002), float(s["explore"]) - 0.1, 0.7)

    # build
    _place(out, build_ostinato(r, float(s["threat"]) - float(s["build"]) + 1.0), float(s["build"]) - 0.3, 0.9)

    # threat: the dread drone from just before the threat to the last card
    drone = _cue(music.dread_drone, 11001)
    d0, d1 = float(s["threat"]) - 1.0, float(s["dawn"]) - 2.5
    seg = drone[: dsp.ns(d1 - d0, SR)]
    seg = seg * dsp.curve([(0, 0.0), (2.0, 0.8), (d1 - d0 - 0.05, 0.9), (d1 - d0, 0.0)], len(seg), SR)[:, None]
    _place(out, seg, d0)
    _place(out, _cue(music.hum_start, 11003), float(s["hum"]), 1.0)

    # impacts closing in after the Hum, then the riser into the last card's slam
    last = float(edit["hits"][2]) if len(edit["hits"]) > 2 else d1
    t = float(s["hum"]) + 3.0
    gap = 1.6
    while t < last - 0.3:
        _place(out, dsp.pan(music.sub_boom(SR, r, 40.0, 1.2, 0.6), r.uniform(-0.2, 0.2)), t, 0.35)
        t += gap
        gap = max(0.35, gap * 0.82)
    rise = 7.0
    _place(out, riser(r, rise), last - rise, 0.8)

    # card slams; the one under the title is a bell, not a boom
    for i, h in enumerate(edit["hits"]):
        if h >= float(s["dawn"]):
            _place(out, dsp.pan(music.bell(SR, r, float(dsp.midi_hz(38)), 6.0, 0.6), 0.0), h, 0.25)
            _place(out, music.piano(SR, 26, 0.5, 6.0), h, 0.5)
        else:
            big = h == last
            _place(out, music.sub_boom(SR, r, 30.0 if big else 34.0, 3.5 if big else 2.5, 2.5 if big else 1.6), h, 1.0 if big else 0.6)

    # nothing new starts between the last slam and dawn: the boom's tail rings through the dark
    _place(out, _cue(music.dawn_relief, 11004), float(s["dawn"]) + 0.2, 0.85)

    out = out[: dsp.ns(end + 2.0, SR)]
    out = dsp.fade(out, SR, 0.0, 2.0)
    return dsp.normalize(out, 10 ** (-1.0 / 20.0))


def write_wav(path: pathlib.Path, y: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(y, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--edit", default=str(ROOT / "tools/trailer/edit.json"))
    ap.add_argument("--out", default=str(ROOT / "build/trailer/score.wav"))
    a = ap.parse_args()
    edit = json.loads(pathlib.Path(a.edit).read_text())
    y = score(edit)
    write_wav(pathlib.Path(a.out), y)
    print(f"[score] {a.out}: {len(y) / SR:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
