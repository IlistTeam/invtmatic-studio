// Real offline TM750 task lifecycle, via the MCP SDK; no PLC session is opened.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const workspace=path.resolve(__dirname,'../..');
const source=path.join(workspace,'analysis/side-scriptengine-check/API_Check_v6.project');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const output=path.join(workspace,'analysis/persistent-tasks-result.json');
const report={started:new Date().toISOString(),source,source_sha256:hash(source),steps:[]};
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],env:{...process.env},stderr:'pipe'});
let stderr='';transport.stderr.on('data',b=>stderr+=b.toString());
const client=new Client({name:'TM750-task-validation',version:'1'});
let managed=false;
function save(){fs.writeFileSync(output,JSON.stringify(report,null,2));}
async function call(name,args={},expected=true){
 const start=Date.now();let result,isError;
 try{
  const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});isError=wire.isError||false;
  const text=wire.content.find(c=>c.type==='text').text;
  try{result=JSON.parse(text);}catch{result={protocol_error:text};}
 }catch(error){if(expected)throw error;result={protocol_error:String(error)};isError=true;}
 report.steps.push({name,args,isError,wall_ms:Date.now()-start,result});save();
 console.log(name,args.name||'',Date.now()-start,'ms',isError?'ERROR':'OK');
 assert.equal(isError,!expected,JSON.stringify(result));return result;
}
async function tasks(application_guid){return (await call('invt_inspect_tasks',{application_guid})).tasks;}
function byGuid(items,guid){const result=items.find(t=>t.guid===guid);assert.ok(result);return result;}
(async()=>{
 try{
  await client.connect(transport);report.tools=(await client.listTools()).tools.map(t=>t.name);assert.equal(report.tools.length,39);
  const started=await call('invt_session_start');managed=true;report.studio_pid=started.pid;
  await call('invt_open_copy',{project:source,expected_sha256:report.source_sha256});
  const inspected=await call('invt_inspect');const app=inspected.objects.find(o=>o.application);assert.ok(app);
  const application_guid=app.guid;
  const baseline=await tasks(application_guid);report.original_tasks=baseline;assert.ok(baseline.length>=2);
  assert.equal((await call('invt_build',{application_guid})).build_ok,true);
  const programA=await call('invt_create_pou',{application_guid,name:'PRG_TaskProbeA',pou_type:'program',declaration:'PROGRAM PRG_TaskProbeA\nVAR\n    nCounter : UDINT;\nEND_VAR',implementation:'nCounter := nCounter + 1;'});
  const programB=await call('invt_create_pou',{application_guid,name:'PRG_TaskProbeB',pou_type:'program',declaration:'PROGRAM PRG_TaskProbeB\nVAR\n    xState : BOOL;\nEND_VAR',implementation:'xState := FALSE;'});
  const block=await call('invt_create_pou',{application_guid,name:'FB_TaskGuardProbe',pou_type:'function_block',declaration:'FUNCTION_BLOCK FB_TaskGuardProbe\nVAR\n    xState : BOOL;\nEND_VAR',implementation:'xState := FALSE;'});
  const created=await call('invt_create_task',{application_guid,name:'Task_Probe',interval_ms:20,priority:20,watchdog:{enabled:true,time_ms:100,sensitivity:2}});
  assert.equal(created.created,true);assert.equal(created.saved,true);assert.equal(created.build_ok,true);
  const task_guid=created.task_guid;
  assert.equal(created.after.kind,'Cyclic');assert.equal(created.after.interval_ms,20);assert.equal(created.after.priority,'20');
  assert.equal(created.after.watchdog.enabled,true);assert.equal(created.after.watchdog.time_ms,100);assert.equal(created.after.watchdog.sensitivity,'2');
  const configured=await call('invt_configure_task',{application_guid,task_guid,settings:{interval_ms:30,priority:15,watchdog:{enabled:true,time_ms:150,sensitivity:3}}});
  assert.equal(configured.after.interval_ms,30);assert.equal(configured.after.watchdog.time_ms,150);assert.equal(configured.after.priority,'15');
  const partial=await call('invt_configure_task',{application_guid,task_guid,settings:{priority:14}});
  assert.equal(partial.after.interval_ms,30);assert.deepEqual(partial.after.watchdog,configured.after.watchdog);
  const disabled=await call('invt_configure_task',{application_guid,task_guid,settings:{watchdog:{enabled:false}}});
  assert.equal(disabled.after.watchdog.enabled,false);assert.equal(disabled.after.watchdog.time_ms,150);assert.equal(disabled.after.interval_ms,30);
  await call('invt_configure_task',{application_guid,task_guid,settings:{watchdog:{enabled:true,time_ms:150,sensitivity:3}}});
  await call('invt_bind_program',{application_guid,task_guid,program_guid:programA.created_guid,comment:'Основная программа'});
  const binding=await call('invt_bind_program',{application_guid,task_guid,program_guid:programB.created_guid,index:0,comment:'Подготовка'});
  assert.deepEqual(binding.after.bindings.map(b=>b.program_name),['PRG_TaskProbeB','PRG_TaskProbeA']);
  const stable=await tasks(application_guid);
  const guards=[
   ['invt_create_task',{application_guid,name:'task_probe',interval_ms:10,priority:20}],
   ['invt_create_task',{application_guid,name:'Bad_Config_Task',task_configuration_guid:app.guid,interval_ms:10,priority:20}],
   ['invt_configure_task',{application_guid,task_guid:app.guid,settings:{priority:10}}],
   ['invt_bind_program',{application_guid,task_guid,program_guid:programA.created_guid}],
   ['invt_bind_program',{application_guid,task_guid,program_guid:block.created_guid}],
   ['invt_bind_program',{application_guid,task_guid,program_guid:block.created_guid,index:99}],
   ['invt_bind_program',{application_guid,task_guid,program_guid:programA.created_guid,application_guid:'00000000-0000-0000-0000-000000000000'}],
   ['invt_configure_task',{application_guid,task_guid,settings:{interval_ms:0}}],
   ['invt_configure_task',{application_guid,task_guid,settings:{watchdog:{enabled:true}}}],
   ['invt_configure_task',{application_guid,task_guid,settings:{}}]
  ];
  for(const [name,args] of guards)await call(name,args,false);
  assert.deepEqual(await tasks(application_guid),stable);
  const second=await call('invt_create_task',{application_guid,name:'Task_SecondProbe',interval_ms:50,priority:25});
  const declined=await call('invt_bind_program',{application_guid,task_guid:second.task_guid,program_guid:programB.created_guid},false);
  assert.equal(declined.changed,false);
  const allowed=await call('invt_bind_program',{application_guid,task_guid:second.task_guid,program_guid:programB.created_guid,allow_multi_task:true});assert.equal(allowed.build_ok,true);
  // A valid program and an out-of-range index exercises index validation itself.
  await call('invt_bind_program',{application_guid,task_guid:second.task_guid,program_guid:programA.created_guid,allow_multi_task:true,index:99},false);
  const finalTasks=await tasks(application_guid);
  for(const original of baseline)assert.deepEqual(byGuid(finalTasks,original.guid),original);
  report.final_tasks=finalTasks;report.existing_tasks_unchanged=true;
  const status=await call('invt_session_status');assert.equal(status.pid,started.pid);report.project_copy=status.project_copy;
  await call('invt_close_project');await call('invt_open_copy',{project:status.project_copy});
  const reopened=await tasks(application_guid);assert.deepEqual(reopened,finalTasks);report.tasks_persisted=true;
  assert.equal((await call('invt_build',{application_guid})).build_ok,true);
  assert.equal((await call('invt_session_status')).pid,started.pid);
  assert.equal((await call('invt_session_stop')).graceful,true);managed=false;
  report.source_unchanged=hash(source)===report.source_sha256;assert.ok(report.source_unchanged);report.success=true;
 }catch(error){report.success=false;report.error=error.stack;console.error(error);process.exitCode=1;}
 finally{if(managed)await call('invt_session_stop').catch(()=>{});await client.close();report.stderr=stderr;report.finished=new Date().toISOString();save();}
})();
