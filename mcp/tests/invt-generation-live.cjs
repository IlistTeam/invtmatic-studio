// End-to-end object generation using the actual MCP SDK and an offline TM750 copy.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const workspace=path.resolve(__dirname,'../..');
const source=path.join(workspace,'analysis/side-scriptengine-check/API_Check_v6.project');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const output=path.join(workspace,'analysis/persistent-generation-result.json');
const report={started:new Date().toISOString(),source,source_sha256:hash(source),steps:[],created:[]};
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],env:{...process.env},stderr:'pipe'});
let stderr='';transport.stderr.on('data',b=>stderr+=b.toString());
const client=new Client({name:'TM750-generation-validation',version:'1'});
let managed=false;
function save(){fs.writeFileSync(output,JSON.stringify(report,null,2));}
async function call(name,args={},expected=true){
  const start=Date.now();const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});
  const result=JSON.parse(wire.content.find(c=>c.type==='text').text);
  report.steps.push({name,args,wall_ms:Date.now()-start,isError:wire.isError||false,result});save();
  console.log(name,args.name||'',Date.now()-start,'ms',wire.isError?'ERROR':'OK');
  assert.equal(wire.isError||false,!expected,JSON.stringify(result));return result;
}
(async()=>{
  try{
    await client.connect(transport);
    report.tools=(await client.listTools()).tools.map(t=>t.name);assert.equal(report.tools.length,39);
    const started=await call('invt_session_start');managed=true;report.studio_pid=started.pid;
    await call('invt_open_copy',{project:source,expected_sha256:report.source_sha256});
    const inspected=await call('invt_inspect');
    const app=inspected.objects.find(o=>o.application);assert.ok(app);
    const pou=inspected.objects.find(o=>o.name==='PLC_PRG'&&o.textual);assert.ok(pou);
    const application_guid=app.guid;
    assert.equal((await call('invt_build',{application_guid})).build_ok,true);
    const specs=[
      ['invt_create_dut',{name:'ST_Probe',dut_type:'structure',declaration:'TYPE ST_Probe :\nSTRUCT\n    xReady : BOOL;\n    nValue : DINT;\nEND_STRUCT\nEND_TYPE'}],
      ['invt_create_dut',{name:'E_Probe',dut_type:'enumeration',declaration:"{attribute 'qualified_only'}\n{attribute 'strict'}\nTYPE E_Probe :\n(Idle := 0, Run := 1);\nEND_TYPE"}],
      ['invt_create_dut',{name:'T_Probe',dut_type:'alias',base_type:'DINT',declaration:'TYPE T_Probe : DINT;\nEND_TYPE'}],
      ['invt_create_dut',{name:'U_Probe',dut_type:'union',declaration:'TYPE U_Probe :\nUNION\n    nValue : DINT;\n    dwValue : DWORD;\nEND_UNION\nEND_TYPE'}],
      ['invt_create_gvl',{name:'GVL_Probe',declaration:"{attribute 'qualified_only'}\nVAR_GLOBAL\n    data : ST_Probe;\n    state : E_Probe := E_Probe.Idle;\n    value : T_Probe;\n    bits : U_Probe;\nEND_VAR"}],
      ['invt_create_pou',{name:'FB_Probe',pou_type:'function_block',declaration:'(* Проверка: порошок, клапан. *)\nFUNCTION_BLOCK FB_Probe\nVAR_INPUT\n    xEnable : BOOL;\nEND_VAR\nVAR_OUTPUT\n    xReady : BOOL;\nEND_VAR',implementation:'xReady := xEnable;'}],
      ['invt_create_pou',{name:'F_Probe',pou_type:'function',return_type:'DINT',declaration:'FUNCTION F_Probe : DINT\nVAR_INPUT\n    value : DINT;\nEND_VAR',implementation:'F_Probe := value + 1;'}],
      ['invt_create_pou',{name:'PRG_Probe',pou_type:'program',declaration:'PROGRAM PRG_Probe\nVAR\n    nCounter : DINT;\nEND_VAR',implementation:'nCounter := nCounter + 1;'}]
    ];
    for(const [tool,spec] of specs){
      const r=await call(tool,{...spec,application_guid});assert.equal(r.created,true);assert.equal(r.saved,true);assert.equal(r.build_ok,true);
      assert.equal(r.object.name,spec.name);assert.equal(r.object.declaration.replace(/\r\n/g,'\n').trim(),spec.declaration.trim());
      if(spec.implementation!==undefined)assert.equal(r.object.implementation.trim(),spec.implementation.trim());
      report.created.push({tool,...spec,guid:r.created_guid});
    }
    const snapshot=await call('invt_inspect');
    for(const item of report.created)assert.ok(snapshot.objects.find(o=>o.guid===item.guid&&o.textual));
    const count=snapshot.objects.length;
    const rejected=[
      ['invt_create_gvl',{name:'gvl_probe',declaration:'VAR_GLOBAL\n    x : BOOL;\nEND_VAR'}],
      ['invt_create_pou',{name:'New_Probe',pou_type:'program',declaration:'PROGRAM Wrong_Probe\nVAR\nEND_VAR'}],
      ['invt_create_pou',{name:'Bad_Function',pou_type:'function',declaration:'FUNCTION Bad_Function : DINT\nVAR\nEND_VAR'}],
      ['invt_create_dut',{name:'Bad_Alias',dut_type:'alias',base_type:'DINT',declaration:'TYPE Bad_Alias : BOOL;\nEND_TYPE'}],
      ['invt_create_gvl',{name:'Invalid_App_Probe',application_guid:'00000000-0000-0000-0000-000000000000',declaration:'VAR_GLOBAL\n    x : BOOL;\nEND_VAR'}]
    ];
    for(const [tool,spec] of rejected){const r=await call(tool,{application_guid,...spec},false);assert.equal(r.created,false);}
    assert.equal((await call('invt_inspect')).objects.length,count);
    // Reference every kind from compiled code, so this tests usable objects rather
    // than only the ability to insert nodes in the project tree.
    const declaration=pou.declaration.replace('END_VAR','    fbProbe : FB_Probe;\n    unionProbe : U_Probe;\nEND_VAR');
    const implementation=pou.implementation+'\nfbProbe(xEnable := xInput);\nGVL_Probe.data.xReady := fbProbe.xReady;\nGVL_Probe.data.nValue := F_Probe(value := 2);\nGVL_Probe.state := E_Probe.Run;\nGVL_Probe.value := GVL_Probe.data.nValue;\nunionProbe.nValue := GVL_Probe.value;\nGVL_Probe.bits := unionProbe;\nPRG_Probe();';
    assert.equal((await call('invt_patch_st',{application_guid,object_guid:pou.guid,declaration,implementation})).build_ok,true);
    // Ensure the broken declaration participates in the compiled application.
    const consumer=implementation+'\nxOutput := GVL_Broken_Probe.xBroken;';
    assert.equal((await call('invt_patch_st',{application_guid,object_guid:pou.guid,implementation:consumer},false)).build_ok,false);
    const bad=await call('invt_create_gvl',{application_guid,name:'GVL_Broken_Probe',declaration:'VAR_GLOBAL\n    xBroken : Missing_Probe_Type;\nEND_VAR'},false);
    assert.equal(bad.created,true);assert.equal(bad.saved,true);assert.equal(bad.build_ok,false);assert.ok(bad.created_guid);
    assert.equal((await call('invt_patch_st',{application_guid,object_guid:bad.created_guid,declaration:'VAR_GLOBAL\n    xBroken : BOOL;\nEND_VAR'})).build_ok,true);
    report.repaired_created_guid=bad.created_guid;
    const exported=await call('invt_export_pou',{object_guid:report.created.find(o=>o.name==='FB_Probe').guid});
    for(const file of exported.exports)assert.ok(fs.statSync(file).size>0);
    const current=await call('invt_session_status');assert.equal(current.pid,started.pid);report.project_copy=current.project_copy;
    await call('invt_close_project');await call('invt_open_copy',{project:current.project_copy});
    const reopened=await call('invt_inspect');
    for(const item of report.created){const obj=reopened.objects.find(o=>o.guid===item.guid);assert.ok(obj);assert.equal(obj.name,item.name);assert.equal(obj.declaration.replace(/\r\n/g,'\n').trim(),item.declaration.trim());}
    assert.ok(reopened.objects.find(o=>o.guid===bad.created_guid));
    assert.equal((await call('invt_build',{application_guid})).build_ok,true);
    assert.equal((await call('invt_session_status')).pid,started.pid);
    assert.equal((await call('invt_session_stop')).graceful,true);managed=false;
    report.source_unchanged=hash(source)===report.source_sha256;assert.ok(report.source_unchanged);report.success=true;
  }catch(e){report.success=false;report.error=e.stack;console.error(e);process.exitCode=1;}
  finally{
    if(managed)await call('invt_session_stop').catch(e=>console.error(e));
    await client.close();report.stderr=stderr;report.finished=new Date().toISOString();save();
  }
})();
