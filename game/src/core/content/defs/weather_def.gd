class_name WeatherDef
extends ContentDef
## A weather state. The weather system blends between states over time.

var fog_density: float = 0.002
var volumetric_density: float = 0.01
var rain: float = 0.0
var snow: float = 0.0
var wind: float = 0.3
var cloud_cover: float = 0.3
var temperature_offset: float = 0.0
## Multiplier on noise travel (rain masks sound).
var noise_mask: float = 1.0
## Relative selection weight per season {spring, summer, autumn, winter}.
var season_weights: Dictionary = {}
var duration_hours: Vector2 = Vector2(2, 8)


func _fields() -> PackedStringArray:
	return ["fog_density", "volumetric_density", "rain", "snow", "wind", "cloud_cover", "temperature_offset",
		"noise_mask", "season_weights", "duration_hours"]


func _parse(r: DefReader) -> void:
	fog_density = r.num("fog_density", 0.002)
	volumetric_density = r.num("volumetric_density", 0.01)
	rain = r.num("rain", 0.0)
	snow = r.num("snow", 0.0)
	wind = r.num("wind", 0.3)
	cloud_cover = r.num("cloud_cover", 0.3)
	temperature_offset = r.num("temperature_offset", 0.0)
	noise_mask = r.num("noise_mask", 1.0)
	season_weights = r.dict("season_weights")
	duration_hours = r.range2("duration_hours", Vector2(2, 8))
