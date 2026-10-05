class_name DamageInfo
extends RefCounted
## Everything a hit carries. Receivers implement `take_damage(info: DamageInfo) -> void`.

var amount: float = 0.0
## blunt | slash | pierce | ballistic | fire | explosive | zombie | fall | spikes
var type: StringName = &"blunt"
## Why it happened, for horde memory / stats: melee | firearm | spikes | fire | trap | fall | thrown
var cause: StringName = &"melee"
var source_id: StringName = &""
var source_pos := Vector3.ZERO
var hit_pos := Vector3.ZERO
var direction := Vector3.FORWARD
## 0..1 chance-ish power to sever a damaged limb.
var dismember: float = 0.0
## 0..1 stagger strength.
var stagger: float = 0.0
## Tool power against materials (from ItemDef equip.tool_power), e.g. {"wood": 22}.
var tool_power: Dictionary = {}
## Collider that was hit (limb hitbox etc.); not serialized.
var collider: Object = null


static func make(p_amount: float, p_type: StringName, p_cause: StringName, p_source: StringName = &"") -> DamageInfo:
	var d := DamageInfo.new()
	d.amount = p_amount
	d.type = p_type
	d.cause = p_cause
	d.source_id = p_source
	return d


func to_dict() -> Dictionary:
	var d: Dictionary = {"amount": amount, "type": String(type), "cause": String(cause), "source": String(source_id)}
	if source_pos != Vector3.ZERO:
		d["from"] = [source_pos.x, source_pos.y, source_pos.z]
	return d
