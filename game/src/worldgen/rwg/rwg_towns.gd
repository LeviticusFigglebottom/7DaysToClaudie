class_name RwgTowns
extends RefCounted
## The street plans of a random world's towns (ADR-0031). A town is a generated framework
## (FrameworkDef data: size, tier range, lots, roads, fixtures), so its lots pick or generate their
## buildings exactly like Pell's Crossing's (LotPicker, BuildingGenerator; ADR-0030) and the
## composer grades its pad and paints its streets like any framework's.
##
## Framework space: x east along the row streets, z south, origin at the pad's north-west corner.
## Two layouts. Rows: one or two row streets; lots line both sides of each, facing it, with a verge between
## kerb and lot front for lamps, poles and hydrants. With two rows, cross streets at both ends (and
## between segments) join them. The main street (the first row) runs the full width of the pad:
## its two ends are the town's entries, where the world roads arrive. Crossroads (villages and
## towns, by the kind's `crossroads` chance): a main street and a cross street through its middle,
## lots along all four arms and a corner lot in each angle of the crossing; four entries.
## Zoning: commercial lots gather in the middle of the main street, civic lots at its centre, one
## workshop lot at the end of a back street; everything else is residential. Lot sizes fit every
## building template and the authored buildings zoned for them (docs/POI_AUTHORING.md).

const KINDS: PackedStringArray = ["hamlet", "village", "town"]


## A town's plan: {"kind", "layout": "rows" | "crossroads", "size": [w, d], "lots", "roads",
## "fixtures", "entries": [[x, z], ...] (the ends of the through streets), "entry_dirs": the way
## out of each, "main_z"}.
static func plan(kind: String, cfg: Dictionary, r: RandomNumberGenerator) -> Dictionary:
	var kd: Dictionary = (cfg.get("kinds", {}) as Dictionary).get(kind, {"rows": 1, "segments": 1, "lots": [3, 4], "commercial": 1, "civic": 0})
	var st: Dictionary = cfg.get("street", {})
	var lt: Dictionary = cfg.get("lot", {})
	if r.randf() < float(kd.get("crossroads", 0.0)):
		return _plan_crossroads(kind, kd, st, lt, r)
	var main_w: float = float(st.get("main", 8.0))
	var side_w: float = float(st.get("side", 6.0))
	var verge: float = float(st.get("verge", 3.0))
	var margin: float = float(st.get("margin", 6.0))
	var rows: int = clampi(int(kd.get("rows", 1)), 1, 2)
	var segs: int = 1 if rows == 1 else clampi(int(kd.get("segments", 1)), 1, 3)
	var lr: Array = kd.get("lots", [3, 4])
	var res: Array = lt.get("residential", [20, 23])
	var main_d: float = float(lt.get("main_depth", 32))
	var back_d: float = float(lt.get("back_depth", 26))
	# Segment length: room for the most lots any side of it holds.
	var seg_len: Array[float] = []
	for s: int in segs:
		var k: int = r.randi_range(int(lr[0]), int(lr[1]))
		seg_len.append(float(k) * 22.5 + r.randf_range(0.0, 6.0))
	# x layout: [margin][cross][verge] seg [verge][cross][verge] seg ... [verge][cross][margin]
	var crosses: Array[float] = []
	var seg_x: Array[float] = []
	var x: float = margin
	if rows >= 2:
		crosses.append(x + side_w * 0.5)
		x += side_w + verge
	for s2: int in segs:
		if s2 > 0:
			x += verge
			crosses.append(x + side_w * 0.5)
			x += side_w + verge
		seg_x.append(x)
		x += seg_len[s2]
	if rows >= 2:
		x += verge
		crosses.append(x + side_w * 0.5)
		x += side_w
	x += margin
	var width: float = ceilf(x)
	# z layout, north to south.
	var z: float = margin
	var sides: Array[Dictionary] = []
	var streets_z: Array[float] = []
	for ri: int in rows:
		var sw: float = main_w if ri == 0 else side_w
		var d_n: float = main_d if ri == 0 else back_d
		var d_s: float = main_d if ri == 0 else back_d
		sides.append({"row": ri, "facing": "S", "z": z, "depth": d_n})
		z += d_n + verge
		streets_z.append(z + sw * 0.5)
		z += sw + verge
		sides.append({"row": ri, "facing": "N", "z": z, "depth": d_s})
		z += d_s
	z += margin
	var depth: float = ceilf(z)
	# Lots along every side of every segment.
	var lots: Array = []
	var commercial: int = int(kd.get("commercial", 0))
	var civic: int = int(kd.get("civic", 0))
	var centre_x: float = width * 0.5
	var industrial_done: bool = rows < 2
	for side: Dictionary in sides:
		var is_main: bool = int(side["row"]) == 0
		for s3: int in segs:
			var x0: float = seg_x[s3]
			var x1: float = x0 + seg_len[s3]
			# The lots of this run, west to east: zoning by distance from the main street's middle.
			var run: Array = []
			var cx: float = x0
			while true:
				var zon: String = "residential"
				var front: float = r.randf_range(float(res[0]), float(res[1]))
				var probe_mid: float = cx + 14.0
				if is_main and civic > 0 and absf(probe_mid - centre_x) < 30.0:
					zon = "civic"
				elif is_main and commercial > 0 and absf(probe_mid - centre_x) < width * 0.3:
					zon = "commercial"
				elif not industrial_done and not is_main and s3 == segs - 1 and str(side["facing"]) == "N" and cx + 30.0 > x1 - 1.0:
					zon = "industrial"
				if zon != "residential":
					var fr: Array = lt.get(zon, [28, 28])
					front = r.randf_range(float(fr[0]), float(fr[1]))
				if cx + front > x1 + 0.01:
					# The last lot: residential if it still fits, else the run ends here.
					front = float(res[0])
					zon = "residential"
					if cx + front > x1 + 0.01:
						break
				run.append([zon, front])
				cx += front
				if zon == "civic":
					civic -= 1
				elif zon == "commercial":
					commercial -= 1
				elif zon == "industrial":
					industrial_done = true
			# Spread the slack between the lots (side yards), keeping both ends on the segment.
			var used: float = 0.0
			for e: Array in run:
				used += float(e[1])
			var gap: float = (x1 - x0 - used) / maxf(1.0, run.size())
			var lx: float = x0 + gap * 0.5
			for e2: Array in run:
				var zoning: Array = [e2[0]]
				if str(e2[0]) == "commercial" and is_main:
					zoning = ["commercial", "roadside"]
				lots.append(_lot(lots.size(), lx, float(side["z"]), float(e2[1]), float(side["depth"]), zoning, side["facing"]))
				lx += float(e2[1]) + gap
	# Streets.
	var roads: Array = []
	roads.append({"_doc": "Main street", "points": [[0.0, snappedf(streets_z[0], 0.1)], [snappedf(width * 0.5, 0.1), snappedf(streets_z[0], 0.1)], [width, snappedf(streets_z[0], 0.1)]],
		"width": main_w, "surface": "asphalt", "shoulder": 1.0})
	if rows >= 2:
		roads.append({"_doc": "Back street", "points": [[snappedf(crosses[0], 0.1), snappedf(streets_z[1], 0.1)], [snappedf(crosses[crosses.size() - 1], 0.1), snappedf(streets_z[1], 0.1)]],
			"width": side_w, "surface": "asphalt", "shoulder": 0.8})
		for xc: float in crosses:
			roads.append({"_doc": "Cross street", "points": [[snappedf(xc, 0.1), snappedf(streets_z[0], 0.1)], [snappedf(xc, 0.1), snappedf(streets_z[1], 0.1)]],
				"width": side_w, "surface": "asphalt", "shoulder": 0.8})
	var fixtures: Array = _fixtures(r, width, streets_z, [main_w] + ([side_w] if rows >= 2 else []), crosses, lots, verge, rows)
	return {"kind": kind, "layout": "rows", "size": [int(width), int(depth)], "lots": lots, "roads": roads, "fixtures": fixtures,
		"entries": [[0.0, streets_z[0]], [width, streets_z[0]]], "entry_dirs": [[-1.0, 0.0], [1.0, 0.0]], "main_z": streets_z[0]}


## A crossroads town: the main street and a cross street through its middle, lots along all four
## arms (the main street's 32 m deep, facing it; the cross street's facing east and west), and a
## corner lot in each angle of the crossing facing the main street (shops, the church, the post
## office). Four entries, one at each end.
static func _plan_crossroads(kind: String, kd: Dictionary, st: Dictionary, lt: Dictionary, r: RandomNumberGenerator) -> Dictionary:
	var main_w: float = float(st.get("main", 8.0))
	var side_w: float = float(st.get("side", 6.0))
	var verge: float = float(st.get("verge", 3.0))
	var margin: float = float(st.get("margin", 6.0))
	var res: Array = lt.get("residential", [20, 23])
	var main_d: float = float(lt.get("main_depth", 32))
	var back_d: float = float(lt.get("back_depth", 26))
	var al: Array = kd.get("arm_lots", [2, 3])
	var core_x: float = side_w * 0.5 + verge + back_d
	var core_z: float = main_w * 0.5 + verge + main_d
	var arm_x: float = float(r.randi_range(int(al[0]), int(al[1]))) * 22.5 + r.randf_range(0.0, 4.0)
	var arm_z: float = float(r.randi_range(int(al[0]), int(al[1]))) * 22.5 + r.randf_range(0.0, 4.0)
	var width: float = ceilf(2.0 * (margin + arm_x + core_x))
	var depth: float = ceilf(2.0 * (margin + arm_z + core_z))
	var xc: float = width * 0.5
	var zc: float = depth * 0.5
	var lots: Array = []
	var commercial: int = int(kd.get("commercial", 2))
	var civic: int = int(kd.get("civic", 1))
	# Corner lots in the four angles of the crossing, facing the main street.
	for cz: int in 2:
		for cx: int in 2:
			var zon: String = "residential"
			if civic > 0 and cx == cz:
				zon = "civic"
				civic -= 1
			elif commercial > 0:
				zon = "commercial"
				commercial -= 1
			var x0: float = xc - side_w * 0.5 - verge - back_d if cx == 0 else xc + side_w * 0.5 + verge
			var z0: float = zc - main_w * 0.5 - verge - main_d if cz == 0 else zc + main_w * 0.5 + verge
			lots.append(_lot(lots.size(), x0, z0, back_d, main_d, [zon] + (["roadside"] if zon == "commercial" else []), "S" if cz == 0 else "N"))
	# The main street's arms: 32 m lots facing it, shops nearest the crossing.
	for side: int in 2:
		var z_lot: float = zc - main_w * 0.5 - verge - main_d if side == 0 else zc + main_w * 0.5 + verge
		for half: int in 2:
			var run: Array = _run_lots(r, arm_x, res, commercial)
			commercial -= int(run[1])
			var fronts: Array = run[0]
			var x: float = (xc - core_x - arm_x) if half == 0 else (xc + core_x)
			# Shops at the crossing end of each arm: the run is laid out from the crossing outwards.
			if half == 0:
				fronts.reverse()
			for e: Array in fronts:
				lots.append(_lot(lots.size(), x, z_lot, float(e[1]), main_d, [e[0]] + (["roadside"] if str(e[0]) == "commercial" else []), "S" if side == 0 else "N"))
				x += float(e[1])
	# The cross street's arms: houses facing east and west.
	var industrial: bool = kind == "town"
	for side2: int in 2:
		var x_lot: float = xc - side_w * 0.5 - verge - back_d if side2 == 0 else xc + side_w * 0.5 + verge
		for half2: int in 2:
			var z: float = (zc - core_z - arm_z) if half2 == 0 else (zc + core_z)
			var used: float = 0.0
			while used + float(res[0]) <= arm_z + 0.01:
				var front: float = minf(r.randf_range(float(res[0]), float(res[1])), arm_z - used)
				var zon2: String = "residential"
				if industrial and half2 == 1 and side2 == 1 and used + 2.0 * float(res[0]) > arm_z:
					zon2 = "industrial"
					industrial = false
					front = maxf(front, minf(26.0, arm_z - used))
					if front < 26.0:
						zon2 = "residential"
				# Facing the street: lots west of it face east, lots east of it face west.
				lots.append(_lot(lots.size(), x_lot, z + used, back_d, front, [zon2], "E" if side2 == 0 else "W"))
				used += front
	var roads: Array = [
		{"_doc": "Main street", "points": [[0.0, snappedf(zc, 0.1)], [snappedf(xc, 0.1), snappedf(zc, 0.1)], [width, snappedf(zc, 0.1)]], "width": main_w, "surface": "asphalt", "shoulder": 1.0},
		{"_doc": "Cross street", "points": [[snappedf(xc, 0.1), 0.0], [snappedf(xc, 0.1), snappedf(zc, 0.1)], [snappedf(xc, 0.1), depth]], "width": side_w, "surface": "asphalt", "shoulder": 0.8},
	]
	var fixtures: Array = _crossroads_fixtures(r, width, depth, xc, zc, main_w, side_w, core_x, core_z, lots, verge)
	return {"kind": kind, "layout": "crossroads", "size": [int(width), int(depth)], "lots": lots, "roads": roads, "fixtures": fixtures,
		"entries": [[0.0, zc], [width, zc], [xc, 0.0], [xc, depth]], "entry_dirs": [[-1.0, 0.0], [1.0, 0.0], [0.0, -1.0], [0.0, 1.0]], "main_z": zc}


## Lots (zoning, frontage) along an arm of `length` m: shops first while `commercial` allows.
static func _run_lots(r: RandomNumberGenerator, length: float, res: Array, commercial: int) -> Array:
	var out: Array = []
	var used: float = 0.0
	var shops: int = 0
	while true:
		var zon: String = "residential"
		var front: float = r.randf_range(float(res[0]), float(res[1]))
		if commercial - shops > 0 and out.is_empty():
			zon = "commercial"
			front = 28.0
		if used + front > length + 0.01:
			zon = "residential"
			front = float(res[0])
			if used + front > length + 0.01:
				break
		if zon == "commercial":
			shops += 1
		out.append([zon, front])
		used += front
	# Spread the slack evenly.
	var slack: float = (length - used) / maxf(1.0, out.size())
	for e: Array in out:
		e[1] = float(e[1]) + slack
	return [out, shops]


## A lot's data; both edges are snapped (not the position and size apart), so neighbours share an edge
## exactly instead of overlapping by a rounding.
static func _lot(i: int, x: float, z: float, w: float, d: float, zoning: Array, facing: String) -> Dictionary:
	var x0: float = snappedf(x, 0.1)
	var z0: float = snappedf(z, 0.1)
	return {"id": "lot_%d" % i, "rect": [x0, z0, snappedf(snappedf(x + w, 0.1) - x0, 0.1), snappedf(snappedf(z + d, 0.1) - z0, 0.1)], "zoning": zoning, "facing": facing}


## A crossroads town's fixtures: lamps and hydrants along both streets (clear of the crossing), poles
## along the main street, stop signs at the crossing, wrecks, a barricaded entry, and the shop and
## civic dressing in front of the corner and main-street lots.
static func _crossroads_fixtures(r: RandomNumberGenerator, width: float, depth: float, xc: float, zc: float, main_w: float, side_w: float,
		core_x: float, core_z: float, lots: Array, verge: float) -> Array:
	var out: Array = []
	var nid: Array[int] = [0]
	var add := func(prop: String, x: float, z: float, rot: float) -> void:
		out.append({"id": "fx_%d" % nid[0], "prop": prop, "pos": [snappedf(x, 0.1), snappedf(z, 0.1)], "rot": snappedf(rot, 1.0)})
		nid[0] += 1
	# Along the main street (x), then the cross street (z).
	var k: int = 0
	var x: float = 10.0 + r.randf_range(0.0, 6.0)
	while x < width - 6.0:
		if absf(x - xc) > side_w * 0.5 + 5.0:
			var north: bool = k % 2 == 0
			add.call("street_lamp", x, zc + (-1.0 if north else 1.0) * (main_w * 0.5 + 1.0), 180.0 if north else 0.0)
			if k % 2 == 1:
				add.call("utility_pole", x + 14.0, zc - main_w * 0.5 - 2.1, 90.0)
		k += 1
		x += r.randf_range(30.0, 38.0)
	var z: float = 10.0 + r.randf_range(0.0, 6.0)
	k = 0
	while z < depth - 6.0:
		if absf(z - zc) > main_w * 0.5 + 5.0:
			var west: bool = k % 2 == 0
			add.call("street_lamp", xc + (-1.0 if west else 1.0) * (side_w * 0.5 + 1.0), z, -90.0 if west else 90.0)
		k += 1
		z += r.randf_range(30.0, 38.0)
	for h: int in 4:
		var t: float = r.randf_range(0.15, 0.4)
		match h:
			0:
				add.call("fire_hydrant", xc - core_x - (width * 0.5 - core_x) * t, zc + main_w * 0.5 + 1.7, 0.0)
			1:
				add.call("fire_hydrant", xc + core_x + (width * 0.5 - core_x) * t, zc - main_w * 0.5 - 1.7, 0.0)
			2:
				add.call("fire_hydrant", xc + side_w * 0.5 + 1.7, zc - core_z - (depth * 0.5 - core_z) * t, 0.0)
			3:
				add.call("fire_hydrant", xc - side_w * 0.5 - 1.7, zc + core_z + (depth * 0.5 - core_z) * t, 0.0)
	# Stop signs on the cross street's approaches to the crossing.
	add.call("road_sign_stop", xc + side_w * 0.5 + 1.4, zc - main_w * 0.5 - 2.6, 0.0)
	add.call("road_sign_stop", xc - side_w * 0.5 - 1.4, zc + main_w * 0.5 + 2.6, 180.0)
	# Wrecks in the lanes of both streets.
	for wi: int in r.randi_range(2, 4):
		if r.randf() < 0.6:
			var wx: float = r.randf_range(8.0, width - 8.0)
			if absf(wx - xc) > side_w + 4.0:
				add.call("car_sedan_wreck" if r.randf() < 0.7 else "pickup_wreck", wx, zc + (1.0 if r.randf() < 0.5 else -1.0) * r.randf_range(0.8, main_w * 0.5 - 1.0),
					90.0 + (180.0 if r.randf() < 0.5 else 0.0) + r.randf_range(-20.0, 20.0))
		else:
			var wz: float = r.randf_range(8.0, depth - 8.0)
			if absf(wz - zc) > main_w + 4.0:
				add.call("car_sedan_wreck" if r.randf() < 0.7 else "pickup_wreck", xc + (1.0 if r.randf() < 0.5 else -1.0) * r.randf_range(0.5, side_w * 0.5 - 0.8), wz,
					(180.0 if r.randf() < 0.5 else 0.0) + r.randf_range(-20.0, 20.0))
	# The Cordon closed one end of the main street.
	var west_end: bool = r.randf() < 0.5
	var bx: float = 4.0 if west_end else width - 4.0
	add.call("jersey_barrier", bx, zc - 2.1, 90.0 + r.randf_range(-6.0, 6.0))
	add.call("jersey_barrier", bx + (1.5 if west_end else -1.5), zc + 2.0, 90.0 + r.randf_range(-6.0, 6.0))
	add.call("sawhorse_barricade", bx + (3.5 if west_end else -3.5), zc + r.randf_range(-1.0, 1.0), 90.0 + r.randf_range(-10.0, 10.0))
	add.call("oil_drum_fire", bx + (6.5 if west_end else -6.5), zc - main_w * 0.5 - 1.6, 0.0)
	# Shop and civic dressing in front of the lots facing the main street.
	var did_phone: bool = false
	for l: Variant in lots:
		var lot: Dictionary = l
		var zon: String = str((lot["zoning"] as Array)[0])
		if (zon != "commercial" and zon != "civic") or not str(lot["facing"]) in ["S", "N"]:
			continue
		var rect: Array = lot["rect"]
		var front_z: float = float(rect[1]) + float(rect[3]) + verge * 0.5 if str(lot["facing"]) == "S" else float(rect[1]) - verge * 0.5
		var cxl: float = float(rect[0]) + float(rect[2]) * 0.5
		var face_rot: float = 0.0 if str(lot["facing"]) == "S" else 180.0
		if zon == "commercial":
			if r.randf() < 0.5:
				add.call("dumpster", float(rect[0]) + 2.0, front_z, face_rot)
			if not did_phone:
				add.call("payphone", cxl + float(rect[2]) * 0.3, front_z, face_rot)
				did_phone = true
		else:
			add.call("bench_park", cxl - 4.0, front_z, face_rot)
			add.call("civic_collection_mailbox", cxl + 5.0, front_z, face_rot + 90.0)
	return out


## Lamps, poles, hydrants, stop signs, wrecks, a barricaded entry, dumpsters, benches and litter,
## all on the verges or the streets (never in a lot: buildings fill their lots).
static func _fixtures(r: RandomNumberGenerator, width: float, streets_z: Array[float], street_w: Array, crosses: Array[float], lots: Array, verge: float, rows: int) -> Array:
	var out: Array = []
	var nid: Array[int] = [0]
	var add := func(prop: String, x: float, z: float, rot: float) -> void:
		out.append({"id": "fx_%d" % nid[0], "prop": prop, "pos": [snappedf(x, 0.1), snappedf(z, 0.1)], "rot": snappedf(rot, 1.0)})
		nid[0] += 1
	for si: int in streets_z.size():
		var zs: float = streets_z[si]
		var half: float = float(street_w[si]) * 0.5
		var x_lo: float = crosses[0] if si > 0 and not crosses.is_empty() else 0.0
		var x_hi: float = crosses[crosses.size() - 1] if si > 0 and not crosses.is_empty() else width
		# Lamps every ~34 m, alternating kerbs; their arms reach over the street.
		var k: int = 0
		var lx: float = x_lo + 10.0 + r.randf_range(0.0, 6.0)
		while lx < x_hi - 6.0:
			if not _near_cross(lx, crosses, 6.0):
				var north: bool = k % 2 == 0
				add.call("street_lamp", lx, zs + (-1.0 if north else 1.0) * (half + 1.0), 180.0 if north else 0.0)
			k += 1
			lx += r.randf_range(30.0, 38.0)
		# Poles along the north kerb of the main street, hydrants on alternate kerbs.
		if si == 0:
			var px: float = 22.0 + r.randf_range(0.0, 8.0)
			while px < width - 8.0:
				if not _near_cross(px, crosses, 5.0):
					add.call("utility_pole", px, zs - half - 2.1, 90.0)
				px += r.randf_range(38.0, 44.0)
		var hx: float = x_lo + 24.0 + r.randf_range(0.0, 12.0)
		var hk: int = 0
		while hx < x_hi - 8.0:
			if not _near_cross(hx, crosses, 5.0):
				add.call("fire_hydrant", hx, zs + (1.0 if hk % 2 == 0 else -1.0) * (half + 1.7), 0.0)
			hk += 1
			hx += r.randf_range(55.0, 80.0)
		# Wrecks where they stopped: along the lanes, a few slewed across.
		var wrecks: int = int(round((x_hi - x_lo) / 70.0 * r.randf_range(0.6, 1.4)))
		for wi: int in wrecks:
			var wx: float = r.randf_range(x_lo + 10.0, x_hi - 10.0)
			if _near_cross(wx, crosses, 7.0):
				continue
			var lane: float = (1.0 if r.randf() < 0.5 else -1.0) * r.randf_range(0.8, half - 1.0)
			var rot: float = 90.0 + (180.0 if r.randf() < 0.5 else 0.0) + r.randf_range(-14.0, 14.0)
			if r.randf() < 0.25:
				rot += r.randf_range(-60.0, 60.0)
			add.call("car_sedan_wreck" if r.randf() < 0.7 else "pickup_wreck", wx, zs + lane, rot)
	# Stop signs where cross streets meet the rows.
	for xc: float in crosses:
		for si2: int in streets_z.size():
			var zs2: float = streets_z[si2]
			var half2: float = float(street_w[si2]) * 0.5
			var below: bool = si2 == 0
			add.call("road_sign_stop", xc + (4.2 if below else -4.2), zs2 + (half2 + 1.4 if below else -half2 - 1.4), 0.0 if below else 180.0)
	# The Cordon closed one end of the main street: barriers across it, a fire in a drum.
	var west: bool = r.randf() < 0.5
	var bx: float = 4.0 if west else width - 4.0
	var zm: float = streets_z[0]
	add.call("jersey_barrier", bx, zm - 2.1, 90.0 + r.randf_range(-6.0, 6.0))
	add.call("jersey_barrier", bx + (1.5 if west else -1.5), zm + 2.0, 90.0 + r.randf_range(-6.0, 6.0))
	add.call("sawhorse_barricade", bx + (3.5 if west else -3.5), zm + r.randf_range(-1.0, 1.0), 90.0 + r.randf_range(-10.0, 10.0))
	add.call("oil_drum_fire", bx + (6.5 if west else -6.5), zm - float(street_w[0]) * 0.5 - 1.6, 0.0)
	# Dumpsters, benches, a payphone and a collection box by the commercial and civic lots.
	var did_phone: bool = false
	for l: Variant in lots:
		var lot: Dictionary = l
		var zon: String = str((lot["zoning"] as Array)[0])
		if zon != "commercial" and zon != "civic":
			continue
		var rect: Array = lot["rect"]
		var front_z: float = float(rect[1]) + float(rect[3]) + verge * 0.5 if str(lot["facing"]) == "S" else float(rect[1]) - verge * 0.5
		var cxl: float = float(rect[0]) + float(rect[2]) * 0.5
		var face_rot: float = 0.0 if str(lot["facing"]) == "S" else 180.0
		if zon == "commercial":
			if r.randf() < 0.6:
				add.call("dumpster", float(rect[0]) + 2.0, front_z, face_rot)
			if not did_phone:
				add.call("payphone", cxl + float(rect[2]) * 0.35, front_z, face_rot)
				did_phone = true
		else:
			add.call("bench_park", cxl - 4.0, front_z, face_rot)
			add.call("civic_collection_mailbox", cxl + 5.0, front_z, face_rot + 90.0)
		if r.randf() < 0.5:
			add.call("trash_bag" if r.randf() < 0.6 else "trash_pile", cxl + r.randf_range(-6.0, 6.0), front_z, r.randf_range(0.0, 360.0))
	return out


static func _near_cross(x: float, crosses: Array[float], d: float) -> bool:
	for xc: float in crosses:
		if absf(x - xc) < d:
			return true
	return false
