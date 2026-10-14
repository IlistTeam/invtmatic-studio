// Development-only installed API probe; no public arbitrary-script tool.
const {InvtSession}=require('../dist/invt-session');
const fs=require('fs'),path=require('path');
const workspace=path.resolve(__dirname,'../..'),session=new InvtSession(workspace);
(async()=>{
 try {
  console.log(JSON.stringify(await session.start()));
  await session.call({operation:'open_copy',project:'analysis/side-scriptengine-check/API_Check_v6.project'});
  const build=await session.call({operation:'build'});
  if(!build.build_ok)throw Error('Baseline compiler errors');
  const wire=await session.ipc.sendCommand(`import json\nimport scriptengine as se\nimport invt_operations as ops\nfrom invt_executor import with_executor\np=ops.owned()\na=ops.choose_application(list(p.get_children(True)),{})\nr={'application_guid':str(a.guid)}\nd=a.parent\nwhile d is not None and not hasattr(d,'get_simulation_mode'):\n    d=getattr(d,'parent',None)\nif d is None: raise RuntimeError('No owning simulation device')\nr['device']={'guid':str(d.guid),'name':d.get_name(),'address':unicode(d.get_address()),'before':d.get_simulation_mode()}\ni=d.get_device_identification()\nr['device']['identification']={'type':i.type,'id':i.id,'version':i.version}\nd.set_simulation_mode(True)\nr['device']['after']=d.get_simulation_mode()\np.save()\nif r['device']['after'] != True: raise RuntimeError('Simulation unverified')\np.active_application=a\no=with_executor(se.online.create_online_application,a)\nr['online_methods']=[x for x in dir(o) if not x.startswith('_')]\nr['online_type']=unicode(type(o))\nr['logged_in']=with_executor(lambda:o.is_logged_in)\nwith_executor(o.Dispose)\nprint('PROBE_RESULT:'+json.dumps(r,ensure_ascii=True))\n`,60000);
  fs.writeFileSync(path.join(workspace,'analysis/runtime-api-probe.json'),JSON.stringify(wire,null,2));
  console.log(JSON.stringify(wire));
 }catch(e){console.error(e);process.exitCode=1;}
 finally{console.log(JSON.stringify(await session.stop().catch(e=>({error:String(e)}))));}
})();
