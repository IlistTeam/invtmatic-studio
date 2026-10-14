# Review ST and PLC behavior

Inspect the current textual objects and review them against the available process
requirements. An analysis-only request uses extraction without modifying ST.
If device mapping, task timing or called library code is unavailable, identify
that limit and the missing evidence; do not infer a defect solely from absence
in the extracted subset.

## Check behavior across cycles

Review outputs and state transitions over multiple PLC cycles, including startup,
interruption and restart. Trace the assignments and call order needed to explain
the behavior. Use these questions as prompts for evidence, not automatic findings:

| Area | Evidence to examine |
|---|---|
| Commands | Is a command intended as a maintained level, an edge or an acknowledged request? Can a held HMI/Modbus command retrigger after completion or reset? |
| Stateful FBs | Are timer/edge/communication/motion instances called on the required cycles? Are reset and completion paths reached before reuse? |
| Sequences | Are transitions, timeout/error paths and unexpected states handled consistently? Is recovery intentional rather than an accidental restart? |
| Outputs | Are output values defined on every relevant path? Do multiple writers/tasks compete? Are permissives and feedback faults checked where actuation is decided? |
| Cycle time | Are loops and data-processing batches bounded? Could synchronous work prevent completion within the configured task budget? |
| Data ownership | Do globals and shared structures have clear writers, readers and timing? Can communication updates produce an inconsistent multi-field command? |
| Units and types | Are ranges, scaling, conversions, overflow, invalid sensor values and division checked against the interface contract? |

For timers, review the actual instance call, input transitions and subsequent
use of outputs. A constant `IN` or a conditional call deserves inspection, but is
not sufficient proof of misuse. For Standard TON, the input and output behavior
is defined in the [official TON reference](https://content.helpme-codesys.com/en/libs/Standard/3.5.15.0/Timer/TON.html).
Check the library version in the project rather than assuming a different vendor
timer behaves identically.

For motion, use the selected library's contract for command triggering, Busy,
completion, error, abortion and reset; establish the active instance and axis
ownership. Do not substitute an SML or generic PLCopen example for the TM750's
actual motion interface. Availability of SoftMotion references does not verify
configured EtherCAT drives or working motion.

## Apply the process context

For powder loading, trace drive/valve commands against sensor quality, required
feedback, timeouts, capacity limits and the defined interrupted-cycle behavior.
Check command arbitration between local/HMI/upper-level control. Determine output
states from the agreed process requirements; do not assume that every valve must
close or every output must clear under every interruption.

For the SLM printer, inspect how process sequencing and motion sequencing depend
on each other, how axis readiness/homing/limits are represented, and how drive
or communication errors affect pending actions. Actual hardware stop behavior
requires the chosen system design and commissioning evidence; ST review does
not establish a safety function's certification or coverage.

For Modbus TCP, review units/types and multi-register coherence, explicit command
acknowledgements or identifiers where needed, stale communication, reconnects,
invalid requests and ownership. Do not assume retries are harmless: determine
whether the command is idempotent and whether the application consumes it once.

Direct input access is not an output write. A direct address, global variable,
short name, `WHILE`, missing `CASE ELSE`, or missing word such as “interlock” does
not by itself establish a functional defect. Read surrounding logic and callers;
an edge detector elsewhere does not automatically cover this command either.
Comments, strings and unrelated code must not count as behavioral evidence.

## Report actionable findings

Present demonstrated problems first, ordered by consequence. For each finding
give object path/GUID, section (`declaration` or `implementation`), line when
actually known, trigger, observed code behavior, consequence and a concrete fix.
Count lines within the named section, not an invented concatenation of both.
Include a short code excerpt when it helps reproduce the finding.

Keep plausible concerns separate from proven findings. State the reviewed scope,
unavailable inputs and build status. Prefer a few supported findings to a long
list of keyword warnings. “No demonstrated findings in the inspected scope” is
not a claim that the machine is safe or that omitted hardware metadata was checked.
