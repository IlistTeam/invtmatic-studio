// Public v0.6 tools only for production operations; fixed probes create foreign fixtures.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const {IpcClient,DEFAULT_IPC_CONFIG}=require('../dist/ipc');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..'),report={steps:[]};
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],stderr:'pipe'});
const client=new Client({name:'advanced-public-acceptance',version:'1'});let req,directory,managed=false;
const save=()=>fs.writeFileSync(path.join(workspace,'analysis/advanced-live-result.json'),JSON.stringify(report,null,2));
async function call(name,args={},expected=true){const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});const r=JSON.parse(wire.content.find(c=>c.type==='text').text);report.steps.push({name,args,result:r,isError:!!wire.isError});save();console.log(name,wire.isError?'EXPECTED/ERROR':'OK');assert.equal(!!wire.isError,!expected,JSON.stringify(r));return r;}
const valueRows=r=>r.values.map(v=>{assert.equal(v.ok,true,JSON.stringify(v));assert.equal(v.state,'Good');return Number(v.value);});
async function fixture(stage,args=req){fs.copyFileSync(path.join(__dirname,'probes/invt_advanced_fixtures.py'),path.join(directory,'invt_advanced_fixtures.py'));const payload=Buffer.from(JSON.stringify(args)).toString('base64');const ipc=new IpcClient({...DEFAULT_IPC_CONFIG,baseDir:directory});const w=await ipc.sendCommand(`import json,base64\nimport invt_advanced_fixtures as f\nr=f.run(json.loads(base64.b64decode('${payload}')),'${stage}')\nprint('FIXTURE:'+json.dumps(r,ensure_ascii=True))\n`,15000);assert.ok(w.success,JSON.stringify(w));const r=JSON.parse(w.output.split(/\r?\n/).find(l=>l.startsWith('FIXTURE:')).slice(8));report.steps.push({fixture:stage,result:r});save();return r;}
(async()=>{try{
 await client.connect(transport);report.tools=(await client.listTools()).tools.map(t=>t.name);assert.equal(report.tools.length,44);report.server=client.getServerVersion();assert.equal(report.server.version,'0.6.0');
 directory=(await call('invt_session_start')).directory;managed=true;await call('invt_open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
 const inspected=await call('invt_inspect'),app=inspected.objects.find(o=>o.application).guid,pou=inspected.objects.find(o=>o.name==='PLC_PRG'&&o.implementation!==undefined);
 await call('invt_create_pou',{application_guid:app,name:'F_Inner',pou_type:'function',return_type:'DINT',declaration:'FUNCTION F_Inner : DINT\nVAR_INPUT iValue : DINT; END_VAR\nVAR nInnerLocal : DINT; END_VAR',implementation:'nInnerLocal := iValue + 1000;\nF_Inner := nInnerLocal * 2;'});
 await call('invt_create_pou',{application_guid:app,name:'F_Outer',pou_type:'function',return_type:'DINT',declaration:'FUNCTION F_Outer : DINT\nVAR_INPUT iValue : DINT; END_VAR\nVAR nOuterLocal : DINT; nIntermediate : DINT; END_VAR',implementation:'nOuterLocal := iValue + 100;\nnIntermediate := F_Inner(nOuterLocal);\nF_Outer := nIntermediate + 1;'});
 await call('invt_patch_st',{application_guid:app,object_guid:pou.guid,declaration:'PROGRAM PLC_PRG\nVAR nCycle : UDINT; nResult : DINT; END_VAR',implementation:'nCycle := nCycle + 1;\nnResult := F_Outer(7);'});
 const task=(await call('invt_inspect_tasks',{application_guid:app})).tasks.find(t=>t.name==='MainTask');
 const target=(await call('invt_get_runtime_target',{application_guid:app})).target,mode=await call('invt_set_simulation_mode',{application_guid:app,target_id:target.target_id,enabled:true});req={application_guid:app,target_id:mode.target.target_id};
 await call('invt_create_trace',{...req,task_guid:task.guid,variables:['PLC_PRG.nCycle','plc_prg.NCycle']},false);
 const trace=await call('invt_create_trace',{...req,name:'OwnedTrace',task_guid:task.guid,variables:['PLC_PRG.nCycle','PLC_PRG.nResult']});
 await call('invt_create_trace',{...req,name:'OwnedTrace',task_guid:task.guid,variables:['PLC_PRG.nCycle']},false);
 assert.equal((await call('invt_list_traces',req)).traces.length,1);
 await call('invt_delete_trace',{...req,trace_id:'00000000-0000-0000-0000-000000000001'},false);
 let foreign;if(process.argv.includes('--extended'))foreign=await fixture('foreign_create');
 await call('invt_download_application',req);let debug={...req,debug_id:(await call('invt_prepare_debug',req)).debug_id};
 await call('invt_capture_trace',{...debug,trace_id:trace.trace_id,duration_ms:1000},false);
 await call('invt_start_application',req);
 if(foreign)await fixture('foreign_start');
 await call('invt_capture_trace',{...debug,debug_id:'00000000-0000-0000-0000-000000000001',trace_id:trace.trace_id,duration_ms:1000},false);
 await call('invt_capture_trace',{...debug,trace_id:trace.trace_id,duration_ms:5000},false);
 const capture=await call('invt_capture_trace',{...debug,trace_id:trace.trace_id,duration_ms:1000});assert.equal(capture.packet_cleanup_confirmed,true);assert.equal(capture.overflow,false);assert.equal(capture.timestamp_unit,'ms');
 const count=capture.signals.find(s=>s.variable==='PLC_PRG.nCycle').samples;assert.ok(count.length>=10);for(let i=1;i<count.length;i++)assert.equal(Number(count[i].value),Number(count[i-1].value)+1);assert.ok(capture.signals.find(s=>s.variable==='PLC_PRG.nResult').samples.every(s=>Number(s.value)===2215));
 await call('invt_capture_trace',{...debug,trace_id:trace.trace_id,duration_ms:1000});assert.equal((await call('invt_list_traces',req)).traces[0].packet_owned,false);
 if(foreign){assert.equal((await fixture('foreign_status')).running,true);assert.equal((await fixture('foreign_status')).online,true);await call('invt_delete_trace',{...req,trace_id:foreign.guid},false);assert.equal((await fixture('foreign_clear')).online,false);}
 if(process.argv.includes('--extended')){
  await fixture('arm_capture_logout');const lost=await call('invt_capture_trace',{...debug,trace_id:trace.trace_id,duration_ms:1000},false);
  assert.equal(lost.packet_cleanup_confirmed,false);assert.equal((await call('invt_list_traces',req)).traces[0].packet_owned,true);
  await call('invt_get_runtime_state',req);await call('invt_connect_runtime',req);await call('invt_stop_application',req);
  const recovered=await call('invt_delete_trace',{...req,trace_id:trace.trace_id},false);assert.equal(recovered.reason,'disconnect_required_for_config_delete');
  await call('invt_disconnect_runtime',req);await call('invt_connect_runtime',req);debug={...req,debug_id:(await call('invt_prepare_debug',req)).debug_id};
  assert.equal((await call('invt_list_traces',req)).traces[0].packet_owned,false);
 }
 await call('invt_stop_application',req);
 const objs=(await call('invt_inspect')).objects,inner=objs.find(o=>o.name==='F_Inner'&&o.implementation!==undefined);
 await call('invt_set_breakpoint',{...debug,object_guid:inner.guid,line:2,task_guid:task.guid});await call('invt_debug_continue',debug);
 let state=(await call('invt_get_debug_state',debug)).state;assert.equal(state.application_state,'halt_on_bp');
 const fi=state.frames.find(f=>f.location?.pou?.toUpperCase()==='F_INNER'),fo=state.frames.find(f=>f.location?.pou?.toUpperCase()==='F_OUTER');assert.ok(fi.frame_id&&fo.frame_id);
 assert.deepEqual(valueRows(await call('invt_read_frame_variables',{...debug,frame_id:fi.frame_id,variables:['iValue','nInnerLocal']})),[107,1107]);
 assert.deepEqual(valueRows(await call('invt_read_frame_variables',{...debug,frame_id:fo.frame_id,variables:['iValue','nOuterLocal']})),[7,107]);
 if(process.argv.includes('--extended')){await fixture('native_continue',debug);await call('invt_read_frame_variables',{...debug,frame_id:fo.frame_id,variables:['iValue']},false);state=(await call('invt_get_debug_state',debug)).state;}
 await call('invt_read_frame_variables',{...debug,frame_id:fi.frame_id,variables:['missingLocal']},false);
 await call('invt_read_frame_variables',{...debug,frame_id:'00000000-0000-0000-0000-000000000001',variables:['iValue']},false);
 await call('invt_debug_step',{...debug,kind:'over'});await call('invt_read_frame_variables',{...debug,frame_id:fo.frame_id,variables:['iValue']},false);
 state=(await call('invt_debug_step',{...debug,kind:'over'})).state;const fresh=state.frames.find(f=>f.location?.pou?.toUpperCase()==='F_OUTER');assert.ok(fresh.frame_id);
 assert.deepEqual(valueRows(await call('invt_read_frame_variables',{...debug,frame_id:fresh.frame_id,variables:['iValue','nOuterLocal']})),[7,107]);
 await call('invt_debug_continue',debug);await call('invt_read_frame_variables',{...debug,frame_id:fresh.frame_id,variables:['iValue']},false);
 await call('invt_stop_application',{...req,halt_behavior:'finish_cycle'});const offlineRequired=await call('invt_delete_trace',{...req,trace_id:trace.trace_id},false);assert.equal(offlineRequired.reason,'disconnect_required_for_config_delete');
 await call('invt_disconnect_runtime',req);await call('invt_delete_trace',{...req,trace_id:trace.trace_id});assert.equal((await call('invt_list_traces',req)).traces.length,0);
 const closed=await call('invt_close_project');assert.equal(closed.source_unchanged,true);report.shutdown=await call('invt_session_stop');assert.equal(report.shutdown.graceful,true);managed=false;report.passed=true;
}catch(e){report.passed=false;report.error=String(e);console.error(String(e));process.exitCode=1;}finally{if(managed){if(req)await call('invt_stop_application',{...req,halt_behavior:'finish_cycle'}).catch(()=>{});report.shutdown=await call('invt_session_stop').catch(e=>({error:String(e)}));}save();await client.close();}})();
