# ADR-0015: Progression that pays off — derived stats, XP sources, supply drops

**Status**: Accepted · 2026-10

## Context
Attributes and perks existed as data, but half of their effects (carry capacity, max health,
stamina recovery, loot quality, structure toughness, the third log, stagger, sleeper sense) were
never read. There was no way to spend points in game, several XP sources were never paid
(looting, building, the Hum), and nothing like 7 Days to Die's airdrops rewarded a long run.
Consistent play has to feel like it adds up.

## Decision
* **Derived character stats are recomputed, never trusted from a save.** `PlayerState.refresh_derived()`
  sets pack capacity (`carry_bulk`), shoulder logs (`log_carry`, as `Inventory.carry_bonus`), max
  health and stamina recovery from `Progression.modifier()`. It runs on creation, after loading
  and whenever points are spent (`Progression.spent`). So rebalancing perk data applies to old
  saves. Raising Grit fills the new health. Loading keeps the saved health.
* **Bonuses that belong to a built thing are stored with it.** A structure piece keeps the builder's
  toughness multiplier (`hp_mult`, Wits + Builder) in its save entry. A later change to the
  builder's perks does not resize walls that already stand.
* **Spending is a command.** `progression.raise_attribute` and `progression.buy_perk` go through
  the command bus (ADR-0003). They return the reason a choice is locked
  (`attribute_block_reason`, `perk_block_reason`), and the Field Manual's **Record** tab shows that
  reason.
* **XP sources are one table.** `data/config/progression.json` `xp` maps source to amount.
  `Progression.award(source, times)` is the only way systems pay XP besides kills, which pay
  `EnemyDef.xp` × the infected tier's `xp`. Looting scales by container tier, first entry and
  clearing scale by POI tier, and the Hum pays more for each Hum survived. The world setting
  `xp_multiplier` applies inside `add_xp`.
* **Supply drops** (`SupplyDrops`) are scheduled by the world settings `supply_drops` (after each
  Hum / weekly / every 3 days / off) and `supply_drop_markers`. The spot is deterministic: world
  seed + drop id, 110–300 m from the player, dry, flat, inside the detailed map and clear of
  POIs. The loot tier is 2–5 from the gamestage. A drop persists in `WorldState.drops` and is
  cleared once it has been emptied and left behind. The landing is a 45 m noise stimulus, so the
  reward is contested.
* **Weapon stagger matters.** The damage needed to stagger is the enemy's `stagger_threshold` ×
  (1.3 − `DamageInfo.stagger`). The default 0.3 keeps the old behaviour. Heavy Hands adds to
  blunt stagger.
* **Quality tiers have names and colours in data** (`loot.json` `quality_tiers`, Scrap …
  Pristine). Quality scales melee and firearm damage alike (`ItemStack.quality_damage_mult`).

## Consequences
+ Every perk effect in the data is now consumed by a system (checked by unit tests). A new effect
  is one modifier key plus one read.
+ Saves stay small and robust to rebalancing. Only `hp_mult`, `WorldState.drops` and
  `flags.last_drop_day` were added (backward compatible: missing keys default).
− Derived values must never be written by other code paths (for example, debug tools must call
  `refresh_derived()` after editing progression).
− Drops can land among trees (only slope, water and POIs are checked). There is no visible drone
  yet, only the chute (TECH_DEBT TD-029).
