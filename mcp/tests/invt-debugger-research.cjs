// Owned TM750 simulation only. Fixed development probe, not a public script tool.
const {InvtSession}=require('../dist/invt-session');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..'),session=new InvtSession(workspace);
const stage=process.argv[2]||'inventory';
if(!['inventory','core_inventory','execution_probe','model_inventory','breakpoint_inventory','breakpoint_proof','document_inventory','mapping_inventory','manager_inventory','manager_proof'].includes(stage))throw Error('Unknown fixed research stage');
const report={date:'2026-10-14',stage,steps:[]};
function verifyProof(inv){
 const events=inv.events.filter(e=>e.values);
 assert.equal(events.length,5);assert.ok(events.every(e=>e.state==='halt_on_bp'));
 const expected=[[0,0,0],[1,0,0],[1,0,0],[1,0,1],[1,0,11]];
 const names=['PLC_PRG.nCycle','PLC_PRG.nAfter','PLC_PRG.fbProbe.nInside'];
 events.forEach((e,i)=>assert.deepEqual(names.map(n=>Number(e.values[n].replace(/^[A-Za-z_][A-Za-z0-9_]*#/,''))),expected[i]));
 assert.equal(events[0].source.guid,inv.chosen_breakpoint.source_guid);
 assert.equal(events[0].source.position_id,inv.chosen_breakpoint.editor_position_id);
 assert.notEqual(events[1].source.position_id,events[0].source.position_id);
 assert.notEqual(events[2].source.guid,events[0].source.guid);
 assert.equal(events[3].source.guid,events[2].source.guid);assert.equal(events[4].source.guid,events[0].source.guid);
 assert.ok(events[2].call_stack_count>events[1].call_stack_count);
 const commands=inv.events.filter(e=>e.tokens);assert.equal(commands.length,4);assert.ok(commands.every(e=>e.enabled&&e.executed));
 assert.equal(inv.owned_breakpoint_cleared,true);assert.equal(inv.final_state,'stop');
}
if(process.argv[3]==='--verify-saved'){
 const saved=JSON.parse(fs.readFileSync(path.join(workspace,'analysis/debugger-breakpoint-proof.json'),'utf8'));
 assert.equal(saved.passed,true);assert.equal(saved.shutdown.graceful,true);
 verifyProof(saved.inventory);console.log('Saved native breakpoint/step assertions: PASS');process.exit(0);
}
(async()=>{
 try{
  await session.start();
  fs.copyFileSync(path.join(__dirname,'probes/invt_debugger_inventory.py'),path.join(session.status().directory,'invt_debugger_inventory.py'));
  async function call(operation,args={}){const r=await session.call({operation,...args});report.steps.push({operation,result:r});assert.ok(r.ok,JSON.stringify(r));return r;}
  await call('open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
  const inspected=await call('inspect');const application_guid=inspected.objects.find(o=>o.application).guid;
  if(stage!=='inventory'){
   await call('create_pou',{application_guid,name:'FB_DebugProbe',pou_type:'function_block',declaration:'FUNCTION_BLOCK FB_DebugProbe\nVAR\n nInside : UDINT;\nEND_VAR',implementation:'nInside := nInside + 1;\nnInside := nInside + 10;'});
   const pou=inspected.objects.find(o=>o.name==='PLC_PRG'&&o.implementation!==undefined);
   await call('patch_st',{application_guid,object_guid:pou.guid,declaration:'PROGRAM PLC_PRG\nVAR\n nCycle : UDINT;\n nAfter : UDINT;\n fbProbe : FB_DebugProbe;\nEND_VAR',implementation:stage==='mapping_inventory'?'(* Кириллица, пустая строка и два оператора в одной строке *)\n\n  nCycle := nCycle + 1; nAfter := nAfter + 1;\nfbProbe();\nnAfter := nAfter + 1;':'nCycle := nCycle + 1;\nfbProbe();\nnAfter := nAfter + 1;'});
  }
  const target=(await call('runtime_target',{application_guid})).target;
  const sim=await call('simulation_mode',{application_guid,target_id:target.target_id,enabled:true});
  const request={application_guid,target_id:sim.target.target_id};
  await call('download_application',request);
  const payload=Buffer.from(JSON.stringify(request)).toString('base64');
  const wire=await session.ipc.sendCommand(`import json,base64\nimport invt_debugger_inventory as probe\nr=probe.${stage}(json.loads(base64.b64decode('${payload}')))\nprint('DEBUGGER_INVENTORY:'+json.dumps(probe.json_safe(r),ensure_ascii=True))\n`,stage==='breakpoint_proof'?15000:60000);
  report.wire={success:wire.success,error:wire.error,requestId:wire.requestId};
  assert.ok(wire.success,JSON.stringify(wire));
  report.inventory=JSON.parse(wire.output.split(/\r?\n/).find(l=>l.startsWith('DEBUGGER_INVENTORY:')).slice('DEBUGGER_INVENTORY:'.length));
  if(['breakpoint_proof','manager_proof'].includes(stage) && report.inventory.error)throw Error(report.inventory.error);
  if(['breakpoint_proof','manager_proof'].includes(stage))verifyProof(report.inventory);
  await call('disconnect_runtime',request);report.passed=true;
  console.log(JSON.stringify({stage,command_count:report.inventory.commands?.length,assemblies:report.inventory.assemblies?.map(a=>({name:a.name,types:a.types.length})),core_type:report.inventory.core_shape?.type,model_types:report.inventory.model_types?.map(t=>t.name)}));
 }catch(e){report.passed=false;report.error=String(e);console.error(e);process.exitCode=1;if(/timed out/i.test(String(e))){session.state='faulted';session.lastError=String(e);report.transport_quarantined=true;}}
 finally{const checkpoint=path.join(session.status().directory||'','debugger_checkpoint.json');try{if(fs.existsSync(checkpoint))report.checkpoint=JSON.parse(fs.readFileSync(checkpoint,'utf8'));}catch(e){report.checkpoint_error=String(e);}report.shutdown=await session.stop().catch(e=>({error:String(e)}));fs.writeFileSync(path.join(workspace,'analysis/debugger-'+stage.replace('_','-')+'.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:report.passed,checkpoint:report.checkpoint?.checkpoint_stage,shutdown:report.shutdown}));}
})();
