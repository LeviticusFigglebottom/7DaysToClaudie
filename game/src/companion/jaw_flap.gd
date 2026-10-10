class_name JawFlap
extends SkeletonModifier3D
## Opens a body's jaw while it speaks (TD-309): after the animation has posed the skeleton, turns
## the "jaw" bone down by `open` (0..1) of MAX_DEG about its own x axis. CompanionMind drives
## `open` from the loudness of the voice line playing (envelope()), so the mouth moves with the
## syllables and shuts in the pauses.

const MAX_DEG: float = 13.0
## Loudness frames a second in an envelope.
const RATE: float = 30.0

var open: float = 0.0
var _bone: int = -2

static var _envelopes: Dictionary = {}


func _process_modification() -> void:
	var sk: Skeleton3D = get_skeleton()
	if sk == null or open <= 0.001:
		return
	if _bone == -2:
		_bone = sk.find_bone("jaw")
	if _bone < 0:
		return
	var q: Quaternion = sk.get_bone_pose_rotation(_bone)
	# About the bone's -x: the jaw bone's x axis (char_skel's frame) turns a +x rotation up into the
	# skull (test_jaw_flap measures the chin dropping).
	sk.set_bone_pose_rotation(_bone, q * Quaternion(Vector3.RIGHT, -deg_to_rad(MAX_DEG * clampf(open, 0.0, 1.0))))


## The loudness of a voice line, RATE frames a second, 0..1 (its loudest frame 1), read once from
## its samples. Empty for a stream it can't read (then the jaw keeps still).
static func envelope(stream: AudioStream) -> PackedFloat32Array:
	var key: String = stream.resource_path if stream.resource_path != "" else str(stream.get_instance_id())
	if _envelopes.has(key):
		return _envelopes[key]
	var out := PackedFloat32Array()
	var wav := stream as AudioStreamWAV
	if wav != null and wav.format == AudioStreamWAV.FORMAT_16_BITS:
		var data: PackedByteArray = wav.data
		var ch: int = 2 if wav.stereo else 1
		var frames: int = data.size() / (2 * ch)
		var step: int = maxi(1, int(float(wav.mix_rate) / RATE))
		var peak: float = 0.0
		var i: int = 0
		while i < frames:
			var acc: float = 0.0
			var n: int = 0
			var j: int = i
			while j < mini(i + step, frames):
				var v: float = float(data.decode_s16(j * 2 * ch)) / 32768.0
				acc += v * v
				n += 1
				j += 4  # every 4th sample: plenty for a loudness
			var rms: float = sqrt(acc / maxf(1.0, float(n)))
			out.append(rms)
			peak = maxf(peak, rms)
			i += step
		if peak > 0.0:
			for k: int in out.size():
				# A little gate: the reverb tail and breath leave the mouth shut.
				out[k] = clampf((out[k] / peak - 0.12) / 0.88, 0.0, 1.0)
	_envelopes[key] = out
	return out


## The envelope at `t` seconds (0 past its end).
static func at(env: PackedFloat32Array, t: float) -> float:
	var k: int = int(t * RATE)
	return env[k] if k >= 0 and k < env.size() else 0.0
