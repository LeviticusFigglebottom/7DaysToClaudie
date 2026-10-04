"""Build manifest: which input hash produced which outputs (and their sha256)."""
from __future__ import annotations

import json
import time

from .hashing import file_sha256
from .paths import MANIFEST, gen_path

VERSION = 1


def load() -> dict:
    if MANIFEST.exists():
        try:
            data = json.loads(MANIFEST.read_text())
            if data.get("version") == VERSION:
                return data
        except json.JSONDecodeError:
            pass
    return {"version": VERSION, "tasks": {}}


def save(data: dict) -> None:
    """Atomic write (several builds may run concurrently; a reader never sees a partial file).
    Merges with entries written by other processes since we loaded."""
    import os
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    current = load()
    current["tasks"].update(data["tasks"])
    tmp = MANIFEST.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, MANIFEST)


def is_current(data: dict, name: str, input_hash: str, outputs: list[str]) -> bool:
    entry = data["tasks"].get(name)
    if not entry or entry.get("hash") != input_hash:
        return False
    return all(gen_path(o).exists() for o in outputs)


def record(data: dict, name: str, input_hash: str, outputs: list[str]) -> None:
    data["tasks"][name] = {
        "hash": input_hash,
        "outputs": {o: file_sha256(gen_path(o)) for o in outputs if gen_path(o).exists()},
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
