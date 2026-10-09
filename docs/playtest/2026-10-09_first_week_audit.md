# First-week UX audit (2026-10-09)

This carries the first-hour audit (2026-10-09_first_hour_audit.md) on from day 2 to the morning
after the first Hum (day 7–8 on the default rules). It covers:
* base building (the build menu, blueprint ghosts, freeform logs, repairs);
* the Waystation 9 trader;
* Ezra after recruiting;
* hunting;
* a grotto;
* the supply drop;
* levelling;
* the Hum's warnings, its night and the morning after.

## How it was run

`make first-week` runs the first hour, then the week steps, headless (text only, about 4 min).
`make first-hour FIRST_HOUR_ARGS="--through hum --week-only"` renders the week alone at
1280x720, about 20 min on lavapipe. `--week-only` finishes the journal and recruits Ezra by
command, then goes straight to the week.

Days pass by the clock, not by play. The day before the Hum and the Hum day itself run in
30-minute steps, so every warning fires at its hour. Other gaps are skipped with `set_time`.

Same caveats as the first-hour audit: the art is stand-ins (no generated assets here), the
driver teleports and aims, and a human pass still has to judge pacing.

Severity: **High** blocks or misleads a new player; **Med** costs them time or reads badly;
**Low** is polish.

## Findings

| # | Step | Issue | Severity | Owner | Proposed fix / status |
|---|---|---|---|---|---|
| W1 | Laying out a blueprint | With a ghost on the cursor, nothing on screen named the keys to place, turn or cancel it. The manual's "Lay it out" drops you into a mode with no instructions. | High | Presentation | **Fixed (0ccc358):** the hint line reads "[Left mouse] place  ·  [R] turn  ·  [X] cancel". |
| W2 | Carrying logs | The same for carried logs: set, turn, stand/pitch (V) and drop (G) were only in the journal's card. | Med | Presentation | **Fixed (0ccc358):** "[Left mouse] set the log  ·  [R] turn  ·  [V] stand / pitch  ·  [G] drop", while no prompt is up. |
| W3 | Butchering | "[E] Butcher white-tailed deer" shows 1.6 m from the carcass, and pressing it says "Too far away". It happened in both the headless and the rendered runs. | High | Creatures (wildlife) | Use one reach for the prompt and the command (the interaction ray's reach, or the carcass's own radius). |
| W4 | Supply drop | When the canister lands, its flare and smoke fill the whole screen within 2 m, and the crate under them got no prompt in either run. The player can't see or open what they walked to. | High | World (supply drops) | Keep the flare and smoke above head height, or fade them within a few metres. Check the crate's interaction shape after landing. |
| W5 | Supply drop | The drone's "Supplies are coming down" was the only word. Nothing said where it landed. | Med | Presentation | **Fixed (0ccc358):** "The canister is down, north-west, 140 m. Its smoke marks the spot." |
| W6 | The Hum, captions | With sound captions on, the Hum's rise is music and had no caption. | Med | Presentation | **Fixed (0ccc358):** "[a deep hum rises through the ground]". Hollowed screams and the wave drums are still uncaptioned; they need a hook on HumDirector's waves. |
| W7 | The night before the Hum | Standing outside with no fire from 18:00 on day 6, the player froze to death before 16:00 on day 7 ("The cold took you"). The warnings and the Hum then played on under the death screen. A first-week player who misjudges one night loses the run's best moment. | Med | hub (survival tuning) + World (weather) | A cold warning before it bites ("You're freezing. Find a fire.") at a set body temperature. The tether's vitals show it, but nothing says it. Check how cold day 6 nights are on the default rules. |
| W8 | Messages | "Too far away" and the first journal card wrapped onto two lines: the label's minimum width was estimated, not measured. | Low | Presentation | **Fixed (next commit):** only lines over 80 characters wrap, at 820 px. |
| W9 | The grotto | The grotto's mouth rendered floating blocks and an overhang of loose geometry over water (frame `w_cave_mouth`). Inside looked right. | Med | World (caves) | Check the volume terrain at larch_hollow's grotto mouth. It may only affect stand-ins. |
| W10 | Ezra's orders | Each order answers in his voice ("Right behind you.", "On it.", "I'll be here."). "Fetch" with nothing looked at fails as "nothing to fetch: look at it first", which the card shows but the HUD doesn't. Store is a separate command, not an order. | Low | Creatures (companion) | Show a failed order as one of his lines ("Show me what — look at it first."). |
| W11 | Bow | One press of attack with the bow did nothing visible: no arrow, no draw. The driver doesn't hold the draw, so this is unverified. | — | Presentation (driver) | A held-draw step in the driver next round. |
| W12 | The trader | The screen fits at 720p and dims locked rows with what they need ("needs Known standing"). Buying, selling and taking a contract all work. A contract taken on day 2 and left was failed by day 6 with "-10 standing", which is fair but steep for a first contract. | Low | hub (trade tuning) | Optional: the first contract a run takes doesn't cost standing when it lapses. |
| W13 | The Hum's warnings | They fired in order: the forecast on the tether the night before; "The Hum tonight." at 16:00; "The ground has started to hum. Within the hour, they come." at 21:00; "THE HUM HAS BEGUN." at 22:00; the countdown in the HUD's corner. | — | — | Works. |
| W14 | The first Hum | My first report said four Hollowed came. **That was the driver:** it jumped the clock from about 22:20 to 03:54 and skipped waves 2–4. Run on the clock 15 minutes at a time, 16 came across the waves (the default plan is 17) and the player put down 7–9 of them. | — | Presentation (driver) | **Fixed in the driver:** the night runs on the clock. The Hum's size is fine. |
| W15 | The morning after | Dawn brought the report, the autosave line, a new supply drop and the level-up within a second, and the report scrolled away first. | Low | hub + Presentation | **Fixed:** the hub's StatusFeed paces them. GameUI now queues its three (the dawn line at 5, the level-up at 3, the drone at 0) behind the report (10). Rerun: report, then "Dawn… Progress saved.", then the level, then the drone. |
| W16 | Record | It reads well at 720p: attributes, perks with ranks, points to spend, the gamestage with its formula, and the run's stats. Spending a point updates at once. | — | — | Works. |
| W17 | Building | The build menu lists by category with locked entries dimmed ("schematic needed"). A blueprint's materials show what you carry. The site prompt counts what it still needs, and the hammer's repair hint names the cost. | — | — | Works. |

| W18 | Thirst | The run-up to the Hum (day 6 18:00 to day 7, on the clock) killed a player who didn't drink: "You died of thirst." No line warned first, only the vitals bar. It also happened to my driver twice. | High | hub (survival warnings) | Thirst and hunger lines like the new cold ones ("You're thirsty." / "You're parched. Drink, now."). |
| W19 | Cold | With the hub's new cold lines, waking in the day-2 blizzard went straight to "You're freezing. Find a fire, now.", with no "You're cold" first. | Low | hub | Say the first step once even when the drop past it is quick. |

## Frames
`2026-10-09_first_week_frames.webp`: the build controls, the trader, butchering, the grotto
mouth, the canister's flare up close, and the Hum's night. Rerun the commands above for the
full set (about 40 frames plus the text log).
