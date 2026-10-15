"""Bounded large-array confirmation; one fresh process per case/tool/pass.

prepare-calibration -> run --stage calibration -> freeze --sizes JSON
-> run --stage formal -> verify. All run artifacts append-only; --resume
skips completed launches, retaining failed launches as failures (no retries).
"""
from pathlib import Path
import argparse,gzip,hashlib,json,math,os,queue,resource,shutil,signal,subprocess,threading,time
from protocol import sha,verify_hashes,read_rows
from run import own_rss
HERE=Path(__file__).resolve().parent
JULIA='/home/eriknovak/.julia/juliaup/julia-1.12.1+0.x64.linux.gnu/bin/julia'
DEPOT='/tmp/tamerop-c22-grid-depot:/tmp/tamerop-c22-construction-depot:/tmp/tamerop-q6q7-depot:/home/eriknovak/.julia'
LIMITS=dict(rss_bytes=8*1024**3,available_bytes=2*1024**3,phase_seconds=180,worker_seconds=1800,total_seconds=14400)
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def generate(out,c):
    import numpy as np
    path=out/'large_inputs'/('_'.join(map(str,c['shape']))+f"_{c['pattern']}_{c['seed']}.u16.gz")
    path.parent.mkdir(exist_ok=True);side=path.with_suffix('.json')
    if not side.exists():
        assert not path.exists()
        rng=np.random.Generator(np.random.PCG64(c['seed']));h=hashlib.sha256();n=math.prod(c['shape'])
        with path.open('wb') as stream,gzip.GzipFile(fileobj=stream,mode='wb',compresslevel=1,mtime=0,filename='') as f:
            for begin in range(0,n,1048576):
                size=min(1048576,n-begin)
                if c['pattern'] in ('noise','binary'):
                    vals=rng.integers(0,8 if c['pattern']=='noise' else 2,size=size,dtype=np.uint16)
                    if c['pattern']=='binary':vals*=4
                else:
                    inds=np.arange(begin,begin+size,dtype=np.int64);s=np.zeros(size,dtype=np.int64);stride=1
                    for dim in c['shape']:
                        v=2*((inds//stride)%dim)-(dim-1);s+=v*v;stride*=dim
                    s//=max(c['shape']);assert s.max()<=65535;vals=s.astype('<u2')
                raw=vals.astype('<u2',copy=False).tobytes();h.update(raw);f.write(raw)
        save(side,dict(input=str(path.relative_to(out)),raw_sha256=h.hexdigest(),compressed_sha256=sha(path),encoded_bytes=n*2,compressed_bytes=path.stat().st_size,generator='NumPy PCG64 integers UInt16 in 1048576-element blocks; smooth exact coordinate quadratic; little endian column-major; gzip level1 mtime0',numpy=np.__version__))
    c.update(json.loads(side.read_text()));return c

def case(d,conv,pattern,n,level,seed,order='sublevel',reserved=False):
    shape=list(n) if isinstance(n,list) else [n]*d
    return dict(id=f'{d}d_{conv}_{pattern}_{level}',shape=shape,convention=conv,pattern=pattern,level=level,seed=seed,order=order,reserved=reserved)
def prepare(out):
    p=out/'calibration_manifest.json';assert not p.exists();cases=[]
    for d in (2,3):
        for pattern in ('noise','binary','smooth'):
            n=(6144 if pattern=='smooth' else 4096) if d==2 else (256 if pattern=='smooth' else 160)
            for conv in ('V','T'):cases.append(generate(out,case(d,conv,pattern,n,'calibration',20261011)))
    save(p,dict(cases=cases,samples=1,passes=1,limits=LIMITS));print(p,flush=True)
def freeze(out,sizes):
    path=out/'formal_manifest.json';assert not path.exists()
    # Freeze all task specifications BEFORE generating reserved data.
    cases=[]
    for d in (2,3):
        for p in ('noise','binary','smooth'):
            levels=sizes[f'{d}d_{p}'];assert len(levels)==3 and levels==sorted(set(levels))
            for conv in ('V','T'):
                for i,n in enumerate(levels):cases.append(case(d,conv,p,n,f'size{i+1}',20261020+i))
                n=levels[1];shape=[n+7,n-11] if d==2 else [n+3,n-5,n+7]
                cases.append(case(d,conv,p,shape,'reserved',20261117,order='superlevel' if p!='noise' else 'sublevel',reserved=True))
    save(out/'TASK_FREEZE.json',dict(cases=cases,sizes=sizes,samples=3,passes=3,limits=LIMITS,weights='equal weight per case; 4 cases in each of 12 lane/structure strata',practical_band=[1/1.1,1.1],selection='absolute seconds and resource feasibility; no relative-performance selection',created=time.time()))
    for c in cases:generate(out,c)
    save(path,dict(cases=cases,samples=3,passes=3,limits=LIMITS));print(path,flush=True)
def binding(out):
    ch=json.loads((out/'candidate_hashes.json').read_text());verify_hashes(out/'candidate',ch)
    env=json.loads((out/'environment/ready.json').read_text())
    verify_hashes(out/'environment',env['extensions']);verify_hashes(out/'environment',env['binaries'])
    return dict(candidate_manifest=sha(out/'candidate_hashes.json'),environment=sha(out/'environment/ready.json'))
def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def launch(out,dest,c,tool,samples,total_start):
    dest.mkdir(parents=True);save(dest/'case.json',c)
    env={**os.environ,'JULIA_DEPOT_PATH':DEPOT,'JULIA_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','CRIPSER_NUM_THREADS':'1','JULIA_PKG_PRECOMPILE_AUTO':'0','PYTHONDONTWRITEBYTECODE':'1'}
    h=dest.parent.parent/'harness'
    cmd=([JULIA,'--startup-file=no','--compiled-modules=existing','--pkgimages=existing','--heap-size-hint=3G','--project='+str((out/'candidate').resolve()),str(h/'large_julia.jl')] if tool=='tamerop' else [str(out/'environment/venv/bin/python'),str(h/'large_python.py')])
    cpu=min(os.sched_getaffinity(0));cmd=['taskset','-c',str(cpu),*cmd,str(out),str(dest/'case.json'),str(samples),str(dest)]
    save(dest/'launch.json',dict(command=cmd,cpu=cpu,environment={k:env[k] for k in ('JULIA_DEPOT_PATH','JULIA_NUM_THREADS','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','CRIPSER_NUM_THREADS')}))
    start=time.monotonic();phase_start=start;phase='startup';last=0;reason=None;q=queue.Queue()
    with (dest/'stdout.ndjson').open('w') as log,(dest/'stderr.log').open('w') as err,(dest/'monitor.ndjson').open('w') as mon:
        proc=subprocess.Popen(cmd,cwd=out,env=env,stdout=subprocess.PIPE,stderr=err,text=True,start_new_session=True,preexec_fn=no_core)
        save(dest/'process.json',dict(pid=proc.pid,process_group=proc.pid,started_unix=time.time(),case=c['id'],tool=tool))
        def reader():
            for line in proc.stdout:q.put(line)
        thread=threading.Thread(target=reader);thread.start()
        while proc.poll() is None or thread.is_alive() or not q.empty():
            try:line=q.get(timeout=.2)
            except queue.Empty:line=None
            if line:
                log.write(line);log.flush()
                try:r=json.loads(line)
                except json.JSONDecodeError:r={}
                if r.get('kind')=='start':phase=r['phase'];phase_start=time.monotonic()
                if r.get('kind')=='sample':print(c['id'],tool,r['sample'],round(r['seconds'],3),'s',flush=True)
            now=time.monotonic()
            if now-last>=.5:
                last=now;rss=own_rss(proc.pid);avail=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))*1024
                mon.write(json.dumps(dict(seconds=now-start,phase=phase,rss_bytes=rss,available_bytes=avail,loadavg=os.getloadavg()))+'\n');mon.flush()
                if reason is None and proc.poll() is None:
                    if rss>LIMITS['rss_bytes']:reason='rss_limit'
                    elif avail<LIMITS['available_bytes']:reason='system_available_limit'
                    elif now-phase_start>LIMITS['phase_seconds']:reason='phase_timeout'
                    elif now-start>LIMITS['worker_seconds']:reason='worker_timeout'
                    elif now-total_start>LIMITS['total_seconds']:reason='campaign_timeout'
                    if reason:
                        os.killpg(proc.pid,signal.SIGTERM)
                        try:proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        thread.join();code=proc.wait()
    rows=read_rows(dest/'stdout.ndjson');accepted=[r for r in rows if r.get('kind')=='sample' and r['accepted']]
    complete=code==0 and reason is None and len(accepted)==samples and any(r.get('kind')=='complete' for r in rows)
    result=dict(case=c['id'],tool=tool,complete=complete,reason=reason,returncode=code,seconds=time.monotonic()-start)
    save(dest/'completion.json',result);print('DONE',c['id'],tool,result,flush=True)
    return result

def qualification_gate(out,cases):
    q=json.loads((out/'qualification.json').read_text())
    assert not q['protocol_errors']
    assert q['candidate_manifest_sha256']==sha(out/'candidate_hashes.json')
    assert q['environment_sha256']==sha(out/'environment/ready.json')
    qm=json.loads((out/'manifest.json').read_text());qc={c['id']:c for c in qm['cases']}
    for c in cases:
        assert len(c['shape']) in (2,3) and min(c['shape'])>1
        lane=[len(c['shape']),c['convention'],c['order'],False,False]
        controls=[v for v in q['cases'] if v['lane']==lane and min(qc[v['case']]['shape'])>1]
        assert controls and all(v['status']=='verified' for v in controls),('unqualified non-singleton lane',lane)
    controls=json.loads((out/'harness_controls/independent_verification.json').read_text())
    assert controls['all_passed'] and controls['cases']==12
    packed=json.loads((out/'packed_verification.json').read_text())
    assert packed['passed']==12 and packed['canonicalizer_sha256']==sha(HERE/'large_outputs.py')

def run(out,stage,ids=None,resume=False):
    mpath=out/f'{stage}_manifest.json';m=json.loads(mpath.read_text());run=out/f'{stage}_run';start=time.monotonic()
    if stage=='formal':qualification_gate(out,m['cases'])
    if run.exists():assert resume
    else:
        run.mkdir();(run/'harness').mkdir()
        for name in ('large_study.py','large_python.py','large_outputs.py','large_julia.jl','large_analyze.py','protocol.py','run.py'):shutil.copy2(HERE/name,run/'harness'/name)
        save(run/'binding.json',dict(**binding(out),manifest_sha256=sha(mpath),harness={p.name:sha(p) for p in (run/'harness').iterdir()},host=dict(uname=list(os.uname()),cpu=next(l.split(':',1)[1].strip() for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),logical_cpus=os.cpu_count(),meminfo=Path('/proc/meminfo').read_text(),user_context='other heavy computations paused')))
    b=json.loads((run/'binding.json').read_text());assert b['manifest_sha256']==sha(mpath);assert all(binding(out)[k]==b[k] for k in ('candidate_manifest','environment'))
    verify_hashes(run/'harness',b['harness'])
    cases=[c for c in m['cases'] if ids is None or c['id'] in ids.split(',')]
    already=sum(json.loads(p.read_text())['seconds'] for p in run.glob('p*/*/completion.json'))
    start-=already
    for pas in range(1,m['passes']+1):
        for i,c in enumerate(cases):
            for tool in (('tamerop','cubicalripser') if (pas+i)%2 else ('cubicalripser','tamerop')):
                dest=run/f'p{pas}'/(c['id']+'_'+tool)
                if (dest/'completion.json').exists():continue
                if time.monotonic()-start>=LIMITS['total_seconds']:return
                if dest.exists():raise RuntimeError('incomplete launch retained; inspect before resuming: '+str(dest))
                launch(out,dest,c,tool,m['samples'],start)
    binding(out);save(run/'finished.json',dict(seconds_this_invocation=time.monotonic()-start))

def verify(out,stage):
    mpath=out/f'{stage}_manifest.json';m=json.loads(mpath.read_text());run=out/f'{stage}_run';b=json.loads((run/'binding.json').read_text());assert b['manifest_sha256']==sha(mpath)
    assert all(binding(out)[k]==b[k] for k in ('candidate_manifest','environment'));verify_hashes(run/'harness',b['harness'])
    results=[];errors=[]
    for c in m['cases']:
        ref=None;inputhash=None;case_result=dict(case=c['id'],verified=True,samples=0,intervals=None,failures=[])
        for pas in range(1,m['passes']+1):
            for tool in ('tamerop','cubicalripser'):
                d=run/f'p{pas}'/(c['id']+'_'+tool)
                if not (d/'completion.json').exists():case_result['failures'].append(f'{pas}/{tool}: missing');continue
                complete=json.loads((d/'completion.json').read_text())
                if not complete['complete']:case_result['failures'].append(complete);continue
                rows=read_rows(d/'stdout.ndjson');samples=[r for r in rows if r.get('kind')=='sample' and r['accepted']]
                assert len(samples)==m['samples'] and {r['sample'] for r in samples}==set(range(1,m['samples']+1))
                for r in samples:
                    assert r['reset_verified'] and r['seconds']>0
                    if tool=='tamerop':assert r['compile_seconds']==r['recompile_seconds']==0
                    p=d/r['output'];assert sha(p)==r['output_sha256'];hist=json.loads(p.read_text())
                    assert sum(row[3] for row in hist)==r['intervals']
                    assert all(row[3]>0 and row[3]==int(row[3]) and 0<=row[0]<len(c['shape']) and (row[2] is None or row[1]<row[2]) for row in hist)
                    if ref is None:ref=hist;inputhash=r['input_sha256']
                    assert hist==ref,(c['id'],pas,tool,'barcode mismatch');assert r['input_sha256']==inputhash
                    case_result['samples']+=1;case_result['intervals']=r['intervals']
        case_result['verified']=not case_result['failures'];results.append(case_result)
    save(run/'verification.json',dict(cases=results,verified=sum(r['verified'] for r in results),total=len(results),samples=sum(r['samples'] for r in results),bindings_verified=True))
    print(json.dumps(dict(verified=sum(r['verified'] for r in results),total=len(results),samples=sum(r['samples'] for r in results))),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare-calibration','freeze','run','verify']);p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',choices=['calibration','formal'],default='calibration');p.add_argument('--sizes',type=Path);p.add_argument('--ids');p.add_argument('--resume',action='store_true');a=p.parse_args();out=a.out.resolve()
    if a.action=='prepare-calibration':prepare(out)
    elif a.action=='freeze':freeze(out,json.loads(a.sizes.read_text()))
    elif a.action=='run':run(out,a.stage,a.ids,a.resume)
    else:verify(out,a.stage)
if __name__=='__main__':main()
