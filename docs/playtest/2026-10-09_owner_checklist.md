# Round 4: what to check (owner playtest, 2026-10-09)

One section per thing to look at: **what changed** in a sentence, **where** to go, **what to
try**, and what would count as **still broken**. Directions are from the drop site where you
wake on a new main-map game. The full map (**M**) shows only where you have walked.

Play the packaged build (the generated models and textures). The source tree without
`make assets` shows stand-in boxes, and some items below only look right with the real art.

---

## 1. Hands and wrists (report 4, item 1)
**Changed:** the idle hands rest low in the screen's corners with relaxed fingers and no bent
wrists. Every hold sits in a comfortable wrist range. The lighter is held in a real grip. The
hand mesh has knuckles, set-in nails and tendons.
**Where:** right at the start. Empty hands, then the lighter (slot 1), then the stone axe once you
make it.
**Try:** stand still, then walk; hold the lighter up; swing the axe; climb a ladder.
**Still broken if:** the wrists bend hard down or in, the backs of the hands face you like
paddles, or the fingers read as smooth sausages.

## 2. The intro (item 2)
**Changed:** a new game opens with an intro over the loading screen: rumours of the Cordon, your
Order 14 papers, the radio as Lift 3 goes down, and a shot of the wreck. The load waits for it
and never stutters it. The wreck is a picture rendered when the build is made, slowly zoomed in on,
so nothing in the intro draws 3D. The words sit low on that card, so the wreck shows above them. Hold **Esc** (or **B**) to skip; skipping costs you no load
time.
**Where:** New Game. It can be replayed from the menu's **The Intro**.
**Try:** watch it once to the end, then skip one early.
**Still broken if:** a card stutters or freezes mid-fade, skipping leaves you waiting longer
than no intro would, the wreck shot is black, or the words cover the aircraft.

## 3. The main menu (item 3)
**Changed:** the menu and every screen share one style. Behind the menu, the view drifts slowly
across four pictures of Larch Hollow at dusk; between two pictures it dims briefly toward dusk
rather than showing both at once. Build #94's menu froze as soon as you used it: it built and drew
the whole valley in 3D behind the menu. The pictures are now rendered when the build is made, so
the menu draws no 3D at all (ADR-0065). Every build now has to pass a check that uses the real
menu for 20 seconds and fails on any freeze. The menu, New Game, Options and Load fit a
1280x720 window, Back and Start included; on a 1440p or 4K screen the whole interface scales up
(Options → Interface size, "Auto").
**Where:** the main menu. **Options → Menu backdrop** switches moving / still / off.
**Try:** hover and click every entry right away, then leave it on the menu for a minute; open
Options, New Game and Random World over it; try a small window too.
**Still broken if:** the menu freezes or stutters at any point, a panel's Back or Start is off
the screen, text looks tiny on your monitor, or any screen still looks like plain Godot grey.

## 4. Roads, banks and town edges (item 4)
**Changed:** roads stay level across their width and climb within a grade cap, cutting into
steep ground. Bridge ramps and the level pads under buildings by the road keep to the same caps.
Cuts and fills meet the land in short, varied natural banks instead of long planar faces. Town
lots keep their overgrowth and trees.
**Where:** the road from the drop site north-east into Pell's Crossing (~350 m), then any road
that climbs a hill.
**Try:** walk the road's edge on a slope and look along it; stand at a town's edge and look
out.
**Still broken if:** a road tilts sideways, a bank is a long slanted face, or a town sits on
bare plates with no plants.

## 5. Bigger towns, Pell's west end (item 5)
**Changed:** towns grow street networks (cross streets, blocks), not one straight road. Pell's
Crossing has a west end: Mill Street West runs on from Mill Street round the north end of the
Larkspur cliffs, with about 40 houses on six blocks. Yards meet their streets without a lip.
**Where:** Pell's Crossing. Walk west along Mill Street until it becomes Mill Street West.
**Try:** walk its cross streets; walk from a yard onto the street.
**Still broken if:** a yard stands a step or more above its street, or two streets crease where
they meet.

## 6. Interior routes and ladders (item 6)
**Changed:** ladders were invisible because they were built facing into the wall; every
ladder now faces the room. Every building's intended route was walked by a bot, and doors,
props and landings that blocked it were moved.
**Where:** Pell County Library's fire escape (Pell's Crossing); the motel's room 3 window; Cedar
Ridge's stair gate.
**Try:** climb up and down every ladder you find; walk every room's way in and out.
**Still broken if:** a ladder is invisible, or a door, prop or landing blocks a way that looks
open.

## 7. Crafting and inventory (item 7)
**Changed:** the salvage roll's recipe sheet shows ready recipes first, in dark ink. Ones you
can't make show what's missing in readable dim ink, never white; a long "need" line wraps to a
second line instead of being cut. Make by hand also lists, at the end, what a campfire or a
workbench makes ("at a Workbench"), with an **At a station** filter. Items can be dragged, with
tooltips, sorting and filters; the Sort and Show buttons sit above the cloth, clear of the
recipes, and a dragged item's label stays on screen over the belt. Crafted tools go on your belt.
While the roll is open the messages at the top left wait, and show once you close it.
**Where:** **Tab** (the salvage roll), the Make by hand flap; a lit campfire's Use.
**Try:** make cordage and a stone axe; drag an item to the belt; pick Food & Meds, then hover an
item; look at At a station.
**Still broken if:** any text is white on paper, you can't tell what a recipe still needs or
where it is made, or a message you expected never shows.

---

## 8. The first days: tutorial, Ezra's call
**Changed:** an optional journal of eight Program cards (Field Manual **B → Journal**). The
first card is announced as you wake; each step done names the next. When all eight are done,
Ezra's distress call comes in on the tether with a bearing. Every card was walked to the call:
each one names the prompts you will see ("Pick up log", "[G] add fuel", "Use Campfire"), and the
whole card fits the page at 1280x720. Things you hold the key for (harvesting, filling a bottle,
searching) now say so: **Hold [E] Harvest Sword Fern**.
**Where:** from the start. Ezra's camp is about 390 m north-west of the drop.
**Try:** follow the cards; bring him a cloth bandage.
**Still broken if:** a card names a label that isn't on screen, a card's text runs off its page,
a "Hold" prompt finishes on a tap (or a tap prompt needs holding), or the call never comes.

## 9. The Lift 3 wreck
**Changed:** the aircraft you came in on is a place: a swath of snapped trees ending in the
burned forward fuselage, with notes from its crew.
**Where:** about 700 m east of the drop site.
**Try:** walk the swath to the nose; read what you find there.
**Known gap:** TD-377. The hull is the Cordon transport's clean shell (no burned livery), the
swath has no felled trunks lying down, and there is no flare item.

## 10. The map and the note reader
**Changed:** **M** opens a survey sheet of the valley under fog. Only where you've walked shows,
with the drop, your bed and any distress call marked. A note opens in its own hand (scrawl,
typed, printed) when you pick it up. The Field Manual's **Notes found** lists them by where
you found them.
**Try:** walk a loop and open the map; pick up a note and turn its pages.
**Still broken if:** the map shows places you haven't been, or a note runs off its page.

## 11. Gamepad and rebinding
**Changed:** the game plays on a pad alone: the right stick looks, RT attacks, Y opens the roll,
d-pad up the field manual (LB / RB turn its tabs), Back the map, Start pauses, and **A** presses
whatever has the focus in every menu (it didn't: a pad could walk the menu but press nothing).
Hold B to skip the intro. With a gun in hand, hold X (nothing in reach) to reload; LB / RB turn a
blueprint while you place it. **Options → Controls** rebinds keys and pad buttons and warns about
conflicts. The full layout is in HOW_TO_PLAY §3.
**Try:** from the main menu, start a new game and play ten minutes on the pad alone: the journal,
crafting in the roll (up / down choose a recipe), the map, pause; place a campfire and turn it with
LB / RB; reload a rifle by holding X while looking at the sky. Rebind one key to another's and
read the warning.
**Still broken if:** any screen can't be opened, used or left with the pad.

## 12. Graphics options (Ultra on the RX 9070 XT)
**Changed:** the first run picks a preset from your GPU's name; a 9070 XT gets Ultra (shadows to
220 m, tree detail ×1.5, view 2000 m). Options shows the detected GPU and a Recommended
button, plus a frame cap.
**Try:** check Options reads your card and Ultra; walk Pell's Crossing at dusk.
**Still broken if:** the recommended preset isn't Ultra, or Ultra stutters where High doesn't.

## 13. Felling
**Changed:** every swing lands before the next begins, and steady chopping regains stamina. A
full-grown fir takes seven to eleven swings of the stone axe. When you're too winded, it says so.
**Try:** fell three trees in a row.
**Still broken if:** swings miss a trunk you're facing, or stamina runs out before a tree
falls.

## 14. Survival warnings
**Changed:** cold, thirst and hunger warn in words before they hurt ("You're cold. Find shelter
or a fire."). Cold damage grows with how cold you are. The world waits while you're down.
**Try:** spend a night out with no fire; skip a day's water.
**Still broken if:** you die of something nothing warned you about.

## 15. The Hum
**Changed:** the warnings come in order: the tether's forecast the night before, "The Hum
tonight." at 16:00, "Within the hour, they come." at 21:00, then the countdown. The night
comes in waves (about 17 on the default rules). Its report, the dawn autosave, the level-up and
the next supply drop come one at a time. With **Options → Sound captions** on, the Hum's rise is
captioned.
**Where:** day 7 on the default rules, at a base with a fire.
**Still broken if:** a wave never comes, or the morning's lines pile up and the report scrolls
away.

## 16. Waystation 9 in the Cordon wall (D7)
**Changed:** the valley's south end is built (region D7): Route 9 and the river run down to the
Cordon wall, the river through its own gate, with a burnt firebreak before it. Waystation 9 is
now the Program's post in the wall itself, and the trader (counter and contract board) stands
there, not in the old ring of barriers.
**Where:** about 1.2 km south of the drop site, down Route 9.
**Try:** walk Route 9 south to the wall; trade at the counter; take a contract from the board.
**Still broken if:** the road or river ends in a cliff or a gap at the wall, you can walk through
the wall, or the trader can't be reached.

---

## Also new
* **Load screen:** the menu's **Load…** shows every run as a card: the frame you saved on, the
  day, where you were, play time and world. **Delete** asks twice.
* **Loading screen:** turns through the Field Manual's Survival pages. On the main map it shows
  the survey sheet under your save's fog.
* **What's New:** a panel on the menu with this list in short; it opens by itself once per build.
* **Sound captions** (Options): the Hum rising, the crackle of a call on the tether and the intro's
  sounds are put into words. Other sounds (wolves howling) aren't captioned yet.

## Known gaps
* **TD-377:** the Lift 3 wreck's art (above).
* **Generated assets** are needed for the full look: hands, the wreck, the tether's screen and
  the trees only look right in the packaged build.
* **TD-378:** the menu backdrop is a slow pan over still pictures, not a filmed camera move: a
  video would take about 16 hours of software rendering a minute to make.
* **TD-376:** a save from before the tutorial starts it from the first card, even with an axe
  and a bed already made.
