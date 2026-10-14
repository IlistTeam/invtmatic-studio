/** INVT session lifecycle; upstream IPC + watcher, owned processes only. */
import * as fs from 'fs';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import { randomUUID, createHash } from 'crypto';
import { IpcClient, DEFAULT_IPC_CONFIG } from './ipc';
import { ScriptManager } from './script-manager';

export const INVT_EXE = 'C:\\INVT\\Invtmatic Studio V3.0.1.4\\CODESYS\\Common\\Invtmatic Studio.exe';
export const INVT_PROFILE = 'Invtmatic Studio V3.0';
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));
export function vendorArgs(profile: string, script: string): string[] {
  for (const value of [profile, script]) {
    if (/["\r\n\0]/.test(value) || value.endsWith('\\')) throw new Error('Invalid launch argument');
  }
  return [`--profile="${profile}"`, `--runscript="${script}"`];
}
export function inside(root: string, value: string): boolean {
  const relative = path.relative(root, value);
  return relative !== '' && relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative);
}

export class InvtSession {
  private child: ChildProcess | null = null;
  private ipc: IpcClient | null = null;
  private directory: string | null = null;
  private state = 'stopped';
  private lastError: string | null = null;
  private pending: Promise<any> | null = null;
  private projectCopy: string | null = null;
  private source: string | null = null;
  private sourceHash: string | null = null;
  readonly workspace: string;
  constructor(workspace: string, private exe = INVT_EXE, private profile = INVT_PROFILE,
              private timeout = 60000) {
    this.workspace = fs.realpathSync(workspace);
    if (!Number.isFinite(timeout) || timeout < 100 || timeout > 180000) throw new Error('Invalid command timeout');
  }
  status(): any {
    return { state: this.state, pid: this.child?.pid ?? null, directory: this.directory,
      project_copy: this.projectCopy, source_project: this.source, source_sha256: this.sourceHash,
      busy: !!this.pending, last_error: this.lastError, runtime_scope: 'verified_simulation_only', physical_runtime_allowed: false };
  }
  private exclusive<T>(operation: () => Promise<T>): Promise<T> {
    if (this.pending) return Promise.reject(new Error('Session busy; wait for current command'));
    const promise = operation();
    this.pending = promise;
    return promise.finally(() => { if (this.pending === promise) this.pending = null; });
  }
  async start(): Promise<any> {
    return this.exclusive(async () => {
      if (this.state === 'ready') return this.status();
      if (this.child) throw new Error('Stop the existing session before restarting');
      if (!fs.statSync(this.exe).isFile()) throw new Error('Studio executable is not a file');
      this.state = 'starting'; this.lastError = null;
      const root = path.join(this.workspace, '.invt');
      fs.mkdirSync(root, {recursive:true});
      if (!inside(this.workspace, fs.realpathSync(root))) throw new Error('Session root outside workspace');
      const sessionRoot = path.join(root, 'persistent');
      fs.mkdirSync(sessionRoot, {recursive:true});
      if (!inside(this.workspace, fs.realpathSync(sessionRoot))) throw new Error('Session root outside workspace');
      this.directory = path.join(sessionRoot, randomUUID());
      fs.mkdirSync(this.directory);
      const manager = new ScriptManager();
      for (const name of ['invt_project.py', 'invt_operations.py', 'invt_creation.py', 'invt_tasks.py', 'invt_runtime.py', 'invt_executor.py']) {
        fs.copyFileSync(path.join(__dirname,'scripts',name), path.join(this.directory,name));
      }
      const watcher = path.join(this.directory, 'watcher.py');
      fs.writeFileSync(watcher, manager.prepareScript('invt_watcher', {IPC_BASE_DIR:this.directory}), 'utf8');
      this.ipc = new IpcClient({ ...DEFAULT_IPC_CONFIG, baseDir:this.directory,
        pollIntervalMs:25, maxPollIntervalMs:100, deleteResultAfterRead:false });
      await this.ipc.ensureDirectories();
      const out = fs.openSync(path.join(this.directory,'stdout.log'),'w');
      const err = fs.openSync(path.join(this.directory,'stderr.log'),'w');
      const child = spawn(this.exe, vendorArgs(this.profile,watcher), {
        shell:false, windowsVerbatimArguments:true, windowsHide:true, cwd:path.dirname(this.exe),
        stdio:['ignore',out,err], env:{...process.env, INVT_MCP_OWNER_PID:String(process.pid), INVT_IPC_SESSION:this.directory}
      });
      fs.closeSync(out); fs.closeSync(err);
      this.child = child;
      child.on('exit', () => {
        if (this.child !== child) return;
        this.child = null;
        if (this.state !== 'stopping') { this.state = 'faulted'; this.lastError = 'Studio process exited'; }
      });
      child.on('error', e => {this.lastError=String(e);this.state='faulted';});
      fs.writeFileSync(path.join(this.directory,'owner.json'),JSON.stringify({owner_pid:process.pid,studio_pid:child.pid,profile:this.profile}));
      try {
        const deadline = Date.now()+90000;
        while (!(await this.ipc.isReady())) {
          if (this.state === 'faulted' || Date.now()>deadline) throw new Error(this.lastError ?? 'Startup timeout');
          await sleep(100);
        }
        const pong = await this.execute({operation:'ping'});
        if (!pong.ok || pong.pid !== child.pid) throw new Error('Primary-thread handshake failed');
        this.state = 'ready';
        return this.status();
      } catch(e) {
        await this.killOwned(); this.state='faulted'; this.lastError=String(e); throw e;
      }
    });
  }
  private async execute(request: any): Promise<any> {
    const encoded = Buffer.from(JSON.stringify(request),'utf8').toString('base64');
    const code = `import json, base64\nimport invt_operations\nrequest = json.loads(base64.b64decode("${encoded}").decode("utf-8"))\nprint("INVT_RESULT:" + json.dumps(invt_operations.dispatch(request), ensure_ascii=True))\n`;
    const start = Date.now();
    const wire = await this.ipc!.sendCommand(code, this.timeout);
    if (!wire.success) throw new Error(wire.error || 'Watcher execution failed');
    const lines = wire.output.split(/\r?\n/).filter(l=>l.startsWith('INVT_RESULT:'));
    if (lines.length!==1) throw new Error('Missing or ambiguous structured result');
    const result = JSON.parse(lines[0].slice('INVT_RESULT:'.length));
    result.elapsed_ms = Date.now()-start;
    result.request_id = wire.requestId;
    result.result_file = path.join(this.directory!, 'results', wire.requestId+'.report.json');
    fs.writeFileSync(result.result_file,JSON.stringify(result,null,2),'utf8');
    return result;
  }
  async call(request: any): Promise<any> {
    return this.exclusive(async () => {
      if (this.state!=='ready') throw new Error('Session not ready; start or restart it');
      const prepared = {...request};
      let copy: string | null = null;
      if (request.operation==='open_copy') {
        if (this.projectCopy) throw new Error('Close the current project before opening another');
        const source = fs.realpathSync(path.resolve(this.workspace,request.project));
        if (!inside(this.workspace, source) || path.extname(source).toLowerCase()!=='.project') throw new Error('Project must be inside workspace');
        const content = fs.readFileSync(source);
        const digest = createHash('sha256').update(content).digest('hex');
        if (request.expected_sha256 && request.expected_sha256!==digest) throw new Error('Source hash mismatch');
        const dir = path.join(this.directory!,'projects',randomUUID());
        fs.mkdirSync(dir,{recursive:true});
        copy = path.join(dir,path.basename(source));
        fs.writeFileSync(copy,content); prepared.project=copy;
        this.source=source; this.sourceHash=digest;
      }
      if (request.operation==='export_pou') {
        prepared.export_directory=path.join(this.directory!,'exports',randomUUID());
        fs.mkdirSync(prepared.export_directory,{recursive:true});
      }
      try {
        if (request.operation==='monitor_variables') {
          const started=performance.now(), samples:any[]=[];
          do {
            const sample=await this.execute({...prepared,operation:'read_variables'});
            samples.push({elapsed_ms:performance.now()-started,...sample});
            if (!sample.ok) return {ok:false,target:sample.target,samples,reason:'Polling stopped on read/connection error',atomic:false};
            const remaining=request.duration_ms-(performance.now()-started);
            if(remaining<=0)break;
            await sleep(Math.min(request.interval_ms,remaining));
          } while(performance.now()-started<request.duration_ms && samples.length<200);
          return {ok:true,target:samples[0].target,samples,atomic:false,
            duration_ms_actual:performance.now()-started,interval_ms_requested:request.interval_ms,
            timing:'Host monotonic deadlines; sequential IPC reads, no scan synchronization'};
        }
        const result = await this.execute(prepared);
        if (copy && result.ok) this.projectCopy=copy;
        if (request.operation==='close_project' && result.ok) this.projectCopy=null;
        if (this.source) result.source_unchanged=createHash('sha256').update(fs.readFileSync(this.source)).digest('hex')===this.sourceHash;
        return result;
      } catch(e) {
        // A timeout does not cancel execution on the UI thread. Quarantine the
        // session; do not submit another mutation or automatically replay it.
        this.state='faulted'; this.lastError=String(e); throw e;
      }
    });
  }
  private async killOwned(): Promise<void> {
    const child=this.child;
    if (!child) return;
    child.kill();
    await Promise.race([new Promise<void>(r=>child.once('exit',()=>r())),sleep(5000)]);
    if (child.exitCode===null && child.signalCode===null) throw new Error('Owned Studio process did not exit');
    if(this.child===child)this.child=null;
  }
  async stop(): Promise<any> {
    if(this.pending) await this.pending.catch(()=>{});
    return this.exclusive(async()=>{
      const wasFaulted=this.state==='faulted';
      this.state='stopping';
      let graceful=false;
      let cleanupError:string|null=null;
      if(this.child && this.ipc && !wasFaulted) {
        try {
          const answer=await this.execute({operation:'prepare_shutdown'});
          if(!answer.ok && answer.reason==='unowned_project') {
            // User opened another project in our window. Release the watcher but
            // preserve that window and its contents; never kill an unowned project.
            await this.ipc.sendTerminate();
            this.child.unref(); this.child=null; this.state='released';
            return {ok:false,state:'released',reason:'Unowned project preserved'};
          }
          if(!answer.ok)throw new Error('Owned project/runtime cleanup failed: '+JSON.stringify(answer));
          fs.writeFileSync(path.join(this.directory!,'exit.signal'),'');
          const until=Date.now()+10000;
          while(this.child && Date.now()<until)await sleep(100);
          graceful=!this.child;
        } catch(e) {this.lastError=String(e);cleanupError=String(e);}
      }
      await this.killOwned();
      this.state='stopped'; this.ipc=null; this.projectCopy=null;
      return {ok:!cleanupError,graceful,directory:this.directory,cleanup_error:cleanupError};
    });
  }
}
