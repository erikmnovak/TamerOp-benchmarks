"""Fresh supported array request; compression/canonicalization outside timing."""
import gc,gzip,hashlib,json,sys,time
from pathlib import Path
start=time.perf_counter()
import numpy as np
import cripser
from large_outputs import canonical
load=time.perf_counter()-start
out=Path(sys.argv[1]);c=json.loads(Path(sys.argv[2]).read_text());samples=int(sys.argv[3]);dest=Path(sys.argv[4])
def emit(**kw):print(json.dumps(kw,allow_nan=False),flush=True)
def signature(x):return hashlib.sha256(memoryview(x.ravel(order='F')).cast('B')).hexdigest()
def query(x):
    return cripser.compute_ph(-x if c['order']=='superlevel' else x,filtration=c['convention'],maxdim=len(c['shape'])-1,top_dim=False,embedded=False,representatives=False,n_threads=1)

emit(kind='environment',tool='cubicalripser',load_seconds=load,python=sys.version,version=cripser.__version__,numpy=np.__version__,threads=1,reset='fresh supported compute_ph; all previous outputs discarded')
emit(kind='start',phase='prepare',case=c['id'])
p=out/c['input'];assert hashlib.sha256(p.read_bytes()).hexdigest()==c['compressed_sha256']
with gzip.open(p,'rb') as f:raw=f.read()
assert hashlib.sha256(raw).hexdigest()==c['raw_sha256']
x=np.frombuffer(raw,dtype='<u2').astype(np.float64).reshape(c['shape'],order='F');del raw
before=signature(x)
emit(kind='start',phase='warm',case=c['id'])
w=x+1;t=time.perf_counter();warm=query(w);elapsed=time.perf_counter()-t
del warm,w;gc.collect();emit(kind='warmup',case=c['id'],seconds=elapsed)
for sample in range(1,samples+1):
    gc.collect();assert signature(x)==before
    emit(kind='start',phase='query',case=c['id'],sample=sample)
    t=time.perf_counter();result=query(x);elapsed=time.perf_counter()-t
    emit(kind='start',phase='verify',case=c['id'],sample=sample)
    assert signature(x)==before
    hist=canonical(result,c);p=dest/f'a{sample}.json';p.write_text(json.dumps(hist,allow_nan=False))
    emit(kind='sample',tool='cubicalripser',case=c['id'],sample=sample,attempt=sample,accepted=True,seconds=elapsed,
         compile_seconds=None,recompile_seconds=None,allocation_bytes=None,gc_seconds=None,input_bytes=x.nbytes,
         result_bytes=result.nbytes+sys.getsizeof(result)-(result.nbytes if result.flags.owndata else 0),
         native_coordinate_columns=result.shape[1]-3,reset_verified=True,input_sha256=before,
         output=p.name,output_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),intervals=sum(v[3] for v in hist))
    del result,hist
emit(kind='complete',tool='cubicalripser',case=c['id'])
