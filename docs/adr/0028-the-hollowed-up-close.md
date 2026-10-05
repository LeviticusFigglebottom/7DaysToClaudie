# ADR-0028: The Hollowed up close: dead skin, real clothes, the Bloom on the body, populations

**Status**: Accepted · 2026-10

## Context
The Hollowed are what the player looks at from arm's length, and they read as mannequins:
* Skin, cloth, eyes and growths all used `std_surface`. The skin had no light under it, the eyes
  were matte, and the clothes were the body offset by a few millimetres with no seams or hems.
* The Bloom's veins on Seeded and Bloomed bodies were patterned from the skinned position, so they
  slid over the skin as limbs moved (TD-027). At the Bloomed tier they lit up as bright cracked
  tiles.
* Everyone dressed alike, wherever they were found. The clinic's patients wore flannel and denim.
* The specials were silhouettes in parameters only. The Husk's plates stuck out as shelves, the
  Blister's blisters were opaque lumps, and the Rammer was a 2.3 m body widened by a non-uniform
  in-game scale. That stretched its low-resolution head and pushed its arms out (TD-027).
* Necks were thick and heads upright; a crowd idled in step (TD-025).

## Decision
* **Anatomy in the generator, not in game scale.**
  * Heads hang forward from a hunched neck, with a slack jaw, teeth and gums, clouded wet eyes,
    a gaunt face, bony hands and nails. The neck is a separate, thinner primitive.
  * The head keeps its share of the triangle budget: the other segments shrink to make room for
    extras (nails, buttons, growths, plates, pustules), and the head never does.
  * `mass` (0..1) builds bulk into the skeleton and the body: wider hips and shoulders, a yoke
    that rides high round a short neck, a knotted hump, slab forearms, a gut. The rest arm angle
    stays the same, so every action still fits. The Rammer uses it and loses its `body_scale`; its
    head is built at full resolution at 2.3 m. The Blister keeps its in-game widening (its belly
    and pustules are in the mesh; the widening adds the bloat).
* **Two character shaders, `std_surface` untouched.** `skin.gdshader` and `cloth.gdshader` share
  `character.gdshaderinc`. Only the materials that use them pay for subsurface scattering or a
  custom `light()`, so props, kit and terrain are unaffected.
  * They keep `std_surface`'s instance uniforms at the same indices: `instance_wear` 0,
    `instance_variation` 1, `bloom_glow` 2, `weather_exposure` 3. A body mixes skin, cloth and
    std_surface materials (hair, teeth, boots) on one instance, so each name must sit at one
    index. `hollow_burst` takes index 8, clear of std_surface's slots (`light_lit` is 4).
  * Skin: Godot's skin subsurface profile, light through thin parts (ears, fingers, caps,
    pustules), pallor, livid and sallow mottling, bruised extremities and settled blood, wet lips
    and eyelids, and wet clear-coated eyes. The Ashen get ash dust and lichen paint inside painted
    shapes.
  * Bloom veins on the skin: a dark net near its sites on every Hollowed. As the tier rises it
    pales into filaments that spread in patches and glow faintly (`glow_energy` 0.15, brighter on
    Hum nights through `hm_bloom`). Growth materials glow with the tier too.
  * Cloth: a wrapped diffuse, GGX and fibre-sheen `light()`; seams and stitch rows; hem stitching;
    fraying along torn edges; grime in creases. Retroreflective trim (the Cordon's tape) flares
    back toward whoever holds the light.
* **Rest-pose vertex data instead of skinned positions.** `char_attrs.py` writes extra UV layers,
  which glTF carries as `TEXCOORD_1..5` and Godot imports as:

  | attribute | content |
  |---|---|
  | `UV2` | rest-pose x, y (Godot object space, metres) |
  | `CUSTOM0` | rest-pose z, gate, wet, bruise |
  | `CUSTOM1` | trim, seam, paint, edge (signed distances in metres; 1.0 = nothing near) |

  * Patterns read the rest pose, so veins, mottling, stitches and paint stay put as the body
    moves. That closes TD-027's sliding veins.
  * Marks are distances, not masks. A distance interpolates linearly across a triangle, so a 3 mm
    seam is a crisp anti-aliased line on triangles centimetres wide.
  * A mesh without the layers reads zeros. Nothing is gated, and wet and bruise are 0. But every
    distance reads 0 too, which means on a seam, on the trim and on the paint. A material for such
    a mesh turns those marks off: `seam_shade` and `stitch_amount` 0, and no `trim` or `paint`
    (`fp_sleeve` does this). Gibs get the attributes from the body's rest pose before their origin
    moves, so a severed arm keeps its veins.
* **Tiers and bursts are gated geometry in one model.** Each vertex carries a gate code: 0 always,
  1 Seeded and up, 2 Bloomed only, 4 an intact pustule, 5 a burst crater. The vertex shader
  collapses gated-out geometry to a point, so it draws nothing and casts no shadow.
  * Every body carries the tier growths: pale fruiting caps and filament mats from the skull,
    nape, shoulders and spine (`char_extras.TIER_SITES`).
  * `bloom_glow` (InfectedTiers) chooses the tier per instance, and `EnemyVisual.burst()` sets
    `hollow_burst` when a body dies.
  * There is still one glb per body and no material swaps. The growths cost triangles even on
    normal-tier bodies (about 1.4k: 0.5k from Seeded up, 0.9k Bloomed only, inside the budget).
    The Blister carries 3.5k of intact pustules and 0.85k of burst craters.
  * Measured budgets (all 21 bodies): 15.27k-15.29k triangles at LOD0, gated geometry included,
    plus 504 in the hidden stump caps, under `char_build.BODY_BUDGET` (15.8k). Godot's import
    LODs bring a body to 5.9k-7.5k (LOD1), 1.6k-3.5k (LOD2) and 0.3k-0.8k (LOD3).
* **Clothes as garments, chosen by data.**
  * `char_wardrobe.py` builds tops, pants, collars, belts, straps, ties and mantles. Each has its
    own cloth thickness, so a jacket stands off a shirt. Plackets, yokes and pockets are built
    with seams, and buttons are separate geometry.
  * Garments are layered (a vest over coveralls, a cardigan over a dress). Edges are hemmed or
    torn, with tears that show what is underneath. Hard hats, caps, beanies and bandages are
    headgear; wristbands, IV lines, lanyards, necklaces and charms are accessories.
  * Eleven new bodies dress the valley's people: Cordon crews in coveralls and hi-vis, clinic
    patients and a nurse, Sunday shirts and dresses, a logger, a hunter, and Ashen in hides with
    lichen paint.
  * A new content kind, `population` (`data/populations/`), lists the bodies each enemy type
    wears, weighted. `mix` is the share that wear them; the rest are visitors in their own
    clothes. A building names its population (`PoiDef.population`), and a sleeper entry or a
    region (`region.json` `population`) can name its own.
  * `EnemyVisual` picks the body deterministically from the entity id, so the same sleeper wears
    the same clothes on every visit and every machine. Types a population doesn't list, and every
    special, keep their own bodies.
  * A body whose model is not generated yet falls back to the type's own pick. A model regenerated
    but not imported yet falls back to the stand-in body.
* **Specials built as features.**
  * Husk: rows of armour plates (riot gear, torn sheet steel, fungal shell). Each plate stands off
    the body more at its lower edge so the next row tucks under it, is rigid to its bone, and is
    fused at the rim with Bloom growth.
  * Blister: clusters of taut translucent pustules over wet pits. Each pustule has a gated torn
    lip that replaces it once burst. The big pustules are rounder than the small ones.
  * Rammer: `mass` 1.0.
* **Motion variety, additive.** `char_anim.py` gains `idle_b` (head loll), `idle_c` (twitches) and
  `walk_limp`. `EnemyVisual` maps `idle` and `walk_b` to a variant per Hollowed, chosen
  deterministically, so a crowd doesn't idle in step. The AI keeps asking for the same actions.
* **First-person arms belong to ADR-0029.** Its `fp_skin` and `fp_sleeve` materials
  (`data/materials/fp.json`) use these two shaders without the vertex layers, so they read zeros:
  no marks and nothing gated. The older `skin_human` and `cloth_jumpsuit` stay on `std_surface`.
  The libraries keep the API `char_fp.py` uses.
* **QA shots that can't come back empty.** The old `hollow_closeup` showed no Hollowed. The shot
  now spawns its Hollowed authored, at the normal tier (the tier used to be rolled from the
  gamestage, so the body changed between runs), and puts it back where it was spawned before the
  frame is taken. It logs the body the Hollowed wears and whether it is visible
  (`SHOT hollow_closeup: ... body characters/..., visible true`), and warns if the Hollowed is
  gone. The old run's log was not kept, so its cause is inferred, not reproduced. The likeliest is
  a body scene that did not load: `ResourceLoader.exists()` is true for any model with an import
  sidecar, and the old `EnemyVisual.build()` called `instantiate()` on the null that `load()`
  returned, which left the Hollowed with no body at all. `build()` now falls back to the stand-in
  body. New shots:
  `special_hollowed_40m` (the three specials and a Hollow 40 m down a path),
  `population_lineup` (Hollows dressed by the clinic, the church, the Cordon garage and the
  trapper's cabin), `cordon_torch_night` (the tape and a Bloomed glow by torchlight) and
  `clinic_waiting` (the clinic's waiting room with its own sleepers).

## Consequences
+ Faces, hands and clothes hold up at arm's length. Seams, hems and tape are crisp, veins stay put,
  and eyes and mouths are wet.
+ The specials read at 40 m: a plated Husk, a Blister studded with pustules, a hunched Rammer with
  arms to its knees.
+ Buildings tell who they held: patients in gowns in the clinic, the congregation in church
  clothes, crews in hi-vis at the Cordon garage. A new place needs one JSON line.
+ The Rammer's frame matches its capsule and its head is not stretched.
− Two more shaders to keep in step with `std_surface`'s instance uniform slots. A new
  `std_surface` instance uniform must avoid index 8.
− Every body pays for its tier growths and both pustule states, even when they are hidden
  (TD-069).
− Garments are skinned with the body: no cloth simulation and no secondary motion (TD-070).
− Population looks change only the model; voices, loot and behaviour don't follow them yet
  (TD-071).
− Subsurface scattering, transmittance and the cloth `light()` are unprofiled on target hardware
  (TD-072).
