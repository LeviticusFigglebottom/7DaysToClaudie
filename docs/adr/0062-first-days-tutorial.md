# ADR-0062: The first-days tutorial: Program cards on the tether, then Ezra's distress call

**Status**: Accepted · 2026-10 (backend; the journal tab, HUD nudge and map marker are the
Presentation session's)

## Context
The owner asked for "an optional, basic tutorial, in a dedicated journal tab, instructing how to make
some essential early game items, and culminating with receiving a distress signal on the wrist
device, leading to Ezra." The closest system is the Program directives (ADR-0015): chaptered goals fed
by gameplay events. They say *what* to do, not *how*, and Ezra (ADR-0058) is only reached through the
chapter-3 directive *Find the lineman*, which could never complete if he was recruited before chapter
3 opened (a recruit happens once a world, and only the open chapter counted).

## Decision

### Content: `data/tutorial/first_days.json`, kind `tutorial_step`
Each step is a `TutorialStepDef`: `id`, `order`, `title`, `body`, `event`, `targets`, `count`
(unknown fields are errors; targets are cross-checked like DirectiveDef's; `order` is unique). The
eight cards, in the Program's terse voice, quote the real recipes and blueprints (test_tutorial checks
the ones named):

| # | Step | Event (targets, count) |
|---|---|---|
| 1 | Gather sticks, stones and fibre | gather (plant_fiber, stick, stone; 6) |
| 2 | Make a stone axe (cordage from 3 fibre; 1 stick, 1 stone, 1 cordage) | craft (stone_axe) |
| 3 | Fell a tree | fell_tree (the player's own; Ezra's don't count) |
| 4 | Build a campfire (6 stones, 4 sticks; light it, feed it) | build (campfire) |
| 5 | Fill and boil water | craft (water_bottle_clean) |
| 6 | Make a cloth bandage (the 2 issued cloth) | craft (cloth_bandage) |
| 7 | Raise a shelter (lean-to, or a bough bed) | build (lean_to, bough_bed, bedroll) |
| 8 | Sleep in your bed (respawn point, save) | sleep |

Events reuse DirectiveDef's names; `gather` (`Events.item_picked_up` for the local player, so a
harvest, a pickup or a container take) is the one new hook. The torch is left out: it needs a third
cloth, and the start kit's two go to the bandage, which matters more (he is hurt).

Keys are written `{key:<input action>}` and shown by `TutorialTracker.render_body()` through
`PlayerInteraction.key_label`, the function every interaction prompt uses since TD-119, so a rebound
key reads right. A placeholder naming an action not in `input_bindings.json` is a content error.

### `TutorialTracker`, a GameWorld module (`world.tutorial`)
Wired like DirectiveTracker. API for the UI: `is_enabled()`, `steps()` ({id, title, body (raw),
done, current, progress (capped), count}), `distress()` ({received, companion_id, position, text}),
`render_body(text)`; `Events.tutorial_changed()` on any change and
`Events.tutorial_distress(companion_id, position)` once. State lives in `PlayerState.tutorial`
(`TutorialProgress`).

* **Any order.** Every step counts whenever its event happens; `current` is the first by order not
  done. Strict order would make a player who lit a fire before making the axe do it again, and the
  cards read as a checklist anyway.
* **XP:** each finished step pays `tutorial_step` (10) through `progression.award` (ADR-0015). The
  directives already pay for the same early work, so this stays small (80 in all).
* **Optional twice over:** the world setting `tutorial` (Survival, default on; ADR-0014) and the
  player's own switch, the `tutorial.set_enabled {enabled}` command (saved). Off, nothing is tracked
  and no call comes; turned back on, it resumes where it stood. It can't be turned on in a world whose
  setting is off. Ezra stays findable as before either way.

### The distress call
When the last step finishes, the call is scheduled `delay_minutes` (45) of game time later
(`data/config/tutorial.json`, saved as `distress_due`). It is delivered on the first tick after that
which is not during the Hum, not while the player sleeps and not while the world loads:
`tutorial_distress("ezra", camp)` and the radio text from the config (Ezra, hurt, in his line truck
by the power line, needing a first aid kit or painkillers, as in ezra.json and *Find the lineman*).
The camp is `CompanionDirector.camp_spot()`, or the camp building's own position from
`PoiManager.all_buildings()` when it is not built yet (a streamed world). If Ezra is already
recruited or dead, or the world has no camp, the call is skipped: `received` true, `text` "".
Recruiting him between the last step and the call skips it too.

### Find the lineman counts in any chapter
`recruit` is now a once-a-world event (`Directives.ONCE_EVENTS`): its directives count whichever
chapter is open, and a loaded save with Ezra already recruited credits it on setup. So the call does
not unlock or advance *Find the lineman*; following it and giving him the aid simply completes it,
with its reward, early. This also fixes the existing stall for players who found him on their own.

### First aid for him
`companion.recruit` takes one of ezra.json's `recruit_items` (first aid kit or painkillers); a bandage
only revives him once he is with you. Neither is craftable early (the first aid kit needs a workbench
and two medicine quarterlies), so the bandage card says where they are found (medicine cabinets and
nightstands) and the radio text says a bandage won't hold. Painkillers are in the common medical and
nightstand loot tables, so a first trip into Pell's Crossing usually finds some (TD-375).

### Saves
`PlayerState.to_dict` writes an optional `tutorial` ({enabled, progress, done, distress_due,
distress_received, distress_heard}); no version bump. A save without it is marked `legacy`; on load
the tracker counts the tutorial done (call received, none heard) when the clock is past day
`old_save_done_after_day` (2), else it starts from the first card.

## Consequences
* A new player gets eight practical cards and, on day 1 or 2, a reason and a direction to go to Ezra.
* The journal, the nudge and the marker are presentation; the backend needs no UI to run.
* An old save on day 1 or 2 starts the tutorial from zero even if the fire and bed already stand
  (TD-376).
