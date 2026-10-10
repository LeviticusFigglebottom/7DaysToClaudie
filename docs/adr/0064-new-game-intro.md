# ADR-0064: The new-game intro plays over the load, and the load waits for its quiet moments

**Status**: Accepted · 2026-10 (round 4, Presentation)

## Context
Player report 4, item 2 asks for an intro cutscene that shows the crash and its context before the
player gets control. The report sets two conditions:
* Ideally the intro plays while the world loads.
* It may do so only if it doesn't stutter or freeze. Otherwise it plays after the load, before
  control.

The owner's lore call (WORKBOARD, 2026-10-08): the intro shows the crash of #4471's Program drop
aircraft short of the drop site. It never tells the cause of the outbreak; the player finds that
out from lore in the world.

The load has two halves (ADR-0036):
* **The worker half.** The world loader runs on a thread and the main thread is idle, so anything
  animated runs smoothly.
* **The main-thread half.** GameWorld's boot steps, then the spawn. These are heavy. TD-102 records
  frames up to ~0.3–0.5 s headless, and ~2 s for steps that load many new models in a rendered
  run. A fade or a typewriter caught in one of those frames jumps or stops.

## Decision

### Cards from data
`IntroPlayer` (`game/src/ui/intro/`) plays `game/data/intro/intro.json`. The file is an ordered
list of cards:
* **caption**: a rust stamp line and lines typed on black.
* **document**: a Program form typed on tilted paper, with a rubber stamp struck once the text is
  in.
* **radio**: a transcript, line by line, `SPEAKER|text`.
* **impact**: the crash. It cuts in with no fade, the frame shakes, a fire-white flash decays and
  its sound plays (`sfx/lift3_crash`, synthesized for it: the rotor striking the trees, the hull
  tearing, the turbine winding down; TD-379).
* **title**: the game's name and the tagline.

Each card has `hold` seconds and an optional `sound` (or `sounds`). `music` names the intro's
score. The placeholders `{day}`, `{time}` and `{hum_in}` are filled from the session; `{hum_in}`
is the days until the first Hum in words, following the world rules.

`IntroPlayer.validate` rejects:
* unknown keys and kinds;
* cards without lines;
* holds outside 1–15 s;
* radio lines without a speaker.

A unit test runs it on the shipped file. The text is data: editing the story needs no code.

Everything is drawn with UiStyle (ADR-0063): the kit's type on black with film grain and a
vignette, and the paper theme for the forms. All assets are generated or committed. The score is
`music/dread_drone`, and the sounds come from the existing catalogue.

### It plays during the load, and the load waits for the quiet moments
`is_calm()` is true only while a card is fully shown and holding, never during a fade or while
text is typed. `GameUI.load_may_step()` exposes it. GameWorld's `_load_step` skips its
main-thread work (the boot steps, the world-loaded frame, the spawn polling) on frames where it is
false.

This is a three-line hook in World's file, agreed by message. The effect:
* a heavy step only ever lands on a still card, where a long frame is invisible;
* the worker half is never gated;
* without an intro the gate is always open, so nothing changes for loads, Continue, `--skip-intro`
  runs, or the smoke and tour runners (which all pass `skip_intro`).

The time the intro spends moving is time the main-thread half doesn't run. Holds are roughly half
the intro's length, so the main-thread half can take up to twice as long in wall time. That time
is behind the intro.

Hitches never skip a card: time within a phase advances by at most 0.1 s a frame.

### Whichever ends first
* **The intro ends first:** it fades out and the normal loading screen is underneath, showing the
  progress. The intro also shows the load's progress in a dim line at its foot.
* **The world is ready first:** GameWorld hides the loading screen. GameUI then:
  * pauses the tree (the pause menu's pause, so no clock, AI or survival ticks unseen);
  * pushes an `intro` modal, so the player has no control and the mouse is free;
  * releases both when the intro ends.

### Once per new game, skippable, replayable
* GameUI starts the intro on a new game only. Loads, `skip_intro` and headless runs never get it.
* Holding Esc, Space or Enter for 0.9 s skips it, with a progress bar beside "Hold Esc to skip".
  A Skip button does the same.
* The main menu's **The Intro** replays it over the menu.

## Consequences
* The intro's length adds nothing to a load that is already longer than the intro. A short load
  waits for the intro (or the player skips it).
* New story beats are a data edit. A new card kind is a builder in `IntroPlayer` plus its name in
  `KINDS`.
* There is no in-world cinematic (a camera over the crash site). The world has no wreck at the
  drop site, and the text says the player walked the last mile from it. A wreck set piece and a
  camera shot of it would be a follow-up (TD-379).
