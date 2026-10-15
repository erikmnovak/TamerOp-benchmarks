#!/usr/bin/env python3
"""Materialize only already allocated core requests; no new scored inputs."""
import argparse,copy,csv,hashlib,json,sys
from fractions import Fraction
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qpa_suite'))
import fixtures as F
G,V=F.G,F.V
BASE=F.ROOT/'audit/2026-09-27/qpa_suite_v1'

def gauge(M,name):
    out=[]
    for v,d in enumerate(M['dimensions']):
        a=G.identity(d)
        if d>1:
            a[0][1]=Fraction((1<<64)+2*v+1,7) if 'numerator64' in name else Fraction(1,(1<<64)+2*v+1)
        out.append(a)
    return out

def supplied_map(f,P):
    """Relation maps retain their original presentation; other maps are explicit."""
    field=f['field'];cert=f['certificate'];name=f['case'];extra={}
    if '_presentation_' in name and 'source' in cert and 'generator_births' in cert['source']:
        c=cert['source'];gb,rb=c['generator_births'],c['relation_births']
        A=G.direct_sum(P,[G.projective(P,v) for v in rb]);B=G.direct_sum(P,[G.projective(P,v) for v in gb])
        h=[]
        for v in range(P['n']):
            gs=[i for i,b in enumerate(gb) if P['leq'][b-1][v]];rs=[j for j,b in enumerate(rb) if P['leq'][b-1][v]]
            h.append([[G.parse_scalar(c['relation_columns'][j][i],field) for j in rs] for i in gs])
        q=[V.parse(a,field) for a in c['quotient_projections']];C=f['modules']['M']
        if name.endswith(('numerator64','denominator64')):
            assert field=='QQ'
            gbasis,mbasis=gauge(B,name),gauge(C,name)
            h=[G.matmul(T,H,field,ncols=d) for T,H,d in zip(gbasis,h,A['dimensions'])]
            q=[G.matmul(G.matmul(T,Q,field,ncols=d),G.inverse(U,field),field,ncols=d)
               for T,Q,U,d in zip(mbasis,q,gbasis,B['dimensions'])]
            B=G.gauge_module(P,B,gbasis,field)
            extra['coefficient_stress_preserved']=True
        V.maps_check(P,B,C,q,field)
        for v in range(P['n']):
            assert G.rank(q[v],field,ncols=B['dimensions'][v])==C['dimensions'][v]
            assert not any(x for row in G.matmul(q[v],h[v],field,ncols=A['dimensions'][v]) for x in row)
            assert G.rank(h[v],field,ncols=A['dimensions'][v])+C['dimensions'][v]==B['dimensions'][v]
        extra.update(recipe='supplied_projective_relation_map',known_cokernel=C,quotient_projection=G.matrix_strings_3d(q))
    elif 'middle' in cert:
        H,T=f['modules']['M'],f['modules']['N'];E=cert['middle']
        if f['poset']=='cube3':
            A,B=T,E;h=[G.identity(a,field) if a else G.zeros(b,0,field) for a,b in zip(A['dimensions'],B['dimensions'])]
            extra['recipe']='nonsplit_sequence_inclusion'
        else:
            A,B=E,H;h=[G.identity(b,field) if b else G.zeros(0,a,field) for a,b in zip(A['dimensions'],B['dimensions'])]
            extra['recipe']='nonsplit_sequence_projection'
    else:
        A,B=f['modules']['M'],f['modules']['N']
        eq,n=G.hom_equations(P,A,B,field);basis=G.nullspace(eq,field,ncols=n)
        # Coverage recipe, independent of either tool and any timing result.
        x=[G.normalize(sum((j+1)*b[i] for j,b in enumerate(basis)),field) for i in range(n)]
        h=[];off=0
        for a,b in zip(A['dimensions'],B['dimensions']):
            h.append([[x[off+i+b*j] for j in range(a)] for i in range(b)]);off+=a*b
        extra.update(recipe='independent_Hom_linear_combination',hom_dimension=len(basis))
    V.maps_check(P,A,B,h,field)
    rank=[G.rank(H,field,ncols=d) for H,d in zip(h,A['dimensions'])]
    extra.update(ranks=rank,kernel_dimensions=[a-r for a,r in zip(A['dimensions'],rank)],
                 image_dimensions=rank,cokernel_dimensions=[b-r for b,r in zip(B['dimensions'],rank)])
    mods=copy.deepcopy(dict(A=A,B=B))
    for k,m in mods.items():m.update(id=name+'_'+k,field=field)
    return mods,dict(f=dict(source='A',target='B',components=G.matrix_strings_3d(h))),extra

def build(folder,workflows,suite=BASE):
    source=suite/'base_pairs.json';base=json.loads(source.read_text())
    pairs={f['case']:f for f in base['cases']};ps={p['name']:p for p in base['posets']}
    rows=list(csv.DictReader((suite/'coverage.csv').open()));cases=[]
    for row in rows:
        if row['workflow'] not in workflows:continue
        f=pairs[row['case']];P=ps[f['poset']];field=f['field'];M,N=f['modules']['M'],f['modules']['N']
        G.all_maps(P,M,field);G.all_maps(P,N,field)
        task=row['variant'];degree=0 if row['workflow']=='Q1' else 1 if row['workflow']=='Q2' else f['maxdegree']
        item=dict(id=row['task_id'],base_case=row['case'],task=task,workflow=row['workflow'],poset=f['poset'],field=field,
            split=row['split'],maxdegree=degree,modules=copy.deepcopy(f['modules']),maps={},expected_ext=f['expected_ext'][:degree+1])
        if row['workflow']=='Q4':
            item['modules'],item['maps'],item['certificate']=supplied_map(f,P)
            item.pop('expected_ext')
        elif row['workflow'] in ('Q6','Q7'):
            D=F.load(Path(__file__).with_name('diagrams.py'),'suite_diagrams')
            item.update(D.make(f,P,task,supplied_map));item.pop('expected_ext')
            for name,M in item['modules'].items():M.update(id=item['id']+'_'+name,field=field)
            D.check_input(item,P)
        elif row['workflow']=='Q5':
            side='M' if task=='projective' else 'N'
            item['modules']={'X':copy.deepcopy(f['modules'][side])}
            item['resolution_of']=side;item.pop('expected_ext')
        if row['workflow'] in ('Q1','Q3'):
            eq,n=G.hom_equations(P,M,N,field);vectors=G.nullspace(eq,field,ncols=n)
            assert len(vectors)==f['expected_ext'][0]
            item['expected_hom_basis']=G.matrix_strings(vectors)
        cases.append(item)
    prior=json.loads((suite/'integrated/derived_fixtures.json').read_text())
    spec=dict(schema='tamerop.qpa_core.v1',suite_cases=220,case_count=len(cases),fields=F.FIELDS,
        cases=cases,posets=base['posets'],phases=prior['phases'],limits=prior['limits'],
        base_pairs_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        reservation_policy='No evaluation timings before candidate freeze; correctness-only checks permitted.')
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'fixtures.json').write_text(json.dumps(spec,indent=2)+'\n')
    (folder/'fixtures.g').write_text('QD_SPEC := '+F.D.gap(spec)+';;\n')
    print('Generated',len(cases),'allocated cases')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workflows',default='Q1,Q2,Q3,Q4,Q5')
    a=p.parse_args();build(a.output,a.workflows.split(','))
