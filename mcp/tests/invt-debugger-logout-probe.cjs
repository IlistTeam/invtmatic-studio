// Historical HALT/logout investigation, retained as a developer probe.
// The accepted lifecycle scenario is invt-debugger-live.cjs. This older probe
// deliberately attempts disconnect from HALT and now expects policy refusal;
// it must not be presented as a current passing acceptance test.
const {InvtSession}=require('../dist/invt-session');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..'),s=new InvtSession(workspace),r={steps:[]};
(async()=>{try{
 await s.start();
 async function call(operation,args={}){const x=await s.call({operation,...args});r.steps.push({operation,result:x});assert.ok(x.ok,JSON.stringify(x));return x;}
 await call('open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});const i=await call('inspect'),app=i.objects.find(o=>o.application).guid,pou=i.objects.find(o=>o.name==='PLC_PRG'&&o.implementation!==undefined);
 await call('patch_st',{application_guid:app,object_guid:pou.guid,declaration:'PROGRAM PLC_PRG\nVAR nCycle : UDINT; nAfter : UDINT; END_VAR',implementation:'nCycle := nCycle + 1;\nnAfter := nAfter + 1;'});
 const t=(await call('runtime_target',{application_guid:app})).target;
 const mode=await call('simulation_mode',{application_guid:app,target_id:t.target_id,enabled:true}),req={application_guid:app,target_id:mode.target.target_id};
 await call('download_application',req);const prepared=await call('prepare_debug',req),debug={...req,debug_id:prepared.debug_id};
 const main=(await call('inspect_tasks',{application_guid:app})).tasks.find(t=>t.name==='MainTask');
 await call('set_breakpoint',{...debug,object_guid:pou.guid,line:1,task_guid:main.guid});
 fs.copyFileSync(path.join(__dirname,'probes/invt_debugger_fixture.py'),path.join(s.directory,'invt_debugger_fixture.py'));
 const payload=Buffer.from(JSON.stringify({...req,object_guid:pou.guid,line:2})).toString('base64');
 async function probe(action){const w=await s.ipc.sendCommand(`import json,base64\nimport invt_debugger_fixture as f\na=json.loads(base64.b64decode('${payload}'))\nr=f.run(a,'${action}')\nprint('RESULT:'+json.dumps(r,ensure_ascii=True))\n`,10000);assert.ok(w.success,JSON.stringify(w));const x=JSON.parse(w.output.split(/\r?\n/).find(l=>l.startsWith('RESULT:')).slice(7));r.steps.push({probe:action,result:x});return x;}
 await probe('foreign_create');await call('debug_continue',debug);await probe('metadata');
 await call('disconnect_runtime',req);await call('connect_runtime',req);r.after_reattach=await call('runtime_state',req);
 const values=await call('read_variables',{...req,variables:['PLC_PRG.nCycle','PLC_PRG.nAfter']});
 assert.deepEqual(values.values.map(v=>Number(v.value.replace(/^[A-Za-z_][A-Za-z0-9_]*#/,''))),[0,0]);
 await probe('metadata');await probe('foreign_clear');await call('disconnect_runtime',req);
 r.passed=!r.after_reattach.state.exception_active;
}catch(e){r.error=String(e);r.passed=false;console.error(e);}finally{r.shutdown=await s.stop(true);fs.writeFileSync(path.join(workspace,'analysis/debugger-logout-probe.json'),JSON.stringify(r,null,2));console.log(JSON.stringify({passed:r.passed,error:r.error,shutdown:r.shutdown,cleanup:r.steps.filter(s=>s.operation==='disconnect_runtime').map(s=>s.result.cleanup_trace)}));process.exitCode=r.passed?0:1;}})();
