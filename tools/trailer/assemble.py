"""Cuts the trailer from rendered shots, cards and the score (tools/trailer/edit.json).

    python tools/trailer/assemble.py [--shots build/trailer/shots] [--out build/trailer/hollowmere_trailer.mp4]
                                     [--check]

A shot is a Movie Maker render (game/src/tools/cli/trailer.gd): <shots>/<id>/frame########.png at the
edit's fps, plus frame.wav; or the same packed by --pack <shots>/<id> into shot.mp4 (near-lossless,
what CI uploads instead of gigabytes of PNGs). A shot not rendered yet becomes a labelled slate, so the cut can be
watched as an animatic before every shot exists. Cards and the title are drawn here with the game's
fonts. Every clip is encoded to the same intermediate format and joined without re-timing, so the
lengths in edit.json are the lengths on screen and the score lines up to the frame.

Outputs next to --out: the trailer (H.264 High, yuv420p, AAC, faststart: plays anywhere), a poster
frame (.jpg) and a contact sheet (_sheet.jpg, one frame a second).
--check only validates edit.json (lengths add up, every section starts on a cut).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
FONTS = ROOT / "game/assets/fonts"
SERIF = FONTS / "EBGaramond-Variable.ttf"
MONO = FONTS / "IBMPlexMono-Regular.ttf"
INK = "0xE8E2D6"
SR = 44100
EPS = 1e-6


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-4000:])
        raise SystemExit(f"[trailer] ffmpeg failed: {' '.join(cmd[:8])} ...")


def check(edit: dict) -> list[str]:
    errors = []
    starts = []
    t = 0.0
    ids = set()
    for c in edit["clips"]:
        if c["id"] in ids:
            errors.append(f"duplicate clip id {c['id']}")
        ids.add(c["id"])
        if c["dur"] <= 0:
            errors.append(f"{c['id']}: dur must be > 0")
        if c.get("fade_in", 0.0) + c.get("fade_out", 0.0) > c["dur"] + EPS:
            errors.append(f"{c['id']}: fades longer than the clip")
        starts.append(t)
        t += c["dur"]
    end = edit["sections"]["end"]
    if abs(t - end) > EPS:
        errors.append(f"clips add up to {t:.3f} s, sections.end is {end}")
    for name, at in edit["sections"].items():
        if name != "end" and not any(abs(at - s) < EPS for s in starts):
            errors.append(f"section {name} at {at} s is not on a cut ({', '.join(f'{s:g}' for s in starts)})")
    for h in edit["hits"]:
        if not any(abs(h - s) < EPS for s in starts):
            errors.append(f"hit at {h} s is not on a cut")
    return errors


def _esc(path: pathlib.Path) -> str:
    """A path inside a filtergraph option."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _text(tmp: pathlib.Path, name: str, text: str, font: pathlib.Path, size: int, y: str, color: str = INK) -> str:
    """A drawtext filter reading its text from a file (no escaping of the card's punctuation)."""
    f = tmp / f"{name}.txt"
    f.write_text(text, encoding="utf-8")
    return (f"drawtext=fontfile='{_esc(font)}':textfile='{_esc(f)}':fontcolor={color}:fontsize={size}"
            f":x=(w-text_w)/2:y={y}")


def _fades(c: dict) -> list[str]:
    out = []
    if c.get("fade_in", 0.0) > 0:
        out.append(f"fade=t=in:st=0:d={c['fade_in']}")
    if c.get("fade_out", 0.0) > 0:
        out.append(f"fade=t=out:st={c['dur'] - c['fade_out']:.4f}:d={c['fade_out']}")
    return out


def _afades(c: dict) -> list[str]:
    out = []
    if c.get("fade_in", 0.0) > 0:
        out.append(f"afade=t=in:st=0:d={c['fade_in']}")
    if c.get("fade_out", 0.0) > 0:
        out.append(f"afade=t=out:st={c['dur'] - c['fade_out']:.4f}:d={c['fade_out']}")
    return out


def _encode_args(fps: int) -> list[str]:
    # Near-lossless intermediates with identical parameters, so the concat needs no re-timing.
    return ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p",
            "-g", str(fps), "-r", str(fps), "-video_track_timescale", str(fps * 1000)]


def clip_video(c: dict, start: float, edit: dict, shots: pathlib.Path, tmp: pathlib.Path, out: pathlib.Path) -> str:
    """Renders one clip to `out` (video only). Returns what it was made from."""
    fps = edit["fps"]
    w, h = edit["size"]
    dur = c["dur"]
    fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    shot_dir = shots / c["id"]
    frames = sorted(shot_dir.glob("frame*.png")) if shot_dir.is_dir() else []
    packed = shot_dir / "shot.mp4"
    if "card" in c:
        vf = [fit]
        if c["card"]:
            if c["id"] == "title":
                vf.append(_text(tmp, c["id"], " ".join(c["card"]), SERIF, 150, "(h-text_h)/2-60"))
                if c.get("subtitle"):
                    vf.append(_text(tmp, c["id"] + "_sub", c["subtitle"], SERIF, 44, "(h)/2+70", "0xB9B2A5"))
                if c.get("footer"):
                    vf.append(_text(tmp, c["id"] + "_foot", c["footer"], SERIF, 28, "h-110", "0x8A8478"))
            else:
                vf.append(_text(tmp, c["id"], c["card"], SERIF, 72, "(h-text_h)/2"))
        src = ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={dur}"]
        made = "card"
    elif packed.is_file() or frames:
        # Movie Maker numbers frames from 0; trim from `in`, hold the last frame if the render is short.
        if packed.is_file():
            src = ["-i", str(packed)]
        else:
            src = ["-framerate", str(fps), "-start_number", frames[0].stem[5:].lstrip("0") or "0",
                   "-i", str(shot_dir / "frame%08d.png")]
        vf = [fit, f"fps={fps}", f"tpad=stop_mode=clone:stop_duration={dur}",
              f"trim=start={c.get('in', 0.0)}:duration={dur}", "setpts=PTS-STARTPTS"]
        made = "packed shot" if packed.is_file() else f"{len(frames)} frames"
    else:
        vf = [fit,
              _text(tmp, c["id"], c["id"], MONO, 64, "(h-text_h)/2-40", "0xC8C8C8"),
              _text(tmp, c["id"] + "_t", f"not rendered yet   {start:.1f}-{start + dur:.1f} s", MONO, 30,
                    "(h)/2+50", "0x808080")]
        src = ["-f", "lavfi", "-i", f"color=c=0x1B1D22:s={w}x{h}:r={fps}:d={dur}"]
        made = "slate"
    vf += _fades(c) + ["format=yuv420p"]
    run(["ffmpeg", "-y", "-v", "error", *src, "-vf", ",".join(vf), "-frames:v", str(round(dur * fps)),
         *_encode_args(fps), str(out)])
    return made


def clip_audio(c: dict, shots: pathlib.Path, out: pathlib.Path) -> None:
    """The shot's own sound (Movie Maker's frame.wav), trimmed like its frames; silence otherwise."""
    dur = c["dur"]
    wav = shots / c["id"] / "frame.wav"
    if "card" not in c and wav.is_file():
        af = [f"aresample={SR}", "aformat=sample_fmts=s16:channel_layouts=stereo",
              f"atrim=start={c.get('in', 0.0)}", "asetpts=PTS-STARTPTS", f"apad=whole_dur={dur}",
              f"atrim=duration={dur}"] + _afades(c)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-af", ",".join(af), str(out)])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-t", f"{dur}",
             "-c:a", "pcm_s16le", str(out)])


def pack(shot_dir: pathlib.Path, fps: int) -> int:
    """Packs a shot's PNG frames into shot.mp4 (and drops the PNGs); frame.wav stays as it is."""
    frames = sorted(shot_dir.glob("frame*.png"))
    if not frames:
        print(f"[trailer] {shot_dir}: no frames to pack", file=sys.stderr)
        return 1
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-start_number", frames[0].stem[5:].lstrip("0") or "0",
         "-i", str(shot_dir / "frame%08d.png"), "-c:v", "libx264", "-preset", "medium", "-crf", "12",
         "-pix_fmt", "yuv420p", "-g", str(fps), str(shot_dir / "shot.mp4")])
    for f in frames:
        f.unlink()
    print(f"[trailer] packed {len(frames)} frames -> {shot_dir / 'shot.mp4'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--edit", default=str(ROOT / "tools/trailer/edit.json"))
    ap.add_argument("--shots", default=str(ROOT / "build/trailer/shots"))
    ap.add_argument("--score", default=str(ROOT / "build/trailer/score.wav"))
    ap.add_argument("--out", default=str(ROOT / "build/trailer/hollowmere_trailer.mp4"))
    ap.add_argument("--game-gain-db", type=float, default=-4.0, help="the shots' own sound under the score")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--pack", metavar="SHOT_DIR", help="pack one rendered shot's frames into shot.mp4 and exit")
    ap.add_argument("--list-shots", action="store_true", help="print the ids of the clips that are shots, as JSON")
    a = ap.parse_args()

    edit = json.loads(pathlib.Path(a.edit).read_text())
    if a.pack:
        return pack(pathlib.Path(a.pack), edit["fps"])
    if a.list_shots:
        print(json.dumps([c["id"] for c in edit["clips"] if "card" not in c]))
        return 0
    errors = check(edit)
    for e in errors:
        print(f"[trailer] edit.json: {e}", file=sys.stderr)
    if errors:
        return 1
    if a.check:
        print(f"[trailer] edit.json ok: {len(edit['clips'])} clips, {edit['sections']['end']:g} s")
        return 0
    if not shutil.which("ffmpeg"):
        print("[trailer] ffmpeg not found", file=sys.stderr)
        return 1

    shots = pathlib.Path(a.shots)
    score = pathlib.Path(a.score)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not score.is_file():
        subprocess.run([sys.executable, str(ROOT / "tools/trailer/score.py"), "--edit", a.edit, "--out", str(score)],
                       check=True)

    end = edit["sections"]["end"]
    with tempfile.TemporaryDirectory(prefix="trailer_") as td:
        tmp = pathlib.Path(td)
        vlist, alist, made = [], [], {}
        t = 0.0
        for i, c in enumerate(edit["clips"]):
            v = tmp / f"{i:02d}.mp4"
            s = tmp / f"{i:02d}.wav"
            made[c["id"]] = clip_video(c, t, edit, shots, tmp, v)
            clip_audio(c, shots, s)
            vlist.append(f"file '{v}'")
            alist.append(f"file '{s}'")
            print(f"[trailer] {t:5.1f} s  {c['id']:<18} {made[c['id']]}")
            t += c["dur"]
        (tmp / "v.txt").write_text("\n".join(vlist) + "\n")
        (tmp / "a.txt").write_text("\n".join(alist) + "\n")
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "v.txt"), "-c", "copy",
             str(tmp / "video.mp4")])
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "a.txt"), "-c", "copy",
             str(tmp / "game.wav")])
        # The score over the shots' own sound, levelled for the web (-14 LUFS, -1.5 dBTP).
        mix = (f"[0:a]volume={a.game_gain_db}dB[g];[1:a]aresample={SR},atrim=duration={end},"
               f"afade=t=out:st={end - 1.5}:d=1.5[m];[g][m]amix=inputs=2:normalize=0:duration=longest,"
               f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample={SR}[a]")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp / "game.wav"), "-i", str(score),
             "-filter_complex", mix, "-map", "[a]", "-t", f"{end}", str(tmp / "mix.wav")])
        run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp / "video.mp4"), "-i", str(tmp / "mix.wav"),
             "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high",
             "-pix_fmt", "yuv420p", "-maxrate", "16M", "-bufsize", "32M", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "-t", f"{end}", str(out)])

    title_at = sum(c["dur"] for c in edit["clips"][:-1]) + 2.0
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{title_at}", "-i", str(out), "-frames:v", "1", "-q:v", "2",
         str(out.with_suffix(".jpg"))])
    rows = int(end + 5) // 6
    run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-vf", f"fps=1,scale=320:-1,tile=6x{rows}:padding=4",
         "-frames:v", "1", "-q:v", "3", str(out.with_name(out.stem + "_sheet.jpg"))])
    slates = [k for k, m in made.items() if m == "slate"]
    size = out.stat().st_size / 1e6
    print(f"[trailer] {out} ({size:.1f} MB, {end:g} s); slates: {len(slates)}" + (f" ({', '.join(slates)})" if slates else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
