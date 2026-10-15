"""Bounded comparison through unchanged Ripser CLI and TamerOp public API."""
import argparse, collections, hashlib, itertools, json, math, os, queue, re
import shutil, statistics, subprocess, sys, threading, time
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[2]
JULIA='/home/eriknovak/.julia/juliaup/julia-1.12.1+0.x64.linux.gnu/bin/julia'
FIELDS=(2,3,101)
LIMIT=240
RSS_LIMIT=6*1024**3
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+'\n')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def append(path,obj):
    with path.open('a') as f:f.write(json.dumps(obj)+'\n')
def status(pid):
    try:
        s=Path(f'/proc/{pid}/status').read_text()
        return {key:int(re.search(r'^'+key+r':\s+(\d+)',s,re.M)[1])*1024 for key in ['VmRSS','VmHWM']}
    except (OSError,TypeError):return {}
def canonical(ds):
    return [sorted([[float(b),None if d is None else float(d)] for b,d in diag],key=lambda x:(x[0],math.inf if x[1] is None else x[1])) for diag in ds]
def grade_decoder(path,fmt):
    raw=np.loadtxt(path)
    vals=raw[:,2] if fmt=='sparse' else raw.ravel()
    lookup={}
    for v in np.unique(np.r_[0,vals]):
        key=format(float(v),'.6g')
        if key in lookup and lookup[key]!=float(v):raise ValueError('CLI printed-grade collision')
        lookup[key]=float(v)
    return lookup
def parse_cpp(text,c,lookup):
    diagrams=[[] for _ in range(c['degree']+1)];dim=None
    for line in text.splitlines():
        m=re.search(r'persistence intervals in dim (\d+):',line)
        if m:dim=int(m[1]);continue
        m=re.fullmatch(r'\s*\[\s*([^,]+),\s*([^)]*)\)',line)
        if m:
            assert dim is not None and 0<=dim<=c['degree']
            b=lookup[format(float(m[1]),'.6g')]
            d=lookup[format(float(m[2]),'.6g')] if m[2].strip() else None
            assert d is None or d>b
            diagrams[dim].append([b,d])
    assert dim is not None and diagrams[0], 'missing CLI output'
    return canonical(diagrams)
def matrix(family,n):
    if family=='circle':
        t=2*np.pi*np.arange(n)/n;x=np.column_stack([np.cos(t),np.sin(t)])
    elif family=='planar':x=np.random.default_rng(260106).uniform(-1,1,(n,2))
    else:
        x=np.random.default_rng(610026).normal(size=(n,3));x/=np.linalg.norm(x,axis=1)[:,None]
    # Dyadic grades have exact common Float32/Float64 values and uniquely
    # decodable six-significant-digit CLI output. This is supplied distance data.
    d=np.rint(np.linalg.norm(x[:,None]-x[None,:],axis=2)*4096)/4096
    assert np.array_equal(d,d.T) and np.array_equal(d,d.astype(np.float32))
    return d
def fixture(out,family,n,prime,control=False):
    id=f'{family}_{n}_f{prime}';fmt='lower-distance';threshold=None
    degree=1 if family=='circle' else 2
    if family in ('octahedron','crosspolytope'):
        d=np.ones((n,n));np.fill_diagonal(d,0)
        for i in range(0,n,2):d[i,i+1]=d[i+1,i]=2
        degree=n//2-1
    elif family=='ties':d=np.ones((n,n));np.fill_diagonal(d,0)
    elif family=='zero_cycle':
        d=np.full((n,n),np.inf);np.fill_diagonal(d,0)
        for i,j,v in [(0,1,0),(1,2,1),(2,3,1),(0,3,1)]:d[i,j]=d[j,i]=v
        fmt='sparse';degree=1;threshold=1.0
    elif family=='isolated':
        d=np.ones((n,n));d[0,:]=np.inf;d[:,0]=np.inf;np.fill_diagonal(d,0)
        fmt='sparse';degree=1;threshold=1.0
    elif family=='truncated':
        d=np.array([[0,1,1,2],[1,0,1,2],[1,1,0,2],[2,2,2,0]],float)
        fmt='sparse';degree=1;threshold=1.0
    else:
        d=matrix(family,n)
        if family=='sparse_sphere':fmt='sparse';threshold=1.5
    p=out/'inputs'/(id+'.txt');p.parent.mkdir(parents=True,exist_ok=True)
    if fmt=='lower-distance':
        values=d[np.tril_indices(n,-1)]
        np.savetxt(p,values,fmt='%.17g')
        assert np.array_equal(np.loadtxt(p),values)
        edges=n*(n-1)//2
    else:
        i,j=np.tril_indices(n,-1)
        keep=np.isfinite(d[i,j])
        if family=='sparse_sphere':keep &= d[i,j]<=threshold
        i=i[keep];j=j[keep];v=d[i,j]
        np.savetxt(p,np.column_stack([i,j,v]),fmt=['%d','%d','%.17g'])
        edges=int(np.count_nonzero(v<=threshold))
        assert max(np.max(i),np.max(j))==n-1
    c=dict(id=id,family=family,n=n,prime=prime,degree=degree,format=fmt,threshold=threshold,
           input=str(p.relative_to(out)),sha256=sha(p),edges=edges,control=control)
    grade_decoder(p,fmt)
    if control:
        c['expected']=oracle(d,prime,degree,threshold)
    return c
def oracle(d,p,degree,threshold):
    """Independent explicit simplicial boundary reduction for small controls."""
    cells=[]
    for k in range(1,degree+3):
        for vertices in itertools.combinations(range(len(d)),k):
            grade=max((d[i,j] for i,j in itertools.combinations(vertices,2)),default=0.)
            if math.isfinite(grade) and (threshold is None or grade<=threshold):cells.append((grade,k-1,vertices))
    cells.sort();index={v:i for i,(_,_,v) in enumerate(cells)};columns={};births=set();deaths={}
    for j,(grade,dim,v) in enumerate(cells):
        col={index[v[:k]+v[k+1:]]:(1 if k%2==0 else p-1) for k in range(len(v))} if dim else {}
        while col and max(col) in columns:
            pivot=max(col);old=columns[pivot];factor=col[pivot]*pow(old[pivot],-1,p)%p
            for row,val in old.items():
                q=(col.get(row,0)-factor*val)%p
                if q:col[row]=q
                else:col.pop(row,None)
        if col:columns[max(col)]=col;deaths[max(col)]=j
        else:births.add(j)
    result=[[] for _ in range(degree+1)]
    for i in births:
        b,q,_=cells[i]
        if q>degree:continue
        death=cells[deaths[i]][0] if i in deaths else None
        if death is None or death>b:result[q].append([b,death])
    return canonical(result)

def cpp_command(out,c):
    command=[str(out/('ripser-f2' if c['prime']==2 else 'ripser-coeff')),'--format',c['format'],'--dim',str(c['degree'])]
    if c['prime']!=2:command+=['--modulus',str(c['prime'])]
    if c['threshold'] is not None:command+=['--threshold',str(c['threshold'])]
    return ['taskset','-c','0',*command,str(out/c['input'])]
def cpp(out,c,dest,label):
    command=cpp_command(out,c);log=dest/(label+'.stdout');err=dest/(label+'.stderr')
    start=time.perf_counter();peak=0
    with log.open('w') as f,err.open('w') as e:
        proc=subprocess.Popen(command,stdout=f,stderr=e)
        while proc.poll() is None:
            peak=max(peak,status(proc.pid).get('VmHWM',0))
            if time.perf_counter()-start>LIMIT or peak>RSS_LIMIT:
                proc.kill();proc.wait();raise RuntimeError('C++ resource limit')
            time.sleep(.01)
    elapsed=time.perf_counter()-start
    if proc.returncode:raise RuntimeError(f'C++ exit {proc.returncode}: '+err.read_text()[-2000:])
    result=parse_cpp(log.read_text(),c,grade_decoder(out/c['input'],c['format']))
    return dict(seconds=elapsed,peak_rss_bytes=peak,accepted=True,reset_verified=True,command=command),result
class JuliaWorker:
    def __init__(self,out,dest):
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',JULIA_NUM_THREADS='1',JULIA_PKG_PRECOMPILE_AUTO='0',JULIA_DEPOT_PATH='/tmp/tamerop-q6q7-depot:/home/eriknovak/.julia')
        cmd=['taskset','-c','0',JULIA,'--startup-file=no','--heap-size-hint=4G','--compiled-modules=existing','--pkgimages=existing',f'--project={out/"candidate"}',str(Path(__file__).with_name('worker.jl'))]
        self.err=(dest/'julia.stderr').open('w');self.log=(dest/'julia.ndjson').open('w');self.monitor=(dest/'julia_monitor.ndjson').open('w')
        self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1,env=env)
        dump(dest/'julia_launch.json',dict(command=cmd,pid=self.proc.pid,environment={k:env[k] for k in ['JULIA_DEPOT_PATH','JULIA_NUM_THREADS','OPENBLAS_NUM_THREADS']}))
        self.q=queue.Queue();self.out=out;self.peak=0
        def reader():
            for line in self.proc.stdout:self.q.put(line)
        threading.Thread(target=reader,daemon=True).start()
        try:
            self.environment=self.receive('ready',600)[-1];dump(dest/'julia_environment.json',self.environment)
        except Exception:
            self.close();raise
    def receive(self,until,limit):
        begin=time.monotonic();rows=[];last=0
        while True:
            now=time.monotonic()
            if now-last>1:
                last=now;m=status(self.proc.pid);self.peak=max(self.peak,m.get('VmHWM',0))
                self.monitor.write(json.dumps(dict(time=now,memory=m,load=os.getloadavg()))+'\n');self.monitor.flush()
                if self.peak>RSS_LIMIT:raise RuntimeError('Julia memory limit')
            if now-begin>limit:raise RuntimeError('Julia phase timeout')
            try:line=self.q.get(timeout=.1)
            except queue.Empty:
                if self.proc.poll() is not None:raise RuntimeError('Julia exited unexpectedly')
                continue
            self.log.write(line);self.log.flush()
            row=json.loads(line);rows.append(row)
            if row['kind']=='error':raise RuntimeError(row['message'])
            if row['kind']==until:return rows
    def run(self,c,warm=False):
        self.proc.stdin.write(json.dumps(dict(c,path=str(self.out/c['input'])))+'\n');self.proc.stdin.flush()
        rows=self.receive('sample',600 if warm else LIMIT)
        result=canonical(next(r['diagrams'] for r in rows if r['kind']=='barcode'))
        row=rows[-1];row['peak_rss_bytes']=self.peak
        return row,result
    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.log.close();self.err.close();self.monitor.close()

def verify(out,c,result,reference):
    assert sha(out/c['input'])==c['sha256'],'input changed'
    if c.get('control'):assert result==c['expected'],f'independent oracle failed: {c["id"]}'
    if reference is not None:assert result==reference,f'cross-tool/output stability mismatch: {c["id"]}'

def run(out,manifest,passes,ids,tag,resume=False):
    cases=[c for c in manifest['cases'] if ids is None or c['id'] in ids]
    assert cases
    for pas in passes:
        dest=out/'runs'/f'{tag}_p{pas}'
        if (dest/'complete.json').exists():print('Already completed',dest,flush=True);continue
        if dest.exists() and not resume:raise RuntimeError(f'Review unfinished pass before restarting: {dest}')
        dest.mkdir(parents=True,exist_ok=resume);failures=[];environments=[]
        for c in (cases if pas%2 else list(reversed(cases))):
            casedir=dest/c['id']
            if (casedir/'complete.json').exists():
                assert json.loads((casedir/'complete.json').read_text())['success']
                prior=[json.loads(l) for l in (dest/'samples.jsonl').read_text().splitlines()]
                for tool in ['tamerop','cpp']:
                    accepted=[x for x in prior if x['id']==c['id'] and x['tool']==tool and x['accepted'] and not x['warmup']]
                    assert len(accepted)==manifest['samples'] and all(x['verified'] and x['reset_verified'] for x in accepted)
                environments.append(dict(json.loads((casedir/'julia_environment.json').read_text()),id=c['id']))
                print('Verified completed checkpoint',pas,c['id'],flush=True);continue
            casedir.mkdir();worker=None;reference=None
            try:
                worker=JuliaWorker(out,casedir);environments.append(dict(worker.environment,id=c['id']))
                if tag=='final' and pas==1 and c['id']==manifest['cases'][0]['id']:
                    checks=[]
                    for control in json.loads((out/'controls.json').read_text())['cases']:
                        jr,jd=worker.run(control,warm=True)
                        cr,cd=cpp(out,control,dest,'control_'+control['id'])
                        verify(out,control,jd,cd)
                        checks.append(dict(id=control['id'],passed=True,expected=control['expected'],tamerop=jd,cpp=cd))
                        print('control passed',control['id'],flush=True)
                    dump(out/'control_verification.json',checks)
                for trial in range(manifest['samples']+1):
                    order=['tamerop','cpp'] if (trial+pas)%2 else ['cpp','tamerop']
                    for tool in order:
                        for attempt in range(1,4):
                            label=f'{c["id"]}_{trial}_{tool}_{attempt}'
                            started=time.monotonic()
                            row,result=worker.run(c,warm=trial==0) if tool=='tamerop' else cpp(out,c,dest,label)
                            verify(out,c,result,reference);reference=result
                            row.update(id=c['id'],tool=tool,pass_id=pas,trial=trial,warmup=trial==0,attempt=attempt,load=os.getloadavg(),verified=True,elapsed_with_verification=time.monotonic()-started)
                            append(dest/'samples.jsonl',row);dump(dest/(label+'.barcode.json'),result)
                            print(tag,pas,c['id'],tool,'warm' if trial==0 else trial,round(row['seconds'],3),'s','accepted' if row['accepted'] else 'compilation',flush=True)
                            if trial==0 or row['accepted']:break
                        else:raise RuntimeError('No compilation-free sample')
                dump(casedir/'complete.json',dict(success=True))
            except RuntimeError as e:
                failure=dict(id=c['id'],pass_id=pas,error=str(e));failures.append(failure)
                dump(casedir/'failure.json',failure);print('CASE FAILURE',failure,flush=True)
                if worker is not None:worker.close();worker=None
                # Preserve comparator completion when the Julia worker cannot finish.
                if not list(dest.glob(c['id']+'_1_cpp_*.barcode.json')):
                    try:
                        row,result=cpp(out,c,dest,c['id']+'_unpaired_cpp')
                        row.update(id=c['id'],tool='cpp',unpaired=True,verified=reference is not None)
                        if reference is not None:verify(out,c,result,reference)
                        dump(casedir/'unpaired_comparator.json',row)
                    except RuntimeError as ce:dump(casedir/'comparator_failure.json',dict(error=str(ce)))
            finally:
                if worker is not None:worker.close()
        allcases=manifest['cases']
        environments=[dict(json.loads((dest/c['id']/'julia_environment.json').read_text()),id=c['id']) for c in allcases if (dest/c['id']/'julia_environment.json').exists()]
        failures=[json.loads((dest/c['id']/'failure.json').read_text()) for c in allcases if (dest/c['id']/'failure.json').exists()]
        dump(dest/'julia_environments.json',environments)
        finished=all((dest/c['id']/'complete.json').exists() or (dest/c['id']/'failure.json').exists() for c in allcases)
        dump(dest/('complete.json' if finished else 'progress.json'),dict(success=not failures,pass_id=pas,ids=[c['id'] for c in allcases],failures=failures))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','pilot','controls','run']);ap.add_argument('--out',required=True);ap.add_argument('--family');ap.add_argument('--n',type=int);ap.add_argument('--prime',type=int,default=2);ap.add_argument('--passes',default='1,2,3');ap.add_argument('--tag',default='final');ap.add_argument('--resume',action='store_true');ap.add_argument('--case-id');a=ap.parse_args();out=Path(a.out).resolve()
    if a.mode=='prepare':
        controls=[fixture(out,f,n,p,True) for f,n,p in [('octahedron',6,2),('octahedron',6,3),('crosspolytope',8,101),('ties',8,3),('zero_cycle',4,101),('isolated',4,2)]]
        dump(out/'controls.json',dict(samples=1,cases=controls))
        meta=dict(upstream_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=out/'upstream',text=True).strip(),compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],flags=['-std=c++11','-O3','-DNDEBUG','-DUSE_ROBINHOOD_HASHMAP'],f2_specialized=True,odd_fields_macro='USE_COEFFICIENTS',binaries={f:sha(out/f) for f in ['ripser-f2','ripser-coeff']},cpu=subprocess.check_output(['lscpu'],text=True),os=subprocess.check_output(['uname','-a'],text=True),memory=Path('/proc/meminfo').read_text(),candidate='Frozen snapshot from Ripser.py v1; no library optimization during this study')
        dump(out/'machine_and_build.json',meta)
    elif a.mode=='pilot':
        c=fixture(out,a.family,a.n,a.prime);dest=out/'pilot'/c['id'];dest.mkdir(parents=True,exist_ok=True)
        row,result=cpp(out,c,dest,'cpp');verify(out,c,result,None)
        dump(dest/'result.json',dict(case=c,sample=row,diagrams=result));print(json.dumps(dict(case=c,seconds=row['seconds'],counts=list(map(len,result)))),flush=True)
    elif a.mode=='controls':run(out,json.loads((out/'controls.json').read_text()),[1],None,a.tag)
    else:
        manifest=json.loads((out/'manifest.json').read_text())
        for rel,dig in json.loads((out/'candidate_hashes.json').read_text()).items():assert sha(out/'candidate'/rel)==dig
        for rel,dig in json.loads((out/'machine_and_build.json').read_text())['binaries'].items():assert sha(out/rel)==dig
        run(out,manifest,list(map(int,a.passes.split(','))),[a.case_id] if a.case_id else None,a.tag,resume=a.resume)
if __name__=='__main__':main()
