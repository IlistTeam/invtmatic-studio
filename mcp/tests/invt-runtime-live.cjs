// Actual MCP -> owned Studio -> positively verified TM750 simulation only.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const workspace=path.resolve(__dirname,'../..'),source=path.join(workspace,'analysis/side-scriptengine-check/API_Check_v6.project');
const hash=()=>crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex');
const report={started:new Date().toISOString(),source_sha256:hash(),steps:[],scenarios:[]};
const output=path.join(workspace,'analysis/persistent-runtime-result.json');
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],env:{...process.env},stderr:'pipe'});
let stderr='';transport.stderr.on('data',b=>stderr+=b.toString());
const client=new Client({name:'INVT-simulation-validation',version:'1'});
let runtime={},managed=false;
function save(){fs.writeFileSync(output,JSON.stringify(report,null,2));}
async function call(name,args={},expected=true){
 const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});
 const content=wire.content.find(c=>c.type==='text').text;let result;
 try{result=JSON.parse(content);}catch{result={protocol_error:content};}
 report.steps.push({name,args,isError:!!wire.isError,result});save();
 console.log(name,wire.isError?'ERROR':'OK',result.exception||result.error||'');
 assert.equal(!!wire.isError,!expected,JSON.stringify(result));return result;
}
const rt=(name,args={},expected=true)=>call(name,{...runtime,...args},expected);
const scalar=value=>value.replace(/^[A-Za-z_][A-Za-z0-9_]*#/,''); // Test expectations only; report retains native IEC literal.
async function values(names){const r=await rt('invt_read_variables',{variables:names.map(n=>'PLC_PRG.'+n)});return Object.fromEntries(r.values.map(v=>[v.variable.split('.').slice(1).join('.'),scalar(v.value)]));}
const write=(name,value)=>rt('invt_write_variable',{variable:'PLC_PRG.'+name,value:String(value)});
async function waitValue(name,expected,timeout=10000){
 const until=performance.now()+timeout;
 do{const v=(await values([name]))[name];if(v===String(expected))return true;await new Promise(r=>setTimeout(r,100));}while(performance.now()<until);
 throw Error('Scenario timeout: '+name+' expected '+expected);
}
async function reset(){
 for(const n of ['xStart','xFault','xSensor','xPermit'])await write(n,'FALSE');
 await write('xReset','TRUE');await waitValue('eState','0');await write('xReset','FALSE');
}
(async()=>{
 try{
  await client.connect(transport);report.tools=(await client.listTools()).tools.map(t=>t.name);
  assert.equal(report.tools.length,39);
  const started=await call('invt_session_start');managed=true;report.studio_pid=started.pid;
  await call('invt_open_copy',{project:source,expected_sha256:report.source_sha256});
  const inspected=await call('invt_inspect'),app=inspected.objects.find(o=>o.application),program=inspected.objects.find(o=>o.name==='PLC_PRG'&&o.declaration);
  assert.ok(app&&program);runtime.application_guid=app.guid;
  assert.equal((await call('invt_build',{application_guid:app.guid})).build_ok,true);
  await call('invt_create_dut',{application_guid:app.guid,name:'ST_DebugFeedback',dut_type:'structure',declaration:'TYPE ST_DebugFeedback :\nSTRUCT\n xReady : BOOL;\n nValue : INT;\nEND_STRUCT\nEND_TYPE'});
  const declaration=fs.readFileSync(path.join(__dirname,'fixtures/debug-loader.declaration.st'),'utf8');
  const implementation=fs.readFileSync(path.join(__dirname,'fixtures/debug-loader.implementation.st'),'utf8');
  await call('invt_patch_st',{application_guid:app.guid,object_guid:program.guid,declaration,implementation});
  let target=(await call('invt_get_runtime_target',{application_guid:app.guid})).target;runtime.target_id=target.target_id;report.initial_target=target;
  // The fixture must start in physical/offline mode. No native login is attempted.
  assert.equal(target.mode,'physical');
  await rt('invt_connect_runtime',{},false);
  const sim=await rt('invt_set_simulation_mode',{enabled:true});runtime.target_id=sim.target.target_id;
  assert.equal(sim.target.mode,'simulation');
  await rt('invt_get_runtime_state',{target_id:target.target_id},false);
  await rt('invt_get_debug_capabilities');
  await rt('invt_download_application');
  assert.equal((await rt('invt_get_runtime_state')).state.connected,true);
  await rt('invt_start_application');
  await waitValue('stFeedback.nValue','7');
  assert.equal((await values(['aValues[1]']))['aValues[1]'],'23');
  await rt('invt_read_variables',{variables:['PLC_PRG.noSuchVariable']},false);
  await rt('invt_stop_application');
  await write('nOverwrite',19);assert.equal((await values(['nOverwrite'])).nOverwrite,'19');
  await rt('invt_start_application');await waitValue('nOverwrite','0');
  await rt('invt_force_variable',{variable:'PLC_PRG.nOverwrite',value:'42'});
  const monitor=await rt('invt_monitor_variables',{variables:['PLC_PRG.nOverwrite','PLC_PRG.nScan'],duration_ms:2500,interval_ms:100});
  assert.ok(monitor.samples.length>1);assert.ok(monitor.samples.every(s=>scalar(s.values[0].value)==='42'));
  await rt('invt_unforce_variable',{variable:'PLC_PRG.nOverwrite'});await waitValue('nOverwrite','0');
  await reset();await write('xStart','TRUE');
  assert.equal((await values(['eState','xValve'])).eState,'0');report.scenarios.push({name:'permission absent',passed:true});
  await write('xPermit','TRUE');await waitValue('eState','10');assert.equal((await values(['xValve'])).xValve,'TRUE');
  await write('xSensor','TRUE');await waitValue('eState','30');assert.equal((await values(['xValve'])).xValve,'FALSE');report.scenarios.push({name:'normal loading',passed:true});
  await reset();await write('xPermit','TRUE');await write('xStart','TRUE');await waitValue('eState','90',12000);
  assert.equal((await values(['xAlarm'])).xAlarm,'TRUE');report.scenarios.push({name:'sensor TON timeout',passed:true});
  await reset();await write('xPermit','TRUE');await write('xStart','TRUE');await waitValue('eState','10');await write('xFault','TRUE');await waitValue('eState','90');await reset();report.scenarios.push({name:'fault and recovery',passed:true});
  // Leave an owned force for teardown; reconnect proves it was selectively removed.
  await rt('invt_force_variable',{variable:'PLC_PRG.nOverwrite',value:'99'});
  const disconnected=await rt('invt_disconnect_runtime');assert.deepEqual(disconnected.cleaned_forces,['PLC_PRG.nOverwrite']);
  await rt('invt_read_variables',{variables:['PLC_PRG.eState']},false);
  await rt('invt_connect_runtime');assert.deepEqual((await rt('invt_list_forces')).forces,[]);
  await rt('invt_disconnect_runtime');
  // Intentionally break the permission condition and prove the same assertion detects it.
  await call('invt_patch_st',{application_guid:app.guid,object_guid:program.guid,implementation:implementation.replace('xStart AND xPermit','xStart')});
  await rt('invt_download_application');await rt('invt_start_application');await reset();await write('xStart','TRUE');
  const bad=await values(['eState']);assert.notEqual(bad.eState,'0');report.scenarios.push({name:'deliberate missing interlock detected',passed:true,observed:bad});
  await rt('invt_disconnect_runtime');
  await call('invt_patch_st',{application_guid:app.guid,object_guid:program.guid,implementation});
  await rt('invt_download_application');await rt('invt_start_application');await reset();await write('xStart','TRUE');assert.equal((await values(['eState'])).eState,'0');
  await rt('invt_disconnect_runtime');
  const end=await call('invt_session_status');assert.equal(end.pid,report.studio_pid);assert.equal(hash(),report.source_sha256);
  await call('invt_session_stop');managed=false;report.passed=true;
 }catch(e){report.passed=false;report.error=String(e);console.error(e);process.exitCode=1;}
 finally{if(managed)await call('invt_session_stop').catch(e=>report.cleanup_error=String(e));report.stderr=stderr;report.finished=new Date().toISOString();save();await client.close();}
})();
