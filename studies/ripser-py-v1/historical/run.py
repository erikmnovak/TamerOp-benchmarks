"""Serial, resumable, bounded supervisor. Stops only its own worker processes."""
import os
import argparse,json,os,subprocess,time,threading,queue,hashlib,shutil
from pathlib import Path
ROOT=Path('/home/eriknovak/Documents/projects/TamerOp.jl');HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get('RIPSER_STUDY_DIR',str(ROOT/'audit/2026-10-04/ripser_pilot')))
JULIA='/home/eriknovak/.julia/juliaup/julia-1.12.1+0.x64.linux.gnu/bin/julia'
def read_rows(p):
    out=[]
    if p.exists():
        for l in p.read_text().splitlines():
            try:out.append(json.loads(l))
            except json.JSONDecodeError:pass
    return out

def run(tool,pas,ids):
    base=OUT/'runs';base.mkdir(exist_ok=True)
    index=1+max([int(p.name.split('_')[0]) for p in base.iterdir() if p.is_dir()]+[0])
    dest=base/f'{index:03d}_{tool}_p{pas}';dest.mkdir();(dest/'outputs').mkdir()
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',JULIA_NUM_THREADS='1',JULIA_PKG_PRECOMPILE_AUTO='0',JULIA_DEPOT_PATH='/tmp/tamerop-q6q7-depot:/home/eriknovak/.julia',RIPSER_OUTPUT_DIR=str(dest/'outputs'))
    cmd=([str(OUT/'venv/bin/python'),str(HERE/'python_worker.py')] if tool=='ripser' else [JULIA,'--startup-file=no','--compiled-modules=existing','--pkgimages=existing',f'--project={OUT / "candidate"}',str(HERE/'julia_worker.jl')])+[str(OUT),str(pas),','.join(ids)]
    shutil.copy2(HERE/('python_worker.py' if tool=='ripser' else 'julia_worker.jl'),dest/'worker_source.txt')
    (dest/'launch.json').write_text(json.dumps(dict(command=cmd,tool=tool,pass_id=pas,ids=ids,environment={k:env[k] for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','JULIA_NUM_THREADS','JULIA_DEPOT_PATH')},worker_sha256=hashlib.sha256((HERE/('python_worker.py' if tool=='ripser' else 'julia_worker.jl')).read_bytes()).hexdigest()),indent=2))
    log=(dest/'stdout.ndjson').open('w');err=(dest/'stderr.log').open('w');monitor=(dest/'monitor.ndjson').open('w')
    cmd=['taskset','-c','0']+cmd
    proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
    q=queue.Queue()
    def reader():
        for line in proc.stdout:q.put(line)
    t=threading.Thread(target=reader);t.start()
    begin=time.monotonic();phase_start=begin;current=None;phase='startup';last=0;completed=[];failed=[];reason=None
    while proc.poll() is None or t.is_alive() or not q.empty():
        try:line=q.get(timeout=.2)
        except queue.Empty:line=None
        if line:
            log.write(line);log.flush()
            try:r=json.loads(line)
            except json.JSONDecodeError:r={}
            if r.get('kind')=='start':current=r['case'];phase=r['phase'];phase_start=time.monotonic()
            if r.get('kind') in ('case_complete','case_error'):
                (completed if r['kind']=='case_complete' else failed).append(r['case']);print(tool,pas,r['kind'],r['case'],r.get('error','')[:160],flush=True)
            if r.get('kind')=='environment':print(tool,pas,'loaded',round(r['load_seconds'],2),'seconds',flush=True)
        now=time.monotonic()
        if now-last>1:
            last=now;rss=0
            try:
                s=Path(f'/proc/{proc.pid}/status').read_text();rss=int(next(l.split()[1] for l in s.splitlines() if l.startswith('VmRSS:')))*1024
            except (OSError,StopIteration):pass
            monitor.write(json.dumps(dict(elapsed=now-begin,case=current,phase=phase,rss_bytes=rss,loadavg=Path('/proc/loadavg').read_text().strip()))+'\n');monitor.flush()
            cap=M['limits']['startup_seconds'] if phase=='startup' else M['limits']['phase_seconds']
            if not reason and (rss>M['limits']['rss_bytes'] or now-phase_start>cap or now-begin>M['limits']['worker_seconds']):
                reason='memory_limit' if rss>M['limits']['rss_bytes'] else 'time_limit';print(tool,current,reason,phase,flush=True)
                proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
    proc.wait();log.close();err.close();monitor.close()
    if reason and current not in completed and current not in failed:failed.append(current)
    if proc.returncode and not reason:
        reason='worker_exit'
        if current and current not in completed and current not in failed:failed.append(current)
    summary=dict(tool=tool,pass_id=pas,completed=completed,failed=failed,reason=reason,returncode=proc.returncode,seconds=time.monotonic()-begin)
    (dest/'completion.json').write_text(json.dumps(summary,indent=2))
    if not completed and not failed:raise RuntimeError(f'Worker failed before case start: {dest}')
    return completed+failed
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ids',default='all');ap.add_argument('--passes',default='1,2,3,4');ap.add_argument('--tools',default='both');ap.add_argument('--retry-errors',action='store_true');ap.add_argument('--rerun',action='store_true');a=ap.parse_args()
    M=json.loads((OUT/'manifest.json').read_text());assert json.loads((OUT/'build_verified.json').read_text())['robinhood_macro_verified']
    for rel,dig in json.loads((OUT/'build_verified.json').read_text())['binaries'].items():assert hashlib.sha256((OUT/rel).read_bytes()).hexdigest()==dig
    for rel,dig in json.loads((OUT/'candidate_hashes.json').read_text()).items():assert hashlib.sha256((OUT/'candidate'/rel).read_bytes()).hexdigest()==dig
    ids=[c['id'] for c in M['cases'] if a.ids=='all' or c['id'] in a.ids.split(',')]
    for pas in map(int,a.passes.split(',')):
        if pas%2==0: ids=list(reversed(ids))
        for tool in (['tamerop','ripser'] if pas%2 else ['ripser','tamerop']):
            if a.tools!='both' and tool!=a.tools:continue
            done=set()
            for f in sorted((OUT/'runs').glob('*/completion.json')) if (OUT/'runs').exists() else []:
                s=json.loads(f.read_text())
                if s['tool']==tool and s['pass_id']==pas:done.update(s['completed']+([] if a.retry_errors else s['failed']))
            pending=[i for i in ids if a.rerun or i not in done]
            while pending:
                finished=run(tool,pas,pending);pending=[i for i in pending if i not in finished]
        if pas%2==0: ids=list(reversed(ids))
