// Offline fault injection. Only processes created by this test are terminated.
const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const {InvtSession}=require('../dist/invt-session');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const workspace=path.resolve(__dirname,'../..');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const alive=pid=>{try{process.kill(pid,0);return true;}catch{return false;}};
const result={};
async function checkDisconnect(crash){
  const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],env:{...process.env},stderr:'pipe'});
  let stderr='';transport.stderr.on('data',b=>stderr+=b.toString());
  const client=new Client({name:'lifecycle-validation',version:'1'});
  let pid;
  try{
    await client.connect(transport);
    const call=async(name,args={})=>{
      const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});
      assert.notEqual(wire.isError,true,JSON.stringify(wire));return JSON.parse(wire.content[0].text);
    };
    const started=await call('invt_session_start');pid=started.pid;
    const opened=await call('invt_open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
    const start=Date.now();
    const ownerPid=transport.pid;
    if(crash)process.kill(ownerPid,'SIGKILL');
    else transport._process.stdin.end(); // EOF without SDK's short forced-shutdown deadline
    while(alive(pid)&&Date.now()-start<20000)await sleep(200);
    const record={studio_pid:pid,owner_pid:ownerPid,exit_ms:Date.now()-start,studio_exited:!alive(pid),project_copy:opened.project,directory:started.directory,stderr};
    result[crash?'owner_crash':'stdin_eof']=record;
    assert.ok(record.studio_exited,JSON.stringify(record));assert.ok(fs.statSync(opened.project).size>0);
  }finally{
    await client.close();
    if(pid&&alive(pid))process.kill(pid,'SIGKILL');
  }
}
(async()=>{
  let session;
  try{
    await checkDisconnect(true);console.log('owner crash: PASS');
    await checkDisconnect(false);console.log('stdin EOF: PASS');
    session=new InvtSession(workspace);
    const started=await session.start();
    const realSend=session.ipc.sendCommand.bind(session.ipc);
    // Simulate a slow UI command, bypassing the public fixed-operation API only here.
    session.ipc.sendCommand=()=>realSend('import time\ntime.sleep(3)\nprint("slow command completed")\n',100);
    await assert.rejects(session.call({operation:'inspect'}),/timed out/i);
    assert.equal(session.status().state,'faulted');
    await assert.rejects(session.call({operation:'build'}),/not ready/i);
    const stop=await session.stop();
    result.timeout={studio_pid:started.pid,quarantined:true,replay_rejected:true,studio_exited:!alive(started.pid),stop};
    assert.ok(result.timeout.studio_exited);
    console.log('timeout quarantine: PASS');result.success=true;
  }catch(e){result.success=false;result.error=e.stack;console.error(e);process.exitCode=1;}
  finally{if(session)await session.stop().catch(()=>{});fs.writeFileSync(path.join(workspace,'analysis/persistent-lifecycle-result.json'),JSON.stringify(result,null,2));}
})();
