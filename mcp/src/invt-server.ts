/** INVT-only entrypoint. Fixed project and verified-simulation operations. */
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Command } from 'commander';
import { z } from 'zod';
import { InvtSession } from './invt-session';

const options = new Command().requiredOption('--workspace <path>')
  .option('--exe <path>').option('--profile <name>')
  .option('--physical-address <ipv4>', 'Enable read-only discovery of this explicit private PLC address')
  .option('--physical-runtime', 'Additionally expose explicit physical PLC binding and application operations')
  .option('--timeout-ms <number>', 'Command deadline', '60000').parse().opts();
const session = new InvtSession(options.workspace, options.exe, options.profile, Number(options.timeoutMs), options.physicalAddress, !!options.physicalRuntime);
const server = new McpServer({name:'invtmatic-persistent', version:'0.7.1'});
// SDK's complex overload inference is also avoided by the upstream server.
const api = server as any;
const guid = z.string().uuid();
const application = {application_guid:guid.optional()};
const runtime = {application_guid:guid, target_id:guid};
const variable = z.string().max(512).regex(/^[A-Za-z_][A-Za-z0-9_]*(\[[0-9]+\])*(\.[A-Za-z_][A-Za-z0-9_]*(\[[0-9]+\])*)*$/).refine(v=>!/\s/.test(v));
const variables = z.array(variable).min(1).max(32);
const creation = {name:z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/).max(128).refine(v=>!/\s/.test(v)),
  declaration:z.string().min(1).max(1000000), ...application};
const typeName = z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$/).max(256).refine(v=>!/\s/.test(v));
const milliseconds = z.number().int().min(1).max(60000);
const priority = z.number().int().min(0).max(31);
const watchdog = z.object({enabled:z.boolean(), time_ms:milliseconds.optional(),
  sensitivity:z.number().int().min(1).max(1000).optional()}).strict()
  .refine(v=>!v.enabled || (v.time_ms!==undefined && v.sensitivity!==undefined),
    'Enabling watchdog requires time_ms and sensitivity');
const taskSettings = z.object({interval_ms:milliseconds.optional(),priority:priority.optional(),
  watchdog:watchdog.optional()}).strict().refine(v=>Object.keys(v).length>0,'Supply at least one task setting');
const reply = async (operation:()=>Promise<any>|any) => {
  try {
    const result = await operation();
    return {content:[{type:'text',text:JSON.stringify(result)}], isError:result.ok===false};
  } catch(error) {
    return {content:[{type:'text',text:JSON.stringify({ok:false,error:String(error),session:session.status()})}],isError:true};
  }
};
api.tool('invt_session_start', 'Start one owned UI-initialized Studio and verify primary-thread IPC.', {}, ()=>reply(()=>session.start()));
api.tool('invt_session_status', 'Read persistent session status without touching Studio.', {}, ()=>reply(()=>session.status()));
if (options.physicalAddress) {
  api.tool('invt_get_plc_gateways', 'Read configured Studio gateways. Does not scan, log in, download or start a PLC.', {},
    ()=>reply(()=>session.call({operation:'plc_gateways'})));
  api.tool('invt_find_plc', 'Resolve only the explicitly configured physical PLC IP through the selected gateway. Read cached target identity if available; no broad scan, login or runtime change.',
    {gateway_guid:guid}, (args:any)=>reply(()=>session.call({operation:'plc_find',...args})));
}
if (options.physicalRuntime) {
  api.tool('invt_bind_plc','Bind the open physical-mode project to the explicit PLC IP and selected gateway. Connect only to read actual identity and require a matching device ID; no application login or download.',
    {...application,application_guid:guid,gateway_guid:guid,expected_device_id:z.string().min(1).max(128)},
    (args:any)=>reply(()=>session.call({operation:'plc_bind',...args})));
  for (const [name,operation,description] of [
    ['invt_get_plc_target','plc_target','Read the current explicit physical target binding.'],
    ['invt_connect_plc','plc_connect','Explicit physical login with Keep: no download or update. Returns a fresh target_id.'],
    ['invt_disconnect_plc','plc_disconnect','Logout the owned physical application without stopping it. Returns a fresh target_id.'],
    ['invt_get_plc_state','plc_state','Read physical connection and execution state without auto-login.'],
    ['invt_download_plc','plc_download','Fresh rebuild and explicit full download to the bound physical PLC. Disable automatic boot creation, preserve foreign applications and do not start. Returns a fresh target_id.'],
    ['invt_start_plc','plc_start','Explicit RUN on the owned physical connection; verify read-back.'],
    ['invt_stop_plc','plc_stop','Explicit STOP on the owned physical connection; reject unverified HALT recovery.']
  ]) api.tool(name,description,runtime,(args:any)=>reply(()=>session.call({operation,...args})));
  api.tool('invt_read_plc_variables','Read fresh values from the owned physical PLC connection; no automatic login.',
    {...runtime,variables},(args:any)=>reply(()=>session.call({operation:'plc_read',...args})));
  api.tool('invt_write_plc_variable','Normal write on the owned physical connection, with fresh before/after values. No forcing.',
    {...runtime,variable,value:z.string().min(1).max(4096)},(args:any)=>reply(()=>session.call({operation:'plc_write',...args})));
}
api.tool('invt_open_copy', 'Open a fresh copy of a workspace .project. Source is preserved.', {
  project:z.string().min(1), expected_sha256:z.string().regex(/^[a-f0-9]{64}$/).optional()
}, (args:any)=>reply(()=>session.call({operation:'open_copy',...args})));
api.tool('invt_inspect', 'Read tree, object GUIDs, ST and library resolutions in the open copy.', {}, ()=>reply(()=>session.call({operation:'inspect'})));
api.tool('invt_inspect_tasks', 'Read task configuration GUIDs, task kinds, intervals, priorities, watchdogs and ordered program calls.', application,
  (args:any)=>reply(()=>session.call({operation:'inspect_tasks',...args})));
api.tool('invt_create_task', 'Create a cyclic task in an existing task configuration, verify settings, save and rebuild.', {
  name:creation.name, interval_ms:milliseconds, priority, watchdog:watchdog.optional(),
  task_configuration_guid:guid.optional(), ...application
}, (args:any)=>reply(()=>session.call({operation:'create_task',...args})));
api.tool('invt_configure_task', 'Update supplied cyclic-task period, priority or watchdog settings; preserve other settings and calls, save and rebuild.', {
  task_guid:guid, settings:taskSettings, ...application
}, (args:any)=>reply(()=>session.call({operation:'configure_task',...args})));
api.tool('invt_bind_program', 'Insert a PROGRAM POU into the ordered calls of a task, verify, save and rebuild. Reject duplicate/cross-task calls unless explicitly allowed.', {
  task_guid:guid, program_guid:guid, index:z.number().int().min(0).optional(),
  comment:z.string().max(2048).optional(), allow_multi_task:z.boolean().optional(), ...application
}, (args:any)=>reply(()=>session.call({operation:'bind_program',...args})));
api.tool('invt_build', 'Rebuild the open copy with fresh compiler diagnostics and save it.', application,
  (args:any)=>reply(()=>session.call({operation:'build',...args})));
api.tool('invt_patch_st', 'Replace supplied ST sections, verify read-back, save and rebuild the same session copy.', {
  object_guid:guid, declaration:z.string().max(1000000).optional(), implementation:z.string().max(1000000).optional(), ...application
}, (args:any)=>reply(()=>{
  if(args.declaration===undefined && args.implementation===undefined)throw new Error('Supply declaration and/or implementation');
  return session.call({operation:'patch_st',...args});
}));
api.tool('invt_export_pou', 'Export a textual object as native export and PLCopen XML.', {object_guid:guid},
  (args:any)=>reply(()=>session.call({operation:'export_pou',...args})));
api.tool('invt_create_pou', 'Create ST program/function block/function in the selected application, verify text, save and rebuild. A compiler failure preserves the new object GUID.', {
  ...creation, pou_type:z.enum(['program','function_block','function']),
  return_type:typeName.optional(), implementation:z.string().max(1000000).optional()
}, (args:any)=>reply(()=>session.call({operation:'create_pou',...args})));
api.tool('invt_create_gvl', 'Create a GVL in the selected application, verify the complete declaration, save and rebuild.', creation,
  (args:any)=>reply(()=>session.call({operation:'create_gvl',...args})));
api.tool('invt_create_dut', 'Create a structure/enum/alias/union in the selected application, verify text, save and rebuild.', {
  ...creation, dut_type:z.enum(['structure','enumeration','alias','union']), base_type:typeName.optional()
}, (args:any)=>reply(()=>session.call({operation:'create_dut',...args})));
for (const [name,operation,description] of [
  ['invt_get_debug_capabilities','debug_capabilities','Inspect installed simulation APIs and limitations. Physical runtime operations are disabled.'],
  ['invt_get_runtime_target','runtime_target','Read owning device, project/application identity and actual simulation getter; obtain a target token.']
]) api.tool(name,description,application,(args:any)=>reply(()=>session.call({operation,...args})));
api.tool('invt_set_simulation_mode','Set the owning device simulation flag while disconnected, save and verify actual getter. Disabling never connects to a PLC.',
  {...runtime,enabled:z.boolean()},(args:any)=>reply(()=>session.call({operation:'simulation_mode',...args})));
for (const [name,operation,description] of [
  ['invt_connect_runtime','connect_runtime','Attach to verified simulation with Keep: no download, update, start or boot creation.'],
  ['invt_disconnect_runtime','disconnect_runtime','Clean only session-owned forces, stop and logout the owned simulation connection.'],
  ['invt_get_runtime_state','runtime_state','Read fresh simulation connection/execution/exception state without auto-login.'],
  ['invt_download_application','download_application','Fresh build and explicit full download to verified simulation using Never; no boot or automatic start. Disconnect first.'],
  ['invt_start_application','start_application','Explicit RUN in the owned, verified simulation connection; verify state.'],
  ['invt_list_forces','list_forces','List current simulation forces and distinguish those created by this MCP session.']
]) api.tool(name,description,runtime,(args:any)=>reply(()=>session.call({operation,...args})));
api.tool('invt_stop_application','Explicit STOP in owned simulation. From HALT choose finish_cycle (remaining statements execute) or abort_cycle (can require recovery); no implicit choice.',
  {...runtime,halt_behavior:z.enum(['finish_cycle','abort_cycle']).optional()},
  (args:any)=>reply(()=>session.call({operation:'stop_application',...args})));
api.tool('invt_read_variables','Read one or several simulation variable paths with individual timestamps/errors; sequential, not atomic.',
  {...runtime,variables},(args:any)=>reply(()=>session.call({operation:'read_variables',...args})));
api.tool('invt_monitor_variables','Bounded host polling of simulation variables; stop on error, no atomicity or scan-timing guarantee.',
  {...runtime,variables,duration_ms:z.number().int().min(100).max(10000),interval_ms:z.number().int().min(50).max(5000)},
  (args:any)=>reply(()=>session.call({operation:'monitor_variables',...args})));
for (const [name,operation,description] of [
  ['invt_write_variable','write_variable','One-time simulation write via write_prepared_values, without force. Refuses foreign prepared/forced values.'],
  ['invt_force_variable','force_variable','Force a simulation variable separately from ordinary write; track ownership for selective cleanup.']
]) api.tool(name,description,{...runtime,variable,value:z.string().min(1).max(4096)},
  (args:any)=>reply(()=>session.call({operation,...args})));
api.tool('invt_unforce_variable','Selectively release a force created by this MCP session; never unforce all or foreign forces.',
  {...runtime,variable},(args:any)=>reply(()=>session.call({operation:'unforce_variable',...args})));
api.tool('invt_prepare_debug','Prepare a version-gated debugger generation for the current owned full download in verified simulation; no auto-download/start.',
  runtime,(args:any)=>reply(()=>session.call({operation:'prepare_debug',...args})));
const debugging = {...runtime,debug_id:guid};
api.tool('invt_get_debug_locations','Read exact executable ST implementation rows/columns from the current compiled source. Lines and columns are 1-based; no snapping.',
  {...debugging,object_guid:guid},(args:any)=>reply(()=>session.call({operation:'debug_locations',...args})));
api.tool('invt_set_breakpoint','Set one owned unconditional breakpoint at an exact ST row/column for the selected task in simulation STOP/HALT. Preserve existing points.',
  {...debugging,object_guid:guid,line:z.number().int().min(1).max(1000000),column:z.number().int().min(1).max(32767).optional(),task_guid:guid},
  (args:any)=>reply(()=>session.call({operation:'set_breakpoint',...args})));
api.tool('invt_list_breakpoints','Read application breakpoints and distinguish session-owned points; no modification.',
  debugging,(args:any)=>reply(()=>session.call({operation:'list_breakpoints',...args})));
api.tool('invt_remove_breakpoint','Remove only a breakpoint_id created by this MCP session. No clear-all or foreign removal.',
  {...debugging,breakpoint_id:guid},(args:any)=>reply(()=>session.call({operation:'remove_breakpoint',...args})));
api.tool('invt_get_debug_state','Read fresh HALT/RUN/STOP, source and stack. Mapped unique frames include expiring frame_id values for read-only locals.',
  debugging,(args:any)=>reply(()=>session.call({operation:'debug_state',...args})));
api.tool('invt_read_frame_variables','Read named values in a current HALT frame; frame_id expires on step/resume/source/session change. Reject repeated POU frames; release only own watches.',
  {...debugging,frame_id:guid,variables:z.array(variable).min(1).max(8)},
  (args:any)=>reply(()=>session.call({operation:'read_frame_variables',...args})));
api.tool('invt_create_trace','Create an owned trace configuration offline in verified simulation. No runtime download/start, no auto_start. Choose cyclic task and distinct application variable paths.',
  {...runtime,name:z.string().regex(/^[A-Za-z_][A-Za-z0-9_]{0,63}$/).optional(),task_guid:guid,
   variables:z.array(variable).min(1).max(8),every_n_cycles:z.number().int().min(1).max(1000).optional()},
  (args:any)=>reply(()=>session.call({operation:'create_trace',...args})));
api.tool('invt_capture_trace','Bounded runtime trace in explicit simulation RUN. Current debug_id required. Export samples/CSV, report overflow, delete only own runtime packet; no application auto-start/resume.',
  {...debugging,trace_id:guid,duration_ms:z.number().int().min(100).max(10000)},
  (args:any)=>reply(()=>session.call({operation:'capture_trace',...args})));
api.tool('invt_list_traces','List only trace configurations/packet ownership created by this session in the selected simulation application.',
  runtime,(args:any)=>reply(()=>session.call({operation:'list_traces',...args})));
api.tool('invt_delete_trace','Delete only a session-owned trace configuration after selective packet cleanup; refuse foreign packet replacement/adoption.',
  {...runtime,trace_id:guid},(args:any)=>reply(()=>session.call({operation:'delete_trace',...args})));
api.tool('invt_debug_continue','Explicitly continue from STOP/HALT using the verified Core API; read back RUN/HALT/STOP. Never implicitly resume during cleanup.',
  debugging,(args:any)=>reply(()=>session.call({operation:'debug_continue',...args})));
api.tool('invt_debug_step','Execute one verified step into/over/out from HALT with fixed command GUID and enabled-state checks; no arbitrary command.',
  {...debugging,kind:z.enum(['into','over','out'])},(args:any)=>reply(()=>session.call({operation:'debug_step',...args})));
api.tool('invt_close_project', 'Save and close this session project; keep Studio and IPC running.', {},
  ()=>reply(()=>session.call({operation:'close_project'})));
api.tool('invt_session_stop', 'Save the owned project and close only the owned Studio process.', {}, ()=>reply(()=>session.stop()));

let stopping = false;
async function shutdown() {
  if(stopping)return;
  stopping=true;
  try { await session.stop(true); } catch(e) { console.error(String(e)); }
  process.exit(0);
}
process.stdin.once('end',shutdown);
process.once('SIGINT',shutdown);
process.once('SIGTERM',shutdown);
server.connect(new StdioServerTransport()).catch(e=>{console.error(e);process.exitCode=1;void shutdown();});
