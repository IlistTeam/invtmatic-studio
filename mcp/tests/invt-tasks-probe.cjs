const {Client}=require('@modelcontextprotocol/sdk/client/index.js');
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
const fs=require('fs'),path=require('path');
const workspace=path.resolve(__dirname,'../..');
const transport=new StdioClientTransport({command:process.execPath,args:[path.resolve(__dirname,'../dist/invt-server.js'),'--workspace',workspace],env:{...process.env},stderr:'inherit'});
const client=new Client({name:'INVT-task-API-probe',version:'1'});
async function call(name,args={}){
 const wire=await client.callTool({name,arguments:args},undefined,{timeout:180000});
 const r=JSON.parse(wire.content.find(c=>c.type==='text').text);
 if(wire.isError)throw Error(JSON.stringify(r));return r;
}
(async()=>{
 try{
  await client.connect(transport);await call('invt_session_start');
  await call('invt_open_copy',{project:'analysis/side-scriptengine-check/API_Check_v6.project'});
  const result=await call('invt_inspect_tasks');
  fs.writeFileSync(path.join(workspace,'analysis/task-api-probe.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result,null,2));
 }catch(e){console.error(e);process.exitCode=1;}
 finally{await call('invt_session_stop').catch(()=>{});await client.close();}
})();
