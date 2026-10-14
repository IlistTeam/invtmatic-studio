# Compilation and repair

## Read the actual response

For the persistent MCP, the JSON is in the text content of the tool result. Build
and patch results use direct `ok`, `build_ok`, `diagnostics` and optional
`previous_diagnostics`. The offline fallback wraps the Studio result differently;
see [offline.md](offline.md). Tool transport success is not compiler success.
`invt_inspect`/`invt_export_pou` success does not imply the application builds.

Each diagnostic has `category`, `severity`, `text`, `position`. Preserve these
fields and the raw `result_file`; a display summary must not replace the evidence.
`position` may be empty or localized: retain it verbatim and do not manufacture an
object or line. Map to an inspected GUID/path only when the evidence supports it.

The persistent adapter clears message memory before rebuild and returns earlier
messages separately. Do not combine `previous_diagnostics` with current errors.
Its build success requires messages in compiler category
`97f48d64-a2a3-4856-b640-75c046e37ea9` and no current Error/FatalError. Report warnings
when relevant even if the adapter returns `build_ok:true`. With exceptions or
missing build fields, compilation is not established.

## Choose the appropriate repair

| Problem | Next evidence/action |
|---|---|
| ST syntax, declarations or incompatible types | Locate the current textual section; inspect the expression/declaration and fix the smallest logical cause. One root syntax error can generate many later messages. |
| Unresolved symbol or FB call | Check scope, namespace, instance declaration and actual library/API signature before inventing a replacement identifier. |
| Missing/unresolved library | Compare placeholder default/effective resolutions and installed dependencies. Preserve target-compatible versions; do not upgrade every library to repair one failure. |
| Device/compiler/library mismatch | Establish the intended device description, installation/profile and target requirements; separate these from an ST edit. |
| ScriptEngine exception or internal null-reference | Inspect exception and session logs. Check the installed API and UI-initialized mode; do not rewrite process logic solely to silence an automation exception. |
| IPC timeout or malformed result | Read host status and logs. The operation may still run: recover the session and inspect the saved copy before deciding whether to retry. |

The verified TM750 fixture builds with `IoStandard 3.5.15.0`; 3.5.17.0 broke
generated I/O code. The original 3.1.3.1 diagnostic was not sufficient evidence
that the reopened project still referenced that library. Read current resolutions.
Do not change libraries in unrelated production projects based only on this fixture.

On this installation, noUI rebuild failed internally even after correcting the
library. Persistent MCP uses UI initialization. HCPWorks3 noUI/elevation remedies
from the upstream skill are not a diagnosis of this INVT installation. Logs with
“error” are not automatically ST diagnostics; retain their origin and context.

## Bounded correction loop

1. Record the initial diagnostics, relevant current ST and the copy being edited.
2. State the cause supported by that evidence. If it is uncertain, make a focused
   inspection or isolated probe before changing unrelated code or dependencies.
3. Prepare the complete changed ST section from the latest text. Send it by GUID
   using `invt_patch_st`; follow [development-workflow.md](development-workflow.md)
   for edit preparation and concurrency limits.
4. Compare current errors and read-back with the baseline. If the intended error
   disappeared but another remains, report the specific result; do not call the
   whole application fixed. A failed rebuild still leaves the patch saved.
5. Continue while new evidence supports another focused correction. If the same
   unexplained failure repeats, retain the copy/logs and change the diagnostic
   approach rather than replaying identical edits or guessing new library versions.

For an execution/transport failure, use the recovery rules in
[persistent.md](persistent.md). Never repair it by clearing a fault flag manually,
injecting an arbitrary script into IPC, or terminating every Studio process.
For a task mutation exception, inspect `before`/`after`, `changed` and `saved`,
then use `invt_inspect_tasks` to establish actual settings/calls. A partially
applied task change is not reversed by a compiler failure.

Finish with the copy path, affected object/sections, build result, relevant
warnings and remaining dependency/logic/hardware questions. Compile acceptance
is one validation stage, not a functional test of the requested automation.
