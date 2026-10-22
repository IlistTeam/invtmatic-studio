# TM751 USB hardware integration

Requested on 2026-10-22 for a new INVT TM751 connected directly to this Windows
computer over USB Type-C. Preserve the existing verified simulation workflows.

## Baseline

- Source baseline: `e586ddd8def8c8835655c0eb23f3876fc20a9ae6`, MCP 0.6.0.
- TypeScript build and all 44 existing host/guard tests passed locally.
- Stdio initialization and enumeration of all 44 tools passed locally.
- The portable package was originally verified with Studio 3.0.1.4, core
  3.5.20.60. The current official 3.0.1.8 distribution includes the 3.0.1.4 base
  installer and a separate vendor update. The base installer completed with exit
  code 0. Native MCP startup, copy opening and rebuilding passed on that base:
  44 tools, zero compiler errors/warnings, input project hash unchanged. The
  vendor updater initially reported an empty package path. After selecting the
  package, it completed successfully. Installed manifest now reports program
  3.0.1.8, packages 3.0.2.4 and help 3.0.0.2. The launcher EXE still reports
  3.0.1.3; the Studio window reports 3.0.1.8. ScriptEngine remains 4.1.0.0,
  OnlineManager remains 3.5.20.61.
- The TM751 USB descriptor reads `RNDIS/Ethernet Gadget`, hardware ID
  `USB\\VID_0525&PID_A4A2`, compatible class `02/02/FF`. Windows initially
  selected `usbser.inf` and COM4. Installed the exact matching `RNDIS.inf` from
  Studio's bundled `RNDIS_Windows_Driver.cab`, published as `oem10.inf`. Its catalog
  has a valid Microsoft Windows Hardware Compatibility Publisher signature.
- The initial failed USB port reported a descriptor request failure (Code 43);
  moving to another port restored USB enumeration.
- The resulting USB Ethernet/RNDIS Gadget is Ethernet 2, interface index 18.
  Only this adapter was assigned `192.168.3.20/24`, without a default gateway.
  PLC `192.168.3.10` responds to ICMP and TCP port 11740; the TCP check explicitly
  bound its source to `192.168.3.20`. Office Ethernet and VPN settings were kept.
- Installed TM751 description: type 4102, ID `1631 0051`, version 3.5.15.20.
  This is local device-description evidence, not yet a measured PLC identity.
- Added optional, explicit-address gateway listing and targeted lookup. Eight
  discovery guard tests pass. Native gateway listing passed on the updated IDE.
  No gateway was initially configured. The installed TCP/IP driver has GUID
  `1a8061b1-cbef-4374-910e-34758a8b914c`, parameter 0 IP-Address and parameter 1
  Port. An explicitly created local gateway at `127.0.0.1:1217` resolved the PLC
  to `0D02.1000.2DDC.C0A8.030A`. Targeted lookup did not populate the scan cache,
  so no PLC model/firmware is claimed from that result.
- The source fixture's root is named PLCWinNT but identifies as TM750,
  `4102 / 1631 0050 / 3.5.15.20`. A separate copy was converted through
  `device.update` to TM751 and saved successfully. Renaming its Application
  hung in this installation; the timed-out owned IDE was terminated. Keep the
  standard application name and never replay this rename automatically.

## Acceptance sequence

1. Finish the official Studio installation and update; record executable,
   profile, core/ScriptEngine versions, installed TM751 description and USB
   adapter details. Do not confuse device-description versions with PLC firmware.
2. Establish direct USB communication using the RNDIS interface. Inspect the
   actual local IP and PLC identity before any application download.
3. Probe the installed gateway/device/online APIs, then implement separate
   physical commissioning operations. Keep existing simulation tools restricted
   to positively verified simulation.
4. Create an isolated TM751 test project with internal variables only and no
   output mapping. Compile a copy and retain a reproducible source manifest.
5. Verify physical identity, explicit application download, RUN/STOP, fresh
   reads, a normal test-variable write, disconnect and reconnect. Never report
   a simulated result as a physical test.
6. Validate debugger/trace operations against the installed API and actual TM751
   before advertising them for physical targets. Retain unsupported cases as
   explicit limitations with the observed error.
7. Record source/build/target identities and actual outcomes; update tool
   descriptions, tests and skill documentation together. Preserve original
   source projects and existing Codex MCP registrations.

## Integration constraints

Use an explicit physical target binding that expires when project, device,
gateway/address or connection generation changes. Discover the requested USB
target by its address; do not select the first response from a broad network scan.
Separate connection from download and download from RUN. Do not automatically
create boot applications, update firmware, reset a device or apply forces.
Connection loss must report an uncertain mutation without automatically replaying
it. Physical disconnect/session shutdown must not silently inherit the simulation
cleanup policy of stopping a running application.

The user confirmed FL2002 (digital outputs) and FL1001 (digital inputs), and that
only power and USB are connected: there are no output loads. Physical I/O
acceptance still requires the corresponding bench wiring and observed signals.

## Primary API references

- https://content.helpme-codesys.com/en/ScriptingEngine/ScriptOnline.html
- https://content.helpme-codesys.com/en/ScriptingEngine/ScriptDeviceObject.html
- https://www.invt.com/software-download

## Completed physical acceptance, 2026-10-22

Studio 3.0.1.8 was used through the MCP stdio client against the powered TM751-C,
over USB/RNDIS at 192.168.3.10. Connected GetTargetIdent returned type 4102,
ID `1631 0051`, compatibility version 3.5.15.20, model `TM751-C`, vendor
`Shenzhen INVT Electric Co., Ltd.`, reported runtime version 3.5.15.20.
No system firmware update was performed.

The isolated application contains only Counter (UDINT), TestInput/TestOutput
(DINT). MainTask runs every 100 ms. Source and project edits used ScriptEngine.
The fixture root retains its original name PLCWinNT, but its measured project
device identity is TM751. Application keeps the standard vendor-required name.

End-to-end MCP acceptance passed:

- Actual physical binding matched the selected TM751 description.
- Stale physical token and simulation login against a physical device were
  refused before runtime changes.
- Full download used Never and did not delete foreign applications. Both
  automatic boot creation options were disabled and verified. The application
  remained STOP after download; operating state was program_loaded, without
  bootproject_valid.
- Explicit RUN succeeded; two fresh counter reads increased.
- A normal TestInput write to 21 returned DINT#21. The running program returned
  TestOutput DINT#42. No forcing was used.
- Logout followed by Keep login preserved RUN. Each login/logout returned a
  fresh physical target token.
- Explicit STOP succeeded. Two fresh counter reads stayed UDINT#81.
- Final logout and owned Studio shutdown completed gracefully. The PLC was
  left STOP, with the volatile bench application loaded. The input test project
  hash was unchanged: 5be87fc6b96880d6283b8d15fa9119f09e574febab4de782c66b1cf9495056e1.

Local full evidence is `C:\Codex\INVTMatic\work\plc-live.json`, with per-command
reports retained in the owned session
`C:\Codex\INVTMatic\.invt\persistent\f8ed98b2-14aa-4de1-a5c8-8554a2991004`.
An earlier harness run misparsed typed values such as DINT#42; the native values
were correct. Its report is retained separately as plc-live-first-run.json.
The corrected harness validates integer prefixes and rejects invalid/NaN values.

Host/guard tests: 12 host, 35 original Python guards, 8 discovery guards and
15 physical guards passed (70 total). Physical breakpoint/step/frame/trace and
FL2002/FL1001 wired I/O remain explicitly outside this acceptance.
