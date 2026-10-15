#!/usr/bin/env python3
"""Cuts a trailer shot out of a Movie Maker recording (tools/trailer_shot.sh).

    trailer_cut.py <raw dir> <dest dir> <frames>

The recording starts at launch; the runner (src/tools/cli/trailer_runner.gd) draws one solid
magenta MARKER frame just before the shot. This finds the last marker frame, moves the <frames>
frames after it into <dest> as frame00000000.png ..., and cuts frame.wav at the same frame (Movie
Maker writes mix_rate / fps samples a frame). The WAV header's sizes are not trusted: a run ended
by the exit watchdog never wrote them.
"""
import os
import shutil
import struct
import sys

from PIL import Image


def is_marker(path: str) -> bool:
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        for x, y in ((w // 4, h // 4), (w // 2, h // 2), (3 * w // 4, 3 * h // 4)):
            r, g, b = im.getpixel((x, y))
            if not (r > 240 and g < 15 and b > 240):
                return False
    return True


def read_wav(path: str):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise SystemExit("trailer_cut: %s is not a WAV" % path)
    pos = 12
    fmt = None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            fmt = data[pos + 8:pos + 8 + size]
        elif cid == b"data":
            return fmt, data[pos + 8:]
        pos += 8 + size + (size & 1)
    raise SystemExit("trailer_cut: %s has no data chunk" % path)


def write_wav(path: str, fmt: bytes, pcm: bytes) -> None:
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(pcm)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"data" + struct.pack("<I", len(pcm)) + pcm)


def main() -> None:
    raw, dest, frames = sys.argv[1], sys.argv[2], int(sys.argv[3])
    names = sorted(n for n in os.listdir(raw) if n.startswith("frame") and n.endswith(".png"))
    marker = -1
    # The marker sits <frames> (plus the few frames of the quit) from the end: search backwards.
    for i in range(len(names) - 1, -1, -1):
        if is_marker(os.path.join(raw, names[i])):
            marker = i
            break
    if marker < 0:
        raise SystemExit("trailer_cut: no marker frame in %s" % raw)
    shot = names[marker + 1:marker + 1 + frames]
    if len(shot) < frames:
        raise SystemExit("trailer_cut: only %d of %d frames after the marker" % (len(shot), frames))
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    for k, n in enumerate(shot):
        os.replace(os.path.join(raw, n), os.path.join(dest, "frame%08d.png" % k))
    wav = os.path.join(raw, "frame.wav")
    if os.path.exists(wav):
        fmt, pcm = read_wav(wav)
        channels, rate, _, block = struct.unpack("<HIIH", fmt[2:14])
        per_frame = rate // 30 * block
        first = int(names[marker + 1][5:-4])
        write_wav(os.path.join(dest, "frame.wav"), fmt, pcm[first * per_frame:(first + frames) * per_frame])
    print("trailer_cut: %s: %d frames after marker frame %d" % (os.path.basename(dest), frames, marker))


if __name__ == "__main__":
    main()
