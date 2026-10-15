#!/usr/bin/env python3
"""Independent exact bar-resolution, cup-product and balanced-quotient checks.

No TamerOp or QPA linear algebra is used. Native resolutions are compared to
the normalized category-bar resolution by explicit stalkwise lifts.
"""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('qd_exact',ROOT/'audit/2026-09-27/qpa_diversity/generate_fixtures.py')
G=importlib.util.module_from_spec(s);s.loader.exec_module(G)

def solve(A,b,field,ncols):
    assert len(A)==len(b)
    aug=[list(row)+[v] for row,v in zip(A,b)]
    R,pivs=G.rref(aug,field,ncols=ncols+1)
    assert ncols not in pivs,'Inconsistent comparison lift'
    x=[G.normalize(0,field)]*ncols
    for row,p in zip(R,pivs): x[p]=row[-1]
    return x

def parse(A,field):return [[G.parse_scalar(x,field) for x in row] for row in A]
def columns(vs,n):
    assert all(len(v)==n for v in vs), "Coordinate vector length"
    return [[v[i] for v in vs] for i in range(n)]
def mv(A,v,field):
    assert all(len(row)==len(v) for row in A), "Matrix/vector shape"
    return [G.normalize(sum(x*y for x,y in zip(row,v)),field) for row in A]
def norm(v,field):return [G.normalize(x,field) for x in v]
def sub(a,b,field):return norm([x-y for x,y in zip(a,b)],field)

def maps_check(P,M,N,h,field):
    mm=G.all_maps(P,M,field);nn=G.all_maps(P,N,field)
    for v in range(P['n']):
        assert len(h[v])==N['dimensions'][v]
        assert all(len(row)==M['dimensions'][v] for row in h[v])
    for u,v in P['covers']:
        u-=1;v-=1
        assert G.matmul(nn[u,v],h[u],field,ncols=M['dimensions'][u])==G.matmul(h[v],mm[u,v],field,ncols=M['dimensions'][u]),'Naturality'

def bar_terms(P,M,d,field):
    levels=[G.strict_chains(P,k) for k in range(d+1)]
    labels=[[(ch,j) for ch in level for j in range(M['dimensions'][ch[0]])] for level in levels]
    ix=[{label:i for i,label in enumerate(ls)} for ls in labels]
    mm=G.all_maps(P,M,field);dd=[]
    for k in range(1,d+1):
        D=G.zeros(len(labels[k-1]),len(labels[k]),field)
        for col,(ch,j) in enumerate(labels[k]):
            for l in range(M['dimensions'][ch[1]]):D[ix[k-1][ch[1:],l]][col]+=mm[ch[0],ch[1]][l][j]
            for i in range(1,k+1):D[ix[k-1][ch[:i]+ch[i+1:],j]][col]+=(-1)**i
        dd.append([[G.normalize(x,field) for x in row] for row in D])
    return labels,dd

def identify(P,M,N,E,field):
    d=len(E['dimensions']);terms=E['terms'];diffs=[[parse(a,field) for a in h] for h in E['differentials']]
    aug=[parse(a,field) for a in E['augmentation']]
    assert len(terms)==d+1
    native_maps=[G.all_maps(P,T,field) for T in terms]
    # Independent criterion for projectivity on a finite poset: top multiplicities
    # determine the dimension vector of the projective cover. Equality certifies
    # that its always-surjective augmentation is an isomorphism.
    for T,tm in zip(terms,native_maps):
        tops=[]
        for v in range(P['n']):
            vecs=[]
            for u,w in P['covers']:
                if w-1==v:vecs += list(map(list,zip(*tm[u-1,v]))) if tm[u-1,v] else []
            incoming=columns(vecs,T['dimensions'][v])
            tops.append(T['dimensions'][v]-G.rank(incoming,field,ncols=len(vecs)))
        assert T['dimensions']==[sum(tops[u] for u in range(P['n']) if P['leq'][u][v]) for v in range(P['n'])],'Nonprojective term'
    maps_check(P,terms[0],M,aug,field)
    for k in range(d):maps_check(P,terms[k+1],terms[k],diffs[k],field)
    for v in range(P['n']):
        assert G.rank(aug[v],field,ncols=terms[0]['dimensions'][v])==M['dimensions'][v]
        prev=aug[v]
        for k in range(d):
            D=diffs[k][v]
            assert all(not x for row in G.matmul(prev,D,field,ncols=terms[k+1]['dimensions'][v]) for x in row)
            assert G.rank(prev,field,ncols=terms[k]['dimensions'][v])+G.rank(D,field,ncols=terms[k+1]['dimensions'][v])==terms[k]['dimensions'][v],'Resolution exactness'
            prev=D
    labels,bd=bar_terms(P,M,d,field)
    mm=G.all_maps(P,M,field);lifts=[]
    for k in range(d+1):
        images=[]
        for j,(ch,local) in enumerate(labels[k]):
            v=ch[-1]
            if k==0:
                rhs=[mm[ch[0],v][i][local] for i in range(M['dimensions'][v])];A=aug[v]
            else:
                rhs=[G.normalize(sum(bd[k-1][i][j]*mv(native_maps[k-1][pch[-1],v],lifts[k-1][i],field)[r]
                       for i,(pch,_) in enumerate(labels[k-1]) if bd[k-1][i][j]),field)
                     for r in range(terms[k-1]['dimensions'][v])]
                A=diffs[k-1][v]
            lift=solve(A,rhs,field,terms[k]['dimensions'][v]);assert mv(A,lift,field)==rhs
            images.append(lift)
        lifts.append(images)
    sizes,D=G.bar_cochains(P,M,N,d,field)
    ident=[];projectors=[]
    for k in range(1,d+1):
        vectors=[]
        for raw in E['cochains'][k-1]:
            h=[parse(A,field) for A in raw];maps_check(P,terms[k],N,h,field)
            vec=[]
            for i,(ch,_) in enumerate(labels[k]):vec+=mv(h[ch[-1]],lifts[k][i],field)
            assert len(vec)==sizes[k] and not any(mv(D[k],vec,field)),'Not a bar cocycle'
            vectors.append(vec)
        dim=E['dimensions'][k-1];assert len(vectors)==dim
        assert parse(E['coordinate_columns'][k-1],field)==G.identity(dim,field),'Native coordinates'
        # Projection with kernel im(d_(k-1)); no arbitrary sign normalization.
        B=G.transpose(D[k-1],sizes[k-1])
        Q=G.nullspace(B,field,ncols=sizes[k])
        projected=[mv(Q,v,field) for v in vectors]
        assert G.rank(columns(projected,len(Q)),field,ncols=dim)==dim
        expected=sizes[k]-G.rank(D[k],field,ncols=sizes[k])-G.rank(D[k-1],field,ncols=sizes[k-1])
        assert dim==expected,'Incomplete Ext basis'
        ident.append(dict(vectors=vectors,projected=projected,projector=Q,labels=labels[k]))
    return ident

def cup(P,L,M,N,alpha,beta,field):
    # Our bar boundary deletes vertex i with sign (-1)^i. For the unsigned
    # comparison lifts used for Yoneda extensions the (1,1) product is -beta*alpha.
    def unpack(S,T,vec):
        data={};off=0
        for ch in G.strict_chains(P,1):
            rows,cols=T['dimensions'][ch[-1]],S['dimensions'][ch[0]]
            data[ch]=[[vec[off+i+rows*j] for j in range(cols)] for i in range(rows)];off+=rows*cols
        assert off==len(vec);return data
    aa=unpack(L,M,alpha);bb=unpack(M,N,beta);out=[]
    for ch in G.strict_chains(P,2):
        A=G.matmul(bb[ch[1:]],aa[ch[:2]],field,ncols=L['dimensions'][ch[0]])
        out+=norm([-A[i][j] for j in range(L['dimensions'][ch[0]]) for i in range(N['dimensions'][ch[-1]])],field)
    return out

def induced(P,M,N,T,h,vec,degree,first,field):
    out=[];off=0
    for ch in G.strict_chains(P,degree):
        rows,cols=N['dimensions'][ch[-1]],M['dimensions'][ch[0]]
        A=[[vec[off+i+rows*j] for j in range(cols)] for i in range(rows)];off+=rows*cols
        if first:
            B=G.matmul(A,h[ch[0]],field,ncols=T['dimensions'][ch[0]])
            out += [B[i][j] for j in range(T['dimensions'][ch[0]]) for i in range(rows)]
        else:
            B=G.matmul(h[ch[-1]],A,field,ncols=cols)
            out += [B[i][j] for j in range(cols) for i in range(T['dimensions'][ch[-1]])]
    assert off==len(vec);return out

def tensor_check(P,f,a):
    field=f['field'];R,L=f['modules']['R'],f['modules']['L']
    rd,ld=R['dimensions'],L['dimensions'];offs=[0]
    for r,l in zip(rd,ld):offs.append(offs[-1]+r*l)
    n=offs[-1];rels=[]
    for e,(u,v) in enumerate(P['covers']):
        u-=1;v-=1;rmap=parse(R['edge_matrices'][e],field);lmap=parse(L['edge_matrices'][e],field)
        for j in range(rd[v]):
            for i in range(ld[u]):
                col=G.zeros(n,1,field);col=[row[0] for row in col]
                for k in range(rd[u]):col[offs[u]+k*ld[u]+i]+=rmap[k][j]
                for k in range(ld[v]):col[offs[v]+j*ld[v]+k]-=lmap[k][i]
                rels.append(norm(col,field))
    S=columns([norm([G.parse_scalar(x,field) for x in v],field) for v in a['elementary_columns']],a['dimension'])
    assert len(a['elementary_columns'])==n
    assert all(not x for col in rels for x in mv(S,col,field)),'Unbalanced elementary tensor map'
    assert G.rank(S,field,ncols=n)==a['dimension']
    assert a['dimension']==n-G.rank(columns(rels,n),field,ncols=len(rels)),'Wrong balanced quotient'
    return dict(dimension=a['dimension'],elementary_count=n,relation_count=len(rels),S=S)

def verify(f,P,a):
    field=f['field'];m=f['modules']
    if f['task']=='tensor':return dict(tensor=tensor_check(P,f,a))
    pairs={'LM':('L','M'),'MN':('M','N'),'LN':('L','N'),'LpN':('Lp','N'),'LNp':('L','Np')}
    ids={key:identify(P,m[pairs[key][0]],m[pairs[key][1]],E,field) for key,E in a['ext'].items()}
    for key,E in a['ext'].items():assert E['dimensions']==f['expected_dimensions'][key][1:1+len(E['dimensions'])]
    if f['task']=='yoneda':
        target=ids['LN'][1];Q=target['projector'];basis=columns(target['projected'],len(Q));nonzero=zero=0
        for i,alpha in enumerate(ids['LM'][0]['vectors']):
            for j,beta in enumerate(ids['MN'][0]['vectors']):
                expected=mv(Q,cup(P,m['L'],m['M'],m['N'],alpha,beta,field),field)
                got=mv(basis,[G.parse_scalar(x,field) for x in a['products'][i][j]],field)
                assert got==expected,('Yoneda class or sign',f['id'],i,j,got,expected)
                nonzero+=any(expected);zero+=not any(expected)
        assert nonzero and zero,'Need both nonzero and zero product controls'
        counts=dict(nonzero_products=nonzero,zero_products=zero)
    else:
        counts={}
        for label,key,mapname,first in [('first_columns','LpN','f',True),('second_columns','LNp','g',False)]:
            s=f['maps'][mapname];h=[parse(A,field) for A in s['components']]
            maps_check(P,m[s['source']],m[s['target']],h,field)
            for k in (1,2):
                target=ids[key][k-1];Q=target['projector'];basis=columns(target['projected'],len(Q))
                expected=[]
                for i,vec in enumerate(ids['LN'][k-1]['vectors']):
                    wanted=mv(Q,induced(P,m['L'],m['N'],m['Lp'] if first else m['Np'],h,vec,k,first,field),field)
                    got=mv(basis,[G.parse_scalar(x,field) for x in a[label][k-1][i]],field)
                    assert got==wanted,('Induced class',f['id'],label,k,i)
                    expected.append(wanted)
                counts[f'{label}_degree{k}_rank']=G.rank(columns(expected,len(Q)),field,ncols=len(expected))
    return dict(identifications=ids,checks=counts)

def compare(f,a,b):
    """Construct actual TamerOp-to-QPA coordinate maps, not dimension matches."""
    field=f['field'];transports={}
    if f['task']=='tensor':
        T,Q=a['tensor']['S'],b['tensor']['S'];d=a['tensor']['dimension']
        # Rows of the evaluation matrices identify bases of the dual quotient.
        transports['dual_tensor']=[solve(G.transpose(Q,len(Q[0]) if Q else a['tensor']['elementary_count']),row,field,d) for row in T]
    else:
        for key,levels in a['identifications'].items():
            for k,T in enumerate(levels):
                Q=b['identifications'][key][k];n=len(Q['projector']);d=len(Q['projected'])
                B=columns(Q['projected'],n)
                S=[solve(B,v,field,d) for v in T['projected']]
                assert G.rank(columns(S,d),field,ncols=len(S))==d
                transports[f'{key}_{k+1}']=S
    return {key:G.matrix_strings(value) for key,value in transports.items()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True)
    p.add_argument('--input',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    spec=json.loads(args.fixtures.read_text());cases={f['id']:f for f in spec['cases']};ps={p['name']:p for p in spec['posets']}
    checked={};records=[];rows=0;failures=[];eligible=0;rejected=0;validated_outputs=set()
    for path in args.input:
        data=[json.loads(line) for line in path.read_text().splitlines()]
        assert data and data[-1]['kind']=='completed',f'Incomplete worker: {path}'
        for row in data:
            if row['kind']=='failure':
                assert not row['eligible'];failures.append({**row,'file':str(path)});continue
            if row['kind'] not in ('timing','correctness'):continue
            assert row['reset_verified']
            if row['kind']=='correctness':
                assert not set(row).intersection({'seconds','bytes','nanoseconds','compile_seconds','recompile_seconds','eligible'}),'Correctness mode leaked measurements'
            elif row['eligible']:
                assert not row['warmup']
                if row['tool']=='TamerOp':assert row['compile_seconds']==row['recompile_seconds']==0
                eligible+=1
            elif not row['warmup']:rejected+=1
            if row['answer'] is None:continue
            f=cases[row['case']];a=row['answer'];key=(row['tool'],f['id'])
            # Native bases may change without changing the mathematical answer.
            output_hash=hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest()
            if (key,output_hash) not in validated_outputs:
                result=verify(f,ps[f['poset']],a)
                validated_outputs.add((key,output_hash))
                if key not in checked:
                    checked[key]=(a,result)
                    records.append(dict(tool=row['tool'],case=f['id'],checks=result.get('checks',{}),verified=True))
            assert row['reset_verified'];rows+=1
    matches=[]
    for name,f in cases.items():
        if ('TamerOp',name) in checked and ('QPA',name) in checked:
            transport=compare(f,checked['TamerOp',name][1],checked['QPA',name][1])
            matches.append(dict(case=name,coordinate_transports=transport,verified=True))
    assert records or failures,'No results or documented failures'
    out=dict(validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(args.fixtures.read_bytes()).hexdigest(),verified_native_cases=len(records),verified_matched_cases=len(matches),checked_query_rows=rows,
             eligible_timing_rows=eligible,rejected_timing_rows=rejected,failures=failures,checks=records,matches=matches,mathematical_oracle='normalized bar lifts with signed cup products; balanced tensor relations')
    args.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ('checks','matches','failures')}))

if __name__=='__main__':main()
