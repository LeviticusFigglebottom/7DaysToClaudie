class_name RwgTowns
extends RefCounted
## The street plans of a random world's towns (ADR-0031). A town is a generated framework
## (FrameworkDef data: size, tier range, lots, roads, fixtures), so its lots pick or generate their
## buildings exactly like Pell's Crossing's (LotPicker, BuildingGenerator; ADR-0030) and the
## composer grades its pad and paints its streets like any framework's.
##
## Framework space: x east along the row streets, z south, origin at the pad's north-west corner.
## A town has one or two row streets; lots line both sides of each, facing it, with a verge between
## kerb and lot front for lamps, poles and hydrants. With two rows, cross streets at both ends (and
## between segments) join them. The main street (the first row) runs the full width of the pad:
## its two ends are the town's entries, where the world roads arrive.
## Zoning: commercial lots gather in the middle of the main street, civic lots at its centre, one
## workshop lot at the end of a back street; everything else is residential. Lot sizes fit every
## building template and the authored buildings zoned for them (docs/POI_AUTHORING.md).

const KINDS: PackedStringArray = ["hamlet", "village", "town"]


## A town's plan: {"kind", "size": [w, d], "lots", "roads", "fixtures", "entries": [[x, z], [x, z]]
## (west and east ends of the main street), "main_z"}.
static func plan(kind: String, cfg: Dictionary, r: RandomNumberGenerator) -> Dictionary:
	var kd: Dictionary = (cfg.get("kinds", {}) as Dictionary).get(kind, {"rows": 1, "segments": 1, "lots": [3, 4], "commercial": 1, "civic": 0})
	var st: Dictionary = cfg.get("street", {})
	var lt: Dictionary = cfg.get("lot", {})
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
		if ri == 0 or rows == 1:
			pass
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
				var lot_id: String = "lot_%d" % lots.size()
				var zoning: Array = [e2[0]]
				if str(e2[0]) == "commercial" and is_main:
					zoning = ["commercial", "roadside"]
				lots.append({"id": lot_id, "rect": [snappedf(lx, 0.1), snappedf(float(side["z"]), 0.1), snappedf(float(e2[1]), 0.1), snappedf(float(side["depth"]), 0.1)],
					"zoning": zoning, "facing": side["facing"]})
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
	return {"kind": kind, "size": [int(width), int(depth)], "lots": lots, "roads": roads, "fixtures": fixtures,
		"entries": [[0.0, streets_z[0]], [width, streets_z[0]]], "main_z": streets_z[0]}


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
