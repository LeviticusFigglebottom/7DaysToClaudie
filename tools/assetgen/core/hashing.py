"""Stable hashing shared with the game (Ids.hash64 in GDScript uses the same FNV-1a)."""
from __future__ import annotations

import hashlib
import json
import pathlib

FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
MASK64 = 0xFFFFFFFFFFFFFFFF


def fnv1a64(s: str) -> int:
    """64-bit FNV-1a over UTF-8, unsigned. GDScript Ids.hash64 returns the signed equivalent."""
    h = FNV_OFFSET
    for b in s.encode("utf-8"):
        h = ((h ^ b) * FNV_PRIME) & MASK64
    return h


def signed64(u: int) -> int:
    return u - (1 << 64) if u >= (1 << 63) else u


def seed_for(*parts: object) -> int:
    """Deterministic 32-bit seed from arbitrary parts (for numpy / random)."""
    return fnv1a64("|".join(str(p) for p in parts)) & 0xFFFFFFFF


def file_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_inputs(files: list[pathlib.Path], params: dict) -> str:
    """Hash of source files (content) + params; changes when anything that affects output changes."""
    h = hashlib.sha256()
    for f in sorted(set(files)):
        h.update(f.as_posix().encode())
        h.update(f.read_bytes() if f.exists() else b"<missing>")
    h.update(json.dumps(params, sort_keys=True, default=str).encode())
    return h.hexdigest()
