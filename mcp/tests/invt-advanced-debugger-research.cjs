// Fixed research fixture via real stdio MCP; never a public execute-script tool.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const {IpcClient,DEFAULT_IPC_CONFIG}=require('../dist/ipc');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..'),report={steps:[]};
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],stderr:'pipe'});
const client=new Client({name:'advanced-debugger-research',version:'1'});
let directory,req,managed=false,quarantined=false;
const save=()=>fs.writeFileSync(path.join(workspace,'analysis/advanced-debugger-research.json'),JSON.stringify(report,null,2));
async function call(name,args={}){const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});const r=JSON.parse(wire.content.find(c=>c.type==='text').text);report.steps.push({name,result:r});save();assert.notEqual(wire.isError,true,JSON.stringify(r));console.log(name,'OK');return r;}
async function probe(stage,args=req){fs.copyFileSync(path.join(__dirname,'probes/invt_advanced_debugger_probe.py'),path.join(directory,'invt_advanced_debugger_probe.py'));const ipc=new IpcClient({...DEFAULT_IPC_CONFIG,baseDir:directory});const payload=Buffer.from(JSON.stringify(args)).toString('base64');const w=await ipc.sendCommand(`import json,base64\nimport invt_advanced_debugger_probe as p\nreload(p)\nr=p.run(json.loads(base64.b64decode('${payload}')),'${stage}')\nprint('ADVANCED:'+json.dumps(r,ensure_ascii=True))\n`,20000);if(!w.success&&/timed out|timeout/i.test(w.error||'')){quarantined=true;report.quarantined=true;}assert.ok(w.success,JSON.stringify(w));const r=JSON.parse(w.output.split(/\r?\n/).find(l=>l.startsWith('ADVANCED:')).slice(9));report[stage]=r;report.probes=(report.probes||[]).concat([{stage,result:r}]);save();console.log(stage,r.error?'REPORTED LIMIT':'OK');return r;}
function values(r){return r.resolved_variables.map(v=>{assert.equal(v.state,'Good',JSON.stringify(v));assert.equal(v.error,undefined);assert.equal(v.stack_relative,true);return [v.pou.toUpperCase(),v.expression,Number(v.value)];});}
function verifyTrace(capture){
 assert.equal(capture.error,undefined,JSON.stringify(capture));assert.ok(capture.exported);
 assert.equal(capture.phases.find(p=>p.phase==='start').running,true);assert.equal(capture.phases.find(p=>p.phase==='stop').running,false);
 const data={};let current;
 for(const line of fs.readFileSync(capture.export_path,'utf8').split(/\r?\n/)){const f=line.split(';').map(v=>v.trim());if(/^\d+\.Variable$/.test(f[0])){current=f[1];data[current]=[];}else if(f[0]===''&&f.length===3&&current)data[current].push([Number(f[1]),Number(f[2])]);}
 const cycles=data['PLC_PRG.nCycle'],results=data['PLC_PRG.nResult'];assert.ok(cycles.length>=10);assert.equal(results.length,cycles.length);
 for(let i=1;i<cycles.length;i++){assert.ok(cycles[i][0]>cycles[i-1][0]);assert.equal(cycles[i][1],cycles[i-1][1]+1);}
 assert.ok(results.every(s=>s[1]===2215));report.trace_assertions={samples:cycles.length,cycle_increments:1,result:2215,start_stop_confirmed:true};
}
(async()=>{try{
 await client.connect(transport);report.tool_count=(await client.listTools()).tools.length;assert.equal(report.tool_count,44);report.server=client.getServerVersion();
 const started=await call('invt_session_start');managed=true;directory=started.directory;fs.copyFileSync(path.join(__dirname,'probes/invt_advanced_debugger_probe.py'),path.join(directory,'invt_advanced_debugger_probe.py'));
 await call('invt_open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
 const inspected=await call('invt_inspect'),app=inspected.objects.find(o=>o.application).guid,pou=inspected.objects.find(o=>o.name==='PLC_PRG'&&o.implementation!==undefined);
 const inner=await call('invt_create_pou',{application_guid:app,name:'F_Inner',pou_type:'function',return_type:'DINT',declaration:'FUNCTION F_Inner : DINT\nVAR_INPUT iValue : DINT; END_VAR\nVAR nInnerLocal : DINT; END_VAR',implementation:'nInnerLocal := iValue + 1000;\nF_Inner := nInnerLocal * 2;'});
 await call('invt_create_pou',{application_guid:app,name:'F_Outer',pou_type:'function',return_type:'DINT',declaration:'FUNCTION F_Outer : DINT\nVAR_INPUT iValue : DINT; END_VAR\nVAR nOuterLocal : DINT; nIntermediate : DINT; END_VAR',implementation:'nOuterLocal := iValue + 100;\nnIntermediate := F_Inner(nOuterLocal);\nF_Outer := nIntermediate + 1;'});
 await call('invt_patch_st',{application_guid:app,object_guid:pou.guid,declaration:'PROGRAM PLC_PRG\nVAR nCycle : UDINT; nResult : DINT; END_VAR',implementation:'nCycle := nCycle + 1;\nnResult := F_Outer(7);'});
 const target=(await call('invt_get_runtime_target',{application_guid:app})).target,sim=await call('invt_set_simulation_mode',{application_guid:app,target_id:target.target_id,enabled:true});req={application_guid:app,target_id:sim.target.target_id};
 await probe('trace_create');
 await call('invt_download_application',req);await call('invt_start_application',req);verifyTrace(await probe('trace_capture'));await call('invt_stop_application',req);
 const debug={...req,debug_id:(await call('invt_prepare_debug',req)).debug_id},task=(await call('invt_inspect_tasks',{application_guid:app})).tasks.find(t=>t.name==='MainTask');
 const objects=(await call('invt_inspect')).objects,fn=objects.find(o=>o.name==='F_Inner'&&o.implementation!==undefined);assert.ok(fn);
 await call('invt_set_breakpoint',{...debug,object_guid:fn.guid,line:2,task_guid:task.guid});await call('invt_debug_continue',debug);
 for(let i=0;i<20;i++){const state=(await call('invt_get_debug_state',debug)).state;if(state.application_state==='halt_on_bp')break;await new Promise(r=>setTimeout(r,100));}
 await probe('metadata',debug);
 if(!process.argv.includes('--hold')){
  report.locals_before_step=values(await probe('locals_read',debug));
  assert.deepEqual(report.locals_before_step,[['F_INNER','iValue',107],['F_INNER','nInnerLocal',1107],['F_OUTER','iValue',7],['F_OUTER','nOuterLocal',107]]);
  await call('invt_debug_step',{...debug,kind:'over'});const stepped=await call('invt_debug_step',{...debug,kind:'over'});
  assert.equal(stepped.state.location.pou.toUpperCase(),'F_OUTER');report.locals_after_step=values(await probe('locals_read',debug));
  assert.deepEqual(report.locals_after_step,[['F_OUTER','iValue',7],['F_OUTER','nOuterLocal',107]]);report.locals_assertions=true;
 }
 if(process.argv.includes('--hold')){
  report.holding=true;report.directory=directory;report.debug=debug;save();console.log('Research HALT ready; bounded fixed-stage control');
  const control=path.join(workspace,'analysis/advanced-debugger-control.json'),until=Date.now()+240000;
  while(Date.now()<until){
   if(fs.existsSync(control)){
    const c=JSON.parse(fs.readFileSync(control,'utf8'));fs.unlinkSync(control);
    assert.equal(c.debug_id,debug.debug_id,'Control belongs to another research halt');
    if(c.stage==='finish')break;
    if(c.stage==='step_over')await call('invt_debug_step',{...debug,kind:'over'});
    else {assert.ok(['metadata','locals_read'].includes(c.stage));await probe(c.stage,debug);}
   }
   await new Promise(r=>setTimeout(r,250));
  }
  report.holding=false;save();
 }
 await call('invt_stop_application',{...req,halt_behavior:'finish_cycle'});await call('invt_disconnect_runtime',req);
 const closed=await call('invt_close_project');assert.equal(closed.source_unchanged,true);report.source_unchanged=closed.source_unchanged;report.shutdown=await call('invt_session_stop');assert.equal(report.shutdown.graceful,true);managed=false;report.probe_completed=true;report.passed=report.locals_assertions===true;
}catch(e){report.probe_completed=false;report.passed=false;report.error=String(e);console.error(e);process.exitCode=1;}finally{if(managed){if(req&&!quarantined)await call('invt_stop_application',{...req,halt_behavior:'finish_cycle'}).catch(()=>{});report.shutdown=await call('invt_session_stop').catch(e=>({error:String(e)}));}save();await client.close();}})();
