const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {vendorArgs,inside,InvtSession}=require('../dist/invt-session');
const workspace=path.resolve(__dirname,'../..');

test('physical discovery requires explicit host opt-in before an IDE command',async()=>{
  const session=new InvtSession(workspace);session.state='ready';let called=false;
  session.execute=async()=>{called=true;return {ok:true};};
  await assert.rejects(session.call({operation:'plc_find'}),/not enabled/);
  assert.equal(called,false);
  assert.equal(session.status().state,'ready');
  assert.equal(session.status().physical_runtime_allowed,false);
});

test('physical discovery refuses public, loopback, malformed and broadcast addresses',()=>{
  for(const address of ['8.8.8.8','127.0.0.1','224.0.0.1','192.168.03.10','192.168.3.255','192.168.3.0','192.168.3.10\n']) {
    assert.throws(()=>new InvtSession(workspace,undefined,undefined,60000,address),/private unicast/);
  }
  const session=new InvtSession(workspace,undefined,undefined,60000,'192.168.3.10');
  assert.equal(session.status().physical_address,'192.168.3.10');
  assert.equal(session.status().physical_runtime_allowed,false);
});

test('an address alone cannot enable physical runtime tools',async()=>{
  assert.throws(()=>new InvtSession(workspace,undefined,undefined,60000,undefined,true),/explicit PLC address/);
  const session=new InvtSession(workspace,undefined,undefined,60000,'192.168.3.10');
  session.state='ready';let called=false;session.execute=async()=>{called=true;return {ok:true};};
  await assert.rejects(session.call({operation:'plc_download'}),/runtime was not enabled/);
  assert.equal(called,false);assert.equal(session.status().state,'ready');
});
test('HALT refusal keeps session ready and never kills or resumes its child',async()=>{
  const session=new InvtSession(workspace);let killed=false;
  session.state='ready';session.child={};session.ipc={};
  session.execute=async()=>({ok:false,reason:'halt_requires_explicit_stop'});
  session.killOwned=async()=>killed=true;
  const result=await session.stop();assert.equal(result.reason,'halt_requires_explicit_stop');
  assert.equal(session.status().state,'ready');assert.equal(killed,false);
});
test('late unowned-project shutdown acknowledgement preserves the window',async()=>{
  const fs=require('fs'),os=require('os');
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'invt-shutdown-ack-'));
  try {
    fs.writeFileSync(path.join(directory,'shutdown_ack.json'),JSON.stringify({owned_cleanup_confirmed:false}));
    const session=new InvtSession(workspace);let released=false;
    session.directory=directory;session.state='ready';session.child={unref:()=>released=true};session.ipc={};
    session.execute=async()=>({ok:true});session.killOwned=async()=>{throw Error('Must not kill the preserved window');};
    const result=await session.stop();assert.equal(result.state,'released');assert.equal(released,true);
  } finally {
    for(const name of ['shutdown_ack.json','exit.signal']){const file=path.join(directory,name);if(fs.existsSync(file))fs.unlinkSync(file);}
    fs.rmdirSync(directory);
  }
});
test('vendor arguments quote values and reject quote injection',()=>{
  assert.deepEqual(vendorArgs('Invtmatic Studio V3.0','E:\\work space\\launch.py'),['--profile="Invtmatic Studio V3.0"','--runscript="E:\\work space\\launch.py"']);
  for(const s of ['bad"value','bad\nvalue','bad\0value','bad\\'])assert.throws(()=>vendorArgs(s,'x.py'));
});
test('workspace scope excludes parent, same directory, sibling and other drive',()=>{
  assert.equal(inside('E:\\work','E:\\work\\copy.project'),true);
  for(const s of ['E:\\work','E:\\work-other\\x','E:\\x','C:\\work\\x'])assert.equal(inside('E:\\work',s),false);
});
test('concurrent mutation is rejected without queueing a later edit',async()=>{
  const session=new InvtSession(workspace);session.state='ready';
  let finish;session.execute=()=>new Promise(r=>finish=r);
  const first=session.call({operation:'inspect'});
  await assert.rejects(session.call({operation:'build'}),/busy/);
  finish({ok:true});await first;assert.equal(session.status().busy,false);
});
test('compiler error keeps session usable; transport failure quarantines it',async()=>{
  const session=new InvtSession(workspace);session.state='ready';
  session.execute=async()=>({ok:false,build_ok:false});
  assert.equal((await session.call({operation:'build'})).ok,false);assert.equal(session.status().state,'ready');
  session.execute=async()=>{throw new Error('transport failure');};
  await assert.rejects(session.call({operation:'build'}),/transport failure/);
  assert.equal(session.status().state,'faulted');
  await assert.rejects(session.call({operation:'build'}),/not ready/);
});
test('source hash mismatch is refused before a project copy or UI command',async()=>{
  const session=new InvtSession(workspace);session.state='ready';let called=false;
  session.execute=async()=>{called=true;return {ok:true};};
  await assert.rejects(session.call({operation:'open_copy',project:'analysis/side-scriptengine-check/API_Check_v6.project',expected_sha256:'0'.repeat(64)}),/hash mismatch/);
  assert.equal(called,false);assert.equal(session.status().state,'ready');
});
test('owned cleanup error is reported and never mistaken for a foreign project',async()=>{
  const session=new InvtSession(workspace);session.state='ready';session.child={};session.ipc={};
  session.execute=async()=>({ok:false,exception:'runtime cleanup error'});
  let killed=false;session.killOwned=async()=>{killed=true;session.child=null;};
  const result=await session.stop();
  assert.equal(killed,true);assert.equal(result.ok,false);assert.match(result.cleanup_error,/runtime cleanup error/);
  assert.equal(session.status().state,'stopped');
});
test('explicit foreign project refusal preserves the unrelated window',async()=>{
  const session=new InvtSession(workspace);session.state='ready';let released=false;
  session.child={unref:()=>released=true};session.ipc={sendTerminate:async()=>{}};
  session.execute=async()=>({ok:false,reason:'unowned_project'});
  session.killOwned=async()=>{throw Error('Must not kill a foreign project');};
  const result=await session.stop();assert.equal(released,true);assert.equal(result.state,'released');
});
