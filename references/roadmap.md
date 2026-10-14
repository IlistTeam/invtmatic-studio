# Readiness and next capabilities for INVTmatic development

This is an implementation roadmap, not a list of available MCP tools. Current
0.4.0 provides text/library inspection, POU/GVL/DUT creation, ST edits,
cyclic-task configuration and program calls, builds and object export, plus
positively verified Studio simulation tools described in simulation-debugging.md. It can
support application logic on a prepared native project. It cannot yet reproduce
a complete powder loader or three-axis SLM machine project from a blank setup.

MCP should implement deterministic operations and read-back. The skill should
define their order, required engineering inputs, interpretation and acceptance
criteria. Instructions alone cannot add an API operation or test physical behavior.

## Priority 1: reproducible development without manual project surgery

| Needed MCP capability | Skill/workflow addition | Acceptance evidence |
|---|---|---|
| Project initialization from a verified TM750 template; environment/device/library manifest | Separate tooling, device-description and actual PLC firmware versions; template-selection rules | A fresh project opens and builds with the intended device and resolved libraries; no dependence on the capability-test fixture |
| Native checkpoints/archive export+restore; save deliverables outside temporary session folders | Versioned native project, extracted ST, dependency manifest and release handoff | Restore to a separate location and rebuild; relative external resources and archive inclusions verified |
| Folder/object lifecycle, rename/move/delete with reference checks | Maintainable hierarchy, deliberate cleanup and source↔object manifest | No dangling references or task calls after rename/remove; build and native reopen passed |
| Unbind/replace/reorder program calls and task removal; remaining task modes as needed | Complete scheduling edits, review direct/indirect shared-state ownership | Exact before/after call order, unrelated tasks unchanged, invalid edits rejected |
| Read-only diff/impact planning, ST expected-hash guard, grouped changes and one final build | Inspect → prepare dependency-ordered changes → review diff → apply → verify | Concurrent/manual edits detected; error retains an inspectable state/checkpoint; no automatic replay after timeout |
| Deterministic ST/manifest export and import into known objects | Git sources, source/project drift detection, reproducible revisions | Regenerate/update a copy from a checked-out text revision; reported GUID/path mapping and build result |

Standalone Git layout: the repository root contains skill resources, `mcp/` sources,
and the fixed TM750 test fixture. Dependencies, builds, session outputs and raw
investigation artifacts are ignored. Installed skill and `dist/` are deployment
copies. Build the INVT entrypoint, not upstream `server.js`. Pinned upstreams and
original-source hashes are in `provenance.json`; repository history belongs to
the GitHub repository rather than an embedded upstream `.git` directory.

Installed stubs show `save_as`, `save_archive`, comparison and object lifecycle
APIs, but their presence is not an INVT validation result. Probe them on copies
before exposing them. Batch operations need clear partial-failure/rollback
semantics; do not call a series of saved writes an atomic transaction.

## Priority 2: actual hardware and communications engineering

| Area | MCP addition | Skill addition / required inputs |
|---|---|---|
| Device topology and I/O | Actual device IDs/descriptions, connectors, parameter IDs/types/access, mappings; then validated device insertion/parameter/mapping writes | Selected I/O modules, channel direction, ranges, scaling, quality, feedback and output-state requirements; compare physical and logical assignments |
| Libraries | Repositories/installed versions, unresolved placeholder checks; explicit reference/redirection operations | Pin target-compatible dependencies, explain dependency changes and recompile; never default to newest IoStandard |
| Modbus TCP | Expose any device/library configuration used by INVT; generate/validate the agreed register contract and offline test endpoints | Client/server role, address base, types/word order/scaling, read/write ownership, commands/acknowledgement, stale data and reconnect behavior |
| HMI | Export a stable tag/alarm/interface contract; integrate the chosen panel's project format separately when possible | Panel model/software, command arbitration, modes, alarm acknowledgement and localization; Studio ST changes alone do not update an external HMI project |
| EtherCAT and 3 servo axes | Device repository/ESI compatibility, topology, PDO mappings, DC and bus-cycle task; motion-axis objects and unit/limit/homing parameters where supported | Actual drives, motors/feedback, mechanics/units, limits and required sequencing; verify motion library/runtime capability/licensing rather than assuming generic SoftMotion examples work |

For loading powder, the first hardware blocker is exact I/O/drive/communications
configuration and its interface contract. For SLM, EtherCAT/axis engineering and
the relationship between motion and process tasks are additional blockers.
Task changes alone do not complete bus engineering. They can still change the
effective bus scheduling when the device inherits the shortest-period task, so
device/bus-task discovery must precede production timing changes.
[The device parameter API](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptDeviceParameters.html)
provides the generic discovery/mapping family; INVT extensions and installed
device descriptions must determine which properties are usable locally.

A practical next development order is native checkpoint/archive and source export,
then read-only device/I/O discovery, then selected Modbus and EtherCAT configuration
writes. Obtain precise hardware models when those stages depend on them; they
should not block hardware-independent ST logic or API discovery now.

## Priority 3: functional validation and commissioning boundary

- Add sequence/FB test harnesses with explicit input traces and expected state/
  output transitions, including held/replayed commands, sensor faults, interruption,
  restart and communication loss. A valid compiler result does not cover these.
- The isolated Studio simulation workflow is implemented with explicit target
  identity, separate write/force and bounded polling. See simulation-debugging.md
  and the maintained API evidence matrix; this does not prove TM750 runtime,
  physical I/O, bus drivers or motion behavior. Extend scenarios for actual machine
  requirements rather than treating the sample loader model as production logic.
- For physical commissioning, design a separate explicitly requested workflow for
  download/runtime status/task timing/diagnostics and controlled online actions.
  Keep physical operations out of the current project/simulation tools; do not inherit upstream online
  capabilities merely because their scripts are present in the fork.
- Improve structured diagnostic locations, call/dependency analysis and performance
  observations. Cycle budget and servo timing need actual target/runtime evidence.

For skill maturity, add realistic workflow checks for create → bind → build,
dependencies-before-consumers, repair after saved failures, compare/restore and
source/project drift. Keep hardware assumptions explicit and findings grounded
in extracted code/device data. The existing skill already covers contextual ST
review, command/timer/state reasoning and current versus earlier diagnostics.
