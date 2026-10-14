# Phase 6: frame-local values and runtime trace

Research on 2026-10-14 uses only an owned TM750 fixture copy and positively
verified Studio simulation. The public v0.5 MCP still has 39 fixed tools and does
not expose frame-local reads or trace. This chat's repeated discovery returns 31,
including a working session_status; a fresh stdio client reports v0.5.0 and 39.

## Function-local values

The fixture calls PLC_PRG → F_Outer(7) → F_Inner(107). At the inner function's
second statement the compiler/core stack maps both functions and their caller.
The tested LanguageModel MonitoringService GetVarReference overload takes:
application GUID, EditorInstancePath, expression, project handle and object GUID.
These values come from the actual CallStackEntry.LocationInformation, not guessed
offsets. The resulting AddressInfo is stack-relative. OnlineMgr.CreateWatch
produces an owned monitoring reference; wait for State=Good before reading Value
and Release that reference afterwards. Reading Value during NotMonitoredYet can
throw an opaque error; that is not proof the variable is unavailable.

| Frame | Variable | Observed value |
|---|---|---:|
| F_Inner | iValue | 107 |
| F_Inner | nInnerLocal | 1107 |
| F_Outer | iValue | 7 |
| F_Outer | nOuterLocal | 107 |

Two Step Over operations execute the inner return expression and implicit return.
The stack shrinks from five to four entries and F_Outer becomes the current frame;
fresh reads then contain only its input/local (7 and 107). Generated/implicit
positions do not always map to an ST line. No claim of arbitrary repeated-POU or
recursive-frame selection is made. A public frame API needs an epoch invalidated
by each step/resume, plus source/code/session checks and explicit ambiguity rules.
EditorInstancePath alone does not uniquely identify recursive invocation depth.

## Runtime trace

The observed wrapper is ScriptDriverTraceObject.plugin 4.2.0.0; do not infer its
version from Studio's core VersionKey. The installed ScriptDriverTrace API creates a configuration wrapper, not a normal
ScriptObject: the wrapper has no guid. Resolve the created node in the application
tree for identity. Configure its own record name, MainTask, two variables,
every_n_cycles=1, trigger disabled and auto_start=False. Opening its editor is
required for online operations. With the application already explicitly running
in verified simulation, trace download/start/stop and CSV save succeeded.

State flags are asynchronous: immediate start can report is_running=False and
immediate stop True. The final probe polls read-only state to confirm transitions,
never retries start/stop merely because its immediate status is old. CSV contains
task timestamps and separate variable sections. Parse data rows, not just file
existence: the cycle counter increases by one and nResult equals 2215. Sampling
was about 50 ms in this fixture; this is not an exact timing guarantee. It differs
from host variable polling and uses runtime trace samples.

The experiment ends its recording and closes its owned IDE. Selective deletion
of a runtime trace packet, preservation of foreign recordings, buffer wrap/drop
reporting and recovery after transport loss remain untested. Do not publish a
general trace MCP tool without those ownership/lifecycle checks.

## Reproduction and evidence

`node tests/invt-advanced-debugger-research.cjs` runs the fixed test on the fixture
copy with actual stdio MCP. Native Studio is required; ordinary CI must not run
this native test. `--hold` is a bounded four-minute developer inspection mode,
not acceptance: only fixed stages and step are accepted via a session-bound
control file. Public MCP exposes no execute-Python or raw-address operation.

The detailed local file is analysis/advanced-debugger-research.json. Earlier
failed exploratory runs are not passes. The reviewed probe is
tests/probes/invt_advanced_debugger_probe.py; raw loaded-assembly/IL-call metadata
stays in ignored local evidence, and no vendor DLL or method body is distributed.
Original fixture, fallback adapter and physical-mode restrictions are preserved.
The final automated acceptance passed 23 MCP calls and five fixed probes, four
stack-local reads before return/two afterwards, and 33 samples per trace variable.
Source unchanged and graceful cleanup are asserted. The sanitized result is
[invt-advanced-debugger-validation-2026-10-14.json](invt-advanced-debugger-validation-2026-10-14.json).

Official context: [trace creation](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptDriverTraceImpl.html),
[trace editor](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptTraceEditorObject.html).
These describe the generic API; the native experiment establishes the INVT result.
