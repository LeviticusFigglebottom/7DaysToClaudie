@tool
extends Node
## Global event bus (autoload `Events`).
##
## Rule of thumb: systems talk to *their own* models directly; cross-module notifications go
## through here so modules stay decoupled (UI never reaches into AI, AI never reaches into UI).
## Signals carry plain data (ids, positions, dictionaries) — never node references that may be
## freed — so the same events can later be replicated over the network (see ADR-0003).

# --- Session lifecycle -------------------------------------------------------------------
signal session_started(is_new_game: bool)
signal session_ending()
signal game_saving(slot: String)
signal game_saved(slot: String, ok: bool)
signal game_loaded(slot: String)

# --- Time / world cycle ------------------------------------------------------------------
signal hour_changed(day: int, hour: int)
signal day_started(day: int)
signal dusk_started(day: int)
signal night_started(day: int)
signal horde_night_warning(day: int, hours_left: float)
signal horde_night_started(day: int)
signal horde_night_ended(day: int, report: Dictionary)
signal weather_changed(weather_id: StringName)

# --- Player ------------------------------------------------------------------------------
signal player_spawned(player_id: StringName)
signal player_damaged(player_id: StringName, amount: float, source: Dictionary)
signal player_died(player_id: StringName, cause: String)
signal player_slept(player_id: StringName, hours: float)
signal player_entered_region(player_id: StringName, region_id: StringName)
signal player_status_message(text: String, kind: StringName)
## A status line that can wait its turn: StatusFeed lets these out as player_status_message, paced
## and highest priority first (StatusFeed.PRIORITY_*), so lines arriving together don't bury
## each other (first-week audit W15).
signal status_message_queued(text: String, kind: StringName, priority: int)
## A sound worth a caption (accessibility, mid-game audit G4): the source emits it where the sound
## plays, and the UI shows "[text, <bearing>]" when sound captions are on. `text` is lowercase,
## without brackets ("wolves howling"); `at` is the sound's world position (the bearing is the UI's).
signal sound_caption(text: String, at: Vector3)
signal player_leveled(player_id: StringName, level: int)
## Points went into an attribute or perk (derived stats changed; Record tab and tether refresh).
signal player_progressed(player_id: StringName)

# --- Inventory / crafting / loot ---------------------------------------------------------
signal inventory_changed(owner_id: StringName)
signal item_picked_up(owner_id: StringName, item_id: StringName, count: int)
signal item_crafted(owner_id: StringName, recipe_id: StringName, item_id: StringName, count: int)
signal container_opened(container_id: StringName)
signal container_looted(player_id: StringName, container_id: StringName, tier: int)

# --- Building / world modification -------------------------------------------------------
signal structure_placed(piece_id: StringName, def_id: StringName, position: Vector3)
signal structure_damaged(piece_id: StringName, hp: float, max_hp: float)
signal structure_destroyed(piece_id: StringName, def_id: StringName, position: Vector3)
signal blueprint_completed(blueprint_id: StringName, def_id: StringName)
## A garden plot brought in (ADR-0049): the crop def and what it gave ({item: count}).
signal crop_harvested(player_id: StringName, crop_id: StringName, items: Dictionary)
## A Hollow killed by a player-built trap or sentry (ADR-0052): the piece and its structure def.
signal trap_killed(piece_id: StringName, structure_id: StringName, enemy_id: StringName)
signal terrain_modified(aabb: AABB)
## A tree came down; `felled_by` is whose blow did it (a player, or the companion: ADR-0058, whose
## trees count at a share for the player).
signal tree_felled(tree_id: StringName, position: Vector3, felled_by: StringName)
## A Remand Program supply canister was released over `position` (lands a little later).
signal supply_drop_incoming(drop_id: StringName, position: Vector3)
signal supply_drop_landed(drop_id: StringName, position: Vector3)

# --- Combat / AI -------------------------------------------------------------------------
signal enemy_spawned(entity_id: StringName, enemy_id: StringName, position: Vector3)
signal enemy_killed(entity_id: StringName, enemy_id: StringName, position: Vector3, killer: Dictionary)
signal enemy_alerted(entity_id: StringName, position: Vector3)
signal limb_severed(entity_id: StringName, limb: StringName, position: Vector3)
## A Hum survivor rooted into the soil at dawn (DESIGN §6) and left the world at `position`; the
## Bloom leaves a fungal mound there (BloomMounds, ADR-0025).
signal hollowed_rooted(entity_id: StringName, enemy_id: StringName, position: Vector3)

# --- Wildlife (ADR-0027) --------------------------------------------------------------------
## A flock went up (cause: person / hollowed / noise / hum); the flush is also a sound in the
## stimulus field the Hollowed hear.
signal birds_flushed(flock_id: StringName, wildlife_id: StringName, position: Vector3, cause: String)
signal wildlife_killed(entity_id: StringName, wildlife_id: StringName, position: Vector3, killer: String)
signal wildlife_butchered(player_id: StringName, wildlife_id: StringName, items: Dictionary)

# --- POIs / quests -----------------------------------------------------------------------
signal poi_entered(poi_instance_id: StringName)
## First time inside a POI in this run (saved with the POI state; not repeated after a load).
signal poi_discovered(poi_id: StringName)
signal poi_exited(poi_instance_id: StringName)
signal poi_cleared(poi_instance_id: StringName)
## A POI trap taken apart (was armed) or salvaged (was sprung) through poi.disarm_trap.
signal trap_disarmed(player_id: StringName, poi_instance_id: StringName, trap_type: StringName, was_armed: bool)

# --- Trade (ADR-0039) --------------------------------------------------------------------
signal contract_accepted(player_id: StringName, contract_id: String, def_id: StringName)
signal contract_completed(player_id: StringName, contract_id: String, def_id: StringName, tier: int)
signal trade_made(player_id: StringName, trader_id: StringName, item_id: StringName, count: int, scrip: int)
# The Ashen (ADR-0048)
## A raid band set out for the base (or the player); `size` fighters.
signal ashen_raid_started(raid_id: String, target: Vector3, size: int)
## A raid is over: `repelled` when the band broke or fell, false when it gave up or the player left.
signal ashen_raid_ended(raid_id: String, repelled: bool)
## A Bloom nest burned to death (ADR-0055): its placement id, its NestDef and where it stood.
signal nest_burned(nest_id: String, def_id: StringName, position: Vector3)
## A scout watched the player long enough and got away (`reported`), or was seen off / killed.
signal ashen_scout_done(entity_id: StringName, reported: bool)
## The faction's escalation level changed (0 unaware, 1 watchers, 2 raids, 3 war parties).
signal ashen_level_changed(level: int)
## A companion joined the player (ADR-0058): its CompanionDef id.
signal companion_recruited(companion_id: StringName)
## The first-days tutorial changed (ADR-0062): a step advanced or finished, it was turned on or
## off, or the distress call came. Read the state from GameWorld.tutorial.
signal tutorial_changed()
## The tutorial's last step led to a distress call on the tether: the companion's CompanionDef id
## and his camp's position (TutorialTracker.distress() has the radio text).
signal tutorial_distress(companion_id: StringName, position: Vector3)
signal note_found(note_id: StringName)
signal schematic_learned(schematic_id: StringName)

# --- UI ----------------------------------------------------------------------------------
signal ui_modal_opened(ui_id: StringName)
signal ui_modal_closed(ui_id: StringName)
