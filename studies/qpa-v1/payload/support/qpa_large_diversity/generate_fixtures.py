#!/usr/bin/env python3
"""Exact product-poset modules; independent cubical Ext and cover-Hom oracles."""
from pathlib import Path
from fractions import Fraction as Q
from itertools import product, combinations
import argparse, hashlib, importlib.util, json, random, sys
sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
G=load(HERE.parent/'qpa_diversity/generate_fixtures.py','small_exact')

def make_poset(lengths):
    vertices=list(product(*(range(n) for n in lengths))); ix={v:i+1 for i,v in enumerate(vertices)}
    covers=[]
    for x in vertices:
        for a,n in enumerate(lengths):
            if x[a]+1<n:
                y=list(x);y[a]+=1;covers.append([ix[x],ix[tuple(y)]])
    edges={tuple(e):i+1 for i,e in enumerate(covers)};relations=[]
    for x in vertices:
        for a,b in combinations(range(len(lengths)),2):
            if x[a]+1>=lengths[a] or x[b]+1>=lengths[b]:continue
            u=list(x);u[a]+=1;v=list(x);v[b]+=1;w=list(u);w[b]+=1
            relations.append([[edges[ix[x],ix[tuple(u)]],edges[ix[tuple(u)],ix[tuple(w)]]],
                              [edges[ix[x],ix[tuple(v)]],edges[ix[tuple(v)],ix[tuple(w)]]]])
    name='cube'+str(len(lengths)) if all(n==2 for n in lengths) else 'grid'+str(lengths[0])
    p=G.poset(name,len(vertices),covers,relations);p.update(vertices=vertices,lengths=list(lengths));return p

def sparse_rank(rows,field):
    basis={};prime=G.field_prime(field)
    for row in rows:
        r={j:G.parse_scalar(v,field) for j,v in row.items() if v}
        while r:
            c=min(r);a=r[c]
            if c not in basis:
                inv=1/a if prime is None else pow(a,-1,prime)
                basis[c]={j:G.normalize(v*inv,field) for j,v in r.items()};break
            for j,v in basis[c].items():
                w=G.normalize(r.get(j,0)-a*v,field)
                if w:r[j]=w
                else:r.pop(j,None)
    return len(basis)

def cubical_oracle(P,M,N,field):
    """Tensor of length-one bimodule resolutions of the chain path algebras."""
    vertices=[tuple(x) for x in P['vertices']];ix={x:i for i,x in enumerate(vertices)}
    dim=len(P['lengths']);md=M['dimensions'];nd=N['dimensions']
    mm=G.all_maps(P,M,field);nm=G.all_maps(P,N,field)
    levels=[];offsets=[];sizes=[]
    def end(x,S):
        y=list(x)
        for a in S:y[a]+=1
        return tuple(y)
    for k in range(dim+1):
        cubes=[(x,S) for x in vertices for S in combinations(range(dim),k)
               if all(x[a]+1<P['lengths'][a] for a in S)]
        offsets.append({});total=0
        for x,S in cubes:offsets[-1][x,S]=total;total+=md[ix[x]]*nd[ix[end(x,S)]]
        levels.append(cubes);sizes.append(total)
    ds=[]
    for k in range(dim):
        rows=[{} for _ in range(sizes[k+1])]
        def add(r,c,v):
            if not v:return
            w=G.normalize(rows[r].get(c,0)+v,field)
            if w:rows[r][c]=w
            else:rows[r].pop(c,None)
        for x,S in levels[k+1]:
            u=ix[x];v=ix[end(x,S)];dst=offsets[k+1][x,S]
            for jaxis,a in enumerate(S):
                T=tuple(b for b in S if b!=a);xp=end(x,(a,));yp=end(x,T)
                first=offsets[k][xp,T];last=offsets[k][x,T];sign=(-1)**jaxis
                for j in range(md[u]):
                    for i in range(nd[v]):
                        r=dst+i+nd[v]*j
                        for h in range(md[ix[xp]]):add(r,first+i+nd[v]*h,sign*mm[u,ix[xp]][h][j])
                        for h in range(nd[ix[yp]]):add(r,last+h+nd[ix[yp]]*j,-sign*nm[ix[yp],v][i][h])
        ds.append(rows)
    for A,B in zip(ds[1:],ds):
        for row in A:
            acc={}
            for k,a in row.items():
                for j,b in B[k].items():acc[j]=G.normalize(acc.get(j,0)+a*b,field)
            assert not any(acc.values()),'cubical d squared'
    ranks=[sparse_rank(A,field) for A in ds]+[0]
    expected=[sizes[k]-ranks[k]-(ranks[k-1] if k else 0) for k in range(dim+1)]
    eq,nvars=G.hom_equations(P,M,N,field)
    hom=G.nullspace(eq,field,ncols=nvars)
    assert len(hom)==expected[0]
    return expected,hom,dict(cubical_cochain_dimensions=sizes,differential_ranks=ranks,
                           d_squared_zero=True,hom_coordinate_count=nvars)

def box(P,lo,hi):
    return G.supported(P,{i+1 for i,x in enumerate(P['vertices']) if all(a<=v<=b for a,v,b in zip(lo,x,hi))})

def presentation(P,field,level,seed):
    """Cokernel of a natural map between sums of vertex projectives."""
    rng=random.Random(seed);vs=P['vertices'];d=len(P['lengths']);top=[n-1 for n in P['lengths']]
    # Increasing level adds different birth/death positions and coupled relations.
    available=[i+1 for i,x in enumerate(vs) if sum(x)<=2 and list(x)!=top]
    births=[1]+[available[(2*j+seed)%len(available)] for j in range(level+2)]
    rb=[];coeff=[]
    for j in range(level+2):
        a=(j+1)%len(births);b=(j+2)%len(births)
        v=[max(vs[births[a]-1][k],vs[births[b]-1][k]) for k in range(d)]
        if j%2==0:
            axis=j%d;v[axis]=min(top[axis],v[axis]+1)
        r=vs.index(tuple(v))+1;rb.append(r)
        col=[0]*len(births)
        for g,birth in enumerate(births):
            if P['leq'][birth-1][r-1]:col[g]=rng.choice([-2,-1,0,1,2])
        col[a]=1;coeff.append(col)
    active=[];qs=[];sections=[];relations=[];dims=[];ranks=[]
    for v in range(P['n']):
        gen=[i for i,b in enumerate(births) if P['leq'][b-1][v]]
        rel=[j for j,b in enumerate(rb) if P['leq'][b-1][v]]
        R=[[G.parse_scalar(coeff[j][i],field) for j in rel] for i in gen]
        # The annihilator rows give quotient coordinates; pivot columns give a section.
        q=G.nullspace(G.transpose(R,ncols=len(rel)),field,ncols=len(gen))
        _,piv=G.rref(q,field,ncols=len(gen));h=len(q)
        minor=[[row[j] for j in piv] for row in q];inverse=G.inverse(minor,field)
        E=G.zeros(len(gen),h,field)
        for i,j in enumerate(piv):E[j]=inverse[i]
        assert G.matmul(q,E,field,ncols=h)==G.identity(h,field)
        assert not any(x for row in G.matmul(q,R,field,ncols=len(rel)) for x in row)
        assert G.rank(R,field,ncols=len(rel))+h==len(gen)
        active.append(gen);qs.append(q);sections.append(E);relations.append(R);dims.append(h);ranks.append(len(gen)-h)
    mats=[]
    for u,v in P['covers']:
        u-=1;v-=1;incl=G.zeros(len(active[v]),len(active[u]),field)
        for j,g in enumerate(active[u]):incl[active[v].index(g)][j]=G.parse_scalar(1,field)
        A=G.matmul(G.matmul(qs[v],incl,field,ncols=len(active[u])),sections[u],field,ncols=dims[u])
        assert G.matmul(A,qs[u],field,ncols=len(active[u]))==G.matmul(qs[v],incl,field,ncols=len(active[u]))
        mats.append(A)
    m=G.module_data(P,dims,mats);G.all_maps(P,m,field)
    cert=dict(generator_births=births,relation_births=rb,relation_columns=coeff,
              quotient_projections=G.matrix_strings_3d(qs),sections=G.matrix_strings_3d(sections),
              relation_ranks=ranks,exact_cokernel_and_naturality=True,seed=seed)
    return m,cert

def family_pair(P,field,family,level,seed):
    top=[n-1 for n in P['lengths']];zero=[0]*len(top);cert={}
    if family=='presentation':
        M,cm=presentation(P,field,level,seed);N,cn=presentation(P,field,level+1,seed+7)
        # Retain a higher-Ext probe in the target and ensure unequal supports/dimensions.
        N=G.direct_sum(P,[N,G.simple(P,P['n'])]);cert=dict(source=cm,target_presentation=cn,target_extra_simple=P['n'])
    elif family=='intervals':
        aa=[];bb=[]
        for j in range(level+1):
            hi=top[:];hi[j%len(top)]=max(0,hi[j%len(top)]-1)
            lo=zero[:];lo[(j+1)%len(top)]=1
            aa.append(box(P,zero,hi));bb.append(box(P,lo,top))
        M=G.direct_sum(P,aa);N=G.direct_sum(P,bb+[G.simple(P,P['n'])])
        cert=dict(source_boxes='one missing terminal face per summand',distinct_supports=True)
    elif family=='nonsplit':
        aa=[];bb=[];ee=[];short=[]
        for j in range(level+1):
            lo=zero[:];hi=top[:]
            if len(top)>1 and j%2:lo[1]=1
            a_hi=hi[:];a_hi[0]=top[0]-1;b_lo=lo[:];b_lo[0]=top[0]
            aa.append(box(P,lo,a_hi));bb.append(box(P,b_lo,hi));ee.append(box(P,lo,hi))
            short.append(dict(lower=lo,upper=hi,cut=top[0],head_upper=a_hi,tail_lower=b_lo))
        M=G.direct_sum(P,aa);N=G.direct_sum(P,bb)
        cert=dict(short_exact_boxes=short,middle=G.direct_sum(P,ee),
                  injection_projection='coordinate inclusions/projections on disjoint head/tail stalks',
                  nonsplit_reason='a section is identity on each head stalk, but naturality at the cut edge forces it to be zero')
        # Verify the actual block sequence maps and the obstruction to any section.
        E=cert['middle'];am=G.all_maps(P,M,field);bm=G.all_maps(P,N,field);em=G.all_maps(P,E,field)
        assert all(m+n==e for m,n,e in zip(M['dimensions'],N['dimensions'],E['dimensions']))
        # Head and tail are separated by coordinate zero, so each nonzero projection/inclusion is identity.
        for u,v in P['covers']:
            u-=1;v-=1
            inj_u=G.identity(N['dimensions'][u],field) if N['dimensions'][u] else G.zeros(E['dimensions'][u],0,field)
            inj_v=G.identity(N['dimensions'][v],field) if N['dimensions'][v] else G.zeros(E['dimensions'][v],0,field)
            proj_u=G.identity(M['dimensions'][u],field) if M['dimensions'][u] else G.zeros(0,E['dimensions'][u],field)
            proj_v=G.identity(M['dimensions'][v],field) if M['dimensions'][v] else G.zeros(0,E['dimensions'][v],field)
            assert G.matmul(em[u,v],inj_u,field,ncols=N['dimensions'][u])==G.matmul(inj_v,bm[u,v],field,ncols=N['dimensions'][u])
            assert G.matmul(proj_v,em[u,v],field,ncols=E['dimensions'][u])==G.matmul(am[u,v],proj_u,field,ncols=E['dimensions'][u])
        eq,n=G.hom_equations(P,M,E,field);sections=G.nullspace(eq,field,ncols=n)
        assert not sections,'This family must have Hom(head,middle)=0'
        cert['actual_maps_checked']=True;cert['hom_head_middle_dimension']=0
    elif family=='higher_extension':
        M=box(P,zero,[v-1 for v in top]);N=G.simple(P,P['n'])
        cert=dict(tensor_interval_resolution=True,expected_top_degree=len(top),expected_top_dimension=1)
    elif family=='projective':
        M=G.direct_sum(P,[G.projective(P,1+j%P['n']) for j in range(level+1)])
        N,c=presentation(P,field,level+1,seed+7);cert=dict(target=c,source_projective_vertices=[1+j%P['n'] for j in range(level+1)])
    elif family=='injective':
        M,c=presentation(P,field,level+1,seed);N=G.direct_sum(P,[G.injective(P,P['n']-j%P['n']) for j in range(level+1)])
        cert=dict(source=c,target_injective_vertices=[P['n']-j%P['n'] for j in range(level+1)])
    else:raise ValueError(family)
    return M,N,cert

def build_one(P,field,family,level=1,seed=11,bits=0,axis='none',split='development',sweep='coverage'):
    M,N,certificate=family_pair(P,field,family,level,seed)
    case=f"{P['name']}_{family}_r{level}_{field}_s{seed}"
    if bits:
        assert field=='QQ';case+=f'_{axis}{bits}'
        def gauges(m,offset):
            out=[]
            for v,d in enumerate(m['dimensions']):
                a=G.identity(d)
                if d>1:
                    value=Q((1<<bits)+2*v+offset,7) if axis=='numerator' else Q(1,(1<<bits)+2*v+offset)
                    a[0][1]=value
                out.append(a)
            return out
        M=G.gauge_module(P,M,gauges(M,1),field);N=G.gauge_module(P,N,gauges(N,3),field)
    for side,m in [('M',M),('N',N)]:m.update(id=case+'_'+side,field=field)
    assert M['dimensions']!=N['dimensions'] or M['edge_matrices']!=N['edge_matrices']
    expected,hom,oracle=cubical_oracle(P,M,N,field)
    if family=='projective':
        assert expected[0]==sum(N['dimensions'][v-1] for v in certificate['source_projective_vertices']) and not any(expected[1:])
    if family=='injective':
        assert expected[0]==sum(M['dimensions'][v-1] for v in certificate['target_injective_vertices']) and not any(expected[1:])
    if family=='nonsplit':assert expected[1]>0
    if family=='higher_extension':assert expected==[0]*len(P['lengths'])+[1]
    f=dict(case=case,family=family,field=field,source=M['id'],target=N['id'],poset=P['name'],
           maxdegree=len(P['lengths']),expected_ext=expected,expected_hom_basis=G.matrix_strings(hom),
           oracle=oracle,certificate=certificate,level=level,seed=seed,split=split,sweep=sweep,
           nominal_bits=bits,coefficient_axis=axis,**G.coefficient_bits([M,N]),
           vertices=P['n'],total_stalk_dimension=sum(M['dimensions'])+sum(N['dimensions']),
           max_stalk_dimension=max(M['dimensions']+N['dimensions']),
           input_entries=sum(len(row) for m in (M,N) for a in m['edge_matrices'] for row in a),
           input_nonzeros=sum(bool(Q(x)) for m in (M,N) for a in m['edge_matrices'] for row in a for x in row),
           hom_output_entries=len(hom)*oracle['hom_coordinate_count'])
    return f,[M,N]

def plan():
    jobs=[]
    for lengths in ((2,2,2),(4,4)):
        for family in ('presentation','intervals','nonsplit','projective','injective','higher_extension'):
            for field in G.FIELDS:jobs.append(dict(lengths=lengths,field=field,family=family))
        for family in ('presentation','intervals'):
            for field in ('QQ','F3'):
                for level in (2,3):jobs.append(dict(lengths=lengths,field=field,family=family,level=level,sweep='stalk'))
    for lengths in ((3,3),(5,5),(2,2),(2,2,2,2)):
        for field in ('QQ','F3'):jobs.append(dict(lengths=lengths,field=field,family='presentation',sweep='poset'))
    for axis in ('numerator','denominator'):
        for bits in (16,64):jobs.append(dict(lengths=(4,4),field='QQ',family='presentation',level=2,bits=bits,axis=axis,sweep='coefficients'))
    for lengths in ((2,2,2),(4,4)):
        for field in ('QQ','F3'):jobs.append(dict(lengths=lengths,field=field,family='presentation',level=2,seed=37,split='held_out',sweep='held_out'))
    return jobs

def selfcheck():
    checks=[]
    for lengths in ((2,2),(2,2,2),(3,)):
        P=make_poset(lengths)
        for field in G.FIELDS:
            for u,v in ((1,P['n']),(1,2),(2,2)):
                M=G.simple(P,u);N=G.simple(P,v)
                a,_,_=cubical_oracle(P,M,N,field);b,_,_=G.bar_oracle(P,M,N,len(lengths),field)
                assert a==b
                checks.append(dict(lengths=lengths,field=field,pair=[u,v],expected=a))
            if len(lengths)==2:
                M,N,_=family_pair(P,field,'presentation',1,11)
                a,_,_=cubical_oracle(P,M,N,field);b,_,_=G.bar_oracle(P,M,N,len(lengths),field)
                assert a==b;checks.append(dict(lengths=lengths,field=field,presentation=True,expected=a))
    return checks

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=HERE/'fixtures.json');ap.add_argument('--selfcheck-only',action='store_true');a=ap.parse_args()
    checks=selfcheck();print('Independent cubical/bar agreements',len(checks),flush=True)
    if a.selfcheck_only:return
    ps={};fixtures=[];modules=[]
    for job in plan():
        job=dict(job);lengths=job.pop('lengths');P=make_poset(lengths);ps[P['name']]=P
        f,ms=build_one(P,**job);fixtures.append(f);modules.extend(ms)
        print(f['case'],f['expected_ext'],'max_stalk',f['max_stalk_dimension'],flush=True)
    out=dict(schema='large_diversity_v1',posets=list(ps.values()),modules=modules,fixtures=fixtures,
             oracle_selfchecks=checks,held_out_policy='seed 37 fixtures generated and correctness-checked, never timed or used to choose optimizations in this baseline')
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    print('Wrote',len(fixtures),'fixtures',flush=True)
if __name__=='__main__':main()
