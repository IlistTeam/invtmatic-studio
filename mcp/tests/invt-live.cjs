const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const fs=require('fs'), path=require('path'), assert=require('assert/strict'), crypto=require('crypto');
const workspace=path.resolve(__dirname,'../..');
const source=path.join(workspace,'analysis/side-scriptengine-check/API_Check_v6.project');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const report={started:new Date().toISOString(),source,source_hash:hash(source),steps:[]};
const output=path.join(workspace,'analysis/persistent-live-result.json');
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],env:{...process.env},stderr:'pipe'});
let stderr='';transport.stderr.on('data',b=>stderr+=b.toString());
const client=new Client({name:'invt-offline-validation',version:'1.0'});
async function call(name,args={},expect=true){
  const start=Date.now();
  const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});
  const result=JSON.parse(wire.content.find(c=>c.type==='text').text);
  report.steps.push({name,wall_ms:Date.now()-start,isError:wire.isError||false,result});
  fs.writeFileSync(output,JSON.stringify(report,null,2));
  console.log(name,Date.now()-start,'ms',wire.isError?'ERROR':'OK');
  if(expect)assert.notEqual(wire.isError,true,JSON.stringify(result));
  else assert.equal(wire.isError,true);
  return result;
}
(async()=>{
  try{
    await client.connect(transport);
    report.server_pid=transport.pid;
    report.tools=(await client.listTools()).tools.map(t=>t.name);
    assert.equal(report.tools.length,39);
    const started=await call('invt_session_start');
    report.studio_pid=started.pid;
    assert.equal(started.state,'ready');
    await call('invt_open_copy',{project:source,expected_sha256:report.source_hash});
    const inspected=await call('invt_inspect');
    const pou=inspected.objects.find(o=>o.name==='PLC_PRG'&&o.textual&&o.implementation!==undefined);
    assert.ok(pou);
    const built=await call('invt_build');assert.equal(built.build_ok,true);
    await call('invt_patch_st',{object_guid:'00000000-0000-0000-0000-000000000000',implementation:'x := 1;'},false);
    await call('invt_patch_st',{object_guid:pou.guid,application_guid:'00000000-0000-0000-0000-000000000000',implementation:'MUST_NOT_APPEAR;'},false);
    const unchanged=await call('invt_inspect');
    assert.equal(unchanged.objects.find(o=>o.guid===pou.guid).implementation,pou.implementation);
    const bad=await call('invt_patch_st',{object_guid:pou.guid,implementation:'this is intentionally invalid ST;'},false);
    assert.equal(bad.build_ok,false);
    assert.ok(bad.diagnostics.some(d=>d.severity==='Error'));
    const valid='(* Проверка постоянного соединения: порошок, ось, клапан. *)\n'+pou.implementation;
    const repaired=await call('invt_patch_st',{object_guid:pou.guid,implementation:valid});
    assert.equal(repaired.build_ok,true);assert.ok(repaired.after.implementation.includes('порошок'));
    const exports=await call('invt_export_pou',{object_guid:pou.guid});
    for(const p of exports.exports)assert.ok(fs.statSync(p).size>0);
    const statuses=[];
    for(let i=0;i<10;i++){const r=await call('invt_inspect');statuses.push(r.elapsed_ms);assert.ok(r.objects.find(o=>o.guid===pou.guid).implementation.includes('порошок'));}
    report.repeat_inspect_ms=statuses;
    const current=await call('invt_session_status');assert.equal(current.pid,started.pid);
    const saved=current.project_copy;
    await call('invt_close_project');
    await call('invt_open_copy',{project:saved});
    const reopened=await call('invt_inspect');assert.ok(reopened.objects.find(o=>o.guid===pou.guid).implementation.includes('порошок'));
    assert.equal((await call('invt_session_status')).pid,started.pid);
    const stop=await call('invt_session_stop');assert.equal(stop.graceful,true);
    report.source_unchanged=hash(source)===report.source_hash;assert.ok(report.source_unchanged);
    report.success=true;
  }catch(e){report.success=false;report.error=e.stack;console.error(e);process.exitCode=1;}
  finally{await client.close();report.stderr=stderr;report.finished=new Date().toISOString();fs.writeFileSync(output,JSON.stringify(report,null,2));}
})();
