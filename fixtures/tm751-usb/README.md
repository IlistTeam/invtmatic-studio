# TM751 USB bench fixture

The native project is the preserved input to the successful 2026-10-22 physical
MCP acceptance on TM751-C. SHA-256:
`5be87fc6b96880d6283b8d15fa9119f09e574febab4de782c66b1cf9495056e1`.
Open a copy through MCP. PLC_PRG.st is a readable listing of its test logic;
declaration and implementation are separate editor sections in the project.
MainTask executes every 100 ms. No physical input/output is accessed by this ST.

This is an internal-variable capability test, not a production machine template.
The device root retains the old fixture name PLCWinNT but identifies as TM751,
4102 / 1631 0051 / 3.5.15.20. Application retains the default name. The inherited
HSIO/ExtCard nodes are not proof of FL2002/FL1001 wiring or I/O acceptance.

Saved gateway GUIDs are machine-specific. Use a configured local gateway and
`invt_bind_plc` to resolve and measure the intended USB target. Use the separate
physical download tool so automatic boot creation is explicitly disabled and
verified immediately before download. Firmware/boot/force/reset operations
are not part of this fixture. See ../../references/physical-plc.md.
