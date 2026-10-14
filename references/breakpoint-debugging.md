# Simulation breakpoints and stepping (MCP v0.5)

Read [simulation-debugging.md](simulation-debugging.md) first. These eight fixed
tools require an owned simulation connection, an explicit full download by this
session, and the verified OnlineManager 3.5.20.61 / Breakpoints.plugin 3.5.20.60.
Studio's VersionKey 3.5.20.60 alone does not identify every component version.
They do not expose arbitrary commands, Python execution or physical PLC debugging.

The new server has 39 tools. An older running MCP/chat can still show 31: rebuild
and reconnect before using the new names. Do not invent unavailable tools.

## Prepare and choose a source location

1. Inspect the current copied project, ST object GUID and task GUID. Obtain the
   selected application's fresh target_id and positively verify simulation.
2. Disconnect/clean any earlier connection. Use the explicit full
   `invt_download_application` to build/download and leave STOP. Ordinary Keep
   attach alone does not establish a baseline for this debugger.
3. `invt_prepare_debug {application_guid,target_id}` returns debug_id, source hash,
   CodeId/DataId and component version. Keep these with the source revision.
4. `invt_get_debug_locations {application_guid,target_id,debug_id,object_guid}`
   returns exact executable positions. Public line/column numbers are **1-based
   in the ST implementation**, not the declaration. Columns are native document
   offsets, not visual tab-expanded widths. Use the returned values.
5. `invt_set_breakpoint {...,object_guid,line,column?,task_guid}` returns a new
   breakpoint_id. The runtime must be STOP/HALT. Blank/comment lines and ambiguous
   multi-statement rows are rejected; no snapping to another statement. If a row
   contains two executable positions, supply its exact column.

Compiler line IDs are different from row numbers. Position combinations are
returned as decimal strings to preserve 64-bit values. Compilation uses readable
TextDocument.GetLineId/FindLineById; source mapping never guesses a code offset.
The BPManager registers a definition and separately activates it in runtime;
presence in a UI list alone does not prove the breakpoint will halt execution.

## Run, step, observe and stop

All tools below take application_guid, target_id and debug_id:

| Tool | Additional arguments / behavior |
|---|---|
| invt_list_breakpoints | Shows application points and owned_by_session; foreign points have no removable owned ID |
| invt_remove_breakpoint | breakpoint_id created by this session; selective removal only |
| invt_get_debug_state | Fresh state, current source location and stack frames; generated frames may lack source mapping |
| invt_debug_continue | Explicitly resumes STOP/HALT; returns observed RUN/HALT/STOP |
| invt_debug_step | kind: into, over or out; HALT and enabled fixed command required |

Use `invt_read_variables` for qualified application/FB-instance paths and typed
values. Transient frame-local variables and changing the selected frame are not
implemented. Do not claim a persistent FB member read is a general frame-local read.
Step source/stack changes and values should agree with the intended statement;
reads remain sequential and are not an atomic application snapshot.

**HALT pauses the debugged task, not all tasks.** Native two-task testing showed
AuxTask continued while MainTask halted. A two-task profile with 100 ms watchdogs
survived a 450 ms explicit halt; this observation does not establish physical
watchdog behavior. Earlier logout failures also reproduced with watchdogs disabled;
do not blame watchdogs or silently change them as a workaround. Other tasks can
update shared variables and
software feedback between reads/steps. Do not equate HALT with a frozen machine
or deterministic scan. No physical Modbus/EtherCAT exchange was tested.

`invt_stop_application {application_guid,target_id,halt_behavior?}` stops the owned
application. From HALT the caller must explicitly choose `finish_cycle` (remaining
statements execute before STOP) or `abort_cycle` (no remaining statements; this
simulator can enter exception STOP and require explicit recovery). No default
choice is made. Disconnect, close and session-stop refuse HALT until this explicit
action; they preserve the session and do not execute the cycle implicitly.
Ordinary start is refused when a prepared debugger has breakpoints;
use explicit debug_continue. The ScriptOnline start/stop wrappers alone do not
handle immediate HALT correctly.

## Generation, ownership and recovery

Each action verifies project/target/app, compiled vs downloaded CodeId/DataId,
source text, document line IDs, tasks/libraries and runtime connection session.
An edit can recreate line IDs even if the same text is restored. Old debug_id
then remains invalid: disconnect/clean, rebuild/download explicitly, prepare anew.
Never reinterpret an old source/position handle against a changed compilation.

After explicit STOP, disconnect and close deactivate runtime points, clean only
owned breakpoint definitions/forces and logout. Foreign definitions are preserved; Studio can
change their runtime activation during logout/login. Do not remove them or
overwrite their condition/task filters. A foreign point at the same source
position causes set_breakpoint to refuse rather than adopt it.
Retaining active runtime traps is different from preserving source definitions.
Native tracing located exception STOP at Core Stop while runtime points remained
active, before logout. Deactivating points before STOP permits cycle completion;
it is therefore used only for the explicit finish_cycle option, not hidden cleanup.

After unexpected logout, observation rejects the lost connection, invalidates the
debug generation and retains owned-point evidence. With owned points, disconnected
cleanup reports unconfirmed cleanup. Explicit Keep reattach, then disconnect to
clean the ledger; subsequent attach/prepare returns a new debug_id. If source/code
also changed, full download is required. No automatic login, download or replay.

A dispatched mutation with an ambiguous result sets the runtime uncertain flag.
Inspect and recover explicitly; do not repeat continue/step/set automatically.
An IPC timeout quarantines the whole session. Stop reports runtime cleanup and
graceful process exit separately; forced termination does not prove graceful exit.
On actual MCP owner loss/EOF the recovery policy aborts the halted cycle, attempts
owned cleanup and can forcibly terminate its own IDE; it never finishes code implicitly.

Native research has now read stack-relative values in two nested functions and
captured runtime trace to CSV in simulation. These are developer proofs, not new
public MCP tools. Stable selected-frame handles, recursive/optimized locals,
trace packet ownership/cleanup and connection-loss cases remain pending. Read
[advanced-debugging.md](advanced-debugging.md) for the exact current boundary.
