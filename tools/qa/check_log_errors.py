#!/usr/bin/env python3
"""Fail on engine/script errors in a headless Godot log (TD-103).

Usage: check_log_errors.py LOG [LOG ...] [--allowlist FILE]

A line is an error when it is Godot's `ERROR:` / `SCRIPT ERROR:` (push_error, engine errors) or
our own `Log.error` line (`[ERROR][tag] ...`). Lines matching any regex in the allowlist
(default: log_error_allowlist.txt next to this script; one Python regex per line, `#` comments,
blank lines ignored) are known engine noise and do not count. Prints every offending line with its
line number and the engine's `at:` line that follows it, and exits 1 if there is any (2 when a log
is missing, so a run that never wrote its log cannot pass).

Why: headless runs used to log errors that never failed CI, e.g. meshes made on worker threads
under the dummy renderer ("Attempting to initialize the wrong RID"). A new one should fail the
build the day it appears, not show up later as noise.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ERROR_RE = re.compile(r"(^|\s)(SCRIPT )?ERROR:|^\[ERROR\]")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def load_allowlist(path: Path) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    if not path.exists():
        return patterns
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line))
        except re.error as e:
            sys.exit(f"[check_log_errors] {path}:{n}: bad regex {line!r}: {e}")
    return patterns


def check(log: Path, allow: list[re.Pattern[str]]) -> tuple[int, int]:
    """Returns (offending, allowed) counts after printing the offending lines."""
    lines = [ANSI_RE.sub("", l) for l in log.read_text(encoding="utf-8", errors="replace").splitlines()]
    bad = allowed = 0
    for i, line in enumerate(lines):
        if not ERROR_RE.search(line):
            continue
        if any(p.search(line) for p in allow):
            allowed += 1
            continue
        bad += 1
        print(f"{log}:{i + 1}: {line.strip()}")
        if i + 1 < len(lines) and lines[i + 1].lstrip().startswith("at:"):
            print(f"    {lines[i + 1].strip()}")
    return bad, allowed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument("--allowlist", type=Path, default=Path(__file__).with_name("log_error_allowlist.txt"))
    args = ap.parse_args()
    allow = load_allowlist(args.allowlist)
    total = 0
    for log in args.logs:
        if not log.is_file():
            print(f"[check_log_errors] FAIL: no log at {log}", file=sys.stderr)
            return 2
        bad, allowed = check(log, allow)
        total += bad
        note = f" ({allowed} allowlisted)" if allowed else ""
        status = "FAIL" if bad else "ok"
        print(f"[check_log_errors] {status}: {log}: {bad} error line(s){note}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
