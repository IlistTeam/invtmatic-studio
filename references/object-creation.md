# Create POU, GVL and DUT in the session copy

Use the three `invtmatic-persistent` creation tools (INVT adapter 0.2.0).
Select the application GUID from `invt_inspect`; omit it only for a project with
one application. Creation is directly under that application. Project-root,
folder and method/interface creation are not exposed by these tools. Cyclic task
creation and explicit program binding use the separate tools in [tasks.md](tasks.md).

## Inputs

All tools require `name` and a complete `declaration`. Names use ASCII IEC
identifier characters, start with a letter or underscore and are 1-128 characters.
The installed API/compiler additionally validates reserved words and actual
namespace rules. A name already present anywhere in the application tree,
case-insensitively, is rejected before creation; inspect/patch an existing object.
This duplicate guard is conservative and does not support shadowing names.

Declarations and implementations are limited to 1,000,000 characters each.
The declaration header must match the requested name and object kind. Leading
ST comments/attributes are allowed. Headers, type selectors and code are data,
not Python. The text must still satisfy the project's compiler.

| Tool | Additional arguments and constraints |
|---|---|
| `invt_create_pou` | `pou_type`: `program`, `function_block`, `function`. Optional ST `implementation`. A function requires `return_type`; other kinds reject it. Return type is a simple or qualified type name, up to 256 characters, and must match the full `FUNCTION` declaration. Only ST is exposed. |
| `invt_create_gvl` | Complete `VAR_GLOBAL ... END_VAR` declaration, optionally preceded by attributes/comments. No implementation section. Ordinary GVL creation; no separate persistent-variable object API. |
| `invt_create_dut` | `dut_type`: `structure`, `enumeration`, `alias`, `union`. Full `TYPE Name : ... END_TYPE` declaration must match that kind. Alias requires `base_type`, a simple/qualified type name up to 256 characters, matching the declaration. Other kinds reject `base_type`; inheritance and integrated enum text lists are not exposed. |

Each tool also accepts optional `application_guid`. For multi-application projects,
provide it explicitly. The tools do not accept a parent path/GUID, `old_text`,
`new_text`, language flags or upstream CODESYS script paths.

Example `invt_create_pou` arguments for the unique application in a session:

```json
{
  "name": "FB_CommandStatus",
  "pou_type": "function_block",
  "declaration": "FUNCTION_BLOCK FB_CommandStatus\nVAR_INPUT\n    xCommand : BOOL;\nEND_VAR\nVAR_OUTPUT\n    xActive : BOOL;\nEND_VAR",
  "implementation": "xActive := xCommand;"
}
```

Example structure and GVL (create the type before the GVL that uses it):

```json
{"name":"ST_Status","dut_type":"structure","declaration":"TYPE ST_Status :\nSTRUCT\n    xReady : BOOL;\nEND_STRUCT\nEND_TYPE"}
```

```json
{"name":"GVL_Status","declaration":"{attribute 'qualified_only'}\nVAR_GLOBAL\n    status : ST_Status;\nEND_VAR"}
```

## Results and failure handling

After preflight and namespace/API validation, the adapter creates the object,
replaces/reads back the supplied text, saves the owned copy and rebuilds the
selected application. A creation result reports `created`, `saved`,
`created_guid`, `object` (path and actual text), `application_guid` and the usual
`ok`/`build_ok`, current/previous diagnostics and local `result_file` when available.
Rejected requests normally have `created:false` and an exception; schema-level
rejections may have no operation result at all. No object is intentionally
deleted or replaced by a creation request.

`ok:false` does not mean “no object exists”: a compiler failure returns
`created:true`, `saved:true` and the GUID. Fix it with `invt_patch_st` by that GUID;
do not repeat creation. An exception after the API returns an object also retains
its identity and attempts to save it; inspect the copy before deciding what to do.
If creation succeeded internally but an API exception/timeout prevented a GUID
response, state may be uncertain. Recover and inspect the application before retry.

Creation rebuilds automatically; do not add an identical rebuild unless there
is new evidence or a changed input. Keep native checkpoints and extracted ST when
needed. Existing source-copy, session serialization and timeout rules still apply.
The original input and the offline fallback adapter are preserved.

Create dependencies first (types, then GVLs/FBs/functions, then consumers). A new
program is not automatically called or task-bound. Reference/integrate objects
through reviewed existing code or `invt_bind_program`; compilation alone
does not prove invocation or validate an unused object's runtime behavior. Compiler
checking of unused code depends on the project/compiler settings; integrate or
explicitly check the object before claiming all its code was validated.

## Verified local integration

Installed stubs: `ScriptIecLanguageObjectContainer.pyi` under the verified Studio
ScriptLib path. Creation uses explicit keyword arguments and `PouType`/`DutType`
enum values, not guessed string overloads. The current web documentation may
differ from the installed API; use the installed profile and actual test results.
[CODESYS container documentation](https://content.helpme-codesys.com/en/ScriptingEngine/ScriptIecLanguageObjectContainer.html)
describes the API family.

Test fixture: `analysis/side-scriptengine-check/API_Check_v6.project` (TM750),
source SHA-256 `4115c61d6b890f8f258f650202886294af4991d086c21e27c45056eacdd2123d`.
`tests/invt-generation-live.cjs` exercises a separate copy without a PLC connection:
all exposed kinds, cross-references from compiled code, invalid requests,
intentional compilation failure/repair, export, close/reopen and stable GUID/text.
Evidence is in `analysis/persistent-generation-result.json`.
