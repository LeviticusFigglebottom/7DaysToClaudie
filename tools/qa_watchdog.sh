#!/bin/bash
# qa_watchdog.sh <done-regex> <command...>
#
# Runs a rendering QA command (make screenshots) and ends it if it hangs on exit. After a long
# rendered run, engine shutdown sometimes never returns: gdb shows the main thread waiting in
# WorkerThreadPool with every worker idle. The stuck process holds the shared render lock until its
# timeout, which stalled every other job for up to 40 minutes. The runner prints a done line once
# all its images are written. If the process is still alive QA_EXIT_GRACE seconds (default 30)
# after that line, its process group is stopped and the run counts as a success. Output streams
# through unchanged.
set -u
done_re=$1
shift
grace=${QA_EXIT_GRACE:-30}
out=$(mktemp)
# In a non-interactive shell a background job is not a process-group leader, so setsid execs in
# place: $! is the command itself and leads its own group (xvfb-run, Xvfb, Godot).
setsid "$@" > "$out" 2>&1 &
pid=$!
tail -n +1 -f --pid=$pid "$out" &
tail_pid=$!
seen=""
while kill -0 "$pid" 2>/dev/null; do
	if [ -z "$seen" ] && grep -qE "$done_re" "$out"; then
		seen=$(date +%s)
	fi
	if [ -n "$seen" ] && [ $(( $(date +%s) - seen )) -ge "$grace" ]; then
		echo "[qa_watchdog] still running ${grace}s after it finished: stopping it (engine shutdown hang)" >&2
		kill -- "-$pid" 2>/dev/null
		sleep 2
		kill -9 -- "-$pid" 2>/dev/null
		break
	fi
	sleep 2
done
wait "$pid" 2>/dev/null
code=$?
wait "$tail_pid" 2>/dev/null
rm -f "$out"
if [ -n "$seen" ]; then
	exit 0
fi
exit "$code"
