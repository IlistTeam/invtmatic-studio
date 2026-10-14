# Offline fallback adapter

Use this preserved adapter when the persistent MCP is unavailable or a dedicated
per-job process is needed. Stop/close a persistent session before using its saved
copy as input here. The executable scripts remain unchanged.

## Offline fallback workflow

1. Run `inspect` on the native `.project` in the user's workspace. Read the full
   `result_file` to obtain object GUIDs, declarations, implementations, and effective
   library versions. `PLC_PRG` can also name a task call: select the textual object
   by GUID, not the first matching name.
2. Keep ST source and requirements in normal text files under version control.
   Prepare `patch_st` with the complete changed declaration and/or implementation.
   The adapter edits a **new project copy**, verifies the text by reading it back,
   saves that copy, and compiles it. Unspecified text sections are preserved.
3. Check both host `ok` and `result.build_ok`; examine all diagnostics and the
   before/after text. An error-free process exit alone does not prove a build.
   `inspect` and `export_pou` success means that operation completed, not that the
   application compiles.
4. Continue from the returned `project_copy` for subsequent changes. The original
   input remains untouched. Keep the final `.project` together with exported ST,
   native/PLCopen exports and a record of resolved library/device versions.
5. Validate process logic separately: a compiler success is not a functional or
   hardware test. Hardware configuration, EtherCAT axes, I/O mappings and fieldbus
   settings must be based on actual selected devices, not generic CODESYS defaults.

## Invocation

All helpers are relative to this skill directory. Host helpers use Python 3.10+,
standard library only; `studio_job.py` runs under Studio's IronPython 2.7.
Use an actual Python interpreter, not the Windows Store alias.

Write a UTF-8 JSON request, for example:

```json
{"operation":"inspect","project":"projects/machine.project"}
```

Run through the shell tool:

```text
python scripts/invt_cli.py --workspace E:\PLCProjects --request E:\PLCProjects\request.json
```

Resolve the actual interpreter on this computer; see `references/mcp-setup.md`.
Studio launching from the Codex sandbox did not reproduce the normal user session;
use the shell tool's host execution approval mechanism when needed. This is not
a requirement to run Studio as Windows Administrator.

Operations:

| operation | Additional fields | Result |
|---|---|---|
| `inspect` | none | Tree, GUIDs, ST and library resolutions |
| `build` | optional `application_guid` | Rebuild and full diagnostics |
| `patch_st` | `object_guid`, `declaration` and/or `implementation`; optional `application_guid` | Edited copy, read-back, rebuild |
| `export_pou` | `object_guid` | Native `.export` and PLCopen `.xml` |

Optional `expected_sha256` guards against a changed input project. ST fields contain
literal text, not paths or executable Python. For several applications specify the
application GUID. New POU creation and device configuration are not exposed by
these preserved scripts. Develop and validate any required adapter extension
separately; the upstream skill's scripts are not an installed fallback capability.

The runner defaults to `--mode ui`, a dedicated process per job, and a 180-second
deadline. It passes exactly `--profile="Invtmatic Studio V3.0"`, with quotes around
the **value**. A normal Python argument list produces different Windows quoting
which this vendor parser can reject. Keep `shell=False` and the provided quoting.
`--mode headless` is for investigation only: TM750 compilation failed in that mode.

Every job writes `.invt/runs/<job_id>/` with source copy, request, progress, complete
result, stdout/stderr and host metadata. A timeout stops only that job's owned
Studio process. Never kill all Studio processes. Read `progress.json` and logs
before retrying. The runner serializes jobs within a workspace.

## MCP

Use `invt_submit` with the same JSON fields; it immediately returns a ticket.
Call `invt_status` after about 10 seconds and read its local `result_file` when
finished. `invt_cancel` stops only that server's owned job. A failed build returns
`ok:false`; the edited project copy remains available for repair.

The stdio server is `scripts/invt_mcp.py --workspace <absolute workspace>`.
It has no external Python dependencies or network listener. See
[MCP setup](mcp-setup.md) for the local registration command and scope.
