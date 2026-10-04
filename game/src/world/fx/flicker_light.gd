class_name FlickerLight
extends OmniLight3D
## Omni light with organic flame flicker (torches, lighters, candles, campfires).

@export var flicker: float = 0.25
@export var speed: float = 9.0
var _base_energy: float = -1.0
var _t: float = 0.0
var _n := FastNoiseLite.new()


func _ready() -> void:
	_n.seed = get_instance_id() & 0xFFFF
	_n.frequency = 1.0
	shadow_bias = 0.05
	omni_attenuation = 1.4


func _process(delta: float) -> void:
	if _base_energy < 0.0:
		_base_energy = light_energy
	_t += delta * speed
	var f: float = _n.get_noise_1d(_t) * 0.7 + _n.get_noise_1d(_t * 2.7 + 50.0) * 0.3
	light_energy = _base_energy * (1.0 + f * flicker)
