"""Quadruped skeleton (ADR-0027): one bone layout for every four-legged animal (deer, hare, the
Hollowed hound), joint tables per species, built on the character toolkit (char_skel.Skeleton, create_armature).

Conventions are the Hollowed's (docs/CHARACTERS.md): armature object "Armature", front = -Y,
the animal's left = +X, ground at Z = 0, origin under the body's middle. The pelvis bone is named
`hips` so char_anim.write_action keys its translation like a Hollowed's.

Bones (exactly):
  root, hips, spine, chest, neck, neck2, head, jaw, ear.L, ear.R, tail,
  scapula.S, upper_arm.S, forearm.S, cannon_f.S, hoof_f.S          (front legs, S = L / R)
  thigh.S, shin.S, cannon_h.S, hoof_h.S                             (hind legs)
`hoof_*` ends at the toe tip on the ground (a deer's hoof, a hare's toes); `cannon_*` is the
metacarpus / metatarsus (a hare's long hind foot lies almost flat in the rest crouch).

The hound (a dog: digitigrade) maps the same names onto a dog's limbs: `scapula` is a long,
sloping shoulder blade, `upper_arm` the humerus running back from the point of the shoulder to an
elbow tucked against the brisket, `forearm` the radius down to the wrist (`carpus`), `cannon_f`
the short front pastern and `hoof_f` the paw (toes and pads flat on the ground); behind, `shin`
runs back to the hock, `cannon_h` is the near-vertical rear pastern and `hoof_h` the hind paw. A
dog's long tail gets a second bone, `tail2` (hound only: deer and hare keep the layout above).
"""
from __future__ import annotations

import numpy as np

from .char_skel import Skeleton

FRONT = (0.0, -1.0, 0.0)
UP = (0.0, 0.0, 1.0)


def _bones():
    b = [
        ("root", None, "root", "root_tail", FRONT),
        ("hips", "root", "pelvis", "spine0", UP),
        ("spine", "hips", "spine0", "chest0", UP),
        ("chest", "spine", "chest0", "neck0", UP),
        ("neck", "chest", "neck0", "neck1", FRONT),
        ("neck2", "neck", "neck1", "head0", FRONT),
        ("head", "neck2", "head0", "nose", UP),
        ("jaw", "head", "jaw0", "chin", UP),
        ("tail", "hips", "tail0", "tail1", UP),
    ]
    for s in ("L", "R"):
        b += [
            (f"ear.{s}", "head", f"ear0.{s}", f"ear1.{s}", FRONT),
            (f"scapula.{s}", "chest", f"scap0.{s}", f"shoulder.{s}", FRONT),
            (f"upper_arm.{s}", f"scapula.{s}", f"shoulder.{s}", f"elbow.{s}", FRONT),
            (f"forearm.{s}", f"upper_arm.{s}", f"elbow.{s}", f"carpus.{s}", FRONT),
            (f"cannon_f.{s}", f"forearm.{s}", f"carpus.{s}", f"fetlock_f.{s}", FRONT),
            (f"hoof_f.{s}", f"cannon_f.{s}", f"fetlock_f.{s}", f"toe_f.{s}", UP),
            (f"thigh.{s}", "hips", f"hip.{s}", f"stifle.{s}", FRONT),
            (f"shin.{s}", f"thigh.{s}", f"stifle.{s}", f"hock.{s}", FRONT),
            (f"cannon_h.{s}", f"shin.{s}", f"hock.{s}", f"fetlock_h.{s}", FRONT),
            (f"hoof_h.{s}", f"cannon_h.{s}", f"fetlock_h.{s}", f"toe_h.{s}", UP),
        ]
    return b


BONES = _bones()
BONE_NAMES = [b[0] for b in BONES]
# The hound's tail curls and tucks: one more bone after `tail` (appended, so every shared bone
# keeps its index).
HOUND_BONES = BONES + [("tail2", "tail", "tail1", "tail2", UP)]
FRONT_LEG = ("scapula", "upper_arm", "forearm", "cannon_f", "hoof_f")
HIND_LEG = ("thigh", "shin", "cannon_h", "hoof_h")

# Joint tables at scale 1 (metres; x is the left side, mirrored for R). A white-tailed doe of
# about 0.95 m at the withers and 1.75 m nose to tail; a snowshoe hare in its rest crouch.
_DEER = {
    "root": (0, 0.0, 0.0), "root_tail": (0, -0.2, 0.0),
    "pelvis": (0, 0.40, 0.90), "spine0": (0, 0.14, 0.93), "chest0": (0, -0.16, 0.95),
    "neck0": (0, -0.40, 0.90), "neck1": (0, -0.53, 1.12), "head0": (0, -0.60, 1.34),
    "nose": (0, -0.86, 1.22), "jaw0": (0, -0.63, 1.29), "chin": (0, -0.82, 1.18),
    "tail0": (0, 0.54, 0.91), "tail1": (0, 0.66, 0.80),
    "ear0": (0.056, -0.588, 1.392), "ear1": (0.172, -0.565, 1.515),
    "scap0": (0.075, -0.25, 1.02), "shoulder": (0.115, -0.37, 0.78), "elbow": (0.12, -0.28, 0.58),
    "carpus": (0.115, -0.30, 0.32), "fetlock_f": (0.11, -0.31, 0.095), "toe_f": (0.11, -0.37, 0.0),
    "hip": (0.10, 0.37, 0.86), "stifle": (0.125, 0.22, 0.60), "hock": (0.115, 0.44, 0.42),
    "fetlock_h": (0.105, 0.40, 0.095), "toe_h": (0.105, 0.34, 0.0),
}
_HARE = {
    "root": (0, 0.0, 0.0), "root_tail": (0, -0.08, 0.0),
    "pelvis": (0, 0.115, 0.205), "spine0": (0, 0.04, 0.225), "chest0": (0, -0.05, 0.215),
    "neck0": (0, -0.115, 0.205), "neck1": (0, -0.145, 0.225), "head0": (0, -0.165, 0.250),
    "nose": (0, -0.245, 0.215), "jaw0": (0, -0.175, 0.230), "chin": (0, -0.232, 0.196),
    "tail0": (0, 0.165, 0.205), "tail1": (0, 0.200, 0.215),
    "ear0": (0.018, -0.170, 0.290), "ear1": (0.038, -0.120, 0.378),
    "scap0": (0.026, -0.055, 0.215), "shoulder": (0.036, -0.088, 0.150), "elbow": (0.040, -0.068, 0.095),
    "carpus": (0.038, -0.088, 0.032), "fetlock_f": (0.037, -0.100, 0.012), "toe_f": (0.037, -0.125, 0.0),
    "hip": (0.040, 0.105, 0.185), "stifle": (0.052, 0.035, 0.125), "hock": (0.050, 0.140, 0.040),
    "fetlock_h": (0.048, 0.030, 0.014), "toe_h": (0.048, -0.020, 0.0),
}
# A gaunt Hollowed hound: a rangy lab/hound mongrel of about 0.62 m at the withers, 0.66 m from
# the point of the shoulder to the buttock, head carried level with the back. Digitigrade: wrists
# and hocks well off the ground, paws flat. The elbow sits back under the brisket; the long tail
# hangs low.
_HOUND = {
    "root": (0, 0.0, 0.0), "root_tail": (0, -0.2, 0.0),
    "pelvis": (0, 0.215, 0.545), "spine0": (0, 0.03, 0.565), "chest0": (0, -0.15, 0.565),
    "neck0": (0, -0.255, 0.545), "neck1": (0, -0.325, 0.630), "head0": (0, -0.370, 0.705),
    "nose": (0, -0.605, 0.652), "jaw0": (0, -0.405, 0.668), "chin": (0, -0.575, 0.618),
    "tail0": (0, 0.330, 0.555), "tail1": (0, 0.395, 0.425), "tail2": (0, 0.415, 0.255),
    "ear0": (0.052, -0.392, 0.738), "ear1": (0.093, -0.428, 0.625),
    "scap0": (0.045, -0.140, 0.600), "shoulder": (0.072, -0.268, 0.468), "elbow": (0.078, -0.192, 0.335),
    "carpus": (0.068, -0.200, 0.118), "fetlock_f": (0.066, -0.222, 0.034), "toe_f": (0.066, -0.272, 0.0),
    "hip": (0.064, 0.240, 0.505), "stifle": (0.080, 0.150, 0.345), "hock": (0.074, 0.292, 0.150),
    "fetlock_h": (0.070, 0.276, 0.034), "toe_h": (0.070, 0.226, 0.0),
}
# A shepherd-type (scaled to 0.70 m by params): a longer body and a croup that falls away to
# well-angulated hind legs, a longer muzzle, and pricked ears standing up off the skull.
_HOUND_SHEPHERD = dict(_HOUND, **{
    "pelvis": (0, 0.235, 0.528), "spine0": (0, 0.04, 0.560), "tail0": (0, 0.352, 0.520),
    "tail1": (0, 0.415, 0.395), "tail2": (0, 0.430, 0.230),
    "nose": (0, -0.630, 0.668), "chin": (0, -0.598, 0.628),
    "ear0": (0.042, -0.390, 0.772), "ear1": (0.085, -0.368, 0.870),
    "hip": (0.064, 0.262, 0.485), "stifle": (0.080, 0.165, 0.320), "hock": (0.074, 0.330, 0.140),
    "fetlock_h": (0.070, 0.316, 0.034), "toe_h": (0.070, 0.266, 0.0),
})
TABLES = {"deer": _DEER, "hare": _HARE, "hound": _HOUND}


def build_joints(p: dict) -> dict[str, np.ndarray]:
    """Joint positions for params: species (deer / hare / hound) and scale (uniform: a buck is a
    bigger doe; its bulk is the body's, not the skeleton's). A hound's `breed` "shepherd" picks the
    shepherd table."""
    table = TABLES[p.get("species", "deer")]
    if p.get("species") == "hound" and p.get("breed") == "shepherd":
        table = _HOUND_SHEPHERD
    s = float(p.get("scale", 1.0))
    j: dict[str, np.ndarray] = {}
    for k, v in table.items():
        v = np.asarray(v, dtype=np.float64) * s
        if abs(v[0]) > 1e-9:
            j[f"{k}.L"] = v.copy()
            j[f"{k}.R"] = v * np.array([-1.0, 1.0, 1.0])
        else:
            j[k] = v
    return j


def bones_for(p: dict):
    return HOUND_BONES if p.get("species") == "hound" else BONES


def make_skeleton(p: dict) -> Skeleton:
    return Skeleton(build_joints(p), p, bones=bones_for(p))


def side_of(bone: str) -> float:
    """+1 left, -1 right, 0 on the midline."""
    if bone.endswith(".L"):
        return 1.0
    if bone.endswith(".R"):
        return -1.0
    return 0.0
