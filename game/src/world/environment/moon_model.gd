class_name MoonModel
extends RefCounted
## The moon's orbit, phase and light, deterministic from the world clock (ADR-0023).
##
## Phase runs continuously with game time: phase = (phase_at_start + days / synodic_days) mod 1,
## 0 new, 0.25 first quarter, 0.5 full, 0.75 last quarter. The moon sits `phase` of a turn east of
## the sun, so it crosses the meridian phase * 24 h after solar noon and rises about
## 24 / synodic_days hours later every day: a full moon rises at dusk and sets at dawn, a new moon
## keeps the sun's hours (and can't be seen). Its declination follows a simplified ecliptic
## (longitude = the sun's + the elongation), so a full moon rides low when the sun rides high and
## the path drifts north and south through each cycle, with a slow node wobble on top.
##
## Directions use EnvironmentController's frame: +X east, +Y up, +Z south (the noon sun).
## Light falls off faster than the lit fraction (lit^energy_exponent): a half moon gives a third of
## a full moon's light, a thin crescent next to nothing. Values come from
## data/config/world_clock.json "moon".

const PHASE_NAMES: PackedStringArray = ["NEW MOON", "WAXING CRESCENT", "FIRST QUARTER", "WAXING GIBBOUS", "FULL MOON",
	"WANING GIBBOUS", "LAST QUARTER", "WANING CRESCENT"]

## Days from new moon to new moon. The real month (29.5 d) is too slow for runs of a few weeks;
## 10 days walks the Hum (every 7th night) through every phase.
var synodic_days: float = 10.0
## Phase at day 1 00:00.
var phase_at_start: float = 0.22
var latitude_deg: float = 46.0
## Swing of the moon's declination over its cycle (the ecliptic's tilt, softened so a summer full
## moon is still up most of the night at this latitude).
var declination_amplitude_deg: float = 14.0
## Tilt of the orbit against the ecliptic, wobbling with the node period.
var inclination_deg: float = 5.1
var node_days: float = 37.0
var energy_exponent: float = 1.5


func configure(cfg: Dictionary) -> MoonModel:
	synodic_days = maxf(1.0, float(cfg.get("synodic_days", synodic_days)))
	phase_at_start = fposmod(float(cfg.get("phase_at_start", phase_at_start)), 1.0)
	latitude_deg = clampf(float(cfg.get("latitude", latitude_deg)), -80.0, 80.0)
	declination_amplitude_deg = float(cfg.get("declination_amplitude", declination_amplitude_deg))
	inclination_deg = float(cfg.get("inclination", inclination_deg))
	node_days = maxf(1.0, float(cfg.get("node_days", node_days)))
	energy_exponent = maxf(0.1, float(cfg.get("energy_exponent", energy_exponent)))
	return self


## Phase at a moment (total game minutes since day 1 00:00): 0 new .. 0.5 full .. 1 new.
func phase_at(total_minutes: float) -> float:
	return fposmod(phase_at_start + total_minutes / (WorldClock.MIN_PER_DAY * synodic_days), 1.0)


## Lit fraction of the disc seen from the ground (0 new, 1 full).
static func illuminated(phase: float) -> float:
	return 0.5 * (1.0 - cos(phase * TAU))


## Moonlight relative to a full moon.
func brightness(phase: float) -> float:
	return pow(illuminated(phase), energy_exponent)


## Angle between the sun and the moon as seen from the ground (0 new .. PI full).
static func elongation(phase: float) -> float:
	return acos(clampf(cos(phase * TAU), -1.0, 1.0))


static func waxing(phase: float) -> bool:
	return phase < 0.5


static func phase_name(phase: float) -> String:
	return PHASE_NAMES[int(round(fposmod(phase, 1.0) * 8.0)) % 8]


## Year position (0..1, continuous) of a clock: the season cycle measured in game minutes, so the
## moon's path doesn't step at midnight the way WorldClock.season_phase() does.
static func year_phase(clock: WorldClock) -> float:
	var seasons: int = maxi(1, clock.season_order.size())
	var year_minutes: float = float(clock.season_length_days * seasons) * WorldClock.MIN_PER_DAY
	var start: float = float(clock.season_start_index * clock.season_length_days) * WorldClock.MIN_PER_DAY
	return fposmod((start + clock.total_minutes) / maxf(year_minutes, 1.0), 1.0)


## Solar noon of a clock (the game's sun is highest midway between sunrise and sunset).
static func noon_hour(clock: WorldClock) -> float:
	return (clock.sunrise_hour + clock.sunset_hour) * 0.5


## Unit vector toward the moon now.
func direction(clock: WorldClock) -> Vector3:
	return direction_at(clock.total_minutes, noon_hour(clock), year_phase(clock))


## Unit vector toward the moon at `total_minutes`, for a day whose solar noon is `noon` (hours)
## at year position `year` (0..1).
func direction_at(total_minutes: float, noon: float, year: float) -> Vector3:
	var phase: float = phase_at(total_minutes)
	var hour: float = fposmod(total_minutes, WorldClock.MIN_PER_DAY) / 60.0
	# Hour angle: the sun's (15 degrees an hour from noon), less the moon's lead east of the sun.
	var ha: float = deg_to_rad(15.0 * (hour - noon)) - phase * TAU
	# Ecliptic longitude: the sun's plus the elongation. The game's sun is highest at year 0.5
	# (WorldClock.sun_elevation_deg), so the sun's longitude is 90 degrees there.
	var lon: float = TAU * (year - 0.25) + phase * TAU
	var node: float = -TAU * total_minutes / (WorldClock.MIN_PER_DAY * node_days)
	var dec: float = deg_to_rad(declination_amplitude_deg) * sin(lon) + deg_to_rad(inclination_deg) * sin(lon - node)
	return celestial(ha, dec, deg_to_rad(latitude_deg))


## Direction of a body at hour angle `ha` (radians, positive west of the meridian) and declination
## `dec`, seen from latitude `lat`, in the +X east / +Y up / +Z south frame.
static func celestial(ha: float, dec: float, lat: float) -> Vector3:
	var cd: float = cos(dec)
	var south: float = cd * cos(ha) * sin(lat) - sin(dec) * cos(lat)
	var up: float = cd * cos(ha) * cos(lat) + sin(dec) * sin(lat)
	var west: float = cd * sin(ha)
	return Vector3(-west, up, south).normalized()


## Altitude in degrees at a moment.
func altitude_at(total_minutes: float, noon: float, year: float) -> float:
	return rad_to_deg(asin(clampf(direction_at(total_minutes, noon, year).y, -1.0, 1.0)))


## Moonrise and moonset during game day `day` (hours, -1 when it doesn't happen that day), found by
## stepping the altitude through the day in `step_minutes`.
func rise_set(clock: WorldClock, day: int, step_minutes: float = 5.0) -> Vector2:
	var noon: float = noon_hour(clock)
	var seasons: int = maxi(1, clock.season_order.size())
	var year_minutes: float = float(clock.season_length_days * seasons) * WorldClock.MIN_PER_DAY
	var start: float = float(clock.season_start_index * clock.season_length_days) * WorldClock.MIN_PER_DAY
	var t0: float = float(day - 1) * WorldClock.MIN_PER_DAY
	var out := Vector2(-1.0, -1.0)
	var prev: float = altitude_at(t0, noon, fposmod((start + t0) / year_minutes, 1.0))
	var t: float = t0 + step_minutes
	while t <= t0 + WorldClock.MIN_PER_DAY + 0.01:
		var alt: float = altitude_at(t, noon, fposmod((start + t) / year_minutes, 1.0))
		if prev < 0.0 and alt >= 0.0 and out.x < 0.0:
			out.x = (t - t0 - step_minutes * alt / (alt - prev)) / 60.0
		elif prev >= 0.0 and alt < 0.0 and out.y < 0.0:
			out.y = (t - t0 - step_minutes * alt / (alt - prev)) / 60.0
		prev = alt
		t += step_minutes
	return out


## Direction sunlight comes from at the moon, for shading its disc: `elongation(phase)` away from
## the moon, toward where the sun actually is in the sky (`sun_dir`), so the lit limb points at the
## sun the player sees and the lit fraction is exactly the phase's.
static func sunlight_at_moon(moon_dir: Vector3, sun_dir: Vector3, phase: float) -> Vector3:
	var e: float = elongation(phase)
	var t: Vector3 = sun_dir - moon_dir * sun_dir.dot(moon_dir)
	if t.length_squared() < 1e-6:
		# Sun straight behind or in front of the moon: any perpendicular will do; pick the west
		# side for a waxing moon, east for a waning one.
		t = Vector3(-1.0 if waxing(phase) else 1.0, 0.0, 0.0)
		t -= moon_dir * t.dot(moon_dir)
		if t.length_squared() < 1e-6:
			t = Vector3(0.0, 0.0, 1.0)
	return (moon_dir * cos(e) + t.normalized() * sin(e)).normalized()
