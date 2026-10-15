"""Independent simplicial and modular-algebra checks; never calls either reducer."""
import os
import json,itertools,math,hashlib,gzip
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=Path(os.environ.get('RIPSER_STUDY_DIR',str(ROOT/'audit/2026-10-04/ripser_pilot')))
def read_output(path):
    with gzip.open(path,'rt') as f:return json.load(f)

def rank(a,p):
    a=np.asarray(a,dtype=np.int64).copy()%p;r=0
    if a.ndim!=2:return 0
    for j in range(a.shape[1]):
        ids=np.flatnonzero(a[r:,j])
        if not len(ids):continue
        k=r+int(ids[0]);a[[r,k]]=a[[k,r]];a[r]=a[r]*pow(int(a[r,j]),-1,p)%p
        for k in range(a.shape[0]):
            if k!=r and a[k,j]:a[k]=(a[k]-a[k,j]*a[r])%p
        r+=1
        if r==a.shape[0]:break
    return r

def graph(raw,selected=None,cloud32=False):
    if raw['kind']=='cloud':
        x=np.array(raw['points']);a=np.sqrt(np.sum((x[:,None]-x[None,:])**2,axis=2))
        if cloud32:a=a.astype(np.float32).astype(float)
    elif raw['kind']=='dense':a=np.array(raw['matrix'])
    else:
        n=raw['n'];a=np.full((n,n),np.inf);np.fill_diagonal(a,0)
        for i,j,v in zip(raw['rows'],raw['cols'],raw['values']):a[i,j]=a[j,i]=v
    vertices=list(range(len(a))) if selected is None else selected
    return a,vertices

def grade(s,a):return max([a[i,i] for i in s]+[a[i,j] for i,j in itertools.combinations(s,2)])
def cells(a,vertices,q,scale):
    return [s for s in itertools.combinations(vertices,q+1) if math.isfinite(g:=grade(s,a)) and g<=scale]
def boundary(rows,cols,p):
    lookup={s:i for i,s in enumerate(rows)};out=np.zeros((len(rows),len(cols)),dtype=np.int64)
    for j,s in enumerate(cols):
        for k in range(len(s)):out[lookup[s[:k]+s[k+1:]],j]=(-1)**k%p
    return out

def independent_diagram(a,vertices,maxq,p,threshold):
    simplices=[]
    for q in range(maxq+2):simplices.extend((grade(s,a),q,s) for s in cells(a,vertices,q,threshold))
    simplices.sort();index={s:i for i,(_,_,s) in enumerate(simplices)};reduced={};positive=set();paired=set();bars=[[] for _ in range(maxq+1)]
    for j,(death,q,s) in enumerate(simplices):
        col={} if q==0 else {index[s[:k]+s[k+1:]]:(-1)**k%p for k in range(len(s))}
        while col and max(col) in reduced:
            pivot=max(col);old=reduced[pivot];fac=col[pivot]*pow(old[pivot],-1,p)%p
            for i,v in old.items():
                w=(col.get(i,0)-fac*v)%p
                if w:col[i]=w
                else:col.pop(i,None)
        if not col:positive.add(j)
        else:
            pivot=max(col);reduced[pivot]=col;paired.add(pivot);birth,d,_=simplices[pivot]
            if d<=maxq and birth<death:bars[d].append([float(birth),float(death)])
    for i in positive-paired:
        birth,q,_=simplices[i]
        if q<=maxq:bars[q].append([float(birth),None])
    return [sorted(b,key=lambda x:(x[0],math.inf if x[1] is None else x[1])) for b in bars]

def normalized_terms(w,a,active,p):
    out={}
    for row in w['terms']:
        s=tuple(int(x) for x in row[:-1]);coef=int(row[-1]);inv=sum(s[i]>s[j] for i in range(len(s)) for j in range(i+1,len(s)))
        s=tuple(sorted(s))
        assert len(set(s))==len(s) and set(s)<=set(active)
        if grade(s,a)>w['scale']:continue
        out[s]=(out.get(s,0)+(-1)**inv*coef)%p
    return {s:v for s,v in out.items() if v}

def coboundary_inconsistent(a,active,q,scale,terms,p):
    previous=cells(a,active,q-1,scale)
    lookup={s:i for i,s in enumerate(previous)}
    pivots={};equations=0
    for s in cells(a,active,q,scale):
        row={lookup[s[:k]+s[k+1:]]:(-1)**k%p for k in range(q+1)}
        rhs=terms.get(s,0)%p;equations+=1
        while row:
            pivot=min(row)
            if pivot not in pivots:
                inv=pow(row[pivot],-1,p)
                pivots[pivot]=({j:v*inv%p for j,v in row.items()},rhs*inv%p)
                break
            old,value=pivots[pivot];fac=row[pivot]
            for j,v in old.items():
                w=(row.get(j,0)-fac*v)%p
                if w:row[j]=w
                else:row.pop(j,None)
            rhs=(rhs-fac*value)%p
        if not row and rhs:
            return dict(nontrivial_verified=True,method='independent sparse coboundary inconsistency',equations=equations,pivots=len(pivots))
    return dict(nontrivial_verified=False,method='independent sparse coboundary consistency',equations=equations,pivots=len(pivots))

def witness_check(w,a,vertices,p):
    scale=w['scale'];active=[v for v in vertices if a[v,v]<=scale];terms=normalized_terms(w,a,active,p);assert terms,'zero representative'
    neighbors={v:{u for u in active if u!=v and a[v,u]<=scale} for v in active}
    cofaces=set()
    for s in terms:
        for v in set.intersection(*(neighbors[u] for u in s)):
            cofaces.add(tuple(sorted(s+(v,))))
    for s in cofaces:assert sum((-1)**k*terms.get(s[:k]+s[k+1:],0) for k in range(len(s)))%p==0,'nonzero coboundary'
    nontrivial=None
    if w['degree']==1:
        # Decide whether the cochain is a gradient, component by component.
        potentials={};nontrivial=False
        for start in active:
            if start in potentials:continue
            potentials[start]=0;stack=[start]
            while stack:
                u=stack.pop()
                for v in neighbors[u]:
                    val=terms.get((min(u,v),max(u,v)),0)*(1 if u<v else -1)
                    want=(potentials[u]+val)%p
                    if v in potentials:
                        if potentials[v]!=want:nontrivial=True
                    else:potentials[v]=want;stack.append(v)
        assert nontrivial,'coboundary representative'
    else:
        # Restriction to a connected component can certify nontriviality globally.
        component=set(next(iter(terms)));todo=list(component)
        while todo:
            v=todo.pop()
            for u in neighbors[v]-component:component.add(u);todo.append(u)
        if len(component)>24:
            certificate=coboundary_inconsistent(a,sorted(component),w['degree'],scale,terms,p)
            assert certificate['nontrivial_verified'],'coboundary representative'
            return dict(degree=w['degree'],terms=len(terms),coface_equations=len(cofaces),**certificate)
        active=sorted(component)
        q=w['degree'];cs=cells(a,active,q,scale);prev=cells(a,active,q-1,scale);delta=boundary(prev,cs,p).T
        v=np.array([terms.get(s,0) for s in cs],dtype=np.int64)[:,None]
        assert rank(np.concatenate((delta,v),axis=1),p)==rank(delta,p)+1,'coboundary representative'
        nontrivial=True
    return dict(degree=w['degree'],terms=len(terms),coface_equations=len(cofaces),nontrivial_verified=nontrivial is True)

def compare_diagrams(a,b,cloud):
    assert len(a)==len(b);details=[]
    for q,(xs,ys) in enumerate(zip(a,b)):
        if not cloud:assert xs==ys,f'degree {q}: exact diagrams differ';continue
        scale=max([1]+[abs(v) for z in xs+ys for v in z if v is not None]);tol=float(8*np.finfo(np.float32).eps*scale)
        # Near-zero bars may collapse at Ripser.py's float conversion; count these explicitly.
        tinyx=[z for z in xs if z[1] is not None and z[1]-z[0]<=2*tol]
        tinyy=[z for z in ys if z[1] is not None and z[1]-z[0]<=2*tol]
        xx=[z for z in xs if z not in tinyx];yy=[z for z in ys if z not in tinyy]
        assert len(xx)==len(yy),f'degree {q}: counts differ away from rounding scale'
        for x,y in zip(xx,yy):
            assert (x[1] is None)==(y[1] is None)
            assert all(abs(u-v)<=tol for u,v in zip(x,y) if u is not None),f'degree {q}: endpoints differ beyond tolerance'
        details.append(dict(degree=q,tolerance=tol,near_diagonal_tamerop=len(tinyx),near_diagonal_ripser=len(tinyy)))
    return details

def graph_family_oracle(raw,case):
    a,vertices=graph(raw);n=len(vertices);p=case['prime'];q=case['degree']
    if case['shape'] in ('octa','permuted octahedra'):
        result=[[] for _ in range(q+1)]
        remaining=set(vertices);components=[]
        while remaining:
            component={min(remaining)};todo=list(component)
            while todo:
                v=todo.pop()
                for u in list(remaining-component):
                    if math.isfinite(a[v,u]):component.add(u);todo.append(u)
            remaining-=component;components.append(sorted(component))
        assert all(len(component)==6 for component in components)
        for component in components:
            ds=independent_diagram(a,component,q,p,np.inf)
            for dim,values in enumerate(ds):result[dim].extend(values)
        return [sorted(v,key=lambda z:(z[0],math.inf if z[1] is None else z[1])) for v in result]
    if case['shape'] not in ('grid','cycle','permuted grid'):return None
    # These connected graphs have no triangles and all edge grades are one.
    edges=[(i,j) for i,j in zip(raw['rows'],raw['cols']) if i!=j]
    assert len(set(edges))==len(edges)
    assert all(a[i,j]==1 for i,j in edges)
    neighbors=[set() for _ in vertices]
    for i,j in edges:neighbors[i].add(j);neighbors[j].add(i)
    assert all(not(neighbors[i]&neighbors[j]) for i,j in edges),'triangle-free assumption failed'
    reached={0};todo=[0]
    while todo:
        for v in neighbors[todo.pop()]-reached:reached.add(v);todo.append(v)
    assert len(reached)==n
    births=sorted(float(a[i,i]) for i in vertices);bars=[[] for _ in range(q+1)]
    bars[0]=sorted([[b,1.0] for b in births[1:]]+[[births[0],None]],key=lambda z:(z[0],math.inf if z[1] is None else z[1]))
    if q>=1:bars[1]=[[1.0,None] for _ in range(len(edges)-n+1)]
    return bars

def common_class_check(t,r,a,vertices,p,q):
    # Whole class spaces at a common scale, rather than identical cocycle coefficients.
    scales=sorted({w['scale'] for res in (t,r) for w in res['witnesses'] if w['degree']==q})
    checks=[]
    for scale in scales:
        cs=cells(a,vertices,q,scale);prev=cells(a,vertices,q-1,scale);nxt=cells(a,vertices,q+1,scale)
        delta=boundary(prev,cs,p).T;nextdelta=boundary(cs,nxt,p).T
        rd=rank(delta,p);betti=len(cs)-rd-rank(nextdelta,p)
        vectors=[]
        for res in (t,r):
            selected=[]
            for w in res['witnesses']:
                if w['degree']!=q or not(w['birth']<=scale and (w['death'] is None or scale<w['death'])) or scale>w['scale']:continue
                ww=dict(w,scale=scale);terms=normalized_terms(ww,a,vertices,p)
                selected.append([terms.get(s,0) for s in cs])
            mat=np.array(selected,dtype=np.int64).T if selected else np.zeros((len(cs),0),dtype=np.int64)
            assert rank(np.concatenate((delta,mat),axis=1),p)==rd+betti,'representatives do not span the expected class space'
            vectors.append(mat)
        assert rank(np.concatenate((delta,*vectors),axis=1),p)==rd+betti,'class spaces differ'
        checks.append(dict(degree=q,scale=scale,betti=betti))
    return checks

def latest(include_superseded=False):
    found={}
    correction=OUT/'adapter_correction.json'
    info=json.loads(correction.read_text()) if correction.exists() else {}
    excluded=info.get('affected')
    for run in sorted((OUT/'runs').iterdir()):
        if not include_superseded and run.name in info.get('superseded_runs',[]):continue
        p=run/'completion.json'
        if not p.exists():continue
        c=json.loads(p.read_text())
        for case in c['failed']:found.pop((c['tool'],c['pass_id'],case),None)
        for case in c['completed']:
            if not include_superseded and excluded and run.name==excluded['run'] and any(case.startswith(f+'_') for f in excluded['families']):continue
            f=run/'outputs'/f"{c['tool']}_p{c['pass_id']}_{case}.json.gz"
            if f.exists():found[(c['tool'],c['pass_id'],case)]=f
    return found

def verify(preflight=False):
    manifest=json.loads((OUT/'manifest.json').read_text());found=latest(include_superseded=preflight);checks=[]
    for case in manifest['cases']:
        for pas in range(1,int(manifest['passes'])+1):
            paths=[found.get((tool,pas,case['id'])) for tool in ('tamerop','ripser')]
            if not all(paths):continue
            check=dict(case=case['id'],pass_id=pas,paths=[str(x.relative_to(OUT)) for x in paths])
            try:
                t,r=[read_output(x) for x in paths];raw=json.loads((OUT/case['input']).read_text())
                check['precision']=compare_diagrams(t['diagrams'],r['diagrams'],case['family']=='cloud')
                idx=None
                if case['landmarks'] is not None:
                    assert t['landmarks']==r['landmarks'],'landmark metadata differs'
                    idx=t['landmarks']['indices'];a,_=graph(raw)
                    assert t['landmarks']['distances']==a[idx].tolist()
                    assert t['landmarks']['radius']==np.min(a[idx],axis=0).max()
                    nearest=np.full(len(a),np.inf);chosen=[]
                    for v in idx:
                        expect=0 if not chosen else int(np.argmax(nearest))
                        assert v==expect;chosen.append(v);nearest=np.minimum(nearest,a[v])
                    check['landmark_metadata_verified']=True
                independent=graph_family_oracle(raw,case) if case['family'] in ('sparse','weighted') else None
                if independent is not None:
                    compare_diagrams(t['diagrams'],independent,False);compare_diagrams(r['diagrams'],independent,False)
                    check['independent_graph_oracle']=True
                check['witnesses']={}
                for tool,res in (('tamerop',t),('ripser',r)):
                    a,vertices=graph(raw,idx,cloud32=tool=='ripser')
                    check['witnesses'][tool]=[]
                    for w in res['witnesses']:
                        entry=witness_check(w,a,vertices,case['prime']);entry['scale']=w['scale']
                        if w['birth']<w['scale']:
                            earlier=dict(w,scale=(w['birth']+w['scale'])/2)
                            entry['earlier_restriction']=witness_check(earlier,a,vertices,case['prime'])
                            entry['earlier_restriction']['scale']=earlier['scale']
                        check['witnesses'][tool].append(entry)
                    if case['family']=='control':
                        ref=independent_diagram(a,vertices,case['degree'],case['prime'],case['threshold'] if case['threshold'] is not None else np.inf)
                        compare_diagrams(res['diagrams'],ref,False)
                if case['family']=='control':
                    a,vertices=graph(raw)
                    check['common_class_spaces']=[v for q in range(1,case['degree']+1) for v in common_class_check(t,r,a,vertices,case['prime'],q)]
                check['status']='pass'
            except Exception as e:check['status']='fail';check['error']=repr(e)
            checks.append(check)
            print(case['id'],pas,check['status'],flush=True)
    out=dict(checks=checks,matched_case_passes=len(checks),expected_case_passes=len(manifest['cases'])*manifest['passes'],failures=sum(c['status']=='fail' for c in checks),limitation='At most six longest positive-degree representatives per degree. Full cocycle equations checked on active cofaces; nontriviality checked in degree one, by dense rank on small higher-degree controls, and by independent sparse coboundary inconsistency on large components. Not literal basis matching or proof for every returned representative.')
    path=OUT/('preflight_verification.json' if preflight else 'verification.json');path.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='checks'},indent=2))
    for c in checks:
        if c['status']=='fail':print(c['case'],c['pass_id'],c['error'])
    return out
if __name__=='__main__':
    import sys
    result=verify(preflight='--preflight' in sys.argv)
    sys.exit(1 if result['failures'] or ('--preflight' not in sys.argv and result['matched_case_passes']!=result['expected_case_passes']) else 0)
