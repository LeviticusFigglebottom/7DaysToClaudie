"""Hollowed skeleton: joint layout from body params, bone frames, Blender armature creation and a
small FK/IK toolkit used by the animation library.

Conventions (docs/CHARACTERS.md): armature object "Armature", front = -Y, character's left = +X,
feet at Z = 0, origin between the feet. Bone names are fixed (BONES below).

Pose representation used everywhere in this package: for each bone a 3x3 rotation Q_b expressed in
*rest armature axes* (rotate the bone about its head as if every parent were at rest). The posed
armature-space orientation of a bone is  O_b = Q_root ... Q_parent Q_b R_b  where R_b is the rest
orientation. Blender's local rotation is  basis_b = R_b^T Q_b R_b  (see to_basis()).
"""
from __future__ import annotations

import math

import numpy as np

# name, parent, head joint, tail joint, z-axis hint (armature space)
FRONT = (0.0, -1.0, 0.0)
UP = (0.0, 0.0, 1.0)
BONES = [
    ("root", None, "root", "root_tail", FRONT),
    ("hips", "root", "pelvis", "spine0", FRONT),
    ("spine", "hips", "spine0", "chest0", FRONT),
    ("chest", "spine", "chest0", "neck0", FRONT),
    ("neck", "chest", "neck0", "head0", FRONT),
    ("head", "neck", "head0", "head_top", FRONT),
    ("jaw", "head", "jaw0", "chin", UP),
    ("shoulder.L", "chest", "clav.L", "shoulder.L", FRONT),
    ("upper_arm.L", "shoulder.L", "shoulder.L", "elbow.L", FRONT),
    ("forearm.L", "upper_arm.L", "elbow.L", "wrist.L", FRONT),
    ("hand.L", "forearm.L", "wrist.L", "hand_tip.L", FRONT),
    ("shoulder.R", "chest", "clav.R", "shoulder.R", FRONT),
    ("upper_arm.R", "shoulder.R", "shoulder.R", "elbow.R", FRONT),
    ("forearm.R", "upper_arm.R", "elbow.R", "wrist.R", FRONT),
    ("hand.R", "forearm.R", "wrist.R", "hand_tip.R", FRONT),
    ("thigh.L", "hips", "hip.L", "knee.L", FRONT),
    ("shin.L", "thigh.L", "knee.L", "ankle.L", FRONT),
    ("foot.L", "shin.L", "ankle.L", "ball.L", UP),
    ("toe.L", "foot.L", "ball.L", "toe_tip.L", UP),
    ("thigh.R", "hips", "hip.R", "knee.R", FRONT),
    ("shin.R", "thigh.R", "knee.R", "ankle.R", FRONT),
    ("foot.R", "shin.R", "ankle.R", "ball.R", UP),
    ("toe.R", "foot.R", "ball.R", "toe_tip.R", UP),
]
BONE_NAMES = [b[0] for b in BONES]
PARENT = {b[0]: b[1] for b in BONES}


def _n(v):
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def rot_axis(axis, angle: float) -> np.ndarray:
    """3x3 rotation about a unit axis (right-handed, radians)."""
    x, y, z = _n(axis)
    c, s = math.cos(angle), math.sin(angle)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def rot_between(a, b) -> np.ndarray:
    """Smallest rotation taking direction a to direction b."""
    a, b = _n(a), _n(b)
    v = np.cross(a, b)
    s = float(np.linalg.norm(v))
    c = float(np.dot(a, b))
    if s < 1e-9:
        if c > 0:
            return np.eye(3)
        perp = _n(np.cross(a, (1, 0, 0) if abs(a[0]) < 0.9 else (0, 1, 0)))
        return rot_axis(perp, math.pi)
    return rot_axis(v / s, math.atan2(s, c))


def mat_to_quat(m: np.ndarray) -> np.ndarray:
    """3x3 rotation -> quaternion (w, x, y, z)."""
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z])
    return q / np.linalg.norm(q)


def bone_frame(head, tail, z_hint) -> np.ndarray:
    """Rest orientation (columns = local X, Y, Z in armature space), Y along the bone."""
    y = _n(np.asarray(tail) - np.asarray(head))
    z = np.asarray(z_hint, dtype=np.float64)
    z = _n(z - y * float(np.dot(z, y)))
    if np.linalg.norm(z) < 1e-6:
        z = _n(np.cross(y, (1.0, 0.0, 0.0)))
    x = np.cross(y, z)
    return np.stack([x, y, z], axis=1)


class Skeleton:
    """Joint positions + bone rest frames for one body."""

    def __init__(self, joints: dict[str, np.ndarray], params: dict, bones=None):
        self.j = {k: np.asarray(v, dtype=np.float64) for k, v in joints.items()}
        self.params = params
        self.bones = list(bones or BONES)
        self.parent = {b[0]: b[1] for b in self.bones}
        self.names = [b[0] for b in self.bones]
        self.rest: dict[str, np.ndarray] = {}
        self.head: dict[str, np.ndarray] = {}
        self.tail: dict[str, np.ndarray] = {}
        for name, parent, hj, tj, zh in self.bones:
            self.head[name] = self.j[hj]
            self.tail[name] = self.j[tj]
            self.rest[name] = bone_frame(self.j[hj], self.j[tj], self._zhint(name, zh))

    def _zhint(self, name, zh):
        # Hands: z along the back of the hand (palm normal reversed) so wrist flexion is about x.
        if name.startswith("hand.") and ("palm_back" + name[4:]) in self.j:
            return self.j["palm_back" + name[4:]] - self.j[name.replace("hand", "wrist")]
        if isinstance(zh, str):
            return self.j[zh] - self.j[name.split("|")[0]] if zh in self.j else zh
        return zh

    def length(self, bone: str) -> float:
        return float(np.linalg.norm(self.tail[bone] - self.head[bone]))

    def axis(self, bone: str) -> np.ndarray:
        return self.rest[bone][:, 1]

    # --- forward kinematics ------------------------------------------------------------------
    def fk(self, Q: dict[str, np.ndarray], hips_offset=(0.0, 0.0, 0.0)):
        """Q: bone -> 3x3 rest-axes rotation (missing = identity). hips_offset: armature-space
        translation of the hips bone. Returns (acc_rot, head_pos) dicts for every bone, where
        acc_rot[b] = Q_root ... Q_b (posed orientation = acc_rot[b] @ rest[b])."""
        acc: dict[str, np.ndarray] = {}
        pos: dict[str, np.ndarray] = {}
        for name, parent, *_ in self.bones:
            q = Q.get(name, np.eye(3))
            if parent is None:
                acc[name] = q
                pos[name] = self.head[name].copy()
                continue
            pa = acc[parent]
            rel = self.head[name] - self.head[parent]
            p = pos[parent] + pa @ rel
            if name == "hips" or (name == self.bones[1][0] and "hips" not in self.parent):
                p = p + np.asarray(hips_offset, dtype=np.float64)
            pos[name] = p
            acc[name] = pa @ q
        return acc, pos

    def point(self, acc, pos, bone: str, rest_point) -> np.ndarray:
        """Posed position of a point rigidly attached to `bone` (given in rest armature space)."""
        return pos[bone] + acc[bone] @ (np.asarray(rest_point) - self.head[bone])

    def to_basis(self, bone: str, Q: np.ndarray) -> np.ndarray:
        """Blender pose-bone quaternion (w,x,y,z) for a rest-axes rotation Q."""
        R = self.rest[bone]
        return mat_to_quat(R.T @ Q @ R)

    def hips_location(self, offset) -> np.ndarray:
        """Blender pose location for the hips bone given an armature-space offset (root at rest)."""
        R = self.rest["hips"]
        return R.T @ np.asarray(offset, dtype=np.float64)

    # --- inverse kinematics helpers ----------------------------------------------------------
    def solve_two_bone(self, Q: dict, upper: str, lower: str, target, pole, hips_offset=(0, 0, 0),
                       z_sign: float = 1.0):
        """Sets Q[upper], Q[lower] so the end of `lower` reaches `target` with the middle joint
        displaced towards `pole` (armature-space direction). Both bones get frames whose local Z
        lies in the bend plane (z_sign=+1: Z towards the pole, e.g. knees; -1 for elbows), so the
        middle joint is a pure hinge (no twist between the two bones). Parents of `upper` must
        already be set in Q. Returns the joint position."""
        acc, pos = self.fk(Q, hips_offset)
        parent = self.parent[upper]
        Pp = acc[parent]
        root = pos[upper]
        l1, l2 = self.length(upper), self.length(lower)
        t = np.asarray(target, dtype=np.float64)
        dvec = t - root
        dist = float(np.linalg.norm(dvec))
        dist = min(max(dist, abs(l1 - l2) + 1e-4), (l1 + l2) * 0.9995)
        dirn = _n(dvec)
        pole = np.asarray(pole, dtype=np.float64)
        pole = _n(pole - dirn * float(np.dot(pole, dirn)))
        cos_a = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)
        a = math.acos(max(-1.0, min(1.0, cos_a)))
        upper_dir = dirn * math.cos(a) + pole * math.sin(a)
        joint = root + upper_dir * l1
        lower_dir = _n(root + dirn * dist - joint)
        rest_up = self.rest[upper][:, 1]
        rest_lo = self.rest[lower][:, 1]
        bend = np.cross(rest_up, rest_lo)
        if float(np.linalg.norm(bend)) > 0.14:
            # Bent rest chain: rotate the rest bend plane onto the new one, keeping each bone's
            # roll relative to the plane exactly as modelled (no twist at the rest target).
            n0 = Pp @ _n(bend)
            u0 = Pp @ rest_up
            n1 = -_n(np.cross(dirn, pole))
            u1 = upper_dir
            F0 = np.stack([u0, n0, np.cross(u0, n0)], 1)
            F1 = np.stack([u1, n1, np.cross(u1, n1)], 1)
            Rm = F1 @ F0.T
            Q[upper] = Pp.T @ Rm @ Pp
            acc_up = Pp @ Q[upper]
            cur = acc_up @ rest_lo
            ang = math.atan2(float(np.dot(np.cross(cur, lower_dir), n1)), float(np.dot(cur, lower_dir)))
            Q[lower] = rot_axis(acc_up.T @ n1, ang)
            return joint
        O_up = self._hinge_frame(upper, upper_dir, pole * z_sign)
        Q[upper] = Pp.T @ O_up @ self.rest[upper].T
        acc_up = Pp @ Q[upper]
        O_lo = self._hinge_frame(lower, lower_dir, pole * z_sign)
        Q[lower] = acc_up.T @ O_lo @ self.rest[lower].T
        return joint

    def _hinge_frame(self, bone, ydir, zhint):
        """Orientation with Y along ydir and Z as close as possible to zhint, but keeping the
        rest pose's small roll offset (the rest Z is not always exactly the bend direction)."""
        y = _n(ydir)
        z = _n(zhint - y * float(np.dot(zhint, y)))
        x = np.cross(y, z)
        return np.stack([x, y, z], axis=1)

    def aim(self, Q: dict, bone: str, direction, zhint, hips_offset=(0, 0, 0)):
        """Sets Q[bone] so the bone points along `direction` with local Z towards zhint."""
        acc, _ = self.fk(Q, hips_offset)
        Pp = acc[self.parent[bone]]
        O = self._hinge_frame(bone, direction, np.asarray(zhint, dtype=np.float64))
        Q[bone] = Pp.T @ O @ self.rest[bone].T


def build_joints(p: dict) -> dict[str, np.ndarray]:
    """Joint positions for body params (rest pose: A-pose, posture baked in).

    params: height, sex ('m'|'f'), build (0 gaunt..1 heavy), arm_scale, leg_scale, hunch (0..1),
    head_forward, shoulder_drop (+ = left lower), arm_angle (deg from vertical), elbow_bend (deg),
    stance (ankle half-spacing / H), toe_out (deg), jaw_drop (deg), jaw_scale.
    """
    H = float(p.get("height", 1.75))
    sex = p.get("sex", "m")
    fem = 1.0 if sex == "f" else 0.0
    arm_s = float(p.get("arm_scale", 1.0))
    leg_s = float(p.get("leg_scale", 1.0))
    build = float(p.get("build", 0.3))
    # Bloom-thickened bulk (the Rammer): a yoke of shoulders, a wide pelvis, built into the frame
    # instead of scaling the body in the game (which stretched the head and pushed the arms out).
    mass = float(np.clip(p.get("mass", 0.0), 0.0, 1.0))
    j: dict[str, np.ndarray] = {}
    a = np.array
    # --- legs (heights as fractions of stature, scaled by leg_scale about the ground) ---------
    hip_z = 0.522 * H * (0.94 + 0.06 * leg_s) * (1.0 + (leg_s - 1.0) * 0.6)
    leg_len = hip_z - 0.042 * H
    knee_z = 0.042 * H + leg_len * 0.505
    hip_x = (0.050 + 0.006 * fem + 0.004 * build) * H * (1.0 + 0.22 * mass)
    ankle_x = float(p.get("stance", 0.068)) * H
    for side, sx in (("L", 1.0), ("R", -1.0)):
        j[f"hip.{side}"] = a([sx * hip_x, 0.0, hip_z])
        knee_x = sx * (hip_x * 0.55 + ankle_x * 0.45)
        j[f"knee.{side}"] = a([knee_x, -0.008 * H, knee_z])
        j[f"ankle.{side}"] = a([sx * ankle_x, 0.010 * H, 0.042 * H])
        toe = math.radians(float(p.get("toe_out", 8.0)))
        fwd = a([sx * math.sin(toe), -math.cos(toe), 0.0])
        anc = j[f"ankle.{side}"]
        j[f"ball.{side}"] = anc + fwd * 0.082 * H + a([0, 0, -0.030 * H])
        j[f"toe_tip.{side}"] = anc + fwd * 0.118 * H + a([0, 0, -0.035 * H])
        j[f"heel.{side}"] = anc - fwd * 0.034 * H + a([0, 0, -0.030 * H])
    # --- spine (neutral, then posture rotations) ---------------------------------------------
    top_scale = (H - hip_z) / (H * (1 - 0.522))
    def zt(f):  # height fraction above the hips mapped into the trunk span
        return hip_z + (f * H - 0.522 * H) * top_scale
    j["pelvis"] = a([0.0, 0.012 * H, zt(0.548)])
    j["spine0"] = a([0.0, 0.020 * H, zt(0.600)])
    j["chest0"] = a([0.0, 0.020 * H, zt(0.690)])
    j["neck0"] = a([0.0, 0.016 * H, zt(0.818)])
    j["head0"] = a([0.0, 0.010 * H, zt(0.884)])
    j["head_top"] = a([0.0, 0.010 * H, zt(0.990)])
    j["jaw0"] = a([0.0, -0.006 * H, zt(0.913)])
    jaw_len = 0.062 * H * float(p.get("jaw_scale", 1.0))
    jd = math.radians(float(p.get("jaw_drop", 6.0)))
    jdir = a([0.0, -math.cos(math.radians(33) + jd), -math.sin(math.radians(33) + jd)])
    j["chin"] = j["jaw0"] + jdir * jaw_len
    # head geometry anchors (for the face builder)
    sw = (0.101 - 0.010 * fem + 0.004 * build) * H * (1.0 + 0.30 * mass)
    j["clav.L"] = a([0.012 * H, -0.010 * H, zt(0.812)])
    j["clav.R"] = a([-0.012 * H, -0.010 * H, zt(0.812)])
    # the yoke rides high round a short neck
    j["shoulder.L"] = a([sw, 0.004 * H, zt(0.806 + 0.010 * mass)])
    j["shoulder.R"] = a([-sw, 0.004 * H, zt(0.806 + 0.010 * mass)])
    # --- arms (A-pose) -------------------------------------------------------------------------
    ang = math.radians(float(p.get("arm_angle", 47.0)))
    fwd_tilt = math.radians(8.0)
    eb = math.radians(float(p.get("elbow_bend", 14.0)))
    l_ua = 0.186 * H * arm_s
    l_fa = 0.150 * H * arm_s
    l_h = 0.100 * H * (0.97 + 0.03 * arm_s)
    for side, sx in (("L", 1.0), ("R", -1.0)):
        d_ua = _n(a([sx * math.sin(ang), -math.sin(fwd_tilt), -math.cos(ang)]))
        j[f"elbow.{side}"] = j[f"shoulder.{side}"] + d_ua * l_ua
        # forearm bends forward (rotation taking d_ua towards -Y)
        bend_axis = _n(np.cross(d_ua, a([0.0, -1.0, 0.0])))
        d_fa = rot_axis(bend_axis, eb) @ d_ua
        j[f"wrist.{side}"] = j[f"elbow.{side}"] + d_fa * l_fa
        d_h = _n(d_fa * 0.85 + a([-sx * 0.15, -0.05, -0.1]))
        j[f"hand_tip.{side}"] = j[f"wrist.{side}"] + d_h * l_h
        # back of the hand faces outward-back; palm faces the thigh
        out = _n(a([sx * math.cos(ang), 0.15, math.sin(ang)]))
        j[f"palm_back.{side}"] = j[f"wrist.{side}"] + _n(out - d_h * float(np.dot(out, d_h))) * 0.05
    j["root"] = a([0.0, 0.0, 0.0])
    j["root_tail"] = a([0.0, 0.0, 0.12 * H / 1.75])

    # --- posture: rotate chains about their joints (hunch / head forward / shoulder drop) -----
    hunch = float(p.get("hunch", 0.0))
    head_fwd = float(p.get("head_forward", 0.0))
    upper = ["chest0", "neck0", "head0", "head_top", "jaw0", "chin", "clav.L", "clav.R"]
    arm_names = [k for k in j if k.endswith((".L", ".R")) and k.split(".")[0] in
                 ("shoulder", "elbow", "wrist", "hand_tip", "palm_back")]
    upper += arm_names

    def rotate(names, pivot, R):
        for k in names:
            j[k] = pivot + R @ (j[k] - pivot)

    # Positive rotation about +X tips points above the pivot forward (-Y).
    # lumbar flex (small), thoracic kyphosis (main), neck forward, head extension to look ahead
    rotate(upper, j["spine0"].copy(), rot_axis((1, 0, 0), math.radians(6.0 * hunch)))
    rotate([k for k in upper if k != "chest0"], j["chest0"].copy(), rot_axis((1, 0, 0), math.radians(16.0 * hunch)))
    neck_names = ["head0", "head_top", "jaw0", "chin"]
    rotate(neck_names, j["neck0"].copy(), rot_axis((1, 0, 0), math.radians(18.0 * hunch + 22.0 * head_fwd)))
    rotate(["head_top", "jaw0", "chin"], j["head0"].copy(),
           rot_axis((1, 0, 0), -math.radians(34.0 * hunch + 20.0 * head_fwd)))
    # shoulders roll forward a little with the hunch; optional asymmetric drop
    for side, sx in (("L", 1.0), ("R", -1.0)):
        names = [k for k in arm_names if k.endswith("." + side)]
        piv = j[f"clav.{side}"].copy()
        drop = float(p.get("shoulder_drop", 0.0)) * (1 if side == "L" else -1)
        R = rot_axis((0, 0, 1), -sx * math.radians(10.0 * hunch)) @ rot_axis((0, 1, 0), sx * math.radians(6.0 * drop))
        rotate(names, piv, R)
    return j


def create_armature(skel: Skeleton, name: str = "Armature"):
    """Creates the Blender armature object (all bones deform) matching skel.rest frames."""
    import bpy
    from mathutils import Vector

    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for bname, parent, *_ in skel.bones:
        eb = data.edit_bones.new(bname)
        eb.head = Vector(skel.head[bname])
        eb.tail = Vector(skel.tail[bname])
        eb.align_roll(Vector(skel.rest[bname][:, 2]))
        eb.use_deform = True
        if parent is not None:
            eb.parent = ebs[parent]
            eb.use_connect = False
        ebs[bname] = eb
    bpy.ops.object.mode_set(mode="OBJECT")
    # Sync rest frames with what Blender actually stored (roll quantization).
    for b in data.bones:
        m = b.matrix_local
        skel.rest[b.name] = np.array([[m[r][c] for c in range(3)] for r in range(3)])
    return obj
