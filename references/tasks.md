# Task configuration and program calls

Use `invtmatic-persistent` version 0.3.0 on an owned project copy. These are offline
engineering operations, not runtime task monitoring or PLC start/stop commands.

## Inspect first

`invt_inspect_tasks {application_guid?}` returns task-configuration GUIDs, tasks,
kind, raw interval/units, raw priority, watchdog and ordered program-call names,
comments and indices. `interval_ms` and watchdog `time_ms` normalize a simple
literal or numeric-with-unit value; an expression that cannot be resolved remains
raw with normalized value `null`. Unavailable fields are reported explicitly.
Do not infer values from a task name. Capture the baseline before editing.

The verified TM750 fixture has `MainTask` (cyclic, 50 ms, priority 1, `PLC_PRG`)
and `EtherCAT_Task` (cyclic, 4 ms, priority 0). These are fixture observations,
not recommended production timing or evidence of a configured physical EtherCAT bus.

## Supported writes

All writes select objects by GUID in the chosen application, verify read-back,
save the copy and rebuild that application. With several applications, specify
`application_guid`. Do not copy GUIDs from another project.

| Tool | Arguments |
|---|---|
| `invt_create_task` | `name`, `interval_ms`, `priority`; optional `watchdog`, `application_guid`, `task_configuration_guid` |
| `invt_configure_task` | `task_guid`, nonempty `settings` containing supplied `interval_ms`, `priority` and/or `watchdog`; optional `application_guid` |
| `invt_bind_program` | `task_guid`, `program_guid`; optional `index`, `comment`, `allow_multi_task`, `application_guid` |

Creation requires exactly one selected **existing** task-configuration object and
creates a cyclic task. Settings writes support cyclic tasks only and preserve
unsupplied fields and program calls. Event/status/external-event/freewheeling/
parent-synchronous types, core binding, new task-configuration creation and bus
cycle assignment are not exposed. Read inspection may still describe those types.

Adapter limits: task name is an ASCII identifier of 1-128 characters; interval
and watchdog time are integer milliseconds 1-60000; priority is an integer 0-31;
watchdog sensitivity is an integer 1-1000. These are supported input bounds,
not a claim that every target supports every possible value. The installed API
and compiler must accept the result. Sub-millisecond periods and arbitrary time
expressions cannot be written through this interface.

Watchdog arguments are `{enabled, time_ms?, sensitivity?}`. Enabling requires
both time and sensitivity explicitly. `{enabled:false}` disables it without
clearing its stored time/sensitivity. Watchdog timing must be chosen from the
task/process requirements and target behavior; a build does not prove worst-case
execution time, jitter or physical watchdog response.

Example arguments for creating a test task in a single-application copy:

```json
{
  "name": "Task_Process",
  "interval_ms": 20,
  "priority": 20,
  "watchdog": {"enabled": true, "time_ms": 100, "sensitivity": 2}
}
```

For configuration, use its returned `task_guid`, for example a settings object
`{"interval_ms":30,"priority":15}`. Do not resend unrelated baseline settings.
Test values above are examples, not production defaults.

## Bind a program, not an FB instance

Select a textual `PROGRAM` POU by GUID. Function blocks and functions must be
called from a program; they are rejected as direct task calls. Only programs
within the selected application are exposed here, not project-global POUs.

Omit `index` to append; otherwise use zero-based insertion position from 0 through
the current call count. Existing calls retain order/comments. `comment` is text
up to 2048 characters. The task's ordered names/comments are read back after
insertion. Index is not a persistent call identity; re-inspect after list changes.
The local API drops comments passed to add/insert, while replace stores them.
The adapter inserts and then replaces the same new entry to apply the comment;
the complete list is verified afterwards. Evidence: `analysis/task-comments-probe.json`.

A duplicate call in the same task is rejected. Binding a program already directly
called by another task is rejected unless `allow_multi_task:true` is explicitly
supplied. That option permits configuration; it does not establish thread safety.
Review shared state and indirect calls as well. The guard sees direct task lists,
not a complete ST call graph. Task-call removal, replacement and reordering of
existing entries are future capabilities.

## Read results before proceeding

Mutation results include `changed`, `created`, `saved`, `task_guid`, before/after
task records where available, `ok`/`build_ok`, diagnostics and a local result file.
`changed` indicates that mutation was attempted/applied; it is not a transaction
or proof that every requested setter succeeded. On an exception after mutation,
the adapter returns actual state and attempts to save it. Inspect before further
work. Compiler failure retains the saved configuration for repair.

Do not recreate a task after an uncertain response; use its GUID or inspect by
name first. Transport timeouts retain the usual session quarantine rules. No
automatic rollback or retry is promised. Read back the unrelated baseline tasks
when the change must preserve them.

These tools do not explicitly configure EtherCAT bus-cycle assignment or
PDOs/DC/axes. However, if the device uses an unspecified/default bus-cycle task,
the shortest-period task can become the effective bus task. Adding a faster task
can therefore affect bus scheduling without changing an explicit device setting.
Read the actual device/bus configuration before changing production timing; the
current inspection does not prove that assignment. For the SLM printer these
settings need a separate device-specific workflow.
[CODESYS bus-cycle documentation](https://content.helpme-codesys.com/en/CODESYS%20EtherCAT/_ecat_buscycle_task.html)
explains why bus scheduling and access to shared I/O need separate review.

## Evidence

Installed API: `ScriptTaskConfigObject.pyi`, `ScriptTaskObject`, `ScriptWatchdog`,
`ScriptPouObjectCollection`; [official API family](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptTaskConfigObject.html).
Read-only probe: `analysis/task-api-probe.json`. Full offline test:
`tests/invt-tasks-live.cjs` and `analysis/persistent-tasks-result.json`.
