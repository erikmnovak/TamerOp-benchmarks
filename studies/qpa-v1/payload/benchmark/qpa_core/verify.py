#!/usr/bin/env python3
"""Independent exact checks of finite-poset algebra, diagrams and complexes."""
import argparse,hashlib,importlib.util,json
import diagrams as D
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('core_exact',ROOT/'benchmark/qpa_derived/verify.py')
V=importlib.util.module_from_spec(s);s.loader.exec_module(V);G=V.G
# Preserve the normalized-bar oracle; only avoid arithmetic on structural zeros.
s=importlib.util.spec_from_file_location('core_rref',Path(__file__).with_name('exact_rref.py'))
R=importlib.util.module_from_spec(s);s.loader.exec_module(R);G.rref=R.rref

def hom_check(P,M,N,maps,field):
    eq,n=G.hom_equations(P,M,N,field);gold=G.nullspace(eq,field,ncols=n);vectors=[]
    for raw in maps:
        h=[V.parse(A,field) for A in raw];V.maps_check(P,M,N,h,field)
        vectors.append([h[v][i][j] for v in range(P['n']) for j in range(M['dimensions'][v]) for i in range(N['dimensions'][v])])
    assert len(vectors)==len(gold)
    assert G.rank(V.columns(vectors,n),field,ncols=len(vectors))==len(gold)
    assert G.rank(V.columns(vectors+gold,n),field,ncols=len(vectors)+len(gold))==len(gold),'Wrong complete Hom span'
    return dict(hom_dimension=len(gold),hom_vectors=vectors,hom_rows=n)


def construction_check(f,P,a):
    field=f['field'];A,B=f['modules']['A'],f['modules']['B']
    K,I,C=[a[k] for k in ('kernel','image','cokernel')]
    h=[V.parse(x,field) for x in f['maps']['f']['components']]
    hs={k:[V.parse(x,field) for x in a[k]] for k in ('kernel_inclusion','image_inclusion','image_projection','cokernel_projection')}
    ki,ii,ip,cq=[hs[k] for k in hs]
    for S,T,m in [(A,B,h),(K,A,ki),(I,B,ii),(A,I,ip),(B,C,cq)]:V.maps_check(P,S,T,m,field)
    ranks=[]
    for v in range(P['n']):
        da,db,dk,di,dc=[M['dimensions'][v] for M in (A,B,K,I,C)]
        rank=G.rank(h[v],field,ncols=da);ranks.append(rank)
        assert (dk,di,dc)==(da-rank,rank,db-rank),'Kernel/image/cokernel dimensions'
        assert G.rank(ki[v],field,ncols=dk)==dk
        assert G.rank(ii[v],field,ncols=di)==di and G.rank(ip[v],field,ncols=da)==di
        assert G.rank(cq[v],field,ncols=db)==dc
        assert not any(x for row in G.matmul(h[v],ki[v],field,ncols=dk) for x in row),'Kernel composition'
        assert not any(x for row in G.matmul(cq[v],h[v],field,ncols=da) for x in row),'Cokernel composition'
        assert G.matmul(ii[v],ip[v],field,ncols=da)==h[v],'Image factorization'
    assert ranks==f['certificate']['ranks']
    return dict(ranks=ranks,kernel_dimensions=K['dimensions'],image_dimensions=I['dimensions'],cokernel_dimensions=C['dimensions'],
                structural_maps_verified=True,_construction=a)

def term_kind(P,T,field,injective):
    maps=G.all_maps(P,T,field);multiplicities=[]
    for v in range(P['n']):
        if injective:
            rows=[row for u,w in P['covers'] if u-1==v for row in maps[v,w-1]]
            rank=G.rank(rows,field,ncols=T['dimensions'][v])
        else:
            cols=[list(col) for u,w in P['covers'] if w-1==v for col in zip(*maps[u-1,v])]
            rank=G.rank(V.columns(cols,T['dimensions'][v]),field,ncols=len(cols))
        multiplicities.append(T['dimensions'][v]-rank)
    expected=[sum(multiplicities[w] for w in range(P['n']) if (P['leq'][v][w] if injective else P['leq'][w][v])) for v in range(P['n'])]
    assert T['dimensions']==expected,'Noninjective term' if injective else 'Nonprojective term'
    return multiplicities

def resolution_check(f,P,a):
    field=f['field'];injective=f['task']=='injective';X=f['modules']['X'];terms=a['terms'];D=f['maxdegree']
    assert len(terms)==D+1 and len(a['differentials'])==D,'Resolution prefix length'
    ds=[[V.parse(A,field) for A in h] for h in [a['augmentation']]+a['differentials']]
    mult=[term_kind(P,T,field,injective) for T in terms]
    for k,h in enumerate(ds):
        previous=X if k==0 else terms[k-1]
        V.maps_check(P,previous if injective else terms[k],terms[k] if injective else previous,h,field)
    for v in range(P['n']):
        assert G.rank(ds[0][v],field,ncols=X['dimensions'][v] if injective else terms[0]['dimensions'][v])==X['dimensions'][v]
        for k in range(D):
            left,right=(ds[k+1][v],ds[k][v]) if injective else (ds[k][v],ds[k+1][v])
            cols=(X['dimensions'][v] if k==0 else terms[k-1]['dimensions'][v]) if injective else terms[k+1]['dimensions'][v]
            assert not any(x for row in G.matmul(left,right,field,ncols=cols) for x in row),'Differential composition'
            r0=G.rank(ds[k][v],field,ncols=(X['dimensions'][v] if k==0 else terms[k-1]['dimensions'][v]) if injective else terms[k]['dimensions'][v])
            r1=G.rank(ds[k+1][v],field,ncols=terms[k]['dimensions'][v] if injective else terms[k+1]['dimensions'][v])
            assert r0+r1==terms[k]['dimensions'][v],'Resolution exactness'
    return dict(term_dimensions=[T['dimensions'] for T in terms],term_multiplicities=mult,
        resolution_degree=D,exact_through=D-1,term_type='injective' if injective else 'projective',maps_verified=True,_resolution=a)

def unflatten(x,M,N):
    out=[];off=0
    for m,n in zip(M['dimensions'],N['dimensions']):
        out.append([[x[off+i+n*j] for j in range(m)] for i in range(n)]);off+=m*n
    assert off==len(x);return out

def flatten(h,M,N):
    return [h[v][i][j] for v in range(len(h)) for j in range(M['dimensions'][v]) for i in range(N['dimensions'][v])]

def resolution_comparison(f,P,a,b):
    """Explicit natural chain maps lifting the identity, without matching bases."""
    field=f['field'];inj=f['task']=='injective';X=f['modules']['X']
    ad=[[V.parse(A,field) for A in h] for h in [a['augmentation']]+a['differentials']]
    bd=[[V.parse(A,field) for A in h] for h in [b['augmentation']]+b['differentials']]
    previous=[G.identity(d,field) for d in X['dimensions']];out=[]
    for k,(S,T) in enumerate(zip(a['terms'],b['terms'])):
        eq,n=G.hom_equations(P,S,T,field);vectors=G.nullspace(eq,field,ncols=n)
        maps=[unflatten(x,S,T) for x in vectors]
        prevS=X if k==0 else a['terms'][k-1];prevT=X if k==0 else b['terms'][k-1]
        source,target=(prevS,T) if inj else (S,prevT)
        rhs=[G.matmul(bd[k][v],previous[v],field,ncols=source['dimensions'][v]) if inj else G.matmul(previous[v],ad[k][v],field,ncols=source['dimensions'][v]) for v in range(P['n'])]
        cols=[]
        for h in maps:
            image=[G.matmul(h[v],ad[k][v],field,ncols=source['dimensions'][v]) if inj else G.matmul(bd[k][v],h[v],field,ncols=source['dimensions'][v]) for v in range(P['n'])]
            cols.append(flatten(image,source,target))
        goal=flatten(rhs,source,target);matrix=V.columns(cols,len(goal));coeff=V.solve(matrix,goal,field,len(vectors))
        assert V.mv(matrix,coeff,field)==goal,'Chain comparison lift'
        x=V.mv(V.columns(vectors,n),coeff,field);h=unflatten(x,S,T);V.maps_check(P,S,T,h,field)
        out.append(G.matrix_strings_3d(h));previous=h
    return out

def construction_comparison(f,P,a,b):
    field=f['field'];out={}
    for key,mapkey in [('kernel','kernel_inclusion'),('image','image_inclusion'),('cokernel','cokernel_projection')]:
        S,T=a[key],b[key];left=[V.parse(x,field) for x in a[mapkey]];right=[V.parse(x,field) for x in b[mapkey]];hs=[]
        assert S['dimensions']==T['dimensions']
        for v,d in enumerate(S['dimensions']):
            if key!='cokernel':
                cols=[V.solve(right[v],list(col),field,d) for col in zip(*left[v])]
                h=V.columns(cols,d)
                assert G.matmul(right[v],h,field,ncols=d)==left[v]
            else:
                n=f['modules']['B']['dimensions'][v]
                At=G.transpose(left[v],ncols=n)
                h=[V.solve(At,row,field,d) for row in right[v]]
                assert G.matmul(h,left[v],field,ncols=n)==right[v]
            assert G.rank(h,field,ncols=d)==d,'Noninvertible universal comparison';hs.append(h)
        V.maps_check(P,S,T,hs,field);out[key]=G.matrix_strings_3d(hs)
    return out

def verify(f,P,a):
    if f['workflow'] in ('Q6','Q7'):return D.verify(f,P,a)
    field=f['field'];m=f['modules'];task=f['task']
    if task=='kernel_image_cokernel':return construction_check(f,P,a)
    if task in ('projective','injective'):return resolution_check(f,P,a)
    if task=='ext1_dimension':
        sizes,ds=G.bar_cochains(P,m['M'],m['N'],1,field)
        expected=sizes[1]-G.rank(ds[0],field,ncols=sizes[0])-G.rank(ds[1],field,ncols=sizes[1])
        assert a['dimension']==expected==f['expected_ext'][1]
        return dict(ext1_dimension=expected)
    if task in ('hom_basis','full_hom_ext'):
        result=hom_check(P,m['M'],m['N'],a['hom'],field)
        if task=='full_hom_ext':
            assert a['ext']['dimensions']==f['expected_ext'][1:]
            assert len(a['requested_coordinate_columns'])==f['maxdegree']
            for dim,coords in zip(a['ext']['dimensions'],a['requested_coordinate_columns']):assert V.parse(coords,field)==G.identity(dim,field)
            result['identifications']={'MN':V.identify(P,m['M'],m['N'],a['ext'],field)}
            result['ext_dimensions']=f['expected_ext']
        return result
    raise ValueError(task)

def compare(f,P,a,b):
    if f['workflow'] in ('Q6','Q7'):return D.compare(f,P,a,b)
    field=f['field'];out={}
    if '_construction' in a:out['structural_isomorphisms']=construction_comparison(f,P,a['_construction'],b['_construction'])
    if '_resolution' in a:
        out['forward_chain_map']=resolution_comparison(f,P,a['_resolution'],b['_resolution'])
        out['reverse_chain_map']=resolution_comparison(f,P,b['_resolution'],a['_resolution'])
    if 'hom_vectors' in a:
        B=V.columns(b['hom_vectors'],b['hom_rows']);d=b['hom_dimension']
        out['hom']=G.matrix_strings([V.solve(B,x,field,d) for x in a['hom_vectors']])
    if 'identifications' in a:out.update(V.compare(dict(f,task='full_hom_ext'),a,b))
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--input',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    spec=json.loads(args.fixtures.read_text());cases={f['id']:f for f in spec['cases']};ps={p['name']:p for p in spec['posets']};checked={};seen=set();failures=[];eligible=rejected=0
    for path in args.input:
        rows=[json.loads(s) for s in path.read_text().splitlines()];assert rows and rows[-1]['kind']=='completed',str(path)
        for row in rows:
            if row['kind']=='failure':failures.append(dict(row,file=str(path)));continue
            if row['kind'] not in ('timing','correctness'):continue
            assert row['reset_verified']
            if row['kind']=='correctness':assert not set(row)&{'seconds','bytes','nanoseconds','compile_seconds','eligible'}
            elif row['eligible']:
                assert not row['warmup']
                if row['tool']=='TamerOp':assert row['compile_seconds']==row['recompile_seconds']==0
                eligible+=1
            elif not row['warmup']:rejected+=1
            if row['answer'] is None:continue
            f=cases[row['case']];a=row['answer'];key=(row['tool'],f['id']);h=hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest()
            if (key,h) not in seen:
                checked[key]=verify(f,ps[f['poset']],a);seen.add((key,h))
                print('Verified',row['tool'],f['id'],flush=True)
    matches=[]
    for name,f in cases.items():
        if ('TamerOp',name) in checked and ('QPA',name) in checked:
            matches.append(dict(case=name,verified=True,transports=compare(f,ps[f['poset']],checked['TamerOp',name],checked['QPA',name])))
    assert checked or failures
    records=[dict(tool=tool,case=name,verified=True,checks={k:v for k,v in r.items() if k not in ('hom_vectors','identifications') and not k.startswith('_')}) for (tool,name),r in checked.items()]
    out=dict(verified_native_cases=len(checked),verified_matched_cases=len(matches),eligible_timing_rows=eligible,rejected_timing_rows=rejected,
        fixture_sha256=hashlib.sha256(args.fixtures.read_bytes()).hexdigest(),validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),checks=records,matches=matches,
        failures=[r for r in failures if (r['tool'],r['case']) not in checked],
        superseded_failures=[r for r in failures if (r['tool'],r['case']) in checked])
    args.output.write_text(json.dumps(out,indent=2)+'\n');print({k:v for k,v in out.items() if k not in ('checks','matches','failures','superseded_failures')})
if __name__=='__main__':main()
