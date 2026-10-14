// Development-only comparison of documented task call comment APIs.
const {InvtSession}=require('../dist/invt-session');
const fs=require('fs'),path=require('path');
const workspace=path.resolve(__dirname,'../..');
const session=new InvtSession(workspace);
(async()=>{
 try{
  await session.start();
  await session.call({operation:'open_copy',project:'analysis/side-scriptengine-check/API_Check_v6.project'});
  const program=await session.call({operation:'create_pou',name:'PRG_CommentProbe',pou_type:'program',
    declaration:'PROGRAM PRG_CommentProbe\nVAR\n    xState : BOOL;\nEND_VAR',implementation:'xState := FALSE;'});
  if(!program.ok)throw Error(JSON.stringify(program));
  const task=await session.call({operation:'create_task',name:'Task_CommentProbe',interval_ms:20,priority:20});
  if(!task.ok)throw Error(JSON.stringify(task));
  // No public arbitrary-script tool is added; this harness uses the private IPC
  // only on its own disposable process/copy to verify documented native methods.
  const wire=await session.ipc.sendCommand(`import json\nimport invt_operations\np=invt_operations.owned()\nt=[o for o in p.get_children(True) if o.get_name()=='Task_CommentProbe'][0]\nr={}\nt.pous.add('PRG_CommentProbe','ASCII add')\nr['add']=list(t.pous[len(t.pous)-1])\nt.pous.replace(len(t.pous)-1,'PRG_CommentProbe','ASCII replace')\nr['replace']=list(t.pous[len(t.pous)-1])\nt.pous.insert(0,'PRG_CommentProbe','ASCII insert')\nr['insert']=list(t.pous[0])\np.save()\nr['after_save']=[list(t.pous[i]) for i in range(len(t.pous))]\nprint(json.dumps(r,ensure_ascii=True))\n`,60000);
  fs.writeFileSync(path.join(workspace,'analysis/task-comments-probe.json'),JSON.stringify(wire,null,2));
  console.log(JSON.stringify(wire,null,2));
 }catch(e){console.error(e);process.exitCode=1;}
 finally{await session.stop().catch(e=>console.error(e));}
})();
