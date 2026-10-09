# First-hour UX audit (2026-10-09)

A fresh-eyes pass over the first hour of play as the owner will meet it: a new game on the main
map (survival, run seed 4471), from the intro to a save and Continue.

## How it was run

`make first-hour` (new: `src/tools/cli/first_hour.gd`) drives the steps in one game. The world
loads once, then the run goes through the steps below. At each step it saves a frame and writes
every word on screen to `build/first_hour/first_hour.txt`: status messages since the last step,
the prompt and its hint, the loading line, and every visible label.

* Two rendered runs (xvfb + lavapipe, 1280x720, about 48 min each): one before the fixes and one
  after. The 720p window is deliberate: it is the smallest screen we support, and it is where
  layouts break first.
* Three headless dry runs (text only, about 3 min each).
* The intro, watched and skipped, comes from the earlier `ui_shots` intro cards and
  `intro_load_probe` (2026-10-09_intro_load_frames.md); it is not repeated here.

**Caveats.** This container has no generated assets, so the world is procedural stand-ins
(boxes, flat foliage). Visual notes are about the UI over that world, not the art. The driver
teleports and aims rather than walking, so travel times and getting lost are not tested. A
human pass still has to judge pacing.

Severity: **High** blocks or misleads a new player; **Med** costs them time or reads badly;
**Low** is polish. Size is the fix's effort (S/M/L).

## Findings

| # | Step | Issue | Severity | Owner | Proposed fix / status |
|---|---|---|---|---|---|
| 1 | Waking | Nothing tells a new player what to do first, or that the journal exists. The first journal line only appeared after the first step was done. | High | Presentation | **Fixed (56f4267):** after the load and the intro, "Journal: Gather sticks, stones and fibre  [B]" is announced once. |
| 2 | Gathering | A harvest or pickup gave no on-screen feedback, only a rustle. With six items to bring in, the player can't tell what they got. | High | Presentation | **Fixed (56f4267, a204cae):** a quiet feed bottom right ("+3 Stick", "+5 Huckleberries"); repeats add up on one line. The headless run shows it; on lavapipe the lines had faded before the frame was taken. |
| 3 | Every prompt | Prompts and hints were unreadable over bright things: a lit campfire, the pale blueprint ghost, snow, the pond. | High | Presentation | **Fixed (a204cae, placement fixed in the next commit):** a dark plate behind each prompt line, sized to its words, centred under the crosshair (a test checks it). |
| 4 | Distress call | The call (about fifty words) was one unwrapped line that ran off the screen, and it faded after 4 s like any message. | High | Presentation | **Fixed (56f4267):** messages wrap at 820 px and stay for their reading time (the call: about 18 s). It is also kept in the journal. |
| 5 | Death → Wake up | In the rendered run the death screen's words stayed over the world after Wake up, and the pause menu then refused to open (it waits for the overlay). The death fade-in and the wake fade-out ran two tweens at once. | High | Presentation | **Fixed (a204cae):** one tween drives the overlay, Wake up clears the words at once, and standing again always lifts it. |
| 6 | Ezra's card | Pad B could not close Ezra's order card (CompanionScreen wasn't on GameUI's close path): a gamepad dead end. | High | Presentation | **Fixed (56f4267)**, with a test. |
| 7 | Felling | A grey fir took 33 swings and stamina emptied after 8. **Partly my driver:** it pressed attack every 54 process frames, which headless is much less than a swing, so presses arrived mid-swing. Creatures also found and fixed swings that missed trunks. | High → resolved | Creatures + Presentation (driver) | **Fixed:** Creatures' felling fix (every swing lands), and the driver now waits 0.9 s of physics ticks between presses (1f1d996). Re-measured: the same fir falls in 10 swings with 67 stamina left. |
| 8 | Crafting the axe | A crafted Stone Axe doesn't go on the toolbelt (it stays in the pack). The card says to put it there, but new players miss this. | Med | hub (PlayerActions) | Put a crafted tool or weapon in the first empty belt slot. The roll already supports dragging it elsewhere. |
| 9 | Crafting | The roll's recipe sheet opens on the first ready recipe (Arrow Stone), not the one the journal asks for (Cordage, then Stone Axe). | Med | Presentation | **Fixed (d71c82c):** the sheet opens on the step's recipe when it is ready, else on a ready ingredient toward it (Cordage before the Stone Axe), with a test. |
| 10 | Every step | Each finished step prints two lines for one deed: "Directive complete: Make a stone axe. +40 XP" and "Journal: Make a stone axe ✓  Next: …". | Med | hub (directives / tutorial) | Fold the directive's XP into the journal line when both complete together, or don't give the arrival directives the same names as the journal steps. |
| 11 | Campfire directive | "Directive complete: Build a campfire.  +60 XP  ·  1 Bottle of Boiled Water" reads like a list of things done, not a reward. | Low | hub (directives) | "+60 XP, and a Bottle of Boiled Water". |
| 12 | Sleep directive | "Sleep under your roof" completes on a roofless bough bed. | Low | hub (directives) | "Sleep in your bed". |
| 13 | Field Manual | Opening Blueprints after the Journal lit both tabs (set_pressed_no_signal() doesn't release the ButtonGroup's others). | Med | Presentation | **Fixed (a204cae)**, with a test. |
| 14 | Field Manual | Blueprints and Survival opened with an empty right-hand side until an entry was clicked. | Low | Presentation | **Fixed (a204cae, then the next commit):** a list tab opens on its first page. The verification run showed Blueprints opening on the Journal's page: the last tab's buttons were still queued for deletion. |
| 15 | Roll at 720p | The recipe sheet covered the roll's toolbar ("Food & Meds…" cut) and the belt's last slot. | Med | Presentation | **Fixed (a204cae):** toolbar and belt shrink to fit (to 70% at most). |
| 16 | Note at 720p | The note's paper ran off the bottom of the screen, under "Put it away". | Med | Presentation | **Fixed (a204cae):** pages and the sheet scale to the window's height. |
| 17 | Container | The refrigerator's flap looked blank. It actually held one soda can, drawn small in the flap's corner with no name, so this was a misread on my part. A container that really is empty did show a blank flap. | Low | Presentation | **a204cae:** an empty container says "Nothing left in here." Open: name the flap's items as the cloth's are (S). |
| 18 | Death screen | The interaction prompt ("[E] Open Refrigerator") showed through the death screen. | Low | Presentation | **Fixed (a204cae):** prompts hide under the death and sleep screens. |
| 19 | Journal nudges | Nudges wrote the key as "(B)"; every prompt writes "[E]". | Low | Presentation | **Fixed (56f4267):** "[B]". |
| 20 | Intro, world card | The wreck card's stamp said "LARCH HOLLOW" on every world, including random ones. | Low | Presentation | **Fixed (d71c82c):** `{place}`, the drop site's region, read when the card shows. |
| 21 | Continue | Loading a save shows "Planning the towns" first, as a new game does. On a Continue the towns exist. | Low | World | A load-specific first line ("Finding your camp…"). |
| 22 | Day 2 | The first sleep woke the player in a blizzard on day 2, under the heavy cold vignette. That is a hard first morning for a new player. | Med | World (weather) | Keep the first two days' weather mild (no storms before day 3), or make it a world setting. |
| 23 | Gathering | Redwood Sorrel looks like a plant you could pick but has no prompt (decoration). Boulders sit beside Loose Stones and look the same at a glance. | Low | World (vegetation data) | A harvest yield for sorrel (a little fibre), or less of it near the drop. Loose Stones a touch lighter than boulders. |
| 24 | Gathering | The card names fireweed first, but the nearest is 125 m from the drop (ferns are 17 m away). | Low | hub (tutorial text) | Name ferns first: "Hold [E] on ferns, fireweed and sedge…". |
| 25 | Drinking | Drinking the issued water says nothing; only the hydration bar moves. | Low | hub (PlayerActions) | A short line, "You drink. (Water +35)", as the boil card's numbers do. |
| 26 | Ezra's card | After recruiting, the card kept his "Get me something for this" plea until reopened. | Low | Creatures (companion screen) | Refresh the card on `companion_recruited`. |
| 27 | Tether | Raising the wrist tether (the HUD's `_raise_wrist`) showed nothing in either rendered run. The wrist model may need the viewmodel, which stand-ins lack, so it may be fine in the packaged build. | Med | Presentation | Recheck on a build with generated assets; if it doesn't show, fall back to a 2D tether panel. |

### What worked
* The prompts name what they do and what is missing: "[E] Campfire — Add materials: Stone 0/6,
  Stick 0/4", "hold [X] to take down the Campfire blueprint (2 Stone, 3 Stick back)", "[E] Use
  Campfire · burns 58m · [G] add fuel", "[E] Fill bottles with stream water".
* The journal's card text matches the labels on screen: Make by hand, Use Campfire, Boil Water,
  Sleep.
* The distress call fires 45 game minutes after the last step, with its bearing and distance
  ("north-west, 390 m"). Ezra's camp is 389 m from the drop, a short walk.
* The death screen says the cause, the consequence and where you wake ("The Program will wake
  you at your bed").
* Save and Continue put the player back where they were. The Continue loading screen shows a
  Survival tip and, after a world's first load, its survey sheet.
* Nothing in the first hour's text gives away the lore trail. The loading tips leave out Ezra
  and the Ashen, and the wreck card only says what a survivor of it would know.

| 28 | Wording | The item is "Plant Fiber" (American) but the journal cards and the manual say "plant fibre". | Low | hub (item data / tutorial text) | Pick one spelling. The rest of the UI writes British ("colour", "metres"). |

## Frames
`2026-10-09_first_hour_before_after.webp`, from the two rendered runs: the roll at 720p, the
distress call, the note at 720p, and the screen after Wake up. The prompt plate and the
Field Manual's tabs were fixed again after the second run and are covered by tests in
`test_hud.gd`. Rerun `make first-hour` for the full set (55 frames plus the text log).
