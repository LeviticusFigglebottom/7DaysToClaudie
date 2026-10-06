# ADR-0049: Farming and rain collection: garden beds that need water, crops as data, rain catchers

**Status**: Accepted · 2026-10

## Context
M3's base tech (DESIGN §"Farming, water, traps, electricity") starts with food you grow and water
you catch. Until now every calorie was scavenged or hunted and every drink came from a stream or a
bottle. The pieces to build on were already there:
* base building (ADR-0006, ADR-0035): assembly blueprints, StructurePiece behaviour from `provides`;
* the weather (ADR-0033): rain, snow and wetness as game-time state;
* seasons and a climate band per season in `survival.json`;
* the command bus and diff-only saves (ADR-0003, ADR-0005);
* world settings (ADR-0014) and XP sources and directives (ADR-0015).

Three constraints shaped it. A crop must be content, not code. The save version is reserved for
session 3's world bundle (v7). And the game must run before `make assets`.

## Decision

### Content
* **Crops are a content kind** (`data/crops/*.json`, `CropDef`). A crop has:
  * `seeds`: items that plant it. A potato is its own seed, and so are the Okafor farm's cellar
    potatoes.
  * `produce` and `seed_return`: `{item: [min, max]}`, rolled at harvest.
  * `grow_days`, `stages` (the last one ripe) and `wilt_days`.
  * `min_temp_c` (no growth below it) and `frost_c` (frost hurts below it).
  * per-season multipliers over `config/farming.json`'s.
  * `regrow_stage`: a perennial (huckleberry, yarrow) drops back to that stage after a harvest.
  * stand-in colours and a height.
* **Five crops:** potatoes, carrots, pole beans, huckleberry and yarrow.
* **Items** (`items/garden.json`): seed potatoes, two seed packets, two seed twists, potato, carrot,
  green beans, baked potato, garden stew, a bucket and a bucket of water.
* **Recipes:**
  * at the campfire, baked potato and garden stew;
  * by hand, huckleberry seeds from berries;
  * at the workbench, a bucket.
* **Seed sources:**
  * a `garden_seeds` loot table, rolled from `junk_common` and the farm's feed bin;
  * wild huckleberry bushes and yarrow (a 0–1 seed yield each);
  * produce itself.
* **Pieces** (`structures/farming.json`, blueprints in a new "farming" category):
  * `garden_bed` provides `garden:4`: four plots in a row.
  * `rain_catcher` provides `rain_catcher:24`: 24 bottles' worth of water.

### Rules (`Farming`, pure functions over the saved state)
* **A bed has one soil moisture** (0..1) for all its plots:
  * rain soaks it under open sky (`rain_fill_minutes`);
  * a bottle adds 0.5, a bucket 1.0 (`water_sources`); the empty container comes back;
  * it dries by `dry_per_day`, plus `crop_use_per_day` per living plant, faster above `hot_from_c`.
* **Growth** happens only through the part of a tick the soil had water in it. Its rate is
  season x temperature factor x the `crop_growth` world setting x (0.5..1 by health).
  * The temperature factor is 0 at the crop's `min_temp_c`, 1 from `best_c` to `hot_c`, and less
    past that.
  * The air temperature is `GameWorld.survival_env`'s: season band, time of day, weather, biome
    and altitude.
  * Winter is 0 in the config, and planting refuses an out-of-season crop.
* **Health:**
  * dry soil takes `1 / wilt_days` a day: wilted below 0.6, dead at 0;
  * watered, a plant recovers `recover_per_day`;
  * frost below `frost_c` takes `1 / frost_kill_days` a day, and nothing mends while it lasts.
* **A ripe plot waits** for its harvest. An annual's plot empties; a perennial goes back to its
  regrow stage.
* **A catcher** fills by `fill_per_hour` x rain (and `snow_fill_per_hour` x snow) under open sky,
  up to its capacity. Open sky means no player-built piece within 7 m above it, and not inside a
  POI.
  * Carried empty bottles and buckets fill from it (`containers`), and it can be drunk from
    (`drink`).
  * The water is murky: bottles come out as stream water, to boil.
* **Buckets fill at streams too.** `world.fill_water` and `WaterSource` learnt the bucket.

### Runtime
* **`FarmManager`** is a GameWorld module (one line in `MODULES`). It does three things:
  * registers `farm.plant`, `farm.water`, `farm.harvest`, `farm.clear`, `farm.draw_water` and
    `farm.drink`; each validates the player, the reach and the state;
  * ticks every farm every 10 accumulated game minutes with the session weather and the
    temperature at the piece;
  * creates and drops farm state as pieces are placed and destroyed.
* **StructurePiece hands farm pieces to it:**
  * the prompt: harvest, then pull up dead plants, then plant (the held seed, else the first
    carried), then water;
  * the second action (hold [X]): water the bed, or drink from the catcher.
* **`FarmVisual`** (a child of the piece) shows the state:
  * generated models when they exist: `crops/<crop>_s<n>`, `crops/dead_plant`, and the catcher's
    `water` part scaled to its level;
  * stand-ins from primitives otherwise, with soil that darkens when wet and plants that sag when
    wilting.
  * `validate` lists every crop stage model, so `--strict-assets` catches a missing one.
* **Progression:**
  * XP sources `plant_crop` (2) and `harvest_crop` (12);
  * `Events.crop_harvested`, and a `harvest` directive event (targets: crop ids) with "Bring in a
    harvest" as chapter 3's seventh directive;
  * Field Manual: a "Gardens and rain" survival page and the "Farming" blueprint category.

### Saves
* **`WorldState.farms`**, keyed by piece id:
  * a bed: `{kind: "bed", water, plots: [{} | {crop, grown, health, dead?}]}`;
  * a catcher: `{kind: "catcher", water}`.
* It is written as it changes and loads empty from saves without it, so there is **no version
  bump**.
* A state whose shape no longer fits its def (a different plot count) starts over. States without
  a structure are pruned at load.

### Models (`tools/assetgen`)
`farm_garden.py` and the catalog `farming.py` make the bed, the catcher, four stages of each crop
read from `data/crops`, the dead plant and the garden items. The stew reuses `item_food`'s open
can. Materials are tints over existing texture sets (`data/materials/garden.json`). They were not
built in this stream (TD-215).

## Consequences
* A base can feed and water itself. It costs a bed, seed, attention to the soil, and the weather's
  cooperation. Summer is generous and winter grows nothing.
* A crop is a JSON entry plus four stage models (generator params). The rules and their numbers
  are all in `farming.json`.
* Tests:
  * `tests/unit/test_farming.gd`: growth, season, temperature and the setting, wilting, drying,
    rain, frost, catchers, and the save round trip;
  * `tests/integration/test_garden_commands.gd`: every command on real pieces, the visuals, a roof
    and destruction.
* Gaps are TD-211..220: grazing and trampling, bed sizes and compost, freezing and evaporating
  water, rot and a yield perk, unbuilt models, partial visual state, the one-key UI, wild seed
  species, ticking unloaded farms, and rain occlusion.
