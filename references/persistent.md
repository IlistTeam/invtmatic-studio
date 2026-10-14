# Persistent INVTmatic connection

Use the registered `invtmatic-persistent` stdio MCP for repeated edits/builds.
Source: the `mcp/` directory in the cloned package. Read the package README for
installation and use that clone's absolute path when registering the server.
Upstream: https://github.com/luke-harriman/Codesys-MCP
Pinned upstream commit: `9a965c7e16cb49996de8d45596d6e15a27a39450`, MIT, v0.6.3.
The INVT entrypoint is `dist/invt-server.js`, not upstream `dist/server.js` or
`dist/bin.js`. It reuses upstream `IpcClient`, `ScriptManager`, and a derived
`invt_watcher.py`; `invt-session.ts` provides the vendor-specific lifecycle.
INVT MCP version 0.4.0 adds verified-simulation runtime tools to the v0.3 task/object
operations. Runtime procedures and arguments are in
[simulation-debugging.md](simulation-debugging.md). Rebuild/reconnect the server after upgrading its code;
an existing stdio process does not reload its tool registry automatically.

## Exposed tool arguments

Use the tools from the `invtmatic-persistent` namespace. Arguments are JSON data;
there is no execute-Python tool, archive tool or hidden upstream command channel.

| Tool | Arguments |
|---|---|
| `invt_session_start` | `{}`; check returned `state:ready`, not a nonexistent build result |
| `invt_session_status` | `{}` |
| `invt_open_copy` | `project`; optional lowercase 64-hex `expected_sha256` |
| `invt_inspect` | `{}` |
| `invt_inspect_tasks` | optional `application_guid` |
| `invt_create_task` | `name`, `interval_ms`, `priority`; optional `watchdog`, `application_guid`, `task_configuration_guid` |
| `invt_configure_task` | `task_guid`, `settings`; optional `application_guid` |
| `invt_bind_program` | `task_guid`, `program_guid`; optional `index`, `comment`, `allow_multi_task`, `application_guid` |
| `invt_build` | optional `application_guid` |
| `invt_patch_st` | `object_guid`, at least one complete `declaration`/`implementation`; optional `application_guid` |
| `invt_export_pou` | `object_guid` |
| `invt_create_pou` | `name`, `pou_type`, full `declaration`; optional `implementation`, `return_type`, `application_guid` |
| `invt_create_gvl` | `name`, full `declaration`; optional `application_guid` |
| `invt_create_dut` | `name`, `dut_type`, full `declaration`; optional `base_type`, `application_guid` |
| `invt_close_project` | `{}` |
| `invt_session_stop` | `{}` |

GUID values must be UUID strings taken from the current inspection. Each supplied
ST section is limited to 1,000,000 characters. For operations returning a
`result_file`, read that file when the response preview is incomplete. Build and
patch return direct `ok`/`build_ok`; a compiler failure has MCP `isError:true`.
If an operation returns `exception` without before/after or build fields, inspect
the current copy before deciding whether an edit was applied.
Creation arguments and side-effect/result semantics are in
[object-creation.md](object-creation.md).
Task parameters and call-order rules are in [tasks.md](tasks.md).

## Workflow and result semantics

1. `invt_session_start` launches one dedicated, UI-initialized Studio. It checks a
   response from the primary UI thread before reporting `state:ready`. An already
   ready session is reused. The user's existing Studio window is not adopted.
2. `invt_open_copy {project, expected_sha256?}` copies a workspace `.project` into
   `.invt/persistent/<session>/projects/<id>/` and opens that copy. External
   resources are not copied. Keep existing library resolutions.
3. `invt_inspect {}` returns GUIDs, full ST, libraries and diagnostics. Select the
   textual POU, not a task-call object with the same name.
4. `invt_patch_st {object_guid, declaration?, implementation?, application_guid?}`
   edits the **same open session copy**, reads it back, saves and rebuilds it.
   `invt_build {application_guid?}` rebuilds without editing. Check direct `ok`
   and `build_ok`, not the fallback's nested `result.build_ok`. Compiler errors
   return MCP `isError:true` but leave the session available for correction.
   Prior diagnostics are in `previous_diagnostics`; current diagnostics are fresh.
5. `invt_export_pou {object_guid}` writes `.export` and PLCopen `.xml` files.
   These operations do not prove functional or hardware correctness.
6. `invt_close_project {}` saves and closes the copy while keeping Studio running.
   `invt_session_stop {}` saves and closes the owned Studio process. Capture
   `project_copy` from `invt_session_status` before closing. All copies, exports,
   requests, result JSON and logs remain under the session directory.

Calls are sequential. A competing mutation returns busy instead of queueing an
edit against a project that might change. ST is data (base64 JSON), not Python.
The public MCP exposes 31 fixed tools: 16 project/lifecycle and 15 simulation tools.
It exposes no physical PLC control or arbitrary script execution. The local IPC directory is trusted executable material: keep
it inside the user's workspace and do not insert third-party command files.

## Failure handling

- `invt_session_status` reads host state without calling the IDE. A normal compiler
  error does not break the connection. A transport error or command timeout marks
  it `faulted` and blocks subsequent commands: the UI operation may still be
  running, so never automatically replay a mutation.
- Read `result_file`, `watcher_error.txt`, `stdout.log` and `stderr.log`. Stop the
  faulted session, then start a new one and inspect the saved copy before further
  edits. Stopping a faulted session may forcibly end only its owned process; the
  last unsaved mutation can be lost. The source input is preserved.
- Normal stdin EOF saves/closes the owned project. A watchdog handles disappearance
  of the MCP owner. If the IDE's UI thread is blocked, the watchdog cannot execute
  until that thread becomes available; it is not an external crash supervisor.
- If the user replaced the project in the dedicated window, normal shutdown
  releases the watcher and preserves that window. Do not manually open other
  projects in the automation window during active work.
- Runtime cleanup errors are reported separately from an unowned-project refusal.
  Failed cleanup ends only the owned Studio process and reports unconfirmed cleanup;
  it never releases the window as if the project were foreign.
- Persistence lasts for the running MCP server/session. It does not adopt an old
  IDE after a Codex/MCP restart. Copies remain available on disk for recovery.
- Never use `--noUI` for TM750 compilation: it failed in the verified installation.
  ScriptEngine uses a background polling thread with API calls marshaled to the
  primary thread. This is a locally tested integration, not INVT certification.

## Local setup and maintenance

Node executable: resolve the actual `node.exe` on this computer, for example
`(Get-Command node -CommandType Application).Source` in PowerShell.

Arguments:
`<clone>\invtmatic-studio\mcp\dist\invt-server.js --workspace <project-workspace>`

Codex MCP tool deadline: 180 seconds. Internal IPC deadline defaults to 60 seconds
(`--timeout-ms` up to 180000); startup waits up to 90 seconds for the watcher plus
the IPC handshake. MCP initialization itself does not launch Studio.
Use `npm ci --ignore-scripts` with the committed lockfile after reinstalling
dependencies; `npm run build:invt` compiles and copies scripts without deleting
the existing build. Use `npm run test:invt` for host regression tests.

Live offline validation scripts: `tests/invt-live.cjs` (edit/build/export/reopen)
and `tests/invt-lifecycle.cjs` (EOF, owner crash, timeout quarantine). They require
the verified test project and host access to the installed IDE. Results are in
`<test-workspace>\analysis\persistent-live-result.json` and
`persistent-lifecycle-result.json`. They must never point at an online PLC.
`tests/invt-generation-live.cjs` validates all exposed POU/DUT kinds, GVL,
cross-object compilation, rejection before creation, correction after a failed
creation build, export and persisted GUID/text after reopen. Its report is
`<test-workspace>\analysis\persistent-generation-result.json`.
`tests/invt-tasks-live.cjs` verifies period/priority/watchdog, partial settings,
program insertion order, duplicate/role/application guards, cross-task consent,
and persisted configuration after reopen. Report: `analysis/persistent-tasks-result.json`.
`tests/invt-runtime-live.cjs` exercises actual MCP simulation and deliberate logic
regression; `tests/invt-runtime-loss.cjs` exercises selective ownership, unexpected
logout and project-close cleanup on its owned copy. Local reports are
`analysis/persistent-runtime-result.json` and `analysis/runtime-loss-result.json`.
`tests/invt-runtime-guards.py` covers fail-closed mode/token/force ownership on host.

The original fallback's three installed Python scripts remain unchanged; their
original-source hashes are in the package's `provenance.json`. To fall back, stop
the persistent session first and submit its saved project copy to
`invtmatic-offline`, whose implementation and MCP registration are independent.
