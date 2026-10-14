# INVTmatic debug capability matrix

Installation: INVTmatic Studio V3.0.1.4, executable version 3.0.1.3, CODESYS
core 3.5.20.60/SP20 Patch6, ScriptEngine 4.1.0.0/IronPython 2.7.
Adapter: INVT MCP v0.5.0, 39 fixed tools (16 project/lifecycle, 15 simulation, 8 debugger).
Debugger gate uses OnlineManager 3.5.20.61 and Breakpoints.plugin 3.5.20.60.
Physical runtime actions and discovery remain disabled. Test source is the fixed
TM750 API_Check_v6.project (SHA256
4115c61d6b890f8f258f650202886294af4991d086c21e27c45056eacdd2123d).

The native fixture is opened only as an owned disposable copy. IoStandard
3.5.15.0 builds; no library upgrade is performed. The source hash remains checked.
Simulation changes reported device identity from type 4102/id 1631 0050/description
3.5.15.20 to type 4097/id 0000 000a/core 3.5.20.60/address 0000. This identity
and the owning-device getter distinguish IDE simulation from physical target data.

| Capability | Status/evidence as of 2026-10-14 |
|---|---|
| Application/device ownership and getter/setter | Tested: ancestor GUID selected, get_simulation_mode false→true; stale/physical tokens refused |
| Online executor | Tested: installed private _executor ExecuteSource workaround and explicit online-object Dispose; no direct fallback or gateway scans |
| Login/full download | Tested: Keep attaches only, Never downloads explicitly; no boot creation/implicit start/delete-foreign-apps |
| RUN/STOP/state | Tested: run/stop read-back; already stopped native STOP raises, so wrapper checks state first |
| Exception status | OperatingState.exception flag read; deliberately provoking a runtime exception is not tested |
| Variables | Tested: native typed IEC strings, struct member and array index; invalid path returns per-value error |
| Ordinary write vs force | Tested: stopped INT write persists, resumed code overwrites; force remains during RUN, selective unforce restores ordinary code updates |
| Forces | Tested: own ledger, selective unforce, disconnect/project-close cleanup; foreign force survives own cleanup; unexpected logout gives fresh errors and stops monitoring. Lost connection with owned force reports unconfirmed cleanup, retains ledger, explicit Keep reattach discovers force, selective cleanup passes |
| Monitoring | Tested: bounded sequential host polling, per-read timestamps; not atomic, not trace, no scan timing guarantee |
| ST scenarios | Full actual MCP suite passed: no permission, normal loading, sensor TON timeout, fault/reset, intentional interlock regression detected and repaired rerun passed; 110 tool calls, 31 registered tools |
| Breakpoints/line stepping/stack | v0.5 real stdio acceptance passed: exact implementation row/column, BPManager registration+activation, over/into/out across PROGRAM→FB, mapped source/frames, re-hit, stale-source/code/connection handles and owned cleanup. Transient frame locals not implemented |
| HALT, tasks and STOP | HALT pauses only the debug task; auxiliary task and software feedback continue. 100 ms watchdogs/450 ms pause tested in simulation. STOP from HALT requires explicit finish_cycle (remaining statements execute) or abort_cycle (can cause exception STOP). No default; disconnect/close/shutdown refuse HALT without an explicit choice |
| Foreign breakpoints and lifecycle | Definitions preserved, foreign collisions/removal refused; explicit cycle finish before STOP, selective owned cleanup, Keep recovery and graceful IDE exit passed. Earlier Core STOP with active points generated exception; deactivation before STOP finishes the cycle and is not hidden cleanup |
| Transient function locals | Native research reads stack-relative values with Good status in F_Inner and its caller F_Outer, including different values of the same input name. After return only the remaining caller frame is read. No public frame-local tool, stable frame handle or recursive-frame proof yet |
| Runtime trace | Native research created/configured its own trace, downloaded/started/stopped it in verified simulation and exported CSV with changing cycle count and expected nested-function output. START/STOP status requires polling. No public trace tool or selective runtime-packet cleanup proof yet |
| system.trace | Script command echo, not PLC trace; deliberately excluded |
| Reset, source/boot download, remote files, online change | Some generic APIs exist, not included/tested in this scope |
| Physical TM750 | Not tested, not enabled; actual firmware/hardware/communication/servo models remain unknown |
| Current chat registry | Earlier v0.4 registry still has 31 tools; reconnect required for v0.5's 39. Fresh stdio clients validate all eight added tools. Earlier direct chat 37-call runtime result remains historical |

Current live acceptance and pending items are tracked in
[invt-debugging-plan.md](invt-debugging-plan.md). Local detailed results:
`analysis/runtime-api-probe.json`, `analysis/persistent-runtime-result.json`,
`analysis/runtime-loss-result.json`. A report with passed:false is not acceptance.
Direct chat evidence after reconnect is in
`analysis/persistent-chat-runtime-result.json`; its sanitized summary is
`docs/invt-debug-chat-validation-2026-10-14.json`. The earlier independent-stdio
JSON registry count of 12 described the chat before reconnect.
The latest repeat still discovers 31 tools in this chat and 39 in a fresh stdio
client. Research evidence for locals/trace is separate from public tool support;
see [invt-advanced-debugger-research.md](invt-advanced-debugger-research.md).
Host guard tests cover mode/token mismatch, target drift, foreign preparations,
selective force preservation and lost connection retaining cleanup ownership.

Integration findings: native STOP when already stopped raises, so transitions
check actual state first. Extended fault probes revealed Not logged in on variable
access after repeated reconnects despite connected/run status. Explicit Dispose
for both public online operations and private probes made the full extended loss
suite pass. Pre-read before write/force rejects a missing monitoring channel before
preparation; no mutation is automatically replayed. A failed native operation
remains a reported failure, not implicit reconnect/download fallback.

Sources: installed ScriptOnline/ScriptDeviceObject stubs and actual INVT probe;
[official ScriptOnline contract](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptOnline.html);
MIT executor inspiration from pinned
[Codesys-MCP](https://github.com/luke-harriman/Codesys-MCP).
The secondary [mcptoolkit online design](https://github.com/zbest1000/mcptoolkit-for-codesys/blob/main/mcptoolkit_for_codesys/tools/online.py)
was used as a separation-of-operations reference, not copied as INVT validation.
