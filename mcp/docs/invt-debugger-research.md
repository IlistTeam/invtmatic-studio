# Phase 6: alternative debugger APIs in INVTmatic

## v0.5 implementation update

The guarded eight-tool bridge is implemented in src/scripts/invt_debugger.py and
the stdio entrypoint now registers 39 tools. Final native acceptance passed
102 calls/probes; details are in invt-debugger-validation-2026-10-14.json.

Readable TextDocument.GetLineId/FindLineById maps implementation rows and native
columns, including Unicode/comments/blank lines and multiple statements per row.
Document line IDs are part of the source fingerprint: restoring identical text
after an edit can still invalidate the old mapping. CodeId/DataId are compared
against the compile context and full download, with target and connection identity.

OnlineManager actually reports 3.5.20.61; VersionKey/other components remain
3.5.20.60. Reflection is narrowly gated to these observed versions. BPManager
SetBreakpoint only registers a definition; separate EnableBreakpoint activation
is required and tested. Call-stack frames use actual code addresses/source mapping;
transient frame locals remain unsupported.

Two-task testing confirmed other tasks continue during HALT. A 450 ms pause with
100 ms watchdogs did not cause an exception at that halt. Later exception STOP
also reproduced with watchdogs disabled: an initial watchdog-only hypothesis was
rejected. Stage tracing located the exception immediately after Core Stop while
runtime points remained active, before logout. Runtime deactivation before Stop
avoided it but completed remaining statements (counters 0→1): this must be explicit.

stop_application now requires halt_behavior=finish_cycle or abort_cycle when
HALT. finish_cycle temporarily deactivates runtime points, finishes the cycle and
restores activation in STOP. abort_cycle preserves the unfinished-state behavior
and can require explicit recovery from exception STOP. No default, hidden resume,
reset or download. Disconnect/close/session-stop refuse unresolved HALT, preserving
project, process and values. Final accepted tests use explicit finish_cycle and
verify refusal is mutation-free. Normal cleanup preserves foreign definitions.
Actual owner loss/EOF uses abort, retains reporting, and may forcibly end its own IDE.
An additional native test entered HALT before owner crash/EOF. Both owned IDEs
exited and the source/saved copies remained. EOF acknowledged cleanup; owner crash
exited without an acknowledgement, so graceful crash cleanup is not claimed.

Earlier failed experimental reports do not prove acceptance. The old fixed
breakpoint_proof predates the exposed protocol and its Core Stop claim concerned
STOP state, not absence of the exception flag. Trace capture and transient locals
remain separate uncompleted work; physical hardware remains unavailable.

## Historical feasibility research before v0.5

The following sections describe the initial 31-tool v0.4 implementation and its
fixed developer probes. They are retained as research history, not the current
capability matrix. The v0.5 update above supersedes their pending items and STOP
assumptions. Only an owned TM750 copy and verified simulation were used.

## Initial prototype progress

- [x] Enumerate installed loaded assemblies and registered commands without execution.
- [x] Find actual ScriptCommand.execute(System.String[]) despite its omission from stubs.
- [x] Resolve ScriptOnline's internal Application getter and verify core app GUID/login.
- [x] Find IOnlineApplication SingleCycle, permanent/temporary breakpoint, position/stack.
- [x] Execute core SingleCycle on a small PROGRAM→FB example: nCycle/nAfter 0→1,
  FB nInside 0→11, returned STOP. This is evidence for this configuration only.
- [x] Discover stepinto/stepover/stepout and inspect enabled status. Disabled in STOP
  without a halted breakpoint; no disabled command is forced.
- [x] Discover scriptengine.trace.create in a separate trace plugin; trace is not
  absent globally just because ScriptOnline has no trace methods. Not exercised.
- [x] Resolve existing LanguageModelMgr and GetCompileContext(application GUID),
  inspect BPManager contracts and compiler breakpoint lists for PROGRAM and FB.
- [x] Select a compiler-produced first executable position, validate its source GUID
  and hit it in simulation. Generic user-supplied line-number mapping remains pending.
- [x] Prove step into/over/out across PROGRAM→FB with source GUID/position IDs,
  variable changes and call-stack depth assertions.
- [x] Selectively clear the installed breakpoint; Core Stop from HALT produced STOP.
  This initial probe did not prove absence of the exception flag; see v0.5 above.
- [ ] Verify repeated continue/re-hit, foreign-breakpoint preservation, task/watchdog
  effects and software communication behavior; physical exchanges remain unavailable.
- [ ] Decide which fixed operations are ready for a guarded production MCP extension.

## Confirmed installed routes

The core implementation is `_3S.CoDeSys.OnlineManager.OnlineApplication` from
OnlineManager.plugin, including the vendor `Invt.InvtOnline.IOnlineApplication22`
interface. `ScriptDriverOnline.OnlineApplication` has a nonpublic Application
getter returning IOnlineApplication5. Probe reads verify the application GUID
and IsLoggedIn before any execution; ScriptEngine executor and Dispose remain
necessary. Reflection is version-sensitive and is not a certified vendor API.

Registered commands include `breakpoints stepinto`, `breakpoints stepover`,
`breakpoints stepout`, `online singlecycleactiveapp`, and breakpoint editing/view
commands. The ScriptCommand wrapper exposes execute(Array[String]); a Python list
is rejected. The command route may depend on active app, editor selection and UI
state. Do not equate command registration with successful debugger operation.

Core SetPermanentBreakpoint requires ICompiledPOU and LanguageModel.IBreakpoint,
not an arbitrary source line number. Compiler objects expose BreakpointList,
GetSourcePositionOfBreakpoint, source position and successor information. The
installed BPManager offers creation/set/clear/query methods and the component
framework can provide existing system instances. Service lookup and exact position
semantics require a generic line-number mapping before production exposure; no
guessed byte offset is applied. Source Position IDs are document identities (e.g.
19/20/2 in one edited PROGRAM), not 1-based line numbers or string byte offsets.

## Native feasibility proof

The fixed PROGRAM contains counter increment, FB call and a final increment. The
FB has two increments (1 then 10). Test assertions match the actual observations:

| Action | Current POU | PROGRAM counter | FB counter | Call-stack depth |
|---|---|---:|---:|---:|
| Initial permanent breakpoint hit | PLC_PRG | 0 | 0 | 3 |
| Step over first assignment | PLC_PRG | 1 | 0 | 3 |
| Step into FB call | FB_DEBUGPROBE | 1 | 0 | 4 |
| Step over first FB assignment | FB_DEBUGPROBE | 1 | 1 | 4 |
| Step out of FB | PLC_PRG | 1 | 11 | 3 |

The final PROGRAM increment remains zero while stepping the FB. Each step ended
in halt_on_bp. The source GUID changed on entry to FB and returned to the PROGRAM
GUID on step-out. Position IDs were read back from the actual compiler/core state.
Breakpoint clearing and Core Stop left STOP; the owned Studio exited gracefully.

An important incompatibility was proved: ScriptOnline.start() waits for RUN and
can time out when a breakpoint is hit immediately. ScriptOnline.stop() rejects
halt_on_bp. Calling Core Start()/Stop() avoids those wrapper restrictions. A future
debugger tool must permit the expected RUN/HALT transition and verify the result;
do not silently resume during cleanup. Command arguments need System.Array[String].
Private getters/fields, compiler object identities and command activation depend
on this installed version and must be revalidated after an upgrade.

The normal v0.4 MCP does not expose these debug transitions. Runtime debugger
state entered manually may therefore require the explicit tested core recovery
procedure; do not assume its ordinary start/stop tools implement full debugging.

## Next implementation slice

1. A private version-gated bridge for the selected simulation application; no
   arbitrary core command, Python execution or physical-mode entrypoint.
2. Read-only source/line/position/stack mapping, with project/app/POU GUID, source
   hash and downloaded CodeId/DataId; invalidate handles after edits/build/download.
3. Set/list/remove owned breakpoints from a verified source line; preserve foreign
   points and clearly report partial/unknown outcomes, with no replay after timeout.
4. Explicit continue/step into/over/out/stop using Core and fixed command GUIDs;
   bounded state polling between IPC calls and expected RUN/HALT/STOP read-back.
5. Negative and lifecycle tests: wrong target/app/source, stale generation,
   connection loss while halted, repeated stepping, code changes and clean teardown.
6. Multi-task/watchdog tests and software feedback; evaluate runtime trace separately.

This proves feasibility for the sample, not completion of phase 6 or a general
production debugger. No physical PLC operation or vendor binary is distributed.

Evidence (local, full metadata): `analysis/debugger-inventory.json`,
`analysis/debugger-core-inventory.json`, `analysis/debugger-execution-probe.json`,
`analysis/debugger-model-inventory.json`, `analysis/debugger-breakpoint-inventory.json`
and `analysis/debugger-breakpoint-proof.json` (successful final run with cleaned state).
The portable observation summary is [invt-debugger-proof-2026-10-14.json](invt-debugger-proof-2026-10-14.json).
Reproduce with `node tests/invt-debugger-research.cjs <fixed-stage>`; reviewed
IronPython probes live in `tests/probes/invt_debugger_inventory.py`. Native IDE
libraries/assemblies and raw workspace logs are not part of GitHub publication.

Official context: [CODESYS stepping](https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_stepping.html),
[scripting command/reentrancy limitations](https://content.helpme-codesys.com/en/CODESYS%20Scripting/_script_restrictions.html),
[separate trace API](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptDriverTraceImpl.html).
Documentation establishes generic interfaces; installed probes establish INVT results.
