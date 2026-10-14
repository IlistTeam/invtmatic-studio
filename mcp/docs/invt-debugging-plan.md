# INVTmatic simulation debugging implementation

Reconciled 2026-10-14 with Git baseline `6076197` and the handoff plan in
`analysis/plc-debugging-plan-2026-10-14.md`.

## Scope and existing foundation

Owned UI Studio, primary-thread IPC, project copies, fresh compiler diagnostics,
POU/GVL/DUT creation, cyclic tasks and ordered program binding are verified.
Preserve those operations and the original Python offline adapter. At the initial
baseline the chat advertised 12 tools and v0.3 source had 16. After v0.4 deployment
and reconnect this chat now exposes all 31 tools. Independent stdio validation
and direct chat validation both passed; future registry changes still need reconnect.

This implementation covers handoff phases 0–4 plus skill/documentation from phase 7.
The physical PLC is currently unavailable. Defer all work requiring physical
hardware, including network discovery, connection, reads, communication setup,
download, RUN/STOP, writes, force/unforce, reset and hardware tests. Reject physical
targets in the current MCP; do not implement a separate physical-runtime mode in
this scope. Resume phase 5 only after the user reports that the PLC is available
and explicitly requests that phase with a specified stand and action scope.
Lack of physical hardware must not block completion of simulation acceptance.
Connection-loss, reconnect and force-cleanup tests are simulation-only.
Phase 6 now includes the delivered v0.5 basic breakpoint/stepping bridge below.
Transient frame locals and trace remain separate unfinished work.

## Execution order and acceptance

1. Inspect installed ScriptOnline/Device stubs and test owning-device selection,
   `get_simulation_mode`, setter read-back and online executor in an isolated copy.
   Build the already fixed IoStandard 3.5.15.0 fixture before runtime operations.
2. Introduce simulation-only target/session/execution tools. Select application
   and its ancestor device by GUID, never the first named device. Check the actual
   simulation getter before every dependent call. Unknown/physical mode fails
   closed. Connection uses `Keep`, explicit full download uses `Never`; neither
   silently starts code nor creates a boot application. Do not replay failures.
3. Add timestamped per-variable reads, bounded polling, separate write/force and
   selective unforce. Refuse foreign prepared values and never unforce all. Track
   forces created by this session and clean them before disconnect/project close.
4. Test a small ST state machine, TON, interlock, timeout and fault recovery through
   actual MCP. Check structured/array paths, write vs force, invalid paths,
   disconnect and repeated simulation cycles. Add a deliberate logic regression
   that scenarios detect. Use wall-clock deadlines; do not claim atomic reads,
   exact polling periods, scan determinism or physical process verification.
5. Record capabilities as tested/API-only/unsupported/unclear. Update source and
   installed skill to match actual tests; commit only related files. Preserve
   backup hashes and existing unrelated `integration/tests/`, `scrypt.py`.

If simulation is unavailable, record the exact failure and continue independent
API/guard/docs work. Do not label runtime acceptance complete or automatically
install a SoftPLC/DAP alternative.

## Transfer corrections

The pinned upstream `download_to_device.py` reverses Force/Never semantics and
automatically creates a boot application; do not copy it. The installed stub and
[official ScriptOnline API](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptOnline.html)
specify Never=full download, Force=online change only, Keep=no update/download.
Upstream write-variable forces prepared values; implement ordinary write via
`write_prepared_values` separately. Reuse only the MIT executor workaround if
proved necessary here; do not adopt its network scan/first-node selection.

## Results

Progress is updated after evidence, not after code is merely written.

| Phase | Status | Evidence / remaining acceptance |
|---|---|---|
| 0: baseline and isolation | Complete | Git `6076197`; backup identified; separate owned Studio and fresh TM750 copies; fixture builds with IoStandard 3.5.15.0 |
| 1: installed API | Complete | Getter false→true, owning device GUID, executor, full download, RUN/STOP, fresh typed reads, separate write/force/selective-unforce tested. Debugger/exception limits recorded in matrix |
| 2: runtime lifecycle | Complete | Ordinary cycles, same-PID teardown, and extended loss/repeated Keep recovery passed after explicit IDisposable cleanup in operations and probes |
| 3: variables | Complete | Structures/arrays, errors, typed reads, write vs force, polling, selective unforce, foreign preservation, unexpected logout and retained-force loss/recovery/cleanup all passed |
| 4: ST scenarios | Complete | Actual MCP suite passed: absent permission, normal loading, sensor TON timeout, fault/reset, deliberately missing interlock detected, correct implementation restored and assertion rerun; same Studio PID and source unchanged |
| 7: skill/Git | Complete | Source/installed skill synchronized and validated; capability matrix and sanitized validation summary maintained; related changes committed in invt-simulation-debugging |
| 5: physical TM750 | Deferred: PLC unavailable | Do not execute hardware-dependent work until the PLC is available and the user requests this phase; no physical runtime operations performed. Not required for simulation acceptance |
| 6: full debugger | Basic v0.5 debugger delivered; advanced work pending | 39-tool stdio server passed 102 calls/probes: eight added tools, exact ST rows/columns, versioned handles, steps/stack, repeated hits, loss/recovery, foreign definitions and graceful exit. Explicit HALT stop behavior required; transient frame locals, selected frames and trace remain pending |

Detailed local evidence: `analysis/runtime-api-probe.json` and
`analysis/persistent-runtime-result.json` (latest live attempt; do not treat a
failed/interrupted report as acceptance). Host refusal/force-ownership tests:
`tests/invt-runtime-guards.py`, seven passed. First live attempt proved lifecycle
and reading, then failed a test expectation because native read_value returns
typed IEC literals, not bare numbers. The test comparison was corrected; runtime
values remain unmodified.

Full `tests/invt-runtime-live.cjs` now passed, including repeated download/login/
start/disconnect cycles. A discovered native STOP-on-STOP error is handled by
checking state before start/stop; an owned cleanup error is no longer mistaken
for a foreign project. Seven host session tests pass including both shutdown paths.

Extended connection-loss test exposed a repeatable Not logged in error on variable
access after successive Keep reconnects, despite connected/run status. Pre-read
now refuses the mutation before preparation, but did not resolve the channel.
Explicit online-object Dispose in both public operations and private fault probes
made the entire extended loss suite pass. Seven runtime guard tests include
Dispose after a failed native action. Final full ST suite passed on this lifecycle
implementation: 110 MCP calls, 31 registered tools, five behavioral checks plus
repaired interlock assertion; source unchanged and graceful owned Studio shutdown.
Extended loss suite passed 31 operations/probes with graceful shutdown. Skill
source/installation validate and match; backup files and MCP config hashes match.

## First scope acceptance

- [x] Baseline, isolated copies, owned Studio and library build recorded.
- [x] Installed API matrix and unsupported debugger scope recorded.
- [x] Actual target getter, device/app identities, token and fail-closed guards.
- [x] Explicit Keep attach/Never download, no boot/implicit RUN/physical login.
- [x] Repeated simulation execution/lifecycle cycles with explicit Dispose.
- [x] Typed/timestamped variable observations, members/arrays and errors.
- [x] Separate write/force/selective-unforce semantics proved in RUN/STOP.
- [x] Bounded polling, disconnect errors and foreign-force preservation.
- [x] Active-force loss retains ledger; explicit reattach/cleanup and close passed.
- [x] Wall-clock ST scenarios, deliberate missing interlock detected, repair passed.
- [x] Skill validated/deployed; backup unchanged; related code/docs committed.

Real PLC commissioning and full debugger are later scopes. Runtime exception
injection, crash-time graceful force cleanup, atomic reads and scan determinism
are not claimed. The previous 12-tool chat registry was reloaded; all 31 tools are
now available. The independent stdio suite and the direct chat test described
below use real tools, not assumed tool names.

## Direct chat acceptance after reconnect

- [x] All 31 tools discovered in this chat; session reports simulation-only scope.
- [x] Separate owned Studio and hash-checked TM750 copy, baseline build and tasks.
- [x] All 15 runtime tools exercised directly: 37 calls in total, including guards.
- [x] Physical RUN refused before any physical runtime action; simulation verified.
- [x] Write/force/unforce, array, input/output, monitoring and invalid path checked.
- [x] STOP on STOP, selective disconnect cleanup, no stale reads and Keep reattach.
- [x] Simulation disabled after disconnect, same PID and graceful owned shutdown.
- [x] Raw local report and sanitized Git summary saved; original fixture unchanged.

Evidence: `analysis/persistent-chat-runtime-result.json` and
`docs/invt-debug-chat-validation-2026-10-14.json`. The earlier JSON summary's
12-tool registry is historical (before reconnect). No additional physical-mode
implementation is needed or authorized while the PLC is unavailable. Phase 6
was reopened for alternative API research described in
[invt-debugger-research.md](invt-debugger-research.md). The accepted v0.5 extension
is documented below; this direct-chat acceptance remains a historical v0.4 result.

## Phase 6 implementation, 2026-10-14

- [x] Resolve readable TextDocument and 1-based source row/native-column mapping;
  comments/blank lines, Unicode and two statements on one row tested.
- [x] Bind debugger handles to target/project/app, source text and document line IDs,
  tasks/libraries, compiled/downloaded CodeId/DataId and runtime connection session.
- [x] Register and separately activate BPManager points; refuse ambiguous locations,
  foreign collisions and non-owned removal. No arbitrary command interface.
- [x] Exercise added eight tools over real stdio MCP (39-tool candidate), step
  over/into/out across PROGRAM/FB, source-mapped frames and qualified variable values.
- [x] Repeat continue/re-hit; stale source (including equal-text restore), old generation,
  unexpected logout, retained ownership, explicit Keep cleanup and new generation tested.
- [x] Two-task observation: auxiliary task continues during MainTask HALT. Initial
  450 ms halt exceeds its 100 ms watchdog without exception; not physical proof.
- [x] Finish foreign-point lifecycle acceptance with an explicit STOP policy.
  Tracing located exception at Core Stop from HALT with active runtime points,
  before logout. Deactivation before STOP permits remaining-cycle execution.
  Caller must choose finish_cycle or abort_cycle; HALT disconnect/close/shutdown
  otherwise refuse without mutation. No blanket watchdog-off restriction.
- [x] Refusal preserves project/session and variable values. Explicit finish_cycle,
  foreign-definition preservation, selective cleanup, Keep reattach and graceful
  exit passed in the final 102-call/probe stdio suite. Abort needs explicit recovery.
- [x] Native owner crash and stdin EOF from HALT end only the test-owned Studio;
  source fixture and saved copy remain. EOF acknowledges cleanup. Owner crash
  exits without acknowledgement: graceful cleanup/post-crash values are not proven.
  The 30-second guardian timeout branch itself was not exercised by these exits.
- [ ] Public transient-frame handles/selected-frame API, recursion and broader task cases.
- [x] Native feasibility: read stack-relative input/local values in nested functions,
  same input name with different caller/callee values, and remaining caller after return.
- [x] Native trace creation/configuration, simulation recording and CSV export with
  cycle/value assertions. Await actual START/STOP rather than immediate cached flags.
- [ ] Public frame-local API: bind frame handles to a halt epoch and validate source,
  code/session identity; reject stale handles after step/resume, unknown/optimized-out
  variables and ambiguous repeated POU/recursive frames; release only owned watches.
- [ ] Public trace API: own recording/configuration and packet, code/target identity,
  bounded duration/buffer, state polling, typed/timestamped export, selective cleanup,
  connection-loss behavior and foreign-recording preservation.
- [ ] All 39 tools directly in this chat: repeat still sees 31, while fresh stdio
  exposes the same v0.5 server's 39. Do not label independent tests as chat acceptance.

Native failed acceptance reports are not passes. Physical PLC work remains deferred.
Evidence: analysis/persistent-debugger-result.json and
docs/invt-debugger-validation-2026-10-14.json. This chat still needs reconnect to
replace the cached 31-tool registry with the verified 39-tool server.

## v0.5 publication

The earlier Skills PR was merged and its owner moved INVTmatic to the standalone
[IlistTeam/invtmatic-studio](https://github.com/IlistTeam/invtmatic-studio) repository.
The v0.5 update is [PR 1](https://github.com/IlistTeam/invtmatic-studio/pull/1),
branch codex/simulation-debugger-v05. The user-selected installation/workspace
instructions introduced after that move are preserved. Portable native acceptance
passed 102 calls/probes; the standalone build matches its 14 runtime files
(except harmless trailing blank lines in one Python file). See
[invt-package-debugger-validation-2026-10-14.json](invt-package-debugger-validation-2026-10-14.json).
Source/installed skill validators pass; fallback scripts and MCP config retain
baseline hashes. Physical actions remain zero.

Both Windows CI runs passed on publication commit e7dda84:
[PR checks](https://github.com/IlistTeam/invtmatic-studio/actions/runs/38546901201)
and [branch checks](https://github.com/IlistTeam/invtmatic-studio/actions/runs/38546894532).
They build the standalone package and execute all 30 host checks.
