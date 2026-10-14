// Native owner-loss tests, exclusively on an owned copy and verified simulation.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..'),report={};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const alive=pid=>{try{process.kill(pid,0);return true;}catch{return false;}};
async function check(crash){
 const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],env:{...process.env},stderr:'pipe'});
 const client=new Client({name:'halt-lifecycle-validation',version:'1'});let pid;
 try{
  await client.connect(transport);
  const call=async(name,args={})=>{const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});assert.notEqual(wire.isError,true,JSON.stringify(wire));return JSON.parse(wire.content[0].text);};
  const started=await call('invt_session_start');pid=started.pid;
  const opened=await call('invt_open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
  const inspected=await call('invt_inspect'),app=inspected.objects.find(o=>o.application).guid,pou=inspected.objects.find(o=>o.name==='PLC_PRG'&&o.implementation!==undefined);
  await call('invt_patch_st',{application_guid:app,object_guid:pou.guid,declaration:'PROGRAM PLC_PRG\nVAR nCycle : UDINT; END_VAR',implementation:'nCycle := nCycle + 1;'});
  const target=(await call('invt_get_runtime_target',{application_guid:app})).target;
  const sim=await call('invt_set_simulation_mode',{application_guid:app,target_id:target.target_id,enabled:true}),req={application_guid:app,target_id:sim.target.target_id};
  await call('invt_download_application',req);const prepared=await call('invt_prepare_debug',req),debug={...req,debug_id:prepared.debug_id};
  const task=(await call('invt_inspect_tasks',{application_guid:app})).tasks.find(t=>t.name==='MainTask');
  await call('invt_set_breakpoint',{...debug,object_guid:pou.guid,line:1,task_guid:task.guid});
  await call('invt_debug_continue',debug);let state;
  for(let i=0;i<20;i++){state=(await call('invt_get_debug_state',debug)).state;if(state.application_state==='halt_on_bp')break;await sleep(250);}
  assert.equal(state.application_state,'halt_on_bp');
  const observed=await call('invt_read_variables',{...req,variables:['PLC_PRG.nCycle']});
  assert.equal(Number(observed.values[0].value.replace(/^[A-Za-z_][A-Za-z0-9_]*#/,'')),0);
  const owner=transport.pid,start=Date.now();
  if(crash)process.kill(owner,'SIGKILL');else transport._process.stdin.end();
  while(alive(pid)&&Date.now()-start<45000)await sleep(250);
  const record={from_state:state.application_state,cycle_before:0,owner_pid:owner,studio_pid:pid,studio_exited:!alive(pid),exit_ms:Date.now()-start,source_unchanged:fs.readFileSync(path.join(workspace,'analysis/side-scriptengine-check/API_Check_v6.project')).equals(source),copy_saved:fs.statSync(opened.project).size>0};
  const ack=path.join(started.directory,'shutdown_ack.json');if(fs.existsSync(ack))record.shutdown_ack=JSON.parse(fs.readFileSync(ack,'utf8'));
  report[crash?'owner_crash':'stdin_eof']=record;
  assert.ok(record.studio_exited,JSON.stringify(record));assert.ok(record.source_unchanged);assert.ok(record.copy_saved);
  // No post-crash runtime values are observable; never claim confirmed cleanup
  // or a completed cycle merely because the owned process exited.
 }finally{await client.close();if(pid&&alive(pid))process.kill(pid,'SIGKILL');}
}
const source=fs.readFileSync(path.join(workspace,'analysis/side-scriptengine-check/API_Check_v6.project'));
(async()=>{try{await check(true);console.log('HALT owner crash: PASS');await check(false);console.log('HALT stdin EOF: PASS');report.passed=true;}catch(e){report.passed=false;report.error=String(e);console.error(e);process.exitCode=1;}finally{fs.writeFileSync(path.join(workspace,'analysis/persistent-debugger-lifecycle-result.json'),JSON.stringify(report,null,2));}})();
