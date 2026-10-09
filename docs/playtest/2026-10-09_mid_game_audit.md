# Mid-game UX audit (2026-10-09): days 8 to 22

This carries the first-week audit (2026-10-09_first_week_audit.md) on from day 8 to the morning
after the third Hum. It covers:
* perks;
* a defended, powered base with a workbench and a garden in the rain;
* Ezra's errands;
* the Ashen (a scout, a raid, a torch held up);
* contracts;
* two dungeons cleared along their routes (the Consolidated School, tier 3; Larch Hollow Sawmill,
  tier 4);
* the Corvane Larkspur adit;
* hounds, a wolf and the deep-wood nest;
* the second and third Hums, each with a Rammer.

## How it was run

`make first-week FIRST_WEEK_ARGS=…` or, for the mid game alone,
`godot --headless --path game -s res://src/tools/cli/first_hour.gd -- --out build/mid_game --mid-only`
(headless text, about 4 min), or `make first-hour FIRST_HOUR_ARGS="--mid-only"` (rendered,
about 30 min). `--mid-only` finishes the journal and recruits Ezra by command, then starts on
day 8.

**Stated plainly:**
* **God mode** is on for the whole mid game: the audit wants every screen, not a run's end.
* The driver adds materials (logs, nails, scrap, electrical parts, seeds and so on) and learns
  the three schematic blueprints, because it skips the days it would have spent finding them.
* It keeps the player fed and watered over skipped days.
* It clears a dungeon by standing by each sleeper and killing it outright, not by fighting.
* Days pass by `set_time`. The Hum nights run on the clock in 15-minute steps.

**Not covered:** the field lab and a pool building in a random world (this run is the main map,
where neither is placed); the adit's buried levels walked through (only its mouth and its plan:
3 levels, 15 sleepers); wolves as a pack (one `grey_wolf` spawned); a Murmur (a crow flock's state,
not reachable from the driver).

## Findings

| # | Step | Issue | Severity | Owner | Proposed fix / status |
|---|---|---|---|---|---|
| M1 | Base defence | The nail sentry and the motion floodlight treat Ezra as a target. `BaseTechNode._nearest_enemy` walks the "enemies" group, and his body is an Enemy with `ally` set. The floodlight warned "caught movement: north-west, 9 m" as soon as it was powered with him at the base. The sentry (same lookup, with sight) would fire on him. He went down during the day-14 Hum ("Ezra: 'Agh!'", "Ezra is down"). | High | hub (base tech) | Skip allies in `_nearest_enemy` (`if e.ally != null: continue`), with a test that a powered sentry ignores a companion in range. |
| M2 | Base defence | A light with no power says "[E] Switch the work light off (no power)": it offers to switch off what isn't on. | Low | hub (base tech) | "[E] Switch the work light on (no power: wire it to a running generator)". |
| M3 | Base defence | The generator ran about 12 game hours on one gas can, then "The generator coughs and dies: out of fuel." Clear, but nothing warns before it dies, and a base's lights go out with no sign of it from inside. | Low | hub (base tech) | A line at 10% fuel ("The generator is running low."). |
| M4 | Building | Every base piece's prompt said what it is and what it wants: "[E] Fuel the generator (gas can)", "hold [X] to run a wire from here", "[E] Load nails (0 / 120)", "[E] Deadfall (set: keep out from under it)", "[E] Tripwire Bell (strung)". A blocked spot says "Can't build here: a tree or rock is in the way." | — | — | Works. |
| M5 | Repairs | The hammer's hint names the cost and what is missing: "repair: 1 Log, 2 Stick, 1 Cordage, 3 Nails (missing)". The refusal says it in full. | — | — | Works. |
| M6 | Garden | Planting and watering read well: "[E] Plant carrot seeds (4 left)", "hold [X] to water the bed". | — | — | Works. |
| M7 | Cold, every night | From day 8 on, "You're freezing. Find a fire, now." came every hour of every night away from a fire, up to ×2 on one line. It's right, but in a long night it is the line you see most. | Low | hub (survival warnings) | Repeat it only when the player gets colder, or every 2–3 hours. The tether's vitals carry it between. |
| M8 | Level-ups | Clearing the school and the sawmill paid enough XP for ten level-ups in a few minutes, and each came as its own "Level N. N points to spend…" line (Levels 3 to 12). | Low | Presentation | **Fixed:** a burst of levels is said once, at its highest, when none has come for 2.5 s. |
| M9 | Dungeons | Both cleared cleanly: "Consolidated School cleared." and "Larch Hollow Sawmill cleared.", 15 sleepers each, with XP. The driver kills outright, so fights, routes and loot rooms are untested here (poi_walk covers routes). | — | — | Works, as far as this run goes. |
| M10 | The Ashen | The scout and the raid announce themselves ("Drums in the trees. The Ashen are coming.") and end ("The Ashen are gone back into the trees."). Holding a torch up at them said nothing: no line, no sign they shied from it. | Med | Creatures (the Ashen) | A bark or line when the fire turns them ("They won't come near the flame."), so the player learns that fire works. |
| M11 | Ezra | The Ashen scout downed Ezra within seconds of arriving ("Ezra is down. Hold E on him with a bandage…"). The prompt to revive him is clear. | Low | Creatures | Check whether a scout (OBSERVE) should be fighting at all. |
| M12 | Contracts | The board offered three cache recoveries and a defence. Taking three at once works ("Contract taken: …" each). Carrying the caches back wasn't driven (it needs the walk). | — | — | Works. |
| M13 | The Hums | Day 14: 23 came with a Rammer, and the tripwire bell rang its bearing ("The tripwire bell is ringing: south, 6 m."). Day 21: 35 came. The reports and dawn lines came paced. | — | — | Works. |
| M14 | Lore trail | No on-screen line in the mid game named the cause of the outbreak. "Corvane" appears only as a company's name, which the trail allows. | — | — | Clean. |

## Frames
`2026-10-09_mid_game_frames.webp` (rendered run): the powered base, the workbench, the garden,
the school, the Ashen, the hounds, the nest, and the day-14 Hum.

---

# Part 2: the gaps (routes walked, a random world, wolves, a Murmur)

`--gaps` walks a building's intended route (its POI `route` cells, in order, each on its own
level), logs the screen's words at every point, frames every third one, and uses whatever the
interaction ray offers. Then it puts down the sleepers. Afterwards it sends a wolf pack at the
player at night and sets a crow flock following them. God mode is on throughout.
* **Main map:** `… -- --out <dir> --gaps`, the Corvane Larkspur adit (18 route points over 3
  levels).
* **Random world:** `… --gaps --world random --world-seed 1 --world-set size=5`. Every size-5 seed
  tried (1, 2, 3, 4, 6, 8, 9, 11) places the field lab; seed 1 puts it in region A4. The run took
  the field lab (22 points over 2 levels, tier 5) and, as "a pool building in a random town",
  the first tier-2+ building of the world's own pool that the main map doesn't have: the Ashen
  Watch Camp (12 points).

**What the route walk can't judge.** It stands on each route cell and looks at the next; it
doesn't pick up the keys and keycards the route names, or try the readers they open. So "the
route can be walked" is checked by poi_walk and TraversalAudit, not here. Here: what the player
sees and is told on the way.

| # | Step | Issue | Severity | Owner | Proposed fix / status |
|---|---|---|---|---|---|
| G1 | Adit, field lab, watch camp | All three routes ran end to end and each building cleared ("Corvane Larkspur Adit cleared.", 15 of 15; "Corvane Field Lab cleared.", 24 of 24; "Ashen Watch Camp cleared.", 9 of 9). The exits named their action: "[E] Slide the bolt back". | — | — | Works. |
| G2 | All three routes | Between the doors, the route gave the player almost no prompts. In the lab, only "[E] Open door" (the admin module), "[E] Search Minus-80 Freezer" and the escape hatch's bolt over 22 points. The keys, keycard readers and airlocks the route turns on weren't offered from the route cell itself. This is a limit of the walk, not a finding against the buildings. | — | Presentation (driver) | Next round: walk to each route point's interactive (key, reader, hatch) rather than its cell. |
| G3 | Watch camp | A bear trap's line said "Struggle free (Jump)", the only line in the game that names an action instead of its key. | Low | Presentation (text in poi_pieces.gd) | **Fixed:** "A bear trap has your leg. Struggle free: [Space]." (the bound key). |
| G4 | Wolves | The pack hunted as it should: 10 m, then 5, 3 and 2 m within 16 s, at night, in both worlds. Nothing said so: no line, and with sound captions on no caption for the howls (the pack plays `voice/wolf_howl`). Captions only reach sounds that GameUI hooks one by one. | Med | hub (an Events signal) + Creatures | A generic `Events.sound_caption(text, at)` that any system can emit with a sound. GameUI shows it with its bearing when captions are on ("[wolves howling, north-east]"). WolfPacks emits it from `play_howl`. I'll do the GameUI side as soon as the signal exists. |
| G5 | A Murmur | Clear and in the game's voice: "Crows are circling over you, calling. Everything can hear where you are." | — | — | Works. |
| G6 | The roll at 720p | An item's card, shown beside the cursor, covered the recipe sheet (frame `m_workbench_roll`). | Low | Presentation | **Fixed:** the card flips to the cursor's left when it would cover the sheet (a test checks it). |
| G7 | Streaming and the roll | On the random world, a building streamed out while one of its containers was open in the roll. The roll then read the freed container every frame (one script error a frame) until it closed. | Med | Presentation | **Fixed:** the roll closes before reading a freed container (a freed object compares equal to null, so it tests validity), with a test. |
| G8 | Lore trail | No line on screen named the cause of the outbreak in the adit, the lab or the camp. The lab's own words (container and door names) keep to its tier-5 place in the trail. | — | — | Clean. |

The mid game's frames: `2026-10-09_mid_game_frames.webp` (the powered base, the workbench roll at
720p, the garden in the rain, the Ashen raid and the torch, the school, the adit mouth, hounds,
the nest, the day-14 Hum).
