// Native finite recursive METHOD fixture. Repeated POU frames must be explicit refusals.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const {IpcClient,DEFAULT_IPC_CONFIG}=require('../dist/ipc');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..'),report={steps:[]};
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],stderr:'pipe'}),client=new Client({name:'recursive-frame-acceptance',version:'1'});
let req,managed=false;
async function call(name,args={},expected=true){const w=await client.callTool({name,arguments:args},undefined,{timeout:180000}),r=JSON.parse(w.content.find(c=>c.type==='text').text);report.steps.push({name,result:r,isError:!!w.isError});assert.equal(!!w.isError,!expected,JSON.stringify(r));console.log(name,w.isError?'REFUSED':'OK');return r;}
(async()=>{try{
 await client.connect(transport);const started=await call('invt_session_start');managed=true;await call('invt_open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
 const i=await call('invt_inspect'),app=i.objects.find(o=>o.application).guid,target=(await call('invt_get_runtime_target',{application_guid:app})).target;
 const mode=await call('invt_set_simulation_mode',{application_guid:app,target_id:target.target_id,enabled:true});req={application_guid:app,target_id:mode.target.target_id};
 fs.copyFileSync(path.join(__dirname,'probes/invt_advanced_fixtures.py'),path.join(started.directory,'invt_advanced_fixtures.py'));
 const p=Buffer.from(JSON.stringify(req)).toString('base64'),ipc=new IpcClient({...DEFAULT_IPC_CONFIG,baseDir:started.directory});const wire=await ipc.sendCommand(`import json,base64\nimport invt_advanced_fixtures as f\nr=f.run(json.loads(base64.b64decode('${p}')),'recursive_fixture')\nprint('FIXTURE:'+json.dumps(r))\n`,15000);assert.ok(wire.success,JSON.stringify(wire));const fixture=JSON.parse(wire.output.split(/\r?\n/).find(s=>s.startsWith('FIXTURE:')).slice(8));
 await call('invt_build',{application_guid:app});const task=(await call('invt_inspect_tasks',{application_guid:app})).tasks.find(t=>t.name==='MainTask');
 await call('invt_download_application',req);const debug={...req,debug_id:(await call('invt_prepare_debug',req)).debug_id};
 await call('invt_set_breakpoint',{...debug,object_guid:fixture.method_guid,line:5,task_guid:task.guid});await call('invt_debug_continue',debug);const state=(await call('invt_get_debug_state',debug)).state;
 const frames=state.frames.filter(f=>f.location?.object_guid===fixture.method_guid);assert.ok(frames.length>=3,JSON.stringify(state));assert.ok(frames.every(f=>f.locals_readable===false&&f.locals_reason==='ambiguous_repeated_pou'&&f.frame_id===undefined));
 report.recursive_frames=frames.length;report.refusal_reason='ambiguous_repeated_pou';
 await call('invt_read_frame_variables',{...debug,frame_id:fixture.method_guid,variables:['iDepth']},false);
 await call('invt_stop_application',{...req,halt_behavior:'finish_cycle'});await call('invt_disconnect_runtime',req);const closed=await call('invt_close_project');assert.equal(closed.source_unchanged,true);report.shutdown=await call('invt_session_stop');assert.equal(report.shutdown.graceful,true);managed=false;report.passed=true;
}catch(e){report.passed=false;report.error=String(e);console.error(String(e));process.exitCode=1;}finally{if(managed){if(req)await call('invt_stop_application',{...req,halt_behavior:'finish_cycle'}).catch(()=>{});report.shutdown=await call('invt_session_stop').catch(e=>({error:String(e)}));}fs.writeFileSync(path.join(workspace,'analysis/recursive-frames-result.json'),JSON.stringify(report,null,2));await client.close();}})();
