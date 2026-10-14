# Frame-local values and trace: research boundary

Public MCP v0.5 still exposes 39 tools. It supports source-mapped stack observation,
breakpoints/stepping and qualified application/FB-member reads; it has no general
selected-frame variable or trace recording tool. Discover the actual tools before
use. A fresh stdio client has 39 while the latest chat registry still has 31.

Native feasibility is confirmed on the verified installation and TM750 copy:

- Function stack-relative inputs/locals were read through the compiler monitoring
  service and owned CreateWatch references, with State=Good before Value and
  Release afterwards. Nested functions had iValue=107 vs 7, locals=1107 vs 107.
  After return the inner frame disappeared and fresh caller values were read.
- Trace configuration, task recording and CSV export worked in simulation.
  Explicit trace START/STOP needs bounded status polling. Recorded cycle counts
  advance by one and the test output is 2215; sample timestamps are runtime data.

Do not equate a qualified FB-member read with an ephemeral function-local read,
or expose arbitrary expressions/raw stack addresses. A future frame read needs
fresh frame handles bound to the current halt epoch, source/code/runtime identity,
and rejection after step/resume. Multiple invocations of one POU and optimized-out
locals still need tests; a POU/instance path is insufficient for recursion.

Future trace operations need owned configuration and runtime packet identity,
bounded recording/buffer/read-back, no auto_start/boot persistence, preservation
of foreign traces and explicit loss/cleanup reporting. The probe stopped recording
and closed its owned IDE; general selective packet cleanup is not yet proven.

The fixed developer reproduction is tests/invt-advanced-debugger-research.cjs in
the MCP sources. It opens a fresh fixture copy in its own Studio, uses reviewed
private probes and asserts trace/locals. It is not a public execute-script tool or
an ordinary PLC workflow. Details: MCP docs/invt-advanced-debugger-research.md and
docs/invt-debugging-plan.md. Physical operations remain disabled.
