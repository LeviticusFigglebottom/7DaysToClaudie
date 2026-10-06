class_name WeatherDef
extends ContentDef
## A weather state. The weather system blends between states over time.
## Rates and the look shared by every state (wetting and drying, lightning, particles, fog) live in
## data/config/weather.json (ADR-0033).

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
## Lightning strikes per game hour at full strength (0 = none). Most fall kilometres away.
var lightning: float = 0.0
## How far gusts swing the wind around its base strength (0 steady .. 1 from calm to double).
var gust: float = 0.25
## How readily ground fog pools in hollows and over water at dawn and dusk (0 never; calm,
## clearing weather forms it best; wind and rain stir it away).
var ground_fog: float = 1.0
## Extra grey haze that rain hangs in the air (depth fog per metre at full strength).
var haze: float = 0.0


func _fields() -> PackedStringArray:
	return ["fog_density", "volumetric_density", "rain", "snow", "wind", "cloud_cover", "temperature_offset",
		"noise_mask", "season_weights", "duration_hours", "lightning", "gust", "ground_fog", "haze"]


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
	lightning = r.num("lightning", 0.0)
	gust = r.num("gust", 0.25)
	ground_fog = r.num("ground_fog", 1.0)
	haze = r.num("haze", 0.0)
	if lightning < 0.0:
		r.err("lightning must be >= 0 strikes per game hour")
	if gust < 0.0 or gust > 1.0:
		r.err("gust must be 0..1")
