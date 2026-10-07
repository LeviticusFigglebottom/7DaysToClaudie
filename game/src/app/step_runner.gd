class_name StepRunner
extends RefCounted
## Main-thread work in small steps, run a few a frame within a time budget (ADR-0036, ADR-0038):
## the world's boot behind the loading screen (40 ms a frame) and, with streaming, the attach,
## build and free work in play (a few ms a frame, nearest first).
##
## A step is [label, Callable, name]: the label is what a loading screen shows while it waits, the
## name is what meters report. A step that returns false is waiting on a worker thread and runs
## again next frame (it keeps its place). Steps run in priority order, lowest first; equal
## priorities run in the order they were added. A running step can queue more right after itself
## with insert_next().

## Called after every step that ran: (name, microseconds, finished).
signal step_ran(step_name: String, usec: int, finished: bool)

var budget_ms: float = 40.0
## A step that alone took at least this share of budget_ms ends the frame, so the next step (which
## may be a heavy one) doesn't start on top of it. 1.0 (the default) fills the whole budget; the
## boot uses 0.5: a 21 ms step followed by a 125 ms one made one 150 ms load frame (TD-197).
var solo_share: float = 1.0
## [priority, sequence, step] sorted by priority then sequence (a float, so insert_next can slot
## steps between two others).
var _queue: Array = []
var _seq: float = 0.0
var _done: int = 0
## The step running now (insert_next places steps after it).
var _running: Array = []


func add(step: Array, priority: float = 0.0) -> void:
	_seq += 1.0
	var e: Array = [priority, _seq, step]
	var i: int = _queue.bsearch_custom(e, _before)
	_queue.insert(i, e)


func add_all(steps: Array, priority: float = 0.0) -> void:
	for s: Array in steps:
		add(s, priority)


## Queues steps to run right after the step running now (or first, between frames), keeping
## their order.
func insert_next(steps: Array) -> void:
	if steps.is_empty():
		return
	var at: int = 1 if not _running.is_empty() and not _queue.is_empty() and is_same(_queue[0][2], _running) else 0
	# Sequence numbers between the neighbours keep the queue sorted for later add() calls.
	var prio: float = float(_queue[at - 1][0]) if at > 0 else (float(_queue[0][0]) if not _queue.is_empty() else 0.0)
	var a: float = float(_queue[at - 1][1]) if at > 0 else (float(_queue[0][1]) - 1.0 if not _queue.is_empty() else 0.0)
	var b: float = float(_queue[at][1]) if at < _queue.size() and float(_queue[at][0]) == prio else a + 1.0
	for i: int in steps.size():
		_queue.insert(at + i, [prio, a + (b - a) * float(i + 1) / float(steps.size() + 1), steps[i]])


func is_idle() -> bool:
	return _queue.is_empty()


func pending() -> int:
	return _queue.size()


## Share of the steps added so far that have finished (0..1).
func progress() -> float:
	var total: int = _done + _queue.size()
	return 1.0 if total == 0 else float(_done) / float(total)


## The label of the next step to run ("" when idle).
func current_label() -> String:
	return str((_queue[0][2] as Array)[0]) if not _queue.is_empty() else ""


## Drops queued steps whose name starts with `prefix` (work no longer wanted: a region that
## detached before its attach steps ran), or is exactly it with `exact`. Returns how many.
func cancel(prefix: String, exact: bool = false) -> int:
	var n: int = 0
	for i: int in range(_queue.size() - 1, -1, -1):
		var nm: String = str((_queue[i][2] as Array)[2])
		if (nm == prefix if exact else nm.begins_with(prefix)) and not is_same(_queue[i][2], _running):
			_queue.remove_at(i)
			n += 1
	return n


## Runs steps until the frame's budget is spent (or one step took solo_share of it); at least one
## runs, so a step that alone overruns still makes progress. Returns how many steps finished.
func run_frame() -> int:
	var t0: int = Time.get_ticks_usec()
	var finished: int = 0
	while not _queue.is_empty():
		var e: Array = _queue[0]
		_running = e[2]
		var s0: int = Time.get_ticks_usec()
		var r: Variant = (_running[1] as Callable).call()
		var waiting: bool = r is bool and not r
		var us: int = Time.get_ticks_usec() - s0
		if not waiting:
			# insert_next may have put steps before or after it: remove this exact entry.
			_queue.erase(e)
			_done += 1
			finished += 1
		step_ran.emit(str(_running[2]), us, not waiting)
		_running = []
		if waiting or float(Time.get_ticks_usec() - t0) / 1000.0 >= budget_ms or float(us) / 1000.0 >= budget_ms * solo_share:
			break
	return finished


static func _before(a: Array, b: Array) -> bool:
	return float(a[0]) < float(b[0]) or (float(a[0]) == float(b[0]) and float(a[1]) < float(b[1]))
