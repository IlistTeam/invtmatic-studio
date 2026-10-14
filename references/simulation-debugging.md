# Simulation debugging through persistent INVT MCP

Use this workflow for executing hardware-independent ST logic in Studio. Version
0.4.0 implements 15 additional fixed tools. Reconnect the MCP after code changes;
the existing chat registry may still expose the previous tools. Use actual tool
discovery, never infer availability from this document alone.

## Target and lifecycle

Start/reuse the intended owned session, open a fresh project copy, inspect the
application GUID and build. Fix compilation/library failures before execution.
`invt_get_runtime_target {application_guid}` reports the ancestor device GUID,
identity, configured address, actual `get_simulation_mode()` evidence and target_id.
Neither a name such as PLCWinNT nor the configured address proves the runtime.

Use `invt_set_simulation_mode {application_guid,target_id,enabled:true}` while
disconnected. Retain its **new** target_id and check `target.mode:simulation`.
The TM750 fixture changes reported device identity from type 4102/id 1631 0050/
description 3.5.15.20 to the Studio simulation type 4097/id 0000 000a/core
3.5.20.60/address 0000. This is not a TM750 firmware reading or physical runtime.
Disabling the flag is also possible while disconnected; it never connects to PLC.

All following tools require explicit `application_guid` and `target_id`. Every
call rereads the owning device getter. Physical/unknown mode, wrong app or stale
token is refused. Runtime target changes while attached require recovery instead
of silently adopting a different controller.

| Tool | Additional arguments / behavior |
|---|---|
| `invt_get_debug_capabilities` | optional application_guid; installed API boundary and capability matrix location |
| `invt_get_runtime_state` | Fresh connected/execution/operating flags; no auto-login, no cached state when disconnected |
| `invt_connect_runtime` | Keep login to existing simulation application; no download/update/start |
| `invt_download_application` | Explicit full download (Never) after fresh successful build; disconnect first |
| `invt_start_application` / `invt_stop_application` | Explicit RUN/STOP with state read-back; already requested state succeeds |
| `invt_disconnect_runtime` | Selectively cleans session forces, stops and logs out the owned connection |

Download and connection never create a boot application, delete foreign apps or
automatically run code. The upstream Force/Never mappings were erroneous; the
INVT implementation follows the installed API. Edit/create/configure/build tools
are refused while attached or force cleanup is unresolved. Disconnect, edit,
build and explicitly download again. An online code update is not implemented.
Online handles are explicitly disposed after each executor action. This is
necessary for the tested repeated reconnect/fault workflow; do not retain an
online application object across IPC scripts or omit Dispose in private probes.

## Variables and observations

| Tool | Additional arguments |
|---|---|
| `invt_read_variables` | `variables`: 1–32 variable paths; a single path is also supported |
| `invt_monitor_variables` | same paths, `duration_ms`:100–10000, `interval_ms`:50–5000 |
| `invt_write_variable` | `variable`, `value` (IEC literal string); one-time write, no force |
| `invt_force_variable` | same arguments; separate force tracked by session |
| `invt_unforce_variable` | `variable`; only a force created by this session |
| `invt_list_forces` | All current force paths with `owned_by_session`, plus owned requests |

Paths support members and nonnegative array indices (`PLC_PRG.st.x`,
`PLC_PRG.a[1]`). They are paths, not arbitrary evaluation expressions. Returned
values are native IEC strings, e.g. INT#7/USINT#10/TRUE. Compare typed expectations
or normalize only the known scalar type in a test; preserve raw values in reports.
Each value has start/completion timestamps, ok/error, and target metadata. A bad
path is an error, not a successful null read. Grouped reads are sequential and
`atomic:false`. Runtime may advance between variables.

Ordinary write uses write_prepared_values and can be overwritten on the next
program cycle. Force uses force_prepared_values and persists until selective
release. Refuse existing prepared values to avoid accidentally applying editor
or foreign preparations. A fresh read validates the variable/monitoring channel
before preparation: connection status alone was insufficient after a rapid
reconnect in testing. Refuse writing/forcing an already forced path. Never
unforce_all_values. The ownership ledger is for this running MCP session, not
a transferable claim after server/IDE restart.

Polling releases the Studio UI between sequential IPC reads, uses host monotonic
deadlines and stops on the first read/connection error. Actual duration and
timestamps are reported; one native call can extend the requested deadline.
It is not runtime trace, an atomic snapshot or scan-synchronous execution.

## Reproducible ST scenarios

Use small hardware-independent logic with explicit input/expected state traces.
The repository test fixtures provide a powder-loader model: idle=0, loading=10,
completion=30, alarm=90; permission, sensor, fault and reset inputs; TON timeout.
They are test models, not production controls or physical process validation.

Initialize/reset inputs, apply an event, poll for a condition with a monotonic
timeout, compare state and outputs, and save raw observations. TON is simulation
wall-clock time (five seconds in the sample), not virtual scan stepping. Include
normal sequence, absent permission, missing sensor, fault and recovery. A deliberate
missing-permission mutation must fail the same behavioral assertion; restore the
correct implementation and rerun that assertion before finishing.

For SLM, use the same pattern for logic and modeled drive feedback. This does not
validate EtherCAT, servo execution, watchdog timing or real outputs. Physical
commissioning needs the selected hardware and a separate allowed-action scope.

## Failure and teardown

Native mutation failure marks the runtime result uncertain. Inspect state and
disconnect/recover; never replay a download/start/write/force automatically.
Transport timeout quarantines the entire owned Studio session as described in
[persistent.md](persistent.md). Error responses never present old values as fresh.
Unexpected logout is tested separately from physical cable loss.

Disconnect cleans only owned forces and preserves foreign ones. Close-project
and normal session shutdown invoke the same cleanup before closing. If connection
is lost with owned forces, cleanup is explicitly unconfirmed and the force ledger
is retained. Do not claim success or silently forget it. If native cleanup fails,
session shutdown reports that error and ends only its owned Studio; a foreign
project in the window is preserved. Forced process termination/owner crash cannot
guarantee graceful unforce and is not a physical runtime recovery procedure.

MCP v0.5 adds version-gated breakpoints, implementation row/column mapping,
step into/over/out and stack observation; follow
[breakpoint-debugging.md](breakpoint-debugging.md), not ordinary ScriptOnline
start/stop wrappers. HALT is task-specific; other tasks and software feedback may
continue. MCP v0.6 adds frame-local reads and task trace capture/export; read
[advanced-debugging.md](advanced-debugging.md) for tested limits, ownership and
loss/recovery. Enum names/system.trace echo alone do not prove functionality.
Do not install a runtime/DAP substitute automatically.
Evidence and remaining work live in the MCP docs and local analysis reports;
verify a report passed before claiming acceptance.
