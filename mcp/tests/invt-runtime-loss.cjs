// Fault/ownership probe on an owned simulation copy. Private IPC is not public MCP.
const {InvtSession}=require('../dist/invt-session');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..'),session=new InvtSession(workspace);
const report={steps:[]};let runtime={};
async function call(operation,args={},ok=true){
 const r=await session.call({operation,...runtime,...args});report.steps.push({operation,result:r});
 assert.equal(r.ok,ok,JSON.stringify(r));return r;
}
async function native(code){
 const wire=await session.ipc.sendCommand(`import scriptengine as se\nimport invt_operations as ops\nimport invt_runtime as rt\np=ops.owned()\na=ops.choose_application(list(p.get_children(True)),{})\ndef probe(o):\n    rt.checked(p,a,${JSON.stringify(runtime).replace(/"/g,"'")})\n${code.split('\n').map(l=>'    '+l).join('\n')}\nrt.with_executor(lambda:rt.use_online(a,probe))\n`,60000);
 report.steps.push({private_probe:code,wire});assert.equal(wire.success,true,JSON.stringify(wire));
}
(async()=>{
 try{
  await session.start();await call('open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
  const inspected=await call('inspect');runtime.application_guid=inspected.objects.find(o=>o.application).guid;
  runtime.target_id=(await call('runtime_target')).target.target_id;
  runtime.target_id=(await call('simulation_mode',{enabled:true})).target.target_id;
  await call('download_application');await call('start_application');
  await call('force_variable',{variable:'PLC_PRG.xInput',value:'TRUE'});
  await native("o.set_prepared_value('PLC_PRG.xOutput','FALSE')\no.force_prepared_values()\nprint('FOREIGN_FORCE_CREATED')");
  const forces=await call('list_forces');assert.ok(forces.forces.some(f=>!f.owned_by_session));
  await call('unforce_variable',{variable:'PLC_PRG.xOutput'},false);
  const detached=await call('disconnect_runtime');assert.deepEqual(detached.cleaned_forces,['PLC_PRG.xInput']);
  await call('connect_runtime');const remaining=await call('list_forces');assert.deepEqual(remaining.forces,[{variable:'PLC_PRG.xOutput',owned_by_session:false}]);
  // Remove only the foreign force deliberately created by this test harness.
  await native("o.set_unforce_value('PLC_PRG.xOutput',False)\no.force_prepared_values()\nprint('HARNESS_FORCE_REMOVED')");
  await native("o.logout()\nprint('UNEXPECTED_LOGOUT')");
  const lost=await call('runtime_state');assert.equal(lost.state.connected,false);assert.equal(lost.state.application_state,undefined);
  const read=await call('read_variables',{variables:['PLC_PRG.xInput']},false);assert.equal(read.values[0].ok,false);assert.equal(read.values[0].value,undefined);
  const monitor=await call('monitor_variables',{variables:['PLC_PRG.xInput'],duration_ms:1000,interval_ms:100},false);assert.equal(monitor.samples.length,1);assert.equal(monitor.samples[0].values[0].value,undefined);
  await call('disconnect_runtime');await call('connect_runtime');await call('start_application');
  await call('force_variable',{variable:'PLC_PRG.xInput',value:'TRUE'});
  await native("o.logout()\nprint('LOGOUT_WITH_OWNED_FORCE')");
  const unconfirmed=await call('disconnect_runtime',{},false);
  assert.deepEqual(unconfirmed.owned_forces,{'PLC_PRG.xInput':'TRUE'});
  // Explicit attach to the same positively verified simulation, no write/force replay.
  await call('connect_runtime');
  assert.ok((await call('list_forces')).forces.some(f=>f.variable==='PLC_PRG.xInput'&&f.owned_by_session));
  await call('disconnect_runtime');
  await call('connect_runtime');await call('start_application');
  await call('force_variable',{variable:'PLC_PRG.xInput',value:'TRUE'});
  await call('close_project'); // Exercises force cleanup/stop/logout before native close.
  report.passed=true;
 }catch(e){report.passed=false;report.error=String(e);console.error(e);process.exitCode=1;}
 finally{report.shutdown=await session.stop().catch(e=>({error:String(e)}));fs.writeFileSync(path.join(workspace,'analysis/runtime-loss-result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:report.passed,error:report.error,shutdown:report.shutdown}));}
})();
