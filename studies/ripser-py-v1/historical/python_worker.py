"""Stock Ripser.py public calls; no patched algorithms or retained result cache."""
import os,time,json,sys,gc,hashlib,resource,gzip
from pathlib import Path
start=time.perf_counter()
import numpy as np
from scipy import sparse
import ripser
load_seconds=time.perf_counter()-start
OUT=Path(sys.argv[1]); PASS=int(sys.argv[2]); IDS=sys.argv[3].split(',')
M=json.loads((OUT/'manifest.json').read_text())
def emit(**x):print(json.dumps(x,allow_nan=False),flush=True)
def rss():
    d={a.split(':')[0]:int(a.split()[1])*1024 for a in Path('/proc/self/status').read_text().splitlines() if a.startswith(('VmRSS:','VmHWM:'))}
    return d
def native(raw):
    if raw['kind']=='cloud':return np.asarray(raw['points'],dtype=np.float64)
    if raw['kind']=='dense':return np.asarray(raw['matrix'],dtype=np.float64)
    return sparse.coo_matrix((np.asarray(raw['values'],dtype=float),(raw['rows'],raw['cols'])),shape=(raw['n'],raw['n']))
def query(x,c):
    return ripser.ripser(x,maxdim=c['degree'],thresh=c['threshold'] if c['threshold'] is not None else np.inf,coeff=c['prime'],distance_matrix=c['family']!='cloud',do_cocycles=c['cocycles'],n_perm=c['landmarks'])
def signature(x):
    if sparse.issparse(x):return hashlib.sha256(x.row.tobytes()+x.col.tobytes()+x.data.tobytes()).hexdigest()
    return hashlib.sha256(x.tobytes()).hexdigest()
def retained(x,seen=None):
    if seen is None:seen=set()
    if id(x) in seen:return 0
    seen.add(id(x));n=sys.getsizeof(x)
    if isinstance(x,dict):return n+sum(retained(k,seen)+retained(v,seen) for k,v in x.items())
    if isinstance(x,(list,tuple)):return n+sum(retained(v,seen) for v in x)
    return n

def output(r,c):
    diagrams=[sorted([[float(b),None if np.isinf(d) else float(d)] for b,d in dgm],key=lambda z:(z[0],np.inf if z[1] is None else z[1])) for dgm in r['dgms']]
    witnesses=[]
    if c['cocycles']:
        for q in range(1,len(r['dgms'])):
            selected=sorted(range(len(r['dgms'][q])),key=lambda i:float(r['dgms'][q][i,1]-r['dgms'][q][i,0]),reverse=True)[:6]
            for i in selected:
                b,d=map(float,r['dgms'][q][i]);s=(b+d)/2 if np.isfinite(d) else (c['threshold'] if c['threshold'] is not None else max(b,1.0))
                # Verification restricts the stock near-death representative to s.
                witnesses.append(dict(degree=q,birth=b,death=None if np.isinf(d) else d,scale=s,terms=r['cocycles'][q][i].tolist()))
    meta=None
    if c['landmarks'] is not None:meta=dict(indices=r['idx_perm'].tolist(),radius=float(r['r_cover']),distances=r['dperm2all'].tolist())
    return dict(diagrams=diagrams,witnesses=witnesses,landmarks=meta)
emit(kind='environment',tool='ripser',pass_id=PASS,load_seconds=load_seconds,version=ripser.__version__,python=sys.version,threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS')},memory=rss())
for c in sorted(M['cases'],key=lambda c: IDS.index(c['id']) if c['id'] in IDS else len(IDS)):
    if c['id'] not in IDS:continue
    emit(kind='start',case=c['id'],phase='prepare')
    try:
        path=OUT/c['input'];assert hashlib.sha256(path.read_bytes()).hexdigest()==c['sha256']
        raw=json.loads(path.read_text())
        x=native(raw);before=signature(x)
        emit(kind='start',case=c['id'],phase='warm')
        t=time.perf_counter();warm=query(x,c);elapsed=time.perf_counter()-t
        assert signature(x)==before
        emit(kind='first_use',case=c['id'],seconds=elapsed,scope='same fixture, result discarded; not measured sample')
        del warm,x;gc.collect()
        expected_hash=None
        for sample in range(1,M['samples']+1):
            gc.collect();emit(kind='start',case=c['id'],phase='query',sample=sample)
            t=time.perf_counter();x=native(raw);construction=time.perf_counter()-t
            before=signature(x)
            t=time.perf_counter();r=query(x,c);elapsed=time.perf_counter()-t
            assert signature(x)==before,'native input mutated'
            emit(kind='sample',tool='ripser',case=c['id'],pass_id=PASS,sample=sample,accepted=True,seconds=elapsed,construction_seconds=construction,construction_plus_query_seconds=construction+elapsed,compile_seconds=None,recompile_seconds=None,allocation_bytes=None,result_bytes=retained(r),memory=rss(),reset_verified=True)
            emit(kind='start',case=c['id'],phase='validation_export')
            encoded=json.dumps(output(r,c),allow_nan=False,separators=(',',':')).encode()
            digest=hashlib.sha256(encoded).hexdigest()
            if expected_hash is None:expected_hash=digest
            assert digest==expected_hash,'mathematical output changed between fresh samples'
            emit(kind='output_check',case=c['id'],sample=sample,sha256=digest)
            if sample==1:
                emit(kind='start',case=c['id'],phase='validation_export')
                with gzip.open(Path(os.environ['RIPSER_OUTPUT_DIR'])/f"ripser_p{PASS}_{c['id']}.json.gz",'wb',compresslevel=1) as out:out.write(encoded)
            del r,x,encoded
        del raw;gc.collect();emit(kind='case_complete',case=c['id'])
    except Exception as e:
        emit(kind='case_error',case=c['id'],error=repr(e));gc.collect()
emit(kind='complete',tool='ripser',pass_id=PASS)
