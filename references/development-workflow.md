# Project inspection and ST development

## Identify what is actually available

Use `invt_inspect` as the source of current object text. Read the saved `result_file`
if a tool preview truncates the JSON; strings recovered from a native project
binary can be stale. Inventory application GUIDs, object GUID/path, textual
sections and library placeholders, including default/effective resolution.
The returned `path` is an array of names; join it with `/` for human reports.

An object name is not its type or device identity. A node named `PLCWinNT` in the
verified fixture contains the converted TM750; task calls can repeat POU names.
Require the relevant textual section on the selected object. Do not infer task
intervals, watchdogs, addresses or servo configuration from names in the tree.
Use `invt_inspect_tasks` for actual periods, priorities, watchdogs and call order.
Detailed hardware addresses and servo/bus configuration still require separate
device metadata inspection, which the current MCP does not expose.

For analysis/review, inspect a copy and do not call `invt_patch_st`. The adapter's
close/stop operations save its owned copy, so this is a source-preserving analysis
workflow, not a promise that the temporary copy is opened with a read-only flag.
Preserve the requested input and record the limits of extraction.

## Establish a baseline and prepare the change

For iterative development, record the source path/hash, open-copy path, application
GUID, target object GUID/path, original declaration/implementation, and baseline
build result. `expected_sha256` on `invt_open_copy` verifies the input at opening;
it is not a concurrency check for later POU edits. Preserve pre-existing compiler
problems separately from regressions caused by the change.

Derive an edit from the latest inspected text. If replacing a selected fragment
while preparing a full section, check that the intended old fragment has the
expected number of matches; resolve ambiguity before generating the new section.
Before sending it, re-inspect if the project may have changed since the snapshot.
Reconcile unexpected differences instead of overwriting another edit.
The MCP has no atomic compare-and-swap for ST; avoid manual edits to the automation
window during a write operation. Do not send unsupported `old_text`, `new_text`,
object-name selectors or script code as tool arguments.

Keep unrelated declarations, comments and sections. For persistent changes,
`object_guid` identifies the POU and optional `application_guid` identifies the
build target. With multiple applications, supply the intended application GUID.
`invt_patch_st` rebuilds automatically; another `invt_build` is unnecessary unless
something changed or the result leaves an unresolved validation question.

An `ok:false` compiler result can still contain successfully saved `before`/`after`
text. Inspect the current copy when a partial edit or script exception is possible.
Fix from that current state; reopening the original input creates a new copy and
discards continuity with the previous session's edits.

## Keep recoverable artifacts

The session copy preserves the original input, but successive patches overwrite
that same copy. Keep intermediate ST revisions and build reports under version
control when they matter. For an additional native checkpoint, save/close the
project through MCP first, copy the closed `.project` within the workspace, then
reopen the checkpoint with `invt_open_copy`. Do not copy an actively written file
and present it as a verified checkpoint.

Preserve relative external resources if the project uses them. A `.project` file
plus a single POU export is not a dependency-complete `.projectarchive`; archive
creation/restoration is currently unsupported. Keep actual library resolutions
and device-description information with the deliverable where available.

Use UTF-8 ST files for readable diffs. Keep GUID/path and declaration/implementation
identity in filenames or a small manifest; export only sections that inspection
actually returned. `invt_export_pou` provides native and PLCopen object exports.
Keep the native `.project` as the engineering project; XML alone does not establish
round-trip fidelity or working task/device configuration.

Compare two projects by inspecting separate copies and comparing their extracted
ST and exposed metadata. Close one before opening another in the same session.
Match objects by GUID when identity survives, otherwise reconcile full paths.
Different GUIDs alone do not prove a code change. This is a text/library comparison;
it cannot prove equality of detailed hardware, visualizations or permissions.
Compare task settings/calls separately using `invt_inspect_tasks` on both copies.

## Development before hardware selection

For the powder loader, specify sequence states, transition conditions, sensor
quality, valve/drive feedback, timeout behavior and command ownership between
HMI and the upper-level controller. For the SLM printer, separately specify the
process sequence and the three axis command/state interfaces. Capture uncertain
requirements without guessing specific devices or plant behavior.

Keep process logic, I/O normalization, communications and drive/motion integration
separable. The persistent MCP can create program/FB/function, GVL and DUT objects
directly in the selected application; see [object-creation.md](object-creation.md).
Folder hierarchies and methods/interfaces are not exposed. Creating a program
does not automatically bind it to a task. For explicit cyclic scheduling use
the task workflow in [tasks.md](tasks.md); an offline build is not runtime execution.

Define the Modbus register contract explicitly: client/server roles, address
notation, access direction, types/word order, scaling, version, command
acknowledgement and stale-data handling. Hardware integration also needs selected
device manuals and mappings. EtherCAT axis work needs actual drive/device
descriptions, PDOs, units, limits, homing and motion-library interfaces; a generic
library or empty axis pool is not sufficient evidence.

After a build, separate what was checked: compiler acceptance, text inspection,
sequence/logic tests, simulation where available, and hardware commissioning.
Do not describe a successful compile as a tested machine application.
