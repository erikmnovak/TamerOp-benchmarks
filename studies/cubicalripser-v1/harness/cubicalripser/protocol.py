"""Evidence checks shared by the supervisor, verifier and negative tests."""
import hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify_hashes(root,manifest):
    for name,value in manifest.items():
        if sha(root/name)!=value:raise ValueError(f'hash mismatch: {name}')
def read_rows(path):
    # A truncated log is a failed/interrupted run, never silently accepted.
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
def check_completion(rows,ids,tool,mode,samples,returncode,reason):
    if returncode!=0 or reason is not None:raise ValueError(f'worker exit/guard: {returncode}, {reason}')
    assert len([r for r in rows if r.get('kind')=='complete' and r.get('tool')==tool])==1,'missing/duplicate completion marker'
    assert len([r for r in rows if r.get('kind')=='environment' and r.get('tool')==tool])==1,'missing environment'
    for ident in ids:
        errors=[r for r in rows if r.get('case')==ident and r.get('kind')=='case_error']
        done=[r for r in rows if r.get('case')==ident and r.get('kind')=='case_complete']
        assert len(done)+len(errors)==1,'missing/duplicate case outcome'
        if errors:continue
        if mode=='qualification':assert len([r for r in rows if r.get('case')==ident and r.get('kind')=='output'])==1
        else:
            accepted=[r for r in rows if r.get('case')==ident and r.get('kind')=='sample' and r.get('accepted')]
            assert len(accepted)==samples,'wrong accepted sample count'
            assert {r['sample'] for r in accepted}==set(range(1,samples+1))
            for r in accepted:
                assert r['tool']==tool and r['reset_verified'] is True and r['seconds']>=0
                if tool=='tamerop':assert r['compile_seconds']==r['recompile_seconds']==0,'compilation in uncached sample'
    return True
