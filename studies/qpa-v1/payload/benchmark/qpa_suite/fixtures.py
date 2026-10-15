"""Exact fixtures for the integrated QPA suite; never reads timing results."""
import importlib.util, random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
D=load(ROOT/'benchmark/qpa_derived/generate.py','integration_derived')
G,B=D.G,D.B
V=load(ROOT/'benchmark/qpa_derived/verify.py','integration_verifier')
FIELDS=['QQ','F2','F3','F101']

def crown(m):
    n=2*m+1;edges=[[i+1,m+i+1] for i in range(m)]+[[i+1,m+(i+1)%m+1] for i in range(m)]+[[m+i+1,n] for i in range(m)]
    edges.sort();leq=[[int(i==j) for j in range(n)] for i in range(n)]
    for u,v in edges:leq[u-1][v-1]=1
    for k in range(n):
        for i in range(n):
            for j in range(n):leq[i][j]|=leq[i][k]&leq[k][j]
    ix={tuple(e):i+1 for i,e in enumerate(edges)}
    rel=[[[ix[i+1,m+i+1],ix[m+i+1,n]],[ix[i+1,m+(i+1)%m+1],ix[m+(i+1)%m+1,n]]] for i in range(m)]
    return dict(name=f'capped_crown{m}',n=n,covers=edges,leq=leq,relations=rel,algebra_dim=sum(map(sum,leq)),vertices=[[i] for i in range(n)])

def presentation(P,field,level,seed):
    """A certified cokernel of sums of vertex projectives on any finite poset."""
    rng=random.Random(seed);n=P['n'];lower=[i+1 for i in range(n) if not any(P['leq'][j][i] for j in range(i))]
    births=[lower[(seed+j)%len(lower)] for j in range(level+3)]
    candidates=[v+1 for v in range(n) if sum(P['leq'][b-1][v] for b in births)>=2]
    rb=[candidates[(seed+j)%len(candidates)] for j in range(level+2)]
    coeff=[]
    for v in rb:
        active=[i for i,b in enumerate(births) if P['leq'][b-1][v-1]]
        col=[0]*len(births)
        for i in active:col[i]=rng.choice([-2,-1,0,1,2])
        col[active[0]]=1;coeff.append(col)
    active=[];qs=[];sections=[];dims=[];ranks=[]
    for v in range(n):
        gen=[i for i,b in enumerate(births) if P['leq'][b-1][v]];rel=[j for j,b in enumerate(rb) if P['leq'][b-1][v]]
        R=[[G.parse_scalar(coeff[j][i],field) for j in rel] for i in gen]
        q=G.nullspace(G.transpose(R,ncols=len(rel)),field,ncols=len(gen));_,piv=G.rref(q,field,ncols=len(gen));h=len(q)
        inv=G.inverse([[row[j] for j in piv] for row in q],field);E=G.zeros(len(gen),h,field)
        for i,j in enumerate(piv):E[j]=inv[i]
        assert G.matmul(q,E,field,ncols=h)==G.identity(h,field)
        assert not any(x for row in G.matmul(q,R,field,ncols=len(rel)) for x in row)
        rank=G.rank(R,field,ncols=len(rel));assert rank+h==len(gen)
        active.append(gen);qs.append(q);sections.append(E);dims.append(h);ranks.append(rank)
    mats=[]
    for u,v in P['covers']:
        u-=1;v-=1;incl=G.zeros(len(active[v]),len(active[u]),field)
        for j,g in enumerate(active[u]):incl[active[v].index(g)][j]=G.parse_scalar(1,field)
        A=G.matmul(G.matmul(qs[v],incl,field,ncols=len(active[u])),sections[u],field,ncols=dims[u])
        assert G.matmul(A,qs[u],field,ncols=len(active[u]))==G.matmul(qs[v],incl,field,ncols=len(active[u]));mats.append(A)
    M=G.module_data(P,dims,mats);G.all_maps(P,M,field)
    cert=dict(generator_births=births,relation_births=rb,relation_columns=coeff,relation_ranks=ranks,
              quotient_projections=G.matrix_strings_3d(qs),sections=G.matrix_strings_3d(sections),exact_cokernel_and_naturality=True,seed=seed)
    return M,cert

def cut_modules(P):
    top=[n-1 for n in P['lengths']];lo=[0]*len(top);cuts=[(n-1)//2 for n in P['lengths'][:2]]
    def box(x,y):
        a=lo[:];b=top[:]
        for axis,tail in enumerate((x,y)):
            if tail:a[axis]=cuts[axis]+1
            else:b[axis]=cuts[axis]
        return B.box(P,a,b)
    L,A,C,N=box(False,False),box(True,False),box(False,True),box(True,True)
    # Four genuine nonsplit interval sequences, with exact natural maps.
    certificates=[]
    for H,T in [(L,A),(L,C),(A,N),(C,N)]:
        support={i+1 for i,(h,t) in enumerate(zip(H['dimensions'],T['dimensions'])) if h or t}
        E=G.supported(P,support);hm,tm,em=[G.all_maps(P,M,'QQ') for M in (H,T,E)]
        inj=[G.identity(t) if t else G.zeros(e,0) for t,e in zip(T['dimensions'],E['dimensions'])]
        proj=[G.identity(h) if h else G.zeros(0,e) for h,e in zip(H['dimensions'],E['dimensions'])]
        for field in FIELDS:
            V.maps_check(P,T,E,inj,field);V.maps_check(P,E,H,proj,field)
            for v in range(P['n']):
                assert H['dimensions'][v]+T['dimensions'][v]==E['dimensions'][v]
            eq,n=G.hom_equations(P,H,E,field);assert not G.nullspace(eq,field,ncols=n)
        certificates.append(dict(head=H,tail=T,middle=E,injection=G.matrix_strings_3d(inj),projection=G.matrix_strings_3d(proj),nonsplit=True))
    return L,A,C,N,certificates

def copies(P,M,n):return G.direct_sum(P,[M for _ in range(n)])
def block_map(P,shapes,src_counts,tgt_counts,field,seed):
    mats=[];blocks=[]
    for j,(a,b) in enumerate(zip(src_counts,tgt_counts)):
        blocks.append([[G.normalize(((i+1)*(k+seed+j)+i-k)%5-2,field) for k in range(a)] for i in range(b)])
    for v in range(P['n']):
        ds=sum(a*M['dimensions'][v] for M,a in zip(shapes,src_counts));dt=sum(b*M['dimensions'][v] for M,b in zip(shapes,tgt_counts))
        mat=G.zeros(dt,ds,field);si=ti=0
        for M,a,b,block in zip(shapes,src_counts,tgt_counts,blocks):
            if M['dimensions'][v]:
                for i in range(b):
                    for j in range(a):mat[ti+i][si+j]=block[i][j]
                si+=a;ti+=b
        mats.append(mat)
    return G.matrix_strings_3d(mats)

def mixed(P,field,task,split):
    L0,A0,B0,N0,seq=cut_modules(P);a,b,c=1,1,2
    L=copies(P,L0,a);M=G.direct_sum(P,[copies(P,A0,b),copies(P,B0,b)]);N=copies(P,N0,c)
    if task=='yoneda':
        mods=dict(L=L,M=M,N=N);maps={};expected=dict(LM=[0,2*a*b,0],MN=[0,2*b*c,0],LN=[0,0,a*c])
    else:
        NN=G.direct_sum(P,[copies(P,A0,b),copies(P,B0,b),N]);Np=G.direct_sum(P,[copies(P,A0,b+1),copies(P,B0,b+1),copies(P,N0,c+1)])
        mods=dict(L=L,Lp=copies(P,L0,a+1),N=NN,Np=Np)
        maps=dict(f=dict(source='Lp',target='L',components=block_map(P,[L0],[a+1],[a],field,3)),
                  g=dict(source='N',target='Np',components=block_map(P,[A0,B0,N0],[b,b,c],[b+1,b+1,c+1],field,3)))
        expected=dict(LN=[0,2*a*b,a*c],LpN=[0,2*(a+1)*b,(a+1)*c],LNp=[0,2*a*(b+1),a*(c+1)])
    for name,m in mods.items():m.update(id=name,field=field);G.all_maps(P,m,field)
    for s in maps.values():
        V.maps_check(P,mods[s['source']],mods[s['target']],[V.parse(A,field) for A in s['components']],field)
        assert any(G.parse_scalar(x,field) for A in s['components'] for row in A for x in row),'Supplied map must be nonzero'
    pairs={'LM':('L','M'),'MN':('M','N'),'LN':('L','N'),'LpN':('Lp','N'),'LNp':('L','Np')}
    for key,want in expected.items():
        actual,_,_=G.bar_oracle(P,*(mods[k] for k in pairs[key]),2,field);assert actual==want,(field,task,key,actual,want)
    cert=dict(family='nonsplit_rectangles',exact_sequences=seq,all_four_fields_nonsplit=True,
              actual_nonzero_structure_maps={name:sum(bool(G.parse_scalar(x,field)) for A in m['edge_matrices'] for row in A for x in row) for name,m in mods.items()})
    assert all(cert['actual_nonzero_structure_maps'].values())
    if task=='yoneda':
        # Explicit extension cocycles across the two cuts, and their nonboundary cup product.
        def cocycle(S,T,target_component):
            out=[]
            for u,v in G.strict_chains(P,1):
                for j in range(S['dimensions'][u]):
                    for i in range(T['dimensions'][v]):
                        # Select the x-cut intermediate summand and the first target copy.
                        value=(j==0 and i==target_component and L0['dimensions'][u] and A0['dimensions'][v]) if S is L else (j==0 and i==0 and A0['dimensions'][u] and N0['dimensions'][v])
                        out.append(G.normalize(int(bool(value)),field))
            return out
        alpha=cocycle(L,M,0);beta=cocycle(M,N,0)
        for S,T,z in [(L,M,alpha),(M,N,beta)]:
            sizes,d=G.bar_cochains(P,S,T,2,field);assert not any(V.mv(d[1],z,field))
        product=V.cup(P,L,M,N,alpha,beta,field);sizes,d=G.bar_cochains(P,L,N,2,field)
        assert not any(V.mv(d[2],product,field))
        projector=G.nullspace(G.transpose(d[1],sizes[1]),field,ncols=sizes[2])
        assert any(V.mv(projector,product,field)),'Product must be a nonzero class'
        cert['product_witness']=dict(alpha=[str(x) for x in alpha],beta=[str(x) for x in beta],cup=[str(x) for x in product],nonzero_mod_boundaries=True)
    return dict(id=f'{"Q8" if task=="yoneda" else "Q9"}_{P["name"]}_{field}_nonsplit_rectangles',task=task,poset=P['name'],field=field,
                level=1,family='nonsplit_rectangles',split=split,modules=mods,maps=maps,expected_dimensions=expected,
                certificate=cert,output='complete signed product table' if task=='yoneda' else 'induced Ext maps in both arguments, degrees 1 and 2')

def tensor(P,field,base,M,N):
    R=dict(dimensions=M['dimensions'],poset=P['name'],edge_matrices=[G.matrix_strings(G.transpose(A,M['dimensions'][u-1])) for A,(u,v) in zip(M['edge_matrices'],P['covers'])])
    R.update(id='R',field=field);N=dict(N,id='L',field=field)
    return dict(id=f'Q10_{base}_reserved',task='tensor',poset=P['name'],field=field,level=1,family='presentation',split='evaluation',
                modules=dict(R=R,L=N),maps={},source_base_id=base,right_orientation='opposite poset',output='balanced tensor dimension and all elementary tensor coordinates')
