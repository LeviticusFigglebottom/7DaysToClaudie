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
signal terrain_modified(aabb: AABB)
signal tree_felled(tree_id: StringName, position: Vector3)

# --- Combat / AI -------------------------------------------------------------------------
signal enemy_spawned(entity_id: StringName, enemy_id: StringName, position: Vector3)
signal enemy_killed(entity_id: StringName, enemy_id: StringName, position: Vector3, killer: Dictionary)
signal enemy_alerted(entity_id: StringName, position: Vector3)
signal limb_severed(entity_id: StringName, limb: StringName, position: Vector3)

# --- POIs / quests -----------------------------------------------------------------------
signal poi_entered(poi_instance_id: StringName)
signal poi_exited(poi_instance_id: StringName)
signal poi_cleared(poi_instance_id: StringName)
signal note_found(note_id: StringName)
signal schematic_learned(schematic_id: StringName)

# --- UI ----------------------------------------------------------------------------------
signal ui_modal_opened(ui_id: StringName)
signal ui_modal_closed(ui_id: StringName)
