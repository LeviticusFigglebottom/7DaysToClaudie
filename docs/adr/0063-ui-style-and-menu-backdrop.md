# ADR-0063: One UI style, a readable crafting sheet, and a flight over the valley behind the menu

**Status**: Accepted · 2026-10 (round 4, Presentation)

## Context
Player report 4:
* Item 7: on the salvage roll, recipes you can't make were "white and almost impossible to read".
* Item 3: the main menu "looks primitive and unlike the rest of the game's menus".

Causes:
* **The white recipes.** The recipe list was a column of flat `Button`s drawn over the paper flap.
  An uncraftable recipe was `disabled`, and Godot draws a disabled button with
  `font_disabled_color`. The default theme sets that to near-white. The code overrode only
  `font_color` (dim ink), so the override never applied to the state that needed it.
* **No shared style.** Each screen built its own StyleBoxes and colours:
  * the field manual and the trader: paper and ink;
  * New Game: a dark flat panel;
  * options: Godot's default theme;
  * the main menu: Plex Mono on a flat colour, with default grey buttons.
* **No scaling.** The window's stretch mode is `disabled`, so every font is a fixed pixel size and
  a 1440p or 4K screen shows the 1080p layout small.

## Decision

### UiStyle: one palette, one set of fonts, two surfaces
`game/src/ui/theme/ui_style.gd` builds two `Theme`s from one palette. Every screen takes its theme
from here instead of styling itself:
* **paper** (the field manual, the crafting sheet, the trader, item cards): ink on aged paper.
* **kit** (the main menu, New Game, options, pause, loading): paper-coloured type on dark oiled
  canvas.
* **Rust** is the single accent colour on both.
* **Fonts** are the committed OFL faces:
  * Special Elite: headings, menu entries and the primary button;
  * IBM Plex Mono: body text;
  * Caveat: margin notes and the menu's tagline.
* **Type variations**: `HeadingLabel`, `SubheadingLabel`, `DimLabel`, `HandLabel`, `ListButton`,
  `MenuEntry` and `PrimaryButton`.
* **Explicit disabled colours** on both themes:
  * paper uses dim ink, which keeps at least 4.5:1 contrast on the paper colour (a unit test
    checks it);
  * "what you lack" is a red-brown ink, also at least 4.5:1;
  * "ready" is a dark green.
  * Rows also carry a ✓ / × mark, so the state reads without colour.
* **Drawn check boxes**: Godot's unchecked box is invisible on the dark canvas.

**UI scale.** The canvas uses `Window.content_scale_factor`; 3D still renders at the window's
resolution.
* Auto mode keeps 1.0 up to 1080 lines, then grows in quarter steps: 1.25 at 1440p, 2.0 at 4K.
* The "Interface size" option can fix it at 75% to 200% (`Settings.ui_scale`, where 0 means auto).

### The crafting sheet and the item card
**CraftSheet** replaces the overlay buttons. It is a paper panel laid over the roll's flap:
* a filter row: All, Ready, then each recipe category present;
* recipes you can make come first, then the rest, ordered by how little they lack;
* each row shows its state on the right ("ready ×3", or "need 2 Stick, a knife");
* a detail card shows every ingredient as have / need, plus the tools, the time and the result's
  numbers;
* Make goes through `inventory.craft` one command at a time (Shift makes as many as you can).
  Double-click and Enter also make.

The model behind it (`rows`, `row`, `status_text`, `passes`, `filters_for`, `detail_bbcode`) is
static and unit-tested.

**ItemCard** is the tooltip TD-014 asked for:
* name, kind and quality;
* damage, reach, food, water, fuel and so on;
* condition, bulk and worth;
* the description and the mouse actions.

**Sort and filter on the cloth** (packed / kind / name; all / gear / food & meds / materials /
papers) are a view only. The inventory's order is state and is never changed by the UI.

### The menu backdrop: the real valley, built off the main thread, frozen if it costs too much
`MenuBackdrop` (`game/src/ui/menu/`) flies slowly up the Tamsin through Larch Hollow (D6) at dusk.
It is built from the main map itself, not from a picture of it.

**One worker task** does the heavy work:
* composes the region at 4 m (`TerrainComposer.get_or_compose`): ~3 s once, then read from the
  region cache;
* builds the terrain mesh job (`TerrainMesher`) and the terrain layer images
  (`TerrainTextures.prepare`);
* makes the river ribbons and lake polygons;
* scatters trees from the region's biome and vegetation masks (deterministic, by 128 m tile);
* computes the camera path along the river, smoothed and kept above the banks.

**The main thread** then adds one piece a frame:
* the environment (the game's sky shader at dusk, fog, AgX);
* the terrain (the game's terrain shader and splat);
* the water (the game's water shader);
* the trees, twelve tile MultiMeshes a frame, with LOD1 near and LOD2 to 900 m by visibility
  range.

It then fades in over 3 s. Content is read on the main thread before the task starts; the worker
gets plain data.

**Cost guard.** The report allows the moving camera only if it doesn't stutter or cost
performance:
* after the fade-in, the backdrop measures its frame times for 4 s;
* below 40 fps it stops the camera and renders one last frame (`UPDATE_ONCE`), leaving a still
  backdrop that costs nothing per frame;
* the log names the measurement (`[menu] backdrop: N ms a frame`);
* the "Menu backdrop" option picks moving, still or off;
* headless runs skip the backdrop.

Under lavapipe the menu runs at about 10 fps and freezes, as intended. A GPU run is the real test
(TD-378).

Without generated assets the backdrop draws the stand-in trees and the procedural terrain layers.
It still reads as a valley at dusk.

### make ui-shots
`make ui-shots` renders the roll, a station sheet, the main menu with its backdrop, options,
New Game and the field manual without loading a world (`ui_shots.gd`, about 30 s plus about 40 s
for the backdrop under lavapipe).

## Consequences
* New screens take `UiStyle.kit_theme()` or `paper_theme()` and its variations. Colours and fonts
  live in one file.
* Disabled controls are readable everywhere the themes apply. Screens that still style themselves
  (the HUD, the tether, the loading screen) move over in the one-style pass (TD-014's rest).
* The menu composes D6 at 4 m once per machine, a ~3 s worker task the first time. The cache file
  is `user://cache/worlds/hollowmere/d6_larch_hollow_400.bin`.
* TD-378: the backdrop's frame cost is unmeasured on a GPU, and its stand-in look without assets
  is plain. Buildings aren't placed (the flight avoids the town).
