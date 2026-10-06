#!/usr/bin/env python3
"""Lists the files in a Godot 4 .pck (pack formats 2-4) without Godot.

Usage: pck_list.py PACK [--require PREFIX ...] [--forbid PREFIX ...]
Prints one res:// path per line, or with --require/--forbid only checks: every PREFIX given with
--require must start at least one path, no path may start with a --forbid PREFIX (exit 1 if not).
CI uses it to prove an exported build carries the generated assets and leaves the tests out
(ADR-0036).
"""
import argparse
import struct
import sys


def list_pck(path: str) -> list[str]:
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"GDPC":
        raise SystemExit(f"{path}: not a Godot pack")
    fmt, _major, _minor, _patch, flags = struct.unpack_from("<5I", data, 4)
    if fmt < 2 or fmt > 4:
        raise SystemExit(f"{path}: unsupported pack format {fmt}")
    if flags & 1:
        raise SystemExit(f"{path}: encrypted directory")
    if fmt >= 3:
        # Format 3+: file base and directory offset follow the flags; the directory is at the end.
        _file_base, dir_offset = struct.unpack_from("<QQ", data, 24)
        pos = dir_offset
    else:
        pos = 24 + 8 + 16 * 4
    (count,) = struct.unpack_from("<I", data, pos)
    pos += 4
    out = []
    for _ in range(count):
        (plen,) = struct.unpack_from("<I", data, pos)
        pos += 4
        name = data[pos:pos + plen].rstrip(b"\0").decode("utf-8")
        pos += plen
        pos += 8 + 8 + 16 + 4  # offset, size, md5, flags
        out.append(name if name.startswith("res://") else "res://" + name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pack")
    ap.add_argument("--require", action="append", default=[])
    ap.add_argument("--forbid", action="append", default=[])
    a = ap.parse_args()
    files = list_pck(a.pack)
    if not a.require and not a.forbid:
        print("\n".join(files))
        return 0
    bad = 0
    for p in a.require:
        n = sum(1 for f in files if f.startswith(p))
        print(f"[pck] {n:6d} files under {p}")
        if n == 0:
            print(f"[pck] MISSING: nothing under {p}", file=sys.stderr)
            bad += 1
    for p in a.forbid:
        hits = [f for f in files if f.startswith(p)]
        if hits:
            print(f"[pck] FORBIDDEN: {len(hits)} files under {p} (e.g. {hits[0]})", file=sys.stderr)
            bad += 1
    print(f"[pck] {len(files)} files in {a.pack}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
