const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {vendorArgs,inside,InvtSession}=require('../dist/invt-session');
const workspace=path.resolve(__dirname,'../..');
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
