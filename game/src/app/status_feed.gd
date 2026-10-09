class_name StatusFeed
extends Node
## Paces the spoken status lines that arrive together (first-week audit W15: at dawn after the
## Hum the night's report, the autosave, the supply drop and a level-up landed within a second,
## and the report was the first to scroll away).
##
## A system that announces something that can wait a moment emits
## `Events.status_message_queued(text, kind, priority)` instead of `player_status_message`; this
## node lets them out as `player_status_message` at least `min_gap_seconds` apart, highest
## priority first (oldest first within a priority). Lines emitted straight to
## `player_status_message` (an interaction's answer, "Too far away") still show at once, and the
## queue waits the gap after them too. Time is the feed's own process time, so a paused game
## holds the queue. Tuning: data/config/status_messages.json.

## Priorities callers use (higher goes first).
const PRIORITY_REPORT: int = 10
const PRIORITY_WARNING: int = 6
const PRIORITY_NORMAL: int = 0

var min_gap: float = 1.5
var max_queued: int = 8

## [{text, kind, priority, seq}]
var _queue: Array[Dictionary] = []
var _t: float = 0.0
var _last_shown: float = -INF
var _seq: int = 0
var _emitting: bool = false


func _ready() -> void:
	var cfg: Dictionary = Content.config(&"status_messages")
	min_gap = float(cfg.get("min_gap_seconds", min_gap))
	max_queued = int(cfg.get("max_queued", max_queued))
	Events.status_message_queued.connect(push)
	Events.player_status_message.connect(_on_shown)


func _exit_tree() -> void:
	if Events.status_message_queued.is_connected(push):
		Events.status_message_queued.disconnect(push)
	if Events.player_status_message.is_connected(_on_shown):
		Events.player_status_message.disconnect(_on_shown)


func _process(delta: float) -> void:
	tick(delta)


## Queues a line. The same text already waiting is not queued twice; past `max_queued` the
## lowest-priority, newest line is dropped.
func push(text: String, kind: StringName = &"info", priority: int = PRIORITY_NORMAL) -> void:
	for q: Dictionary in _queue:
		if str(q["text"]) == text:
			q["priority"] = maxi(int(q["priority"]), priority)
			_queue.sort_custom(_before)
			return
	_seq += 1
	_queue.append({"text": text, "kind": kind, "priority": priority, "seq": _seq})
	_queue.sort_custom(_before)
	while _queue.size() > max_queued:
		_queue.pop_back()


func pending() -> int:
	return _queue.size()


## Advances the feed's clock and lets out the next line when the gap since the last one has passed.
func tick(delta: float) -> void:
	_t += delta
	if _queue.is_empty() or _t - _last_shown < min_gap:
		return
	var q: Dictionary = _queue.pop_front()
	_emitting = true
	Events.player_status_message.emit(str(q["text"]), StringName(str(q["kind"])))
	_emitting = false
	_last_shown = _t


func _on_shown(_text: String, _kind: StringName) -> void:
	if not _emitting:
		_last_shown = _t


static func _before(a: Dictionary, b: Dictionary) -> bool:
	if int(a["priority"]) != int(b["priority"]):
		return int(a["priority"]) > int(b["priority"])
	return int(a["seq"]) < int(b["seq"])
