"""Canonical paths. Generated assets live under game/assets/generated (gitignored)."""
from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
GAME = ROOT / "game"
# HM_GEN_ROOT redirects outputs (used by --check-determinism to rebuild into a scratch dir).
GEN_ROOT = pathlib.Path(os.environ["HM_GEN_ROOT"]) if os.environ.get("HM_GEN_ROOT") else GAME / "assets" / "generated"
TOOLS = ROOT / "tools"
ASSETGEN = TOOLS / "assetgen"
BLENDER_SCRIPTS = ASSETGEN / "blender"
DATA = GAME / "data"
MANIFEST = GEN_ROOT / "manifest.json"
DOCS_IMAGES = ROOT / "docs" / "images"


def gen_path(rel: str) -> pathlib.Path:
    """Absolute path of a generated output given its path relative to GEN_ROOT."""
    return GEN_ROOT / rel


def res_path(abs_path: pathlib.Path) -> str:
    """Godot res:// path for a file inside the game project (or its canonical twin when redirected)."""
    p = abs_path.resolve()
    try:
        return "res://" + p.relative_to(GAME.resolve()).as_posix()
    except ValueError:
        rel = p.relative_to(GEN_ROOT.resolve()).as_posix()
        return "res://assets/generated/" + rel
