# Origin and capability mapping

Analysis source: [chency1024dy/Codesys-Skill](https://github.com/chency1024dy/Codesys-Skill),
commit `2f61dd017cbbd0e30aecb2874c815283c88c479b`.
Read `skill-workspace/codesys-skill/SKILL.md`, its workflow/review/diagnostic/API
references, and representative launcher, patch, message and review scripts.
The fetched reference copy is `E:\Codex\INVT\analysis\codesys-skill-upstream`.

This integration uses newly written INVT-specific instructions, not an installed
second CODESYS skill. No upstream script was imported or executed. The inspected
revision contains no LICENSE/COPYING/NOTICE file; retain provenance and reassess
licensing before redistributing its source or verbatim documentation.

| Upstream subject | Adaptation to the installed INVT integration |
|---|---|
| Project extraction | Use current MCP object GUID/path/text and library resolution results. |
| Safe edits | Preserve the input and prior ST; edit the owned copy with full-section MCP writes. |
| Diagnostic repair | Use structured current messages and classify ST, dependency, API and transport causes. |
| Logic review | Use contextual scan/command/timer/output reasoning; avoid regex findings without evidence. |
| Compatibility | Prefer verified INVT paths, UI builds and installed API/device/library information. |
| Project comparison/artifacts | Compare extracted text/exposed metadata; keep native project and supplemental exports. |
| Object generation | INVT MCP 0.2.0 uses the installed creation API directly for POU/GVL/DUT; see object-creation.md. |
| Task configuration | INVT MCP 0.3.0 reads task settings, creates/configures cyclic tasks and binds local programs in order; see tasks.md. |
| Archive and detailed hardware/security APIs | Record current MCP gaps; no operational promises or upstream script invocation. |
| Online actions | v0.4 adds positively verified Studio simulation, separate write/force/selective unforce and scenarios. Physical runtime control remains excluded; see simulation-debugging.md. |

Deliberate differences: no forced archive operation that the MCP cannot perform;
no HCPWorks3 profile/elevation defaults; no noUI build path; no unsupported fragment
patch parameters; no code-review regex runner; no claim that object XML is a full
project backup. The persistent edit/response model replaces the upstream per-script
launch model. Existing fallback executable scripts and registration are preserved.

Read [persistent.md](persistent.md) for separate Codesys-MCP code provenance. The
skill repository above and the MCP repository are distinct projects.
