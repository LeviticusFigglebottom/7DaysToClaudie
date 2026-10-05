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
    Only the tasks this process recorded or adopted (`mark`) go over the file's current state:
    writing back every entry loaded at start-up reverted what other builds had recorded since,
    and their finished tasks showed as todo again. A lock file serialises the read-merge-replace,
    so two builds saving at once can't drop each other's entries."""
    import os
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:  # pragma: no cover (non-POSIX): unlocked merge
        fcntl = None
    with open(MANIFEST.with_suffix(".lock"), "w") as lf:
        if fcntl is not None:
            fcntl.flock(lf, fcntl.LOCK_EX)
        current = load()
        for name in data.get("_dirty", ()):
            if name in data["tasks"]:
                current["tasks"][name] = data["tasks"][name]
        tmp = MANIFEST.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
        os.replace(tmp, MANIFEST)


def mark(data: dict, name: str) -> None:
    """Notes that this process changed `name`'s entry, so save() writes it (and nothing else)."""
    data.setdefault("_dirty", set()).add(name)


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
    mark(data, name)
