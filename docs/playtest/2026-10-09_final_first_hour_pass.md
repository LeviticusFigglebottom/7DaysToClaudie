# First hour, the round's last pass (2026-10-09, evening)

A new game read as a new player would: wake, the eight journal cards, Ezra's call, the first
night in a lean-to, day 2's morning, Ezra, a search, a note, the map, a death, a save and a
continue. Run headless (`first_hour.gd`, the screen's words at every step) on the integration
branch after e7fea1c, with Build 102's generated assets. The intro was checked on the pack
earlier today (2026-10-09_intro_world_card.webp).

| # | Rank | What a new player meets | Owner | Fix / status |
|---|---|---|---|---|
| 1 | Med | Waking in the new lean-to, the first line after "Rested. Progress saved." is "You're cold. Find shelter or a fire.": the player is in their shelter. The same line greets them again right after Continue. | hub (survival warnings) | Let the line know shelter: "You're cold. Light a fire." while sheltered; or no cold line in the first minutes after waking or loading. |
| 2 | Med | After the eighth card, "Journal: Sleep in your bed ✓ +40 XP" and nothing more: nothing says the journal is over, or that the tether is what comes next, and the call comes 45 game minutes later. | Presentation | **Fixed:** the last card's line ends "The journal is done. Keep an ear on your tether." |
| 3 | Low | "Level 2. 2 points to spend…" was said over the death screen (SIGNAL LOST), where it can't be acted on and is easily missed. | Presentation | **Fixed:** the message feed waits under the death and sleep screens, as it does under the roll, and plays what came once they lift. "The campfire has burned out." (said in your sleep) now shows when you wake. |
| 4 | Low | The new campfire's kindling burns an hour (start_fuel 60). Card 8 says "Be at your fire" at 21:00; a fire built at noon is long out by then, and nothing said how long it lasts. | Presentation (journal text) | **Fixed:** card 4 adds "the kindling burns about an hour" beside "[G], add fuel, feeds it". |
| 5 | Low | The owner checklist promised "about seven swings" for a fir; the run took 10 (survival.json's own note says 7–11). | Presentation (docs) | **Fixed:** "seven to eleven swings". |
| 6 | — | Every card's prompts on screen as the cards name them; "Hold [E]" on harvesting, filling and searching; the call with its bearing; Ezra's card; the death card; save and continue. | — | Works. |

Not findings: forest sorrel and granite boulders offer nothing (decorative ground cover and
boulders, not harvestables). After a night's sleep the morning's lines arrive together (up to
five); at a real player's pace they come further apart.
