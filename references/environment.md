# Verified local environment

## Additional computer, verified 2026-10-22

Installed the official 3.0.1.4 base plus vendor 3.0.1.8 update. Installed manifest
reports program 3.0.1.8 / packages 3.0.2.4 / help 3.0.0.2; the launcher file
version remains 3.0.1.3. Executable/profile paths below are unchanged. The updated
Studio passed native MCP project/build checks and physical TM751-C USB tests:
identity, full download, RUN/STOP, normal variable read/write and reconnect.
ScriptEngine 4.1.0.0, OnlineManager 3.5.20.61, ApplicationObject 3.5.20.60.
TM751 description: type 4102, ID `1631 0051`, version 3.5.15.20. Connected
GetTargetIdent reports TM751-C and runtime version 3.5.15.20; this is not a full
vendor firmware build identifier. Procedure: [physical-plc.md](physical-plc.md).
The older simulation debugger/trace validation below remains distinct from the
new physical acceptance. Keep Application's default name: renaming it hung.

## Original simulation installation

Verified 2026-10-13 on this computer. Recheck paths after Studio upgrades.

- Executable: `C:\INVT\Invtmatic Studio V3.0.1.4\CODESYS\Common\Invtmatic Studio.exe`.
- Profile: `Invtmatic Studio V3.0`.
- Folder/UI release: V3.0.1.4; executable file version: 3.0.1.3.
- CODESYS core VersionKey: 3.5.20.60 (3.5 SP20 Patch 6).
- Installed ScriptEngine package: 4.1.0.0, runtime IronPython 2.7.
- Stubs: `C:\INVT\Invtmatic Studio V3.0.1.4\CODESYS\ScriptLib\Stubs\scriptengine`.
- TM750 device description: type 4102, ID `1631 0050`, version 3.5.15.20.
  This is a device-description version, not measured PLC firmware.

## Launch and lifecycle

The parser rejected a Python list converted to
`"--profile=Invtmatic Studio V3.0"` with “must specify a profile”. A raw Windows
command line with `--profile="Invtmatic Studio V3.0"` works with `shell=False`.
Working directory is the executable's `Common` directory. The minimal noUI probe
completed in 6.36 s and wrote a result. User-session execution was required for
these verified runs; prior sandbox timeouts do not establish a Studio limitation.

Both UI and noUI can run scripts, read/write ST and export. On this TM750 project,
noUI rebuild emitted “Object reference not set” followed by duplicate-key errors;
it did not produce the expected intentional ST diagnostic. The same corrected
project passed in UI mode. Use UI initialization for builds. A dedicated UI
process can execute the script and exit without menu interaction. This remains
the fallback workflow. The current preferred MCP keeps one UI-initialized process
open with the tested persistent watcher; see [persistent.md](persistent.md).

Existing Studio PID 42900 was responsive at the start of the latest check.
The Tools/Scripts dialog opened. Cancelling that file dialog generated a vendor
“script execute requires 1 argument” message, which was dismissed. The earlier
reported post-script menu hang was not reproduced or explained; per-job CLI avoids
depending on that menu. Do not claim that the underlying UI defect is fixed.

## Library findings

The original side-branch report contained `IoStandard 3.1.3.1` missing-library
diagnostics, apparently left from the original template/device conversion. On reopening the saved
TM750 project, the reference was `#IoStandard`, with default/effective 3.5.15.0.
The prepared direct-reference replacement therefore matched nothing.

Experiments on separate copies:

- Explicit placeholder redirection to 3.5.17.0: failed, including missing
  `IoMgrConfigGetConnectorList` / `IoMgrConfigGetParameter`.
- Calling `set_redirection('')`: effective resolution became null in this test;
  generated hundreds of type errors. Do not treat empty redirection as a verified
  restoration workflow on this installation.
- Explicit redirection to `IoStandard, 3.5.15.0 (System)`: clean compile, intentional
  undeclared-symbol error detected, restored ST clean, save/export successful.

The adapter does not automatically change library versions. Use the fixed v6 test
copy only as a capability fixture, not as an approved production machine template.

Evidence in the original workspace:

- `analysis/side-scriptengine-check/api_result_v2.json`: original UI API check.
- `api_result_v3.json`: noUI internal build errors, original prepared script.
- `api_result_v4.json`: UI with IoStandard 3.5.17.0, library incompatibility.
- `api_result_v5.json`: empty redirection failure.
- `api_result_v6.json`: full successful UI cycle (38.78 s).
- `api_result_v7.json`: same 3.5.15.0 in noUI, internal exceptions persist.
- `analysis/inspect-host.json`: adapter read succeeded (30.86 s).
- `analysis/integration-live-result.json`: actual MCP end-to-end verification;
  passed clean build, intentional error detection, repair with Cyrillic ST and
  native/PLCopen export (30.88–37.26 s per job), source hash unchanged.
- `analysis/timeout-host.json` and `analysis/cancel-result.json`: timeout, busy-job
  rejection and cancellation passed; original Studio process remained alive.

## Persistent verification and sources

The fallback Python adapter is an original implementation using the installed API.
Its three executable scripts and MCP registration are preserved. The separate
persistent adapter reuses upstream Codesys-MCP IPC/ScriptManager and derives its
watcher under MIT; its exact commit and lifecycle are in [persistent.md](persistent.md).
It passed the same TM750 edit/build/export/reopen cycle, plus MCP-owner crash,
normal EOF and timeout quarantine checks. Evidence:

- `analysis/persistent-live-result.json`: one Studio PID across repeated commands,
  intentional compiler failure/repair, Unicode ST, export and saved-copy reopen.
- `analysis/persistent-lifecycle-result.json`: owned process shutdown on owner loss
  and EOF, and rejection of further operations after a transport timeout.
- `analysis/persistent-summary.json`: measured timings and fallback integrity.

Related projects and references:

- https://github.com/luke-harriman/Codesys-MCP — basis of the tested persistent MCP.
- https://github.com/chency1024dy/Codesys-Skill — analyzed for workflow/review/
  diagnostic concepts; see [codesys-skill-adaptation.md](codesys-skill-adaptation.md).
- https://content.helpme-codesys.com/en/CODESYS%20Scripting/_cds_starting_script_via_command_line.html
- https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_commandline.html
- https://content.helpme-codesys.com/en/ScriptingEngine/ScriptLibManObject.html
- https://modelcontextprotocol.io/specification/2024-11-05/basic/transports

The installed `execute_on_primary_thread` documentation explicitly warns that
multithreaded scripts are not officially supported and that background threads
must finish before the main script exits. The persistent watcher locally passed
validation with API calls marshaled to the UI thread; this does not remove the
upstream support limitation or prove portability to another installation. Keep
the dedicated-process fallback for failures and revalidate after an upgrade.
