# Physical TM751 over USB

Use the separate physical tools only when the user intends to work with the real
controller. Keep simulation tools restricted to positively verified simulation.
The tested bench has only power and USB connected, without output loads.

USB Type-C on this TM751-C exposes RNDIS networking, not a serial programming
port. The tested Windows adapter uses the matching vendor-bundled RNDIS.inf
(USB VID 0525, PID A4A2), host 192.168.3.20/24, PLC 192.168.3.10, TCP 11740.
No default gateway is needed on this adapter. Preserve other adapters/settings.

Start MCP with `--physical-address 192.168.3.10 --physical-runtime` to expose
56 tools. Without physical options there are still 44 simulation/project tools;
address alone exposes only two additional read-only discovery tools.

1. Start the owned Studio and open a project copy. Inspect its application GUID.
   Select the correct TM751 device description: 4102 / `1631 0051` / 3.5.15.20.
   Disable simulation explicitly using `invt_set_simulation_mode` if necessary.
   A project/device description is not evidence of the connected PLC identity.
2. Call `invt_get_plc_gateways`, choose a known configured gateway by GUID, then
   `invt_bind_plc {application_guid, gateway_guid, expected_device_id:"1631 0051"}`.
   Binding resolves only the configured IP and connects to read GetTargetIdent.
   It compares the measured identity with the project device. It does not log in
   to an application or download anything. Targeted lookup may leave the scan
   cache empty; never invent a model from that cache or select the first PLC.
3. Retain the returned `target.target_id`. Physical runtime tools require
   `{application_guid,target_id}`. `invt_connect_plc` uses Keep, without download.
   `invt_download_plc` performs a fresh rebuild and full download using Never.
   It disables and verifies automatic boot creation in the project, does not
   delete foreign applications and does not call Start.
4. Connect, download and disconnect each return a **new target_id**. Replace the
   old token before the next call. Changed project/source/tasks/libraries,
   device, mode, gateway or address require a fresh offline binding.
5. Use `invt_get_plc_state`, `invt_start_plc`, `invt_stop_plc`,
   `invt_read_plc_variables {...,variables:["PLC_PRG.Counter"]}` and
   `invt_write_plc_variable {...,variable:"PLC_PRG.TestInput",value:"21"}`.
   Values retain their native type prefix, for example `DINT#42` or `UDINT#7`.
   Reads include timestamps and are not atomic. Writes require a fresh before
   value, refuse forced paths/foreign preparations and return actual read-back.
6. `invt_disconnect_plc` logs out without STOP. Session close/shutdown follows
   the same physical policy. If a bench should end stopped, call `invt_stop_plc`
   explicitly and verify STOP before disconnecting. Do not carry simulation's
   automatic stop-on-disconnect policy into a physical machine.

Uncertain mutations block replay. Inspect state and disconnect; transport
timeouts quarantine the session. Never retry an uncertain download/write/start
automatically. Existing unowned application connections are not adopted.

Physical breakpoints, stepping, frame locals, trace, forcing, resets, firmware
updates, boot creation, detailed I/O mappings and fieldbus commissioning are not
exposed by these tools. HALT and runtime exceptions require explicit recovery;
the physical tools refuse to resume/finish an unverified halted cycle.
FL2002/FL1001 I/O acceptance requires separate bench wiring and observations.

The version-gated identity and boot-setting accessors were inspected on Studio
3.0.1.8, ScriptEngine 4.1.0.0, OnlineManager 3.5.20.61 and ApplicationObject
3.5.20.60. Runtime GetTargetIdent reports model TM751-C and version 3.5.15.20;
this does not establish the vendor's complete firmware build/version.

Keep the standard Application name on this installation: its rename hung in the
vendor API. No binary project patching is used. See the recorded commissioning
sequence in `mcp/docs/tm751-usb-commissioning.md` for the evidence and limits.
