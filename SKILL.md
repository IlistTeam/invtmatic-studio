---
name: invtmatic-studio
description: "Develop, review and test IEC 61131-3 ST applications for INVT TM750 in INVTmatic Studio through persistent MCP. Inspect/edit/build project copies, create objects/tasks and debug positively verified simulation with variables, separate write/force and version-gated breakpoints/stepping. Physical PLC runtime control is outside the current integration."
---

# INVTmatic Studio

Use `invtmatic-persistent` for iterative project work. The verified installation
is INVTmatic Studio V3.0.1.4 with a working ScriptEngine; do not reinstall or
enable it as a routine prerequisite. Read [environment.md](references/environment.md)
when starting on a different installation, after an upgrade, or diagnosing launch
or library failures. The preserved `invtmatic-offline` adapter is the fallback.

## Select the workflow

- For inspection, ST development or comparison, read
  [development-workflow.md](references/development-workflow.md).
- For a logic review, also read [code-review.md](references/code-review.md).
  Review findings alone do not authorize changing the reviewed application.
- For failed compilation or an execution exception, read
  [diagnostics.md](references/diagnostics.md).
- Before creating a POU, GVL or DUT, read
  [object-creation.md](references/object-creation.md).
- Before task inspection/configuration or program binding, read
  [tasks.md](references/tasks.md).
- For running logic, watching variables or input scenarios in simulation, read
  [simulation-debugging.md](references/simulation-debugging.md). Obtain fresh
  application GUID and target_id; runtime changes require confirmed simulation.
- Before breakpoints, stepping or stack inspection, read
  [breakpoint-debugging.md](references/breakpoint-debugging.md). HALT pauses the
  selected task; other tasks may continue. Obtain a current debug_id after download.
- For session lifecycle, tools, recovery or registration, read
  [persistent.md](references/persistent.md).
- When the persistent connection is unavailable, use
  [offline.md](references/offline.md); its ticket/result schema is different.
- For extending the integration or assessing readiness for a complete machine
  project, read [roadmap.md](references/roadmap.md). Proposed features there are
  not active tools.

## Persistent development loop

1. Call `invt_session_status`. Reuse the user's intended ready session; otherwise
   start one with `invt_session_start` and open the input using `invt_open_copy`.
   If another project is already open in the managed session, preserve its copy
   and finish/close it before opening another. Do not close the user's other IDE.
2. Run `invt_inspect` and keep its full JSON result. Select the textual object by
   GUID and full path; `PLC_PRG` may also name a non-textual task call. An inspection
   proves extraction, not compilation or the completeness of hardware metadata.
3. Before editing, record a baseline build, the current ST and the copy path.
   Prepare the smallest logical change from that text. `invt_patch_st` accepts
   **complete declaration/implementation sections**, not `old_text`/`new_text`
   fragments. Omitted sections are preserved. It edits the same open copy, saves,
   verifies normalized read-back and rebuilds; a failed build still saves the edit.
4. Check direct `ok` and `build_ok`, current `diagnostics`, and `before`/`after`.
   An MCP compiler-error result leaves the session usable for correction. A
   transport timeout requires recovery before further mutations; never replay
   the mutation automatically. Keep current and previous diagnostics separate.
5. Keep reviewed ST in ordinary UTF-8 files with the native project and relevant
   POU exports. Capture `project_copy` with `invt_session_status` before closing.
   `invt_close_project` saves/closes the copy; `invt_session_stop` also closes the
   owned Studio. Do not leave a test session running after its validation task.

All project edits go through the installed ScriptEngine, never a binary patch to
`.project`. The input copy is preserved, but a plain `.project` copy is not an
archive of external dependencies. PLCopen XML and object exports are supplementary
artifacts, not proof of a complete or lossless project transfer.

## Capability boundaries

The current MCP reads the object tree, ST and library references; creates ST
POUs/GVLs/DUTs directly in the selected application; patches existing textual
objects; reads tasks, creates/configures cyclic tasks and binds programs in call
order; rebuilds; and exports a textual object. It does not expose new project
creation, folder/member creation, archive restoration, XML import, runtime/boot export,
noncyclic task configuration, detailed device parameters, I/O mapping or fieldbus configuration.
For those requests, prepare source/specifications and identify the missing step;
do not invoke upstream CODESYS scripts or invent MCP tools. Extending automation
requires checking the installed API on a test copy and validating the new operation.

Hardware models and mappings for the powder loader and SLM printer are not yet
selected. Keep hardware-independent logic separate from I/O, Modbus and motion
adapters; identify unresolved addresses, units, timing and device interfaces.
Existing EtherCAT tree nodes or motion libraries do not establish functioning
axes. Compiler success does not validate process behavior or machine safety.

Use UI-initialized compilation and preserve device-selected library resolutions.
The verified TM750 fixture uses `IoStandard 3.5.15.0`; newer is not automatically
compatible. Project development remains on copies. Separate runtime tools operate
only in positively verified Studio simulation; physical PLC login, download,
RUN/STOP, forcing, reset, firmware update and network discovery are not exposed.
Disconnect simulation before editing/rebuilding; close/stop cleans session-owned
forces and stops/logs out its runtime. Keep the fallback scripts and
their registration intact. Adaptation provenance is in
[codesys-skill-adaptation.md](references/codesys-skill-adaptation.md).
