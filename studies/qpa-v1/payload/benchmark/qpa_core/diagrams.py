"""Exact diagram fixtures and independent universal-property checks (no native tool).

Matrices act on columns. Complexes use cochain degrees 0,1,2; QPA uses n=-t.
"""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qpa_suite'))
import fixtures as F
G,V=F.G,F.V
R=F.load(Path(__file__).with_name('exact_rref.py'),'diagram_rref');G.rref=R.rref

def parse(h,k):return [V.parse(a,k) for a in h]
def mul(a,b,k,n):return G.matmul(a,b,k,ncols=n)
def zero(a):return not any(x for row in a for x in row)
def ident(M,k):return [G.identity(d,k) for d in M['dimensions']]
def zmap(M,N,k):return [G.zeros(n,m,k) for m,n in zip(M['dimensions'],N['dimensions'])]
def block(a,b,c,d,n1,n2,k):
    assert len(a)==len(b) and len(c)==len(d)
    return [x+y for x,y in zip(a,b)]+[x+y for x,y in zip(c,d)]
def diag(h,j,A,B,C,D,k):
    return [block(x,G.zeros(b,c,k),G.zeros(d,a,k),y,a,c,k) for x,y,a,b,c,d in zip(h,j,A['dimensions'],B['dimensions'],C['dimensions'],D['dimensions'])]
def solvecols(a,b,rows,cols,k):return V.columns([V.solve(a,[r[j] for r in b],k,rows) for j in range(cols)],rows)

def kernel(P,A,B,h,k):
    hs=[V.columns(G.nullspace(x,k,ncols=d),d) for x,d in zip(h,A['dimensions'])]
    ds=[d-G.rank(x,k,ncols=d) for x,d in zip(h,A['dimensions'])];am=G.all_maps(P,A,k);edges=[]
    for u,v in P['covers']:
        y=mul(am[u-1,v-1],hs[u-1],k,ds[u-1]);edges.append(solvecols(hs[v-1],y,ds[v-1],ds[u-1],k))
    K=dict(dimensions=ds,edge_matrices=G.matrix_strings_3d(edges));V.maps_check(P,K,A,hs,k)
    return K,hs

def cokernel(P,A,B,h,k):
    qs=[G.nullspace(G.transpose(x,ncols=a),k,ncols=b) for x,a,b in zip(h,A['dimensions'],B['dimensions'])]
    ds=[len(q) for q in qs];bm=G.all_maps(P,B,k);edges=[]
    for u,v in P['covers']:
        rhs=mul(qs[v-1],bm[u-1,v-1],k,B['dimensions'][u-1]);qt=G.transpose(qs[u-1],ncols=B['dimensions'][u-1])
        edges.append([V.solve(qt,row,k,ds[u-1]) for row in rhs])
    C=dict(dimensions=ds,edge_matrices=G.matrix_strings_3d(edges));V.maps_check(P,B,C,qs,k)
    return C,qs

def hom(P,A,B,k):
    eq,n=G.hom_equations(P,A,B,k);basis=G.nullspace(eq,k,ncols=n)
    xs=[G.normalize(sum((j+1)*z[i] for j,z in enumerate(basis)),k) for i in range(n)];hs=[];o=0
    for a,b in zip(A['dimensions'],B['dimensions']):
        hs.append([[xs[o+i+b*j] for j in range(a)] for i in range(b)]);o+=a*b
    V.maps_check(P,A,B,hs,k);return hs

def make(f,P,task,supplied):
    k=f['field'];mods,maps,cert=supplied(f,P);A,B=mods['A'],mods['B'];h=parse(maps['f']['components'],k)
    def put(name,S,T,x):
        V.maps_check(P,mods[S],mods[T],x,k);maps[name]=dict(source=S,target=T,components=G.matrix_strings_3d(x))
    if task in ('pushout','pullback'):
        mods['C']=copy.deepcopy(f['modules']['N' if task=='pushout' else 'M'])
        S,T=('A','C') if task=='pushout' else ('C','B');put('g',S,T,hom(P,mods[S],mods[T],k))
        return dict(modules=mods,maps=maps,certificate=cert)
    E,q=cokernel(P,A,B,h,k);mods['E']=E
    # Retain the original relation/nonsplit map, and add a genuine middle class.
    # The final quotient makes d1*d0=0 independently of either native package.
    N,M=f['modules']['N'],f['modules']['M'];mods['CN']=G.direct_sum(P,[B,N]);mods['DM']=G.direct_sum(P,[B,M])
    hC=[x+G.zeros(n,a,k) for x,n,a in zip(h,N['dimensions'],A['dimensions'])]
    qC=[[row+[G.normalize(0,k)]*n for row in x] for x,n in zip(q,N['dimensions'])]
    put('c0','A','CN',hC);put('c1','CN','E',qC)
    complexes={'C':dict(terms=['A','CN','E'],differentials=['c0','c1'])}
    if task=='mapping_cone':
        put('d0','A','DM',[x+G.zeros(n,a,k) for x,n,a in zip(h,M['dimensions'],A['dimensions'])])
        put('d1','DM','E',[[row+[G.normalize(0,k)]*n for row in x] for x,n in zip(q,M['dimensions'])])
        put('u0','A','A',ident(A,k));put('u1','CN','DM',diag(ident(B,k),hom(P,N,M,k),B,B,N,M,k));put('u2','E','E',ident(E,k))
        complexes['D']=dict(terms=['A','DM','E'],differentials=['d0','d1'])
        chainmap=dict(source='C',target='D',components=['u0','u1','u2'])
    # Exclude unused modules/maps from timed input construction.
    usedmaps={x for c in complexes.values() for x in c['differentials']}
    if task=='mapping_cone':usedmaps.update(chainmap['components'])
    maps={n:x for n,x in maps.items() if n in usedmaps};usedmods={x for c in complexes.values() for x in c['terms']}
    mods={n:x for n,x in mods.items() if n in usedmods}
    result=dict(modules=mods,maps=maps,complexes=complexes,certificate=cert)
    if task=='mapping_cone':result['chainmap']=chainmap
    return result

def complex_input(f,name):
    c=f['complexes'][name];return [f['modules'][n] for n in c['terms']],[parse(f['maps'][n]['components'],f['field']) for n in c['differentials']]
def check_complex(P,ts,ds,k):
    assert len(ds)==len(ts)-1
    for A,B,h in zip(ts,ts[1:],ds):V.maps_check(P,A,B,h,k)
    for i in range(len(ds)-1):
        for v,d in enumerate(ts[i]['dimensions']):assert zero(mul(ds[i+1][v],ds[i][v],k,d)),'Nonzero differential square'

def check_input(f,P):
    k=f['field'];m=f['modules']
    for M in m.values():G.all_maps(P,M,k)
    for h in f['maps'].values():V.maps_check(P,m[h['source']],m[h['target']],parse(h['components'],k),k)
    for name in f.get('complexes',{}):check_complex(P,*complex_input(f,name),k)
    if 'chainmap' in f:
        C,dc=complex_input(f,'C');D,dd=complex_input(f,'D');us=[parse(f['maps'][n]['components'],k) for n in f['chainmap']['components']]
        for t in range(2):
            for v,d in enumerate(C[t]['dimensions']):assert mul(dd[t][v],us[t][v],k,d)==mul(us[t+1][v],dc[t][v],k,d),'Invalid chain map'

def universal_check(f,P,a):
    k=f['field'];m=f['modules'];A,B,C=[m[x] for x in 'ABC'];h,j=[parse(f['maps'][x]['components'],k) for x in ('f','g')]
    U=a['module'];left,right=[parse(a[x],k) for x in ('left','right')];push=f['task']=='pushout'
    for S,T,x in ([(B,U,left),(C,U,right)] if push else [(U,A,left),(U,C,right)]):V.maps_check(P,S,T,x,k)
    for v,u in enumerate(U['dimensions']):
        da,db,dc=[X['dimensions'][v] for X in (A,B,C)]
        if push:
            r=h[v]+[[-x for x in row] for row in j[v]];q=[x+y for x,y in zip(left[v],right[v])]
            assert u==db+dc-G.rank(r,k,ncols=da) and G.rank(q,k,ncols=db+dc)==u,'Pushout rank'
            assert zero(mul(q,r,k,da)),'Pushout square'
        else:
            r=[x+[-z for z in y] for x,y in zip(h[v],j[v])];q=left[v]+right[v]
            assert u==da+dc-G.rank(r,k,ncols=da+dc) and G.rank(q,k,ncols=u)==u,'Pullback rank'
            assert zero(mul(r,q,k,u)),'Pullback square'
    return dict(dimensions=U['dimensions'],universal_maps_verified=True,_diagram=a)

def homology_check(P,ts,ds,hs,k):
    assert len(ts)==len(hs);check_complex(P,ts,ds,k)
    for t,(T,a) in enumerate(zip(ts,hs)):
        Z,H=a['cycles'],a['module'];i,q=[parse(a[x],k) for x in ('inclusion','quotient')]
        V.maps_check(P,Z,T,i,k);V.maps_check(P,Z,H,q,k)
        for v,d in enumerate(T['dimensions']):
            incoming=ds[t-1][v] if t else G.zeros(d,0,k)
            outgoing=ds[t][v] if t<len(ds) else G.zeros(0,d,k)
            prev=ts[t-1]['dimensions'][v] if t else 0;z=Z['dimensions'][v];hh=H['dimensions'][v]
            rin=G.rank(incoming,k,ncols=prev);rout=G.rank(outgoing,k,ncols=d)
            assert z==d-rout and hh==z-rin,'Homology dimensions'
            assert G.rank(i[v],k,ncols=z)==z and G.rank(q[v],k,ncols=z)==hh
            assert zero(mul(outgoing,i[v],k,z)),'Cycle inclusion'
            lift=solvecols(i[v],incoming,z,prev,k)
            assert mul(i[v],lift,k,prev)==incoming
            assert zero(mul(q[v],lift,k,prev)),'Boundary quotient'
    return [h['module']['dimensions'] for h in hs]

def cone_gold(f,P,qpa=False):
    k=f['field'];C,dc=complex_input(f,'C');D,dd=complex_input(f,'D');us=[parse(f['maps'][n]['components'],k) for n in f['chainmap']['components']]
    Z=dict(dimensions=[0]*P['n'],edge_matrices=[[] for _ in P['covers']]);ts=[];ds=[]
    def term(T,t):return T[t] if 0<=t<3 else Z
    def diff(T,d,t):return d[t] if 0<=t<2 else zmap(term(T,t),term(T,t+1),k)
    for t in range(-1,3):ts.append(G.direct_sum(P,[term(C,t+1),term(D,t)] if qpa else [term(D,t),term(C,t+1)]))
    for t in range(-1,2):
        Dt,Ct,Dn,Cn=term(D,t),term(C,t+1),term(D,t+1),term(C,t+2)
        a,b=diff(D,dd,t),diff(C,dc,t+1);u=us[t+1]
        hs=[]
        for v in range(P['n']):
            negb=[[-x for x in row] for row in b[v]];z=G.zeros(Cn['dimensions'][v],Dt['dimensions'][v],k)
            hs.append(block(negb,z,[[-x for x in row] for row in u[v]],a[v],0,0,k) if qpa else block(a[v],u[v],z,negb,0,0,k))
        ds.append(hs)
    return ts,ds

def verify(f,P,a):
    check_input(f,P);k=f['field']
    if f['task'] in ('pushout','pullback'):return universal_check(f,P,a)
    if f['task']=='homology':
        ts,ds=complex_input(f,'C');dims=homology_check(P,ts,ds,a['homology'],k)
        return dict(homology_dimensions=dims,cycles_boundaries_and_maps_verified=True,_diagram=a)
    qpa=a['convention']=='QPA';ts,ds=cone_gold(f,P,qpa)
    assert a['degrees']==[-1,0,1,2]
    got=[parse(h,k) for h in a['differentials']]
    for X,Y in zip(ts,a['terms']):
        assert X['dimensions']==Y['dimensions'];assert G.all_maps(P,X,k)==G.all_maps(P,Y,k),'Cone structure maps'
    assert got==[[[ [G.normalize(x,k) for x in row] for row in v] for v in h] for h in ds],'Signed cone block differential'
    check_complex(P,a['terms'],got,k)
    return dict(degrees=a['degrees'],term_dimensions=[T['dimensions'] for T in ts],signed_differentials_verified=True,_diagram=a)

def transport(S,T,ls,lt,P,k,quotient):
    hs=[]
    for v,d in enumerate(S['dimensions']):
        assert d==T['dimensions'][v]
        if quotient:
            n=len(ls[v][0]) if ls[v] else (len(lt[v][0]) if lt[v] else 0)
            h=[V.solve(G.transpose(ls[v],ncols=n),row,k,d) for row in lt[v]]
            assert mul(h,ls[v],k,n)==lt[v]
        else:
            h=solvecols(lt[v],ls[v],d,d,k);assert mul(lt[v],h,k,d)==ls[v]
        assert G.rank(h,k,ncols=d)==d;hs.append(h)
    V.maps_check(P,S,T,hs,k);return hs

def compare(f,P,a,b):
    k=f['field'];task=f['task'];a=a['_diagram'];b=b['_diagram']
    if task in ('pushout','pullback'):
        push=task=='pushout'
        def join(x):
            l,r=[parse(x[n],k) for n in ('left','right')]
            return [[xx+yy for xx,yy in zip(u,v)] if push else u+v for u,v in zip(l,r)]
        return dict(universal_isomorphism=G.matrix_strings_3d(transport(a['module'],b['module'],join(a),join(b),P,k,push)))
    if task=='homology':
        out=[]
        for x,y in zip(a['homology'],b['homology']):
            zi=transport(x['cycles'],y['cycles'],parse(x['inclusion'],k),parse(y['inclusion'],k),P,k,False)
            qa,qb=parse(x['quotient'],k),parse(y['quotient'],k)
            rhs=[mul(q,z,k,d) for q,z,d in zip(qb,zi,x['cycles']['dimensions'])]
            out.append(G.matrix_strings_3d(transport(x['module'],y['module'],qa,rhs,P,k,True)))
        return dict(homology_isomorphisms=out)
    # S_t(d,c)=(-c,d) accounts for QPA's [C^(t+1),D^t] order and -u block.
    C,_=complex_input(f,'C');D,_=complex_input(f,'D');hs=[]
    for t in range(-1,3):
        h=[]
        for v in range(P['n']):
            c=C[t+1]['dimensions'][v] if t+1<3 else 0;d=D[t]['dimensions'][v] if t>=0 else 0
            s=G.zeros(c+d,c+d,k)
            for i in range(c):s[i][d+i]=G.normalize(-1,k)
            for i in range(d):s[c+i][i]=G.normalize(1,k)
            h.append(s)
        V.maps_check(P,a['terms'][t+1],b['terms'][t+1],h,k);hs.append(h)
    ad=[parse(h,k) for h in a['differentials']];bd=[parse(h,k) for h in b['differentials']]
    for t in range(3):
        for v,n in enumerate(a['terms'][t]['dimensions']):assert mul(bd[t][v],hs[t][v],k,n)==mul(hs[t+1][v],ad[t][v],k,n)
    return dict(cone_chain_isomorphism=[G.matrix_strings_3d(h) for h in hs])
