# Regions — the main map's interface (ADR-0013)

The handcrafted map is a **7 × 7 grid of 1024 m regions** (7.2 km square). World coordinates are
metres, **X east, Z south**, origin at the centre of region **D4**. With column index
`c` = 0..6 (A–G, west→east) and row index `r` = 0..6 (rows 1–7, north→south) a region covers
`x ∈ [(c − 3.5) × 1024, (c − 2.5) × 1024)`, `z ∈ [(r − 3.5) × 1024, (r − 2.5) × 1024)` — e.g. D6 is
x ∈ [−512, 512), z ∈ [1536, 2560). Use `WorldDef.region_rect()` rather than recomputing.

```
        A          B          C          D          E          F          G
 1  Greywater   Kestrel    Corvane    ...                                       (north: peaks)
 4  ...                               D4 (origin, Hollowmere Lake)
 6  Driftwood   Lowland    Larkspur   D6 Larch Hollow  E6 Mile 12  Sallow Fen  Fen Edge
    Beach       Timber     Ridge      (M1, built)
 7                                    D7 Waystation 9 (Cordon gate)
```
The full roster (names, biomes, danger, status, summaries) is `game/world/main_map/world.json`
`regions[]`; the narrative/region plan is in docs/DESIGN.md.

## Files
```
game/world/main_map/
  world.json                         world-level data shared by every region
  regions/<cell>_<slug>/region.json  one folder per region (status "built")
```

### world.json
| key | meaning |
|---|---|
| `seed`, `region_size`, `cols`, `rows`, `sea_level` | world constants |
| `macro.corner_heights` | 8 × 8 elevations (m) at region corners, bicubic-interpolated + macro noise — the valley's shape |
| `rivers[]` | `{id, name, points:[[x,z]...], width, depth, level:[start,end]}` — continuous across regions |
| `lakes[]` | `{id, name, level, depth, shore, polygon}` |
| `roads[]` | `{id, name, surface, width, shoulder, points, bridges:[{from,to,deck:"auto"}]}` (Route 9 etc.) |
| `regions[]` | `{cell, id, name, biome, danger, status: planned|built, summary, frontier?}` |

Anything that **crosses region borders** (rivers, lakes, highways) lives here so every region
composes it identically.

### region.json
`{id, cell, name, default_biome, detail_noise:{layers:[{frequency, octaves, amplitude}]}, features:[...]}`

| feature `type` | fields | effect |
|---|---|---|
| `lake` | `id, name, ellipse:[cx,cz,rx,rz,rot] or polygon, level:"auto"|m, depth, shore, irregularity` | carved basin + water surface |
| `cliff` | `id, points, height, side, face_width, falloff` | rock face along a polyline (rock_cliff layer) |
| `hill` | `pos, radius, height` | smooth bump |
| `road` | `id, surface, width, shoulder, points, bridges?, markings?` | region road (graded profile, painted; asphalt ≥ 6 m gets lane lines unless `"markings": false`, e.g. lots and aprons) |
| `path` | `id, surface, width, points` | footpath (painted, lightly graded) |
| `framework` | `id, framework, origin:[x,z], rotation, skirt?` | flattened pad + streets + lots (docs/POI_AUTHORING.md) |
| `poi` | `id, poi, origin, rotation, biome?, skirt?, keep_water?, freeboard?` | standalone POI on a pad. `"keep_water": true` (also on `framework`): the pad sits `freeboard` (default 0.6 m) over the lake or river it overlaps, grades only the dry ground and leaves the water and its bed alone (a boathouse slip, a dock: ADR-0024) |
| `biome` | `biome, circle:[x,z], radius, blend` | paints a biome (vegetation, ground layers, ambience, spawns) |
| `clearing` | `pos, radius` | no trees/scatter |
| `spawn` | `id, pos, yaw, props?` | named spawn (e.g. `drop_site`) |
| `frontier` | `id, pos, kind: road|river|cave|trail|sea, leads_to, note` | where an expansion connects (see below) |
| `bloom` | `id, at:[x,z]` or `points:[[x,z]...]` or `poi:<placement id>, offset:[x,z]`; `radius, strength (0..1), edge (0..1)` | where the Bloom has taken the ground: a patch, a seep along a line, or a patch in a POI's own frame (ADR-0025; `data/config/bloom.json` shapes the edges and holds per-POI defaults). Keep the start area clean |

## Borders
Region-local features fade out within **48 m** of the region border (heights blend back to the
shared macro + world features), so a built region always meets its neighbours — built or coarse —
without seams. Keep authored features ≥ 48 m inside the border unless they are world-level.

## Frontiers and expansion
A frontier marks a promise to a neighbouring region: a road or river that continues, a cave
that will open, a trail. When building out a neighbour:
1. Create `regions/<cell>_<slug>/region.json`, set its `status` to `built` in world.json.
2. Honour every frontier that `leads_to` it (continue the road/trail from the same point; caves
   connect through volume chunks).
3. Run `compose_region.gd -- <region>` and inspect the hillshade/biome/splat images in
   `build/region_preview/`; walk the border with F2 free cam.
4. Add the region's POIs/frameworks and run `make validate`.

## Streaming
Built regions compose at 1 m (cached in `user://cache/worlds/<world>/<region>_100.bin`, keyed by
input hash incl. composer VERSION); others at 16 m for far tiles. Near terrain streams in 64 m
chunks around the player, vegetation in 64 m chunks (deterministic scatter), navigation in 32 m
tiles, SDF volumes in 16 m chunks, POIs per placement.
