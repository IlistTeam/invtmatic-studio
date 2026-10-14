# Frame-local reads and runtime trace (MCP v0.6)

Discover the actual registry before use. The v0.6 server exposes 44 fixed tools;
an existing chat can retain 31 until its MCP connection/tool registry is refreshed.
A fresh stdio test is server acceptance, not proof of availability in that chat.
Use positively verified Studio simulation only, with current application_guid,
target_id and debug_id. Read breakpoint-debugging.md for generation and HALT rules.

## Local variables in a stack frame

Call invt_get_debug_state while halted. Select a frame with locals_readable=true
and its opaque frame_id, then call invt_read_frame_variables with runtime identity,
debug_id, frame_id and 1..8 variable paths relative to that frame. This is read-only:
no expressions, arbitrary stack addresses or local writes. Nested function
input/local reads are verified, including different values of the same input name
in caller and callee and fresh caller values after return.

Obtain fresh frame IDs after every step/resume, return, reconnect or code change.
IDs bind source/code, connection, stack and HALT events/runtime state-change
stamp/hit count. Rapid continue and re-hit at the same address invalidates old IDs.
Each watch requires State=Good before Value and is released afterwards. Inspect
each value's ok/state/error/type/timestamp; group reads are sequential, not atomic.
A transition during observation rejects the group. Missing/unavailable locals
return errors, never fabricated values; optimized-away values are not promised.

If the same compiled POU occurs more than once in the current stack, every such
frame has locals_readable=false, locals_reason=ambiguous_repeated_pou and no ID.
A finite recursive METHOD fixture verifies this refusal. The installed reference
API does not uniquely select those invocations. Qualified FB-member reads are
separate persistent-instance observations and do not replace transient locals.

## Trace workflow

1. While disconnected, inspect cyclic tasks and create a configuration with
   invt_create_trace: application_guid, target_id, task_guid, 1..8 distinct
   variables, optional identifier name and every_n_cycles (1..1000, default 1).
   Keep returned trace_id and object_guid; neither identifies a foreign recording.
   Configuration creation saves the copy. auto_start and triggers are disabled.
2. Explicitly download, obtain a current debug_id and RUN the application.
   invt_capture_trace accepts trace_id and duration_ms (100..10000). It never
   starts or resumes application code. The verified profile has a 100-entry
   buffer; (duration_ms+500)/(task_period_ms*every_n_cycles) must be <=90.
   For longer intervals, explicitly choose a larger every_n_cycles at creation.
3. Capture downloads only its own packet, confirms trace START/STOP by bounded
   polling, exports CSV and selectively deletes its runtime packet. Require ok
   and packet_cleanup_confirmed; inspect overflow/overflow_count. A buffer
   overflow means data loss even if export succeeds. Results preserve vendor
   value spelling, native type class, runtime timestamp strings and ms/us units;
   large timestamps are strings to preserve UInt64 precision. Signals are not
   one atomic sample row. Host polling remains a different observation method.
4. invt_list_traces lists this session's configurations and packet ownership.
   Repeated captures use the same configuration without adopting other packets.
5. Stop explicitly, then disconnect and call invt_delete_trace for offline object
   removal. Online delete can clean the owned packet but returns
   disconnect_required_for_config_delete with configuration_preserved=true;
   it never logs out implicitly. Unknown/foreign IDs are refused.

Unexpected logout retains packet ownership and reports cleanup unconfirmed.
Inspect state, explicitly Keep-attach, STOP and request owned cleanup; disconnect
before deleting the configuration. Obtain a new debug_id after reconnect.
Never replay an unconfirmed trace START/STOP or hide a failed cleanup. Session
shutdown cleans owned runtime packets where confirmed; owner crash can terminate
only its IDE without proving graceful packet cleanup. Saved configurations can
remain in project copies after shutdown. The ownership ledger is session-local;
restarted sessions do not adopt or delete pre-existing configurations/packets.

Implementation gates OnlineManager 3.5.20.61, trace wrapper 4.2.0.0 and trace
editor/manager 4.2.0.2. Stop and revalidate after upgrades. Developer acceptance
uses tests/invt-advanced-live.cjs --extended, tests/invt-recursive-frames-live.cjs
and tests/invt-debugger-lifecycle.cjs --trace. These use disposable fixture copies
and fixed private fault fixtures; there is no public execute-script tool.
