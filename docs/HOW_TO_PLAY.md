# How to play Hollowmere

The player's guide to build **0.1.0-m1** (the M1 vertical slice), written from the game's code and
data as of October 2026. Where something isn't in the game yet, the guide says so.

You are a Remand Program convict dropped inside the Cordon, a quarantined valley where a fungus,
the Bloom, has hollowed out the townsfolk. Fell trees and build from logs, scavenge buildings that
play like small dungeons, and hold out against **the Hum**: the nights when every Hollowed in the
valley comes for you.

**Quick start:** get the Windows build (§1) → **New Game…** → **Start** → raise your tether (T) and
follow its first directives: fell three trees, make a stone axe, build a campfire, raise a lean-to
and sleep in it.

## 1. Getting and starting the game

### The downloadable build (play this one)
1. On GitHub, open **Actions** → the **Build** workflow → the newest successful run, and download
   the **hollowmere-windows** artifact (Linux: **hollowmere-linux**). GitHub only lets signed-in
   users download artifacts.
2. The download is a zip holding the build's own zip, `hollowmere-windows-<version>-<rev>.zip`.
   Unzip both, anywhere.
3. Run **Hollowmere.exe**. **Hollowmere.console.exe** is the same game with a console window that
   shows the log as you play. Keep **Hollowmere.pck** beside the program: it is the whole game, with
   every generated model, texture and sound.

You need a GPU with Vulkan 1.2 or Direct3D 12; on older drivers Godot falls back to OpenGL, where
fog, weather and lighting are wrong. The program isn't code-signed, so Windows may ask you to
confirm the first run. The game opens in a 1280 × 720 window (Options has Fullscreen).

### Running from source (developers)
* Open `game/project.godot` in the **Godot 4.7.2** editor, exactly that version: the project, its
  export templates and its tests are pinned to it (`tools/versions.env`), and other versions import,
  render or crash differently (the first playtest ran 4.7.1).
* A clone has **no generated assets**: `make setup assets` builds them on Linux x86_64 only, slowly
  the first time, and they are never committed. Without them everything is a stand-in shape, with
  no textures and no grass. On Linux: `make setup assets import`, then `make run` or `make run-slice`.
* The developer tools (F1–F7, §3) work only in these debug runs.

### The main menu
| Button | What it does |
|---|---|
| Continue (Day N) | Loads your most recent save |
| New Game… | The world settings screen (§2) |
| New Game — Vertical Slice demo (seed 4471, Hum on night 3) | Starts the slice's curated demo run at once: Survivor difficulty, 30-minute days, the first Hum on day 3, always run seed 4471 (New Game… rolls a fresh seed) |
| Random World… | The world settings screen, open on its World tab with a random world chosen |
| Load RunN — Day N · Preset | Each saved run, newest first ("· Random world" marks those) |
| Options… | Mouse sensitivity and invert, field of view, head bob, five volumes, brightness, graphics preset, fullscreen, V-sync |

A boxed **notice** on the menu means something is off with your copy (the packaged build shows
none):
* **"Placeholder world: …"**: the generated models, textures and sounds are missing (a source
  clone without `make assets`); the world will be stand-in shapes.
* **"Incomplete assets: only N% of the generated models were found …"**: re-run `make assets`.
* **"Godot X: this project is made for Godot 4.7.2 …"**: the source is open in another editor.

### Where your files are
Windows `%APPDATA%\hollowmere\`, Linux `~/.local/share/hollowmere/`:

| Path | Holds |
|---|---|
| `saves\run1\`, `run2\` … | one folder per run (§12) |
| `settings.cfg` | your options |
| `logs\godot.log` | the log of the last run: send it with any crash report |
| `worlds\random\` | your generated random worlds (keep it while you have random-world saves) |
| `cache\worlds\` | terrain shaped on a world's first load (rebuilt if deleted, slowly) |
| `screenshot_<time>.png` | F12 screenshots |

## 2. New Game

The **New Game — World Settings** screen has a **Game** tab and a **World** tab; **Start** begins.

### Game tab
* **Mode**: *Survival* (60-minute days, the first Hum on day 7) or *Vertical slice* (30-minute
  days, the first Hum on day 3, then every 7 days). Both start on day 1 at 07:30.
* **Difficulty**: picking a preset (or a mode) resets every option to it; then change what you like.
* **Run seed** (see *Seeds*), then every world setting, by category.

| Difficulty | Differences from Survivor |
|---|---|
| Drifter — gentle | Hollowed jog at night and run in the Hum; 0.75× toughness; half damage to you and your walls; half-size Hums; 1.5× loot and XP; half hunger, thirst and infection; death costs nothing; gamestage ×0.65 |
| Survivor — standard | The intended balance (the defaults below) |
| Remanded — hard | They jog by day; 1.25× toughness, 1.5× damage, 1.25× to walls; 1.5× Hums; 0.75× loot; 1.25× hunger and thirst; death drops everything; gamestage ×1.2 |
| Hollowed — brutal | They run by day and sprint at night; 1.5× toughness, 2× damage, 1.5× to walls, 1.5× wanderers; light sleepers; a Hum every 5 days at 2× size; half loot; 1.5× hunger and thirst; death drops everything; gamestage ×1.4 |
| Rooted — permadeath | Hollowed — brutal with one life: the save is deleted when you die |

| Setting | Default | Choices |
|---|---|---|
| Day length (real minutes) | 60 | 10–180 |
| Starting season | Autumn | Spring, Summer, Autumn, Winter (12 days each) |
| Chopping & digging speed; wildlife; wildlife density | 1×; on; 1× | |
| Hollowed speed by day / at night / in the Hum | Walk / Run / Sprint | Shamble, Walk, Jog, Run, Sprint, relative to each kind's own pace |
| Hollowed toughness, damage to you, damage to structures, wanderer density | 1× | |
| Sleepers wake | Normal | Deep, Normal, Light |
| Special Hollowed (Blister, Husk, Rammer); Seeded and Bloomed tiers | on; on | |
| Gamestage per day survived; gamestage multiplier | 1.5; 1× | |
| First Hum on day; Hum every N days; variance | 7; 7; ±0 | 1–28; 0–28 (0 = never); ±0–3 days |
| Hum horde size; Hollowed alive at once | 1×; 24 | 0.25–3×; 8–64 |
| Loot abundance; loot respawn; XP multiplier | 1×; never; 1× | 0.25–2×; 0–60 days; 0.25–3× |
| Remand supply drops; mark them on the tether | After the Hum; on | Off, After the Hum, Weekly, Every 3 days |
| Hunger & thirst rate; Bloom infection rate | 1×; 1× | |
| On death | Drop pack | None, XP loss, Drop pack, Drop all, Permadeath |

On death: *None* keeps everything; *XP loss* halves your progress toward the next level; *Drop pack*
leaves everything but your toolbelt items where you fell; *Drop all* leaves everything; *Permadeath*
deletes the run. The tether and field manual are never dropped.

### World tab: the map and random worlds
* **Hollowmere Valley (handcrafted)** is planned as 7 × 7 km, but today only **Larch Hollow** is
  built: about a square kilometre around Pell's Crossing with 25 authored buildings, Route 9, the
  Okafor farm and places in the woods. Its land never changes; the run seed dresses its buildings.
* **Random world**: a **World preset** (Standard; Small valley (3 × 3); Highlands; Lakeland;
  Settled county; Wild country), a **Map seed** (**New seed** rolls one) and these options:

| Option | Default | Choices |
|---|---|---|
| Size (1 km regions a side) | 4 | 2–7 |
| Terrain; roughness | Rolling; 0.5 | Flat, Rolling, Hilly, Mountainous; 0–1 |
| Conifer forest, birch groves, meadows, rocky ground | 0.7, 0.35, 0.35, 0.3 | 0–1 each |
| Rivers; lakes | Some; Some | None, Few, Some, Many |
| Towns; town size | 3; Mixed | 0–10; Hamlets, Villages, Mixed, Towns |
| Wilderness places; road density | 1; Normal | 0–2; Sparse, Normal, Dense |

* **Generate preview** builds the world in the background and shows its map (the yellow ring is
  where you'll be dropped) and its towns. It's optional.
* You get rivers and lakes, roads with bridges, towns whose lots fill per run (generated houses,
  shops and workshops, and authored buildings, five of them found only in random towns: Suds & Spin
  Laundromat, Hollowmere Grocery, Bracken Lumber & Feed, Pell County Library, KHLW Valley Radio),
  the authored wilderness places, Bloom patches far from the start and a drop site by a road.
* The first load shapes every region (about 1½ minutes for 3 × 3, a few minutes for 5 × 5 on a
  4-core test machine), then it's cached. 7 × 7 is heavy on memory. No coasts, caves or traders yet.

### Seeds
* **Run seed** (Game tab; a whole number or any text, new each time): the scatter, every loot
  roll, the Hum's plans and how each building is dressed (rooms, wear, lights, the generated
  houses). Reuse one to replay a run's world. Text is hashed into a number, as the map seed is; an
  empty field rolls a fresh seed.
* **Map seed** (World tab; any text): the land, water, roads, towns and places of a random world.
  Same seed and settings, same world, so you can replay one map with different run seeds.

## 3. Controls

Keyboard and mouse (a gamepad can only move, jump, sprint, crouch and interact). Every key and
mouse button can be rebound under **Options → Controls**, also reachable from the pause menu; the
keys below are the defaults.

| Key | Action |
|---|---|
| W A S D, mouse | Move, look |
| Shift (hold) | Sprint, forward only; uses stamina. Run it empty and you can't sprint until it's back to 30 |
| C or Ctrl | Crouch or stand (a toggle): slower, quieter, harder to see. Needed to disarm traps and dismantle |
| Space | Jump (8 stamina). At a sill, fence or crate 0.3–1.3 m high: climb over or onto it. In deep water: hold to swim up |
| Ladders | Walk into a ladder to climb it: W climbs, S (or W while looking down) climbs down, and you step off at the top. From upstairs, walk into its hatch to climb down. Space lets go |
| E | Interact. Hold it to search, harvest, drink or fill bottles at water, butcher and dismantle |
| Left mouse | Use what you hold: swing, fire, throw a stone, set down a can chime. While building: place the ghost or the carried log |
| Right mouse | Hold to guard (melee weapon, light or bare hands). Food, drink or medicine in hand: use it. Revolver: reload. Spear: throw. Placing a blueprint: cancel |
| 1–6, mouse wheel | Toolbelt slots (press the held one again to put it away); the wheel cycles them |
| F | Turn the lighter, torch or flashlight in your hand on or off |
| Y | Look over what you are holding |
| H | Whistle to your companion, Ezra: follow me, or stay where you are (a toggle; §9) |
| G | Drop a carried log; while looking at a fire, add fuel |
| R | Rotate: a blueprint by 15°, a carried log by 90° |
| V | Carried log pose: flat, upright post, pitched (roof) |
| X | Cancel placement; close the salvage roll, field manual or options. Hold it (1 s) on a placed blueprint ghost to take it down |
| Tab or I | Salvage roll: inventory and crafting |
| B | Remand Field Manual: blueprints, your Record, notes found, survival pages |
| T | Raise or lower the tether on your wrist (Left mouse also lowers it) |
| Esc | Close what's open, else pause. Only the pause menu stops the world: it keeps running while the roll, manual or tether is up |
| F5 / F9 / F12 | Quicksave / quickload this run / screenshot |

**In the salvage roll:** Left mouse uses, equips or reads an item (at a container: takes or stores
it); Right mouse drops one, Shift + Right mouse the stack; 1–6 over an item puts it on the toolbelt;
the wheel turns pages or scrolls recipes; click a recipe to make it.

**Developer tools** (the editor and other debug builds only, not the packaged game):

| Key | Tool |
|---|---|
| F1 | Debug menu: spawn Hollowed, give kits, set the time (and start or end the Hum), weather, teleports, god mode, invisibility, no hunger, seed viewer |
| F2 | Free camera (WASD, mouse, Shift fast, E/Q up and down) |
| F3 | AI overlay: each Hollowed's state and target, the Hum's flow field, the heat map |
| F4 | Performance overlay |
| F6 | POI route visualiser: routes, sleepers, ambush triggers, traps |
| F7 | Structural view: stability and hit points of building pieces within 40 m |

## 4. Your first day

You wake at the Remand drop site in Larch Hollow at 07:30 on day 1 (autumn by default), beside the
Program's supply canister, with food 80, water 80, rest 85, health 100 and:
* a **Lighter** on toolbelt slot 1: it lights fires from your pack, and F makes it a light in hand;
* 2 **Program Ration Bars** (25 food each), a **Bottle of Boiled Water** (35 water; keep the
  bottle), 2 **Cloth** (a torch or a bandage), the **Remand Field Manual** and the **Tether**.

The HUD is minimal: the prompt under the crosshair, messages top left, vitals bars bottom left when
something is low, and "Hum in hh:mm" top right in the last day before a Hum. Time, weather,
vitals, directives and a map are on the tether (T).

**Where things are:** a dirt trail leads east from the drop site to Route 9 at the south end of
**Pell's Crossing**, a few hundred metres away. Larch Pond lies a few hundred metres north; the
Tamsin River runs east of Route 9. The tether's map shows the region you're in, north up, captioned
with the world's name and your sector (the region's map cell, D6 at the Larch Hollow drop site): you
(the arrow), where you wake (your bed as a yellow dot, or the drop site as a yellow ring until you
have a bed; pinned to the map's edge when it's elsewhere), supply drops (red diamonds) and buildings
(grey squares, orange once you've been inside, green once cleared).

**A good first day** (the first chapter of Program directives):
1. **Gather** (hold E): plant fibre from fireweed, ferns, sedge, huckleberry bushes and willows;
   sticks from deadfall, saplings and willows; stones from loose stones.
2. **Craft** (Tab, the *Make by hand* flap): Cordage (3 Plant Fiber), then a Stone Axe (Stick,
   Stone, Cordage). Put it on the toolbelt.
3. **Fell trees.** Swing at the trunk. The tree falls away from you; anything along its trunk takes
   a heavy blow (45). It breaks into logs along the fall line, with sticks and boughs by the crown.
   E puts a log on your shoulder (two at most).
4. **Campfire.** Field Manual (B) → Blueprints → Campfire → *Lay it out*, aim, Left mouse. E on the
   ghost hands over 6 Stones and 4 Sticks; E again lights it (lighter or torch in your pack). It
   starts with an hour of fuel; G feeds it.
5. **Lean-to**: 10 Sticks, 6 Bough Bundles, 2 Cordage. Bough Bundles come from fir saplings and
   felled grey firs, or from a Stick and a Plant Fiber. A Bough Bed (6 Bough Bundles, 4 Sticks) is a
   bed without the roof.
6. **Water.** Drink the boiled water when thirsty. At the pond or river, hold E with the empty
   bottle to fill it, then boil it at the lit fire (*Use Campfire* → Boil Water). You can drink
   straight from the water (18 water, −3 health a mouthful), but not while carrying an empty bottle:
   the prompt fills it instead.
7. **Before dark.** Night falls at 21:00, when the Hollowed see much farther and run. Be at your
   fire. Sleep in the lean-to (E) after 19:00: you wake at 06:00, it becomes your respawn point and
   the game saves.

Next, Pell's Crossing has what the woods don't: nails (hardware shelves and toolboxes; a workbench
needs 12), tools, canned food and medicine. Start with tier-1 buildings (§8). The first Hum comes at
22:00 on day 7 (day 3 in the slice): be behind walls by then.

## 5. Staying alive

| Vital | Start | Drains | When it runs low |
|---|---|---|---|
| Health | 100 (+5 per Grit level above 1) | wounds, bleeding, hunger, thirst, cold | 0 is death. Heals 6 an hour (12 asleep) while food ≥ 50, water ≥ 40 and not bleeding |
| Stamina | 100 | sprinting (9 a second), swings (5–14), jumps (8), swimming | Refills at 14 a second after a pause, half as fast when water < 15; its ceiling shrinks when food < 50 or rest < 40 |
| Food | 80 | 4 an hour | At 0: 6 damage an hour |
| Water | 80 | 6 an hour, more when hot | At 0: 10 damage an hour |
| Rest | 85 | 3 an hour awake | At 15 or less: exhausted, 20% slower |
| Body temperature | 37 °C | see *Warmth* | Under 35 °C: 8 damage an hour; over 39.5 °C: 6 |

Rates are per game hour (2.5 real minutes at the default 60-minute day), times the Hunger & thirst
setting; exertion drains food and water faster, sleep slows them to 45%. From the start, water lasts
about half a game day and food most of one. Under 20 health you also move 20% slower.

| Food and drink | Gives |
|---|---|
| Program Ration Bar | 25 food, −4 water, 10 stamina |
| Canned Beans / Canned Stew | 30 / 35 food, a little water; leaves an empty can |
| Hot Stew (canned stew heated at a campfire) | 40 food, 8 water, 4 health, and warmth |
| Huckleberries | 4 food, 3 water |
| Shelf Mushroom, raw / roasted | 6 food, −4 health / 12 food, 2 health |
| Venison, raw / roast; Hare, raw / roast | 16 food, −6 health / 40 food, 5 health, 10 stamina; 9 food, −5 health / 22 food, 3 health |
| Boiled Water / Stream Water (bottle) | 35 water / 25 water, −6 health; both give the bottle back |
| Flat Soda | 18 water, 20 stamina |

The Iron Gut perk takes most of the harm out of raw food and stream water.

### Warmth and fire
Your body holds 37 °C while what you feel is between 14 and 30 °C, and drifts 1.4 °C an hour
outside that. You feel the air (by season: autumn 1 °C at night to 13 °C in the afternoon, winter −6
to 2 °C; coldest around 03:00, warmest around 15:00; colder in rain, storms and snow, on rocky
slopes and riverbanks, and higher up) plus 4 °C of clothing, minus up to 6 °C of wind (30% of
that under a roof) and up to 8 °C when soaked, plus 3 °C under a roof (your structures overhead, or a
building's inside) and up to 14 °C beside a lit fire (nothing beyond 4.5 m of a campfire). Rain
soaks you outdoors and uncovered (WET on the tether); you dry slowly, three times faster by a fire.
The tether shows COLD under 35.8 °C, and the screen frosts at the edges.

**Fires.** A campfire must be lit to cook on: E, with a lighter or torch in your pack. Fuel burns in
real time: a stick 40 seconds, a bough bundle 25, cloth 30 (only when you hold it), a plank
2 minutes, a log 10. A new fire holds an hour of game time, at most 12 game hours. G (or E on a dead
fire) adds the fuel in your hand, else sticks, bough bundles, planks, then logs. It burns on while
you sleep and goes out when the fuel is gone. Its light shows you to the Hollowed, and it slowly
adds heat (attention, §9) to the area.

### Wounds, bleeding and the Bloom
* **Bleeding** (from Hollowed hits, bear traps and shotgun traps) costs health every minute and
  barely clots by itself. A Cloth Bandage stops it (+5 health), a Yarrow Poultice slows it (+12), a
  First Aid Kit stops it (+40). Painkillers give 12 health and 15 stamina.
* **Infection.** Every Hollowed hit and spore adds Bloom infection (times the Bloom infection
  setting). Under 12 your body fights it off (1 an hour); from 12 it grows (0.25 an hour) until
  treated: **Antifungal Tablets** take off 25. At 100 you turn, which is death. The tether shows
  INFECTION n% above 5.
* A raised guard takes its share off the wound and the infection as well as the damage.
* Warnings: a red flash and red wedges toward whoever hit you, a pulsing vignette under 35 health, a
  heartbeat under 30% (faster under 15%). Falls from more than about 4.5 m hurt; water breaks them.

### Sleep and death
E on your lean-to or bough bed → **Sleep**. Between 19:00 and 05:00 you sleep until 06:00, otherwise
you nap 2 hours; before a Hum you wake an hour ahead of it. You can't sleep during the Hum or with
an awake Hollowed within 25 m. Asleep, rest returns at 14 an hour, health heals twice as fast and
food and water drain at 45%. The bed becomes your respawn point, and the game saves when you wake.

When you die, the screen says what killed you. **Wake up** returns you to your last bed (or the drop
site) with 50 health and the bleeding stopped; what you lose depends on the On death setting. With
permadeath the button returns you to the menu.

## 6. Gathering and crafting

### Trees, logs and plants
* Chop with an axe: a Stone Axe chops 22 a swing, a Hatchet 40, a Machete 12 (more with
  Timberwright and the Chopping & digging speed setting). Grey firs and hollow larches give up to
  2–3 logs, paper birches and dead snags 1–2, plus sticks (and bough bundles from firs). Stumps stay;
  trees don't grow back. Chopping is loud, a falling tree louder, and both add heat (§9).
* Logs ride on your shoulder: two, three with Timberwright rank 2. They take no pack space but each
  slows you 12%, and with one on your shoulder Left mouse places it (§7) instead of swinging and you
  can't guard: drop logs (G) before a fight.
* **Harvest** (hold E): fireweed and slough sedge give 2–3 Plant Fiber, sword ferns 1; huckleberry
  bushes 2–5 Huckleberries and some fibre; willows 2–4 Sticks and some fibre; fir saplings 1–2
  Sticks and a Bough Bundle; deadfall ("Gather sticks") 2–4 Sticks; loose stones 1–2 Stones;
  yarrow 1–2 Yarrow; shelf mushrooms 1–2. Most plants grow back in 2–6 days; ferns, saplings and
  stones don't. A shovel digs the ground and sometimes turns up a stone.

### Crafting
Open the salvage roll (Tab): your pack on the left (bulk out of 40 to start, plus your shoulder
logs), and on the right flap what you know how to make, makeable ones first, each line showing what
you have against what it needs and any tool in brackets. Click to make it at once. At a station, E
(*Use Campfire*, *Use Workbench*) opens the roll with its recipes. Crafted tools and weapons come out
at quality 1 until Wits and the Handy perk raise it. *Knife* means a Kitchen Knife or Machete in your
pack; *axe*, a Stone Axe or Hatchet.

| By hand | Needs |
|---|---|
| Cordage | 3 Plant Fiber (or 2 Sinew for 2) |
| Bough Bundle | 1 Stick, 1 Plant Fiber |
| Stone Axe | 1 Stick, 1 Stone, 1 Cordage |
| Crude Spear / Stone Club | 2 Sticks, 1 Cordage / 1 Stick, 2 Stones, 1 Cordage |
| Torch | 1 Stick, 1 Cloth |
| Cloth Bandage | 2 Cloth (or 2 bandages from a Hare Pelt, with a knife) |
| Yarrow Poultice | 2 Yarrow, 1 Cloth |
| Rawhide Strips ×4 | 1 Deer Hide, with a knife |
| Can Chime | 3 Empty Cans, 1 Cordage; needs *Schematic: Can Chime* |
| **At a lit campfire** | |
| Boil Water | 1 Bottle of Stream Water |
| Roasted Mushroom / Roast Venison / Roast Hare / Hot Stew | 1 Shelf Mushroom / Raw Venison / Raw Hare / Canned Stew |
| Crude Spear | 2 Sticks, 1 Cordage |
| **At a workbench** | |
| Wood Plank ×6 | 1 Log, with an axe |
| Repair Kit | 2 Scrap Metal, 1 Duct Tape |
| First Aid Kit | 3 Cloth Bandages, 1 Painkillers, 1 Duct Tape; after reading two *Backcountry Medicine Quarterly* |

Only the campfire and the workbench can be built as stations for now.

### Tools, weapons and quality
| Item | Damage | Notes |
|---|---|---|
| Stone Axe / Hatchet | 16 / 24 | chop; the hatchet nearly twice as fast |
| Crude Spear | 20 | the longest reach (2.8 m); Right mouse throws it |
| Stone Club / Steel Pipe | 24 / 22 | blunt: they stagger |
| Machete / Kitchen Knife | 26 / 13 | knives; the machete takes limbs off, the knife is fast and quiet |
| Shovel / Claw Hammer | 15 / 12 | dig / repair, reinforce, dismantle (§7) |
| Torch / Flashlight | 9 / 8 | lights: 10 minutes of flame / a 28 m beam with 30 minutes of batteries |
| .38 Revolver | 55 | 6 rounds of .38 Rounds; Right mouse reloads; very loud |
| Stone | 12 | thrown |

The lighter gives 15 minutes of light. Quality runs Q1 to Q6 (Scrap, Worn, Serviceable, Good, Fine,
Pristine, coloured in the roll) and scales damage (0.85 + 0.1 × Q) and durability. Tools and weapons
wear with every hit and break at 0%; a Repair Kit (Left mouse on it in the roll) restores the held
one if worn, else the most worn one you carry.

## 7. Building

### Blueprints
Field Manual (B) → **Blueprints** → pick one → **Lay it out**. The ghost follows your aim: **R** turns
it 15°, **Left mouse** places it, **X** or **Right mouse** cancels. If it's red, the reason shows
under the crosshair: too far, too steep (25° at most), in water, blocked, inside a building, you're
standing in the way, or a tree or rock is in the way.

| Blueprint | Materials | Notes |
|---|---|---|
| Campfire | 6 Stone, 4 Stick | cook, boil, warmth, light |
| Lean-to Shelter | 10 Stick, 6 Bough Bundle, 2 Cordage | a roof; sleep, save, respawn |
| Bough Bed | 6 Bough Bundle, 4 Stick | sleep, save, respawn |
| Workbench | 2 Log, 6 Stick, 2 Cordage, 12 Nails | |
| Storage Crate | 6 Wood Plank, 8 Nails | 20 slots |
| Stake Barricade | 2 Log, 6 Stick, 2 Cordage | needs its schematic or the Builder perk |
| Log Wall (4 m) / Log Platform | 6 / 14 Logs | |
| Trapper's Cabin | 26 Logs | needs its schematic or Builder rank 2 |

For material blueprints, E on the ghost hands over whatever it still needs that you carry (the
prompt shows "Stone 3/6" and so on); it's built when everything is in. For log blueprints, carry
logs to the ghost and set one in each slot (Left mouse, or E on the slot). To take a placed ghost
down, look at it and hold X for a second (the line under the prompt says what comes back):
everything you handed over returns to your pack (or lands at your feet), and logs already set in a
log blueprint stay where they are, as ordinary logs.

### Freeform logs, support and collapse
With a log on your shoulder a preview log follows your aim: pale blue fits, pale green has snapped
to a log nearby (stacked in a course, end to end, side by side, notched at a corner, across as a
deck, or a beam on a post), red can't go there. **R** turns it 90°, **V** switches flat / upright post
/ pitched (for roofs), **Left mouse** sets it, **G** drops it.

A log needs the ground or another log under or beside it. Support flows out from logs on the
ground: resting on another log loses a little, hanging off the side of one loses a quarter (a fifth
when reinforced), so a chain of more than three overhanging logs comes down. A log nothing holds up
falls at once (pick it up again), and breaking a piece drops whatever it held up.

### The hammer and defending
Aim a Claw Hammer at your piece to see its health and what a strike will do:
* **Damaged**: Left mouse repairs it (a log: 2 Sticks for 120 HP; a reinforced log: 2 Sticks and
  2 Nails for 200; anything else: a quarter of its build cost).
* **Undamaged**: Left mouse twice within 3 seconds reinforces a log (2 Cordage, 6 Nails): 420 HP
  becomes 760, it spans further, and the Hollowed do 20% less to it.
* **Crouch and hold E**: dismantle it for half its cost, at least one of each thing it took (so a
  placed Can Chime comes back), less if it's damaged; a log comes back whole.

The Hollowed break whatever stands between them and you: a Hollow does 12 a blow to a 420 HP log, a
Rammer's charge 450. Wits and the Builder perk make what you build tougher. A **Stake Barricade**
does 14 damage to a Hollowed touching it, again every 1.2 seconds it stays, and wears as it works.
A **Can Chime** (hold it, Left mouse at the ground) rattles when anything walks through it, with
"Something rattled the can chime." when it's a Hollowed.

### Gardens and rain
The Field Manual's **Farming** blueprints are a **Garden Bed** (2 Logs, 6 Sticks, 4 Leaf Bundles)
and a **Rain Catcher** (1 Log, 8 Sticks, 2 Cordage, 4 Cloth).
* **Seed**: seed packets and seed potatoes turn up in kitchen drawers, sheds and feed bins; wild
  huckleberry bushes and yarrow sometimes give seed when you pick them; a potato plants a potato,
  and four huckleberries crushed by hand give two seeds.
* **Planting**: press **E** on a bed holding a seed (or carrying one) to plant it in the next free
  plot of four. Nothing will go in during winter.
* **Water**: plants grow only while the soil is wet. Rain soaks a bed under open sky; a bottle of
  water tops it up by half, a bucket soaks it (**E** when there's nothing else to do, or hold **X**
  any time). The empty bottle or bucket comes back. A soaked bed dries out in two to three days,
  faster in the heat.
* **Growing**: potatoes take about five good days, carrots four, beans four and a half, yarrow three,
  a huckleberry bush seven. Summer is best, autumn slow, cold nights slower; the "Crop growth speed"
  world setting scales it. Dry soil wilts a plant and kills it in a day or two; frost kills beans
  overnight, while berries and yarrow shrug it off.
* **Harvest**: press **E** on a bed with anything ripe. Annuals leave the plot empty (carrots, beans
  and yarrow may give seed back); a huckleberry bush and yarrow grow back. Pull dead plants with
  **E** (for a little fibre). Bake potatoes at a campfire, or make a garden stew (a potato, a carrot,
  beans, a bottle of boiled water and an empty can).
* **The rain catcher** fills when it rains, about two bottles an hour in a downpour, up to 24. Press
  **E** with empty bottles or a bucket to fill them (the water is murky: boil it), or drink straight
  from it. Under a roof it stays dry. Buckets also fill at streams.

### Traps and power
The Field Manual's **Defense** blueprints add three traps the Hollowed walk into on their own way to
your walls; its **Power** blueprints light and guard a base. Neither blocks your way: you walk
through a trap's frame (mind your step).
* **Spike Pit** (1 Log, 12 Sticks, 1 Cordage): a Hollow that walks in is staked (24), held for a
  couple of seconds, slowed to a crawl while it climbs out and staked again every second. The
  stakes dull as they work (half damage below a third of their health): mend them with a hammer.
  Step in yourself and it hurts.
* **Deadfall** (2 Logs, 4 Sticks, 3 Cordage, 4 Stones): the first thing under the hanging log brings
  it down (110, enough to drop a plain Hollow), loud. Press **E** to lift it again.
* **Tripwire Bell** (3 Sticks, 2 Cordage, 2 Scrap Metal): rings when a Hollow walks through and
  tells you where ("The tripwire bell is ringing: north-west, 40 m."). Everything near hears it too.
* **Generator** (schematic; a Small Engine, 3 Electrical Parts, 10 Scrap Metal, 8 Nails): **E** pours
  in a **Gas Can** (car trunks, auto shops; four hours flat out, longer at a light load, two cans to
  a tank), **E** again starts and stops it. It is loud and warm: the longer it runs, the more of
  them come looking. Small engines are built at the workbench too.
* **Wiring**: with a **Wire Spool** in your pack (toolboxes and hardware shelves; or strip two
  Electrical Parts at the workbench), hold **X** on a generator or a light to start a wire, then
  hold **X** on the next piece to connect it. A spool runs 10 m; no run is longer than 14 m. Pieces
  wired to each other share the power, so you can chain lights. Without a spool, hold **X** to cut a
  piece's wires (the spools come back).
* **Work Light** (a Work Lamp, Electrical Parts, Sticks, Cordage; 60 W): shines while it has power;
  **E** switches it. A lit base is easy to see.
* **Motion Floodlight** (schematic; 150 W): dark until a Hollow moves within 20 m, then it lights
  the ground and warns you.
* **Nail Sentry** (schematic; 200 W): **E** loads it with nails (up to 120); while it has power it
  shoots the nearest Hollow in sight within 14 m, a nail a shot.
* A generator gives 400 W: the pieces on its wires are powered in a fixed order until it runs out,
  so switch something off to free power for the rest. The "Base trap and sentry damage" and
  "Generator fuel use" world settings scale them.

## 8. Buildings are dungeons

Every building is built around a route. The front is locked, barricaded or chained; you find a way
in (a window, a back door, a clawed hole), work through to the **loot room**, and leave by a
shortcut: a door bolted from inside ("Slide the bolt back").
* **Sleepers**, dormant Hollowed lying on beds, slumped in chairs and pews, kneeling or standing,
  wake to noise, light and being seen up close (the Sleepers wake setting).
* **Ambushes**: some groups are *held*. They ignore ordinary noise and light, then rise together
  with an audible stir when their trigger fires: walking into a room, opening a door or window,
  taking a key or an item, searching a container, or a trap going off. Only gunfire, an explosion
  or an alarm within 14 m, or a blow, wakes them sooner.
* **The guardian** in the loot room is one infected tier up (§9) and usually rises when you walk in.
  Containers there roll twice, a tier higher.
* **Cleared** means every sleeper dead: "<Building> cleared." and 150 XP × its tier. If the Hum or
  a wanderer springs a trap or breaks a door while you're away, that ambush is spent and its
  sleepers are up and about when you return.

| Trap | What it does | What to do |
|---|---|---|
| Can chime (cans on a cord across a doorway) | Rattles loudly; your misstep alerts the sleepers near it | Watch doorways; it can't be disarmed |
| Bear trap (jaws half hidden in debris) | 25 damage and bleeding; holds your leg 2.5 s; loud | Crouch + E disarms it (2 Scrap Metal). Caught: tap Space or E |
| Shotgun wire (a wire across a doorway, a shotgun on a chair) | 9 pellets, up to 60 damage close, bleeding; very loud | Crouch + E on the wire (Cordage, Scrap Metal) |
| Loose boards | Groan every stride, loud standing, faint crouched; the first loud groan can spring an ambush | Cross crouched. A groan you didn't make means something is upstairs |
| Rotten floor | Gives way half a second after you step on it: a one-way drop to the room below | Step around it |
| Door alarm or bell | Rings 20 s; set off by you, it wakes the whole building and springs every ambush | Crouch + E disarms it (Scrap Metal); E while it rings smashes it quiet |

The Hollowed set traps off too; a sprung bear trap or shotgun can still be salvaged.

**Locks.** A key from the building opens its lock ("Unlock (key name)"); safes and lockers need
theirs. **Padlocks** (60 HP) and **chains** (90 HP) can be beaten or shot off, loudly; the door is
then just closed. **Deadbolts and bolts** can't be knocked off: find the key or bash the door down.
Doors and barricades take a beating; glass breaks at one blow, loudly. **"Bolted from the other
side"** is the shortcut: open it from inside.

**The vault** of the Tamsin Valley Savings & Loan in Pell's Crossing "needs the combination (or
cut it open)". The Vault Combination is somewhere in the bank; with it, E opens the door quietly.
Or hit the door with anything: it has 1400 HP of steel, every blow screeches like an alarm, and your
first blow wakes the whole building.

**Reading a building.** Windows the route climbs through are marked outside: a torn curtain over
the sill, a crate (two for a high sill) beneath, muddy boot scuffs and a bloody handprint, sometimes
a lantern burning inside. Padlocks, chains and bolts hang where you'd see them. Hold E to search a
container (1–3 s, a little noise) or the remains of dead Hollowed (Seeded and Bloomed carry better
finds). Containers restock only with the Loot respawn setting.

**Every run differs.** The run seed dresses each building: furniture broken or gone, lights on or
off, grime, stains and survivors' marks. Twelve buildings also switch rooms between runs (a room's
purpose and finish, which doors are shut, kicked in or locked, where an ambush waits, where the traps
lie), among them the Merrow House, Mile 9 Diner, Okafor farmhouse, Lou's trailer, the school, the fire
station and the bank. Ordinary houses, shops and workshops, like Larch Street's six, are generated
each run: tier 1, a bolted front, a way in round the back, a small ambush at the loot room.

| Tier | In Larch Hollow (higher tiers: better loot, tougher sleepers) |
|---|---|
| 1 | The Merrow House, Mile 9 Diner, the Post Office, Lou's Trailer, Larch Pond Bait & Boat, Lindqvist's Trapline Cabin, Cedar Ridge Fire Lookout, the Larch Street houses |
| 2 | Pell Pharmacy, Calder Hardware & Feed, St. Ansel's Church, Northwoods Tavern, the Volunteer Fire Station, Cordon Gas & Garage, Tamsin Valley Clinic, the Okafor Barn, Tamsin Timber Camp 4, Ashen Watch Camp, Tamsin River Campground |
| 3 | Pell Ranger Station, the Grange Hall, Pell's Crossing School, Tamsin Valley Savings & Loan, Timberline Motel, the Okafor Farmhouse, the Corvane Larkspur Adit |
| 4 | Larch Hollow Sawmill |

**Underground.** Below the ground it is always night for the Hollowed: in a cellar or a mine level they
see without light and run, whatever the hour, and your light is what they see. The **Corvane Larkspur
Adit**, at the foot of the Larkspur cliffs west of the drop site (a dirt track leads there), goes two
levels down: a timbered drift with a powder magazine and a refuge station, then a stope that broke
into a limestone cave. Bring a light, and the keys you find on the way.

## 9. The Hollowed and other threats

| Kind | Health | Hit | Running, day / night | Sight, day / night | From gamestage | Notes |
|---|---|---|---|---|---|---|
| Hollow | 110 | 11 | 1.5 / 4.3 m/s | 12 / 32 m | 1 | The townsfolk; slow and half blind by day |
| Lurcher | 90 | 9 | 3.8 / 5.6 | 20 / 40 | 3 | Thin and fast; runs even by day |
| Keener | 80 | 7 | 2.2 / 3.6 | 26 / 44 | 8 | Keeps 8 m off; when it sees you it screams, and every Hollowed within 120 m comes, with a few more it calls up |
| Dragger | 70 | 8 | 0.8 / 1.4 | 8 / 20 | in buildings | Legless and low |
| Blister | 130 | 9 | 1.4 / 3.2 | 22 / 36 | 12 | Spits spore globs from 4–16 m that leave a harmful, infecting puddle; bursts into spores when it dies |
| Husk | 220 | 16 | 1.3 / 3.4 | 14 / 30 | 25 | Plated: body hits lose 65% (bullets less); the head is soft |
| Rammer | 480 | 28 | 1.6 / 3.6 | 18 / 32 | 40 | 2.5 m of muscle; charges you, or through a wall |

You walk at 3.4 m/s, sprint at 6.2 and crouch at 1.7. Below its gamestage a kind is replaced by a
Hollow (sleepers keep their kind). Blister, Husk and Rammer can be switched off in the settings.

**Infected tiers.** From gamestage 15 some Hollowed are **Seeded** (×1.6 health, ×1.3 damage,
faster, pale threads glowing under the skin, ×1.8 XP); from 30 some are **Bloomed** (×2.4 health,
×1.6 damage, regenerating 3 HP a second, bursting into spores when killed, ×3 XP). The share grows
with gamestage, and sleepers in harder buildings roll tougher tiers. A setting can turn tiers off.

**Fighting.** Headshots do ×2.2, arms and legs ×0.7; taking the head off kills, and most Hollowed
that lose a leg crawl on. Blunt weapons stagger. Hold Right mouse to guard: it blocks a share of a
blow from the front (45% with a blade or axe, 60% with a club or pipe, 55% with the shovel, 30%
with a light, 25% bare-handed) for stamina, and an empty bar breaks it; you can't swing while
guarding. Step back from Blisters and Bloomed as they die: the burst weakens with distance.

**How they find you.**
* **Sight.** Daylight half-blinds them, but darkness doesn't hide you: they see without light.
  Crouching cuts the distance they notice you at to 55%, standing still to 75%; sprinting raises it
  to 125%. A light in your hand shows you from at least 1.6 × their sight + 30 m (about 80 m to a
  Hollow at night); a fire beside you makes you easier to see.
* **Sound.** Footsteps carry about 2 m crouched, 6 walking, 14 sprinting (more on wood, gravel,
  metal and leaves); doors, searching, a falling tree, glass, chimes, alarms and gunfire carry much
  further. Walls muffle sound; rain, snow and storms mask it.
* **Scent.** You leave a trail they follow, stronger moving or bleeding, weaker wet, none in water,
  carried by the wind. Flushed birds give you away too (§10).
* **Heat.** Noise builds up an area's heat (chopping, digging, gunfire, alarms, Keener screams,
  burning fires); it fades 14 an hour. At 35 a scout (one Hollow) comes to look, at 75 a Keener with
  two Hollows, at 120 a pack (a Lurcher and four Hollows).

**Day and night.** Night is 21:00 to 05:00 (the sun is up 06:15 to 19:15). After dark the Hollowed
see much farther (a Hollow nearly three times as far) and run: a Hollow does 4.3 m/s, faster than
you walk. Wanderers appear out of sight 70–120 m away in ones to threes: nearly twice as many at
night, half as many on day 1, more in town and forest.

### Ezra Vane, the lineman
You are not the first convict the Program dropped here. **Ezra Vane**, two drops before yours and a
lineman before that, is holed up in his line truck out in the timber with a broken leg: on the
main map west of Larch Pond, about 400 m north-west of the drop site; in a random world somewhere
300–900 m from the drop site, away from the roads (the directive *Find the lineman* points the
way). Press **E** to talk to him; give him a **first aid kit** or **painkillers** and he walks with
you.

* **Orders.** E on him opens his card: **Follow me**, **Stay here**, **Guard here** (Gather, Fetch,
  Give and Store are greyed: not yet). **H** whistles him to follow or to stay without the card.
* **Following** he keeps 3–6 m behind you, walks when you walk and runs to catch up; left far
  behind (over 120 m), or after you sleep, respawn or load, he turns up beside you. At night he
  carries a lantern: his own light, it doesn't give you away.
* **Fighting.** Following, he goes for Hollowed that are hunting near you and for whatever hits
  him; guarding, for anything that comes within 20 m of his spot (then he goes back to it);
  staying, only for what comes at him. The Hollowed and the Ashen fight him too, but they still
  come for you first when they see you. He never hits you, your blows and traps don't hurt him,
  and what he kills earns you nothing.
* **Downed.** At 0 health he goes down and the Hollowed leave him. Get to him with a **bandage**
  or a **first aid kit** and hold **E** for 4 s (it is used up): he gets up with a third of his
  health. Leave him three minutes and he's gone; he limps back to your bed (or the drop site) the
  next dawn with half his health. Under the one-life death penalty he doesn't come back.

### The Hum
* **When**: 22:00 on a Hum day until 04:00. By default the first is on day 7, then every 7 days (the
  slice: day 3, then every 7); the settings can move, jitter or switch it off.
* **Warnings**: the tether's forecast 24 hours ahead, "The Hum tonight" 6 hours ahead, "Within the
  hour, they come" 1 hour ahead, "THE HUM HAS BEGUN." at 22:00, and the HUD countdown through the
  last day. Deer and birds leave two hours before. You can't sleep through it, and the night glows
  a faint green.
* **Where and how many**: around your base (the centre of your structures within 40 m of you when
  it starts; if none, around you), from 55–85 m out, in waves from different compass directions over
  five hours: four waves at first, one more every second Hum, up to eight. In all: 12, plus 8 per
  earlier Hum, plus 0.4 × gamestage, times the horde size setting; at most 24 alive at once. About
  72% Hollows, 22% Lurchers, 6% Keeners; Blisters join from gamestage 12, Husks 25, Rammers 40.
* **How they move**: straight for you along the cheapest way. Walls cost them by their hit points,
  so they go round strong ones and through weak ones, breaking what's in the way.
* **They remember.** An approach where many died is flanked next time, the wall that held best gets
  a heavy siege group in the last wave, and a fast clear brings more Lurchers and Keeners. In the
  last 48 hours the tether shows how many to expect and what they learned.
* **At 04:00** "The Hum fades." Survivors wander off and root into the soil as fungal mounds (§10).
  The game saves, you earn 500 XP (50% more for each Hum survived before), and by default a supply
  drop comes in.

**Getting through one:** be at your base, behind walls, before 22:00. Logs make them stop and break;
reinforce the faces they'll hit and stake the approaches. Keep the hammer, sticks and nails for
repairs between waves, bandages and antifungals for bites, and stamina for your guard. Kill Keeners
first.

### Supply drops
By default a Program drone brings one when each Hum ends (or at noon every 7th or 3rd day, by the
setting): "A Program drone is overhead. Supplies are coming down." The canister falls under a chute
110–300 m from you with a red flare and smoke, and lands loudly enough for the Hollowed to come and
look. The tether lists each drop's distance, direction and state (INBOUND, FALLING, LANDED, OPENED)
and marks it on the map. Hold E to search it; its contents improve with gamestage.

## 10. The Bloom, weather and wildlife

**The Bloom on the land.** Where it has taken the ground, pale threads climb the trunks (larches
most), a web binds the forest floor, caps fruit, plants wilt, and at night it glows a cold, pale
green, brighter on Hum nights. For now it's a warning, not a hazard: the ground doesn't infect you.
After a Hum, survivors leave **fungal mounds** for six days; E (*Tear open the mound*) gives 2–4
Bloom Mycelium and a 12% chance of a Bloom Core Sample. Waystation 9 buys both, and pays in Program
Scrip.

**Waystation 9** stands on Route 9 in the south of Larch Hollow, just short of where the river
leaves the valley: a ring of barriers, two towers, a hatch counter and a contracts board (a yellow
square on the tether). Inside the wire nothing rises, and the guards shoot any Hollowed that follow
you in. At the **counter** (E) the quartermaster buys what you carry (keys, notes and Program
caches aside) and sells what the drones bring, for scrip; the shelves restock every three days.
At the **board** (E) he posts four contracts a day; you can hold three:
* **Clear**: every Hollowed in a building put down and its stores (the loot room) searched.
* **Fetch**: a sealed Program cache left in a building; pick it up and bring it back.
* **Defend**: a relay cache by a building; hold E on it to start the uplink, then stay within 30 m
  while waves come for it until it finishes (leave for 8 s and it drops; start it again).
Contracts show on the tether as rings, filled once done; report back to the board to be paid in
scrip, XP and **standing**. Standing (Unknown, Known, Trusted, Program asset) opens better stock,
harder contracts and a discount.

**Weather** changes every few hours, weighted by season: Clear (+1 °C), Overcast (−1), Valley Mist
(−1.5, still air, fog in the hollows, sound a little muffled), Rain (−3, soaks you outdoors, sound
carries about two thirds as far), Storm (−4, heavy rain, gusts, lightning and thunder, sound carries
less than half as far) and, mostly in winter, Snowfall (−4, snow settles, sound muffled). Ground fog
gathers at dawn and dusk and puddles last hours. Seasons run 12 days each (spring, summer, autumn,
winter). The moon has a 10-day cycle: a full moon lights the clearings, a new moon leaves the night
near black. Moonlight only helps you; the Hollowed see in the dark anyway.

**Wildlife** (a setting can turn it off):
* **White-tailed deer** in bands of two to five at forest edges and in meadows, most at dawn and
  dusk, bedding down at night. They see a standing person at 80 m, won't let you inside 32 m, smell
  you downwind at 90 m and bolt at gunshots and Hollowed. **Snowshoe hares** sit tight until you're
  almost on them.
* **Songbirds and crows** flush when you or a Hollowed come close, or at a loud noise, and the
  Hollowed hear the flush (crows the loudest). Crows circle, calling, over whatever put them up.
* **Hunting**: kill a deer or hare with any weapon; the carcass bleeds scent the Hollowed follow.
  Hold E with a knife or axe (in hand or pack) to butcher it: a deer gives 3–5 Raw Venison, a Deer
  Hide, 2–4 Bone and 2–3 Sinew (one less with an axe); a hare 1–2 Raw Hare, a Hare Pelt and maybe
  Bone or Sinew. Roast the meat at a campfire. Animals and carcasses aren't saved: reload and the
  carcass is gone.

* **Hollowed hounds** (world setting *Hollowed hound packs*, on by default). From gamestage 6 a
  wandering group may be a pack of 3–5 starved Bloom dogs instead (twice as likely at night), and
  the heat system can send a pack after you. The first hound to see you howls, which the Hollowed
  hear too, and every hound of the pack within 90 m joins the chase. They spread round you and
  close from different sides, bite and break off, then come again, and they track by scent three
  times better than a Hollow. A lit flame in your hand (torch, lantern or lighter, not the
  flashlight) keeps a hound in front of you about 4 m off, circling; one behind you still bites.
* **Murmurs** (world setting *Murmurs*, on by default). By day, a crow flock you flush may follow
  you instead of settling, more likely where the Bloom is thick. It rings overhead, and every caw
  marks where you stand for the Hollowed in earshot. Shake it off by staying under cover (a roof, a
  floor above, thick canopy) for a while, by a gunshot or explosion near the flock (which has its
  own noise cost), or wait for nightfall, when the crows roost, or for them to give up. A status
  line tells you when a Murmur starts and ends.

Not in the game yet: wolves and the Ashen tribes.

## 11. Progression

| XP source | XP |
|---|---|
| A kill | Hollow 40, Lurcher 60, Keener 80, Dragger 30, Blister 110, Husk 150, Rammer 320; ×1.8 Seeded, ×3 Bloomed |
| Surviving a Hum | 500, and 50% more for every Hum survived before |
| Clearing a building / first time inside one / first search of a container | 150 / 20 / 4, each × the building's tier |
| Felling a tree / setting a log / reinforcing / finishing a blueprint | 10 / 5 / 8 / 30 |
| Crafting | tools 10, weapons 8, traps 6, medical 3, cooking and light 2, materials 1 |
| Reading a note / a hunting kill / butchering | 15 / 15 / 8 |

All × the XP multiplier; digging pays nothing. Level *n* to *n*+1 takes 400 × 1.12^(*n*−1) XP (400,
448, 501 …). Each level gives a point, and you start with one; spend them in the Field Manual's
**Record** tab, where each locked choice says why ("needs Sinew 3").

**Attributes** go from 1 to 10; a level costs 1 point up to 3, 2 up to 6, 3 up to 9 and 4 for 10.
**Perks** cost a point a rank and need their attribute at the level shown:
* **Sinew** (+3% melee damage, +2 pack space a level): Timberwright (1/3/5: +20%, then +20% and a
  third shoulder log, then +30% chopping); Heavy Hands (1/4: +20% blunt damage and more stagger a
  rank); Packhorse (2/5: +8, then +10 pack space).
* **Grit** (+5 max health, +3% stamina recovery): Thick Skin (1/4: 8% less damage, 25% less
  bleeding a rank); Second Wind (1/3: +20%, then +25% stamina recovery); Iron Gut (2: 60% less harm
  from bad food and stream water).
* **Keen** (+0.05 loot quality, +3% firearm damage): Scavenger (1/3: +0.3 loot quality, 20% faster
  searching a rank); Sleeper Sense (2: dormant Hollowed within 8 m outlined through walls, guardians
  in a warm rim); Steady Aim (1/4: +20% firearm damage and 25% less sway a rank: shots land
  closer to the crosshair).
* **Quiet** (3% less noise, +1% move speed): Soft Step (1/3: 20% less noise a rank); Shadow Kin (2:
  30% harder to spot); Light Foot (1/3: sprinting costs 20% less a rank).
* **Wits** (+0.2 crafted quality, +3% structure toughness): Handy (1/3: +1 crafted quality a rank);
  Field Medic (1/3: healing items heal 25% more a rank); Builder (1/4: +15%, then +20% structure
  toughness; rank 1 teaches the Stake Barricade, rank 2 the Trapper's Cabin).

**Gamestage** = (level + days survived × 1.5) × the gamestage multiplier, shown on the tether (GS)
and in the Record. The higher it is, the worse what hunts you (tiers, specials, Hum size) and the
better what you find.

**Learning.** Reading a schematic (Left mouse in the roll) teaches its blueprint or recipe; notes go
to *Notes found* in the manual. Two *Backcountry Medicine Quarterly* unlock the First Aid Kit;
*Timber & Trade Monthly* unlocks nothing yet.

**Program directives** are chapters of goals that pay XP and supplies; only the open chapter counts,
and finishing it opens the next. The tether shows the next two, the Record tab the whole chapter.
1. **Arrival**: fell three trees; make a stone axe; build a campfire; raise a lean-to; sleep.
2. **The Cordon**: search ten containers; go inside a building; put down ten Hollowed; read two
   notes; clear a building; disarm two armed traps.
3. **Holding Ground**: set twenty logs; survive a Hum; recover a supply drop; reach level 7; clear a
   hard building (the ranger station, the grange hall, the Timberline Motel or the Okafor farmhouse).
4. **Into the Bloom**: kill a Seeded or Bloomed; kill a Blister, Husk or Rammer; survive three more
   Hums; reach level 12; clear the sawmill.

A random world may lack those buildings. Then the nearest building of the same tier to the drop
site stands in, and the tether and the Record name it ("Clear Tamsin Valley Savings & Loan"); if
the world has no building of that tier at all, the goal shows as "no such building in this world"
and its chapter goes on without it.

## 12. Saving and loading

* **One save per run.** A new game takes the next free slot (run1, run2 …) and every save of that
  run goes there, so a new game never overwrites another.
* **It saves** when you wake from sleep, when a Hum ends (04:00), on F5, and with the pause menu's
  *Save* or *Save and quit to menu*. Nothing else saves: quitting without saving, or a crash, loses
  everything since. You can't save while dead, and F5 does nothing while you sleep.
* **Loading**: *Continue* (newest save) or *Load RunN* on the main menu; F9 or the pause menu's *Load
  last save* reloads this run. *Load last save* and *Quit without saving* ask you to press twice.
* If the game died mid-save, the previous save loads instead. A newer version's save won't load in
  an older build; older saves are upgraded. Permadeath deletes the run's save when you die.
* A random-world run reads its world from `worlds\random\`; if that's gone, the world is generated
  again from its settings (the same, unless the generator has changed since).
* To back up or delete a run, copy or delete its folder in `saves\`.

## 13. Performance and troubleshooting

| Graphics preset (Options; applies at once) | Main differences |
|---|---|
| Low | 67% render scale with FSR 1; no global illumination, SSAO or volumetric fog; shadows to 60 m; 700 m view; a quarter of the grass |
| Medium | 80% with FSR 2; SSAO and volumetric fog; shadows to 90 m; 1 km view; half the grass |
| High (default) | Full resolution with TAA; SDFGI global illumination; shadows to 130 m; 1.4 km view |
| Ultra | Adds SSIL and screen-space reflections, sharper shadows; 2 km view; all the grass |

If it stutters, try Medium, then Low (rain and snow density follow the preset too). V-sync is on by
default. A world's first load shapes and caches its terrain, so later loads are quicker; random
worlds of 5 × 5 or less load comfortably. Setting the environment variable `HOLLOWMERE_GFX` to
`low`, `medium`, `high` or `ultra` forces a preset at start, if the game fails before you reach
Options. The packaged build has no frame counter (F4 is a developer tool).

| Problem | What it means, what to do |
|---|---|
| Stand-in shapes, no textures or grass; the "Placeholder world" notice | You're running the source without generated assets: play the packaged build |
| The "Godot X … made for Godot 4.7.2" notice | Use the 4.7.2 editor, or the packaged build |
| Windows says "not responding" while loading | The end of the load still has a few long steps (the biggest buildings, terrain setup), and a world's first load shapes its terrain. Let it finish |
| Fog, weather or lighting look wrong | Godot fell back to OpenGL: update the GPU driver (Vulkan 1.2 or Direct3D 12 is needed) |
| "Could not load …" on the menu | The reason follows: the save is "missing or damaged", or "from a newer version of the game" |
| A crash | Send `logs\godot.log` before starting the game again (Godot keeps a few older logs beside it, dated), the console window's text if you used Hollowmere.console.exe, what you were doing, your GPU and preset, and the run's save folder if a save is involved |
