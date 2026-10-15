#!/usr/bin/env python3
"""Historical 48-case qualification generator; use qpa_suite/integrate.py for the active 220-case allocation.
Freeze the bounded Q8/Q9/Q10 extension; no timings choose these inputs."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]

def load(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

G = load(ROOT/'audit/2026-09-27/qpa_diversity/generate_fixtures.py', 'derived_exact')
B = load(ROOT/'audit/2026-09-27/qpa_large_diversity/generate_fixtures.py', 'derived_families')

def gap(x):
    if isinstance(x, dict): return 'rec('+','.join(k+':='+gap(v) for k,v in x.items())+')'
    if isinstance(x, (list, tuple)): return '['+','.join(map(gap,x))+']'
    if isinstance(x, str): return json.dumps(x)
    if isinstance(x, bool): return 'true' if x else 'false'
    return str(x)

def semisimple(P, counts):
    dims = [counts.get(i+1,0) for i in range(P['n'])]
    return G.module_data(P, dims, [G.zeros(dims[v-1],dims[u-1]) for u,v in P['covers']])

def mapped(P, source, target, seed):
    # Rectangular nonidentity maps, with characteristic-dependent ranks preserved.
    return [G.matrix_strings([[((i+1)*(j+seed)+i-j)%5-2 for j in range(s)]
                             for i in range(t)])
            for s,t in zip(source['dimensions'],target['dimensions'])]

def make():
    posets = [B.make_poset(x) for x in ((2,2,2),(4,4))]
    cases = []
    for P in posets:
        coords = [tuple(x) for x in P['vertices']]
        origin = tuple(0 for _ in P['lengths'])
        u = list(origin); u[-1] = 1
        v = list(origin); v[-2] = 1
        w = v[:]; w[-1] = 1
        x,y,z,t = [coords.index(tuple(q))+1 for q in (origin,u,v,w)]
        for field in G.FIELDS:
            for level in (1,2):
                a,b,c = level,level+1,level+2
                L = semisimple(P,{x:a}); M = semisimple(P,{y:b,z:b})
                N = semisimple(P,{t:c})
                stem = f"{P['name']}_{field}_r{level}"
                cases.append(dict(id='Q8_'+stem,task='yoneda',poset=P['name'],field=field,
                    level=level,modules=dict(L=L,M=M,N=N),maps={},
                    expected_dimensions=dict(LM=[0,2*a*b,0],MN=[0,2*b*c,0],LN=[0,0,a*c]),
                    output='complete Ext1 x Ext1 product table in Ext2; native bases and coordinates'))
                NN = semisimple(P,{y:b,z:b,t:c})
                Lp = semisimple(P,{x:a+1}); Np = semisimple(P,{y:b+1,z:b+1,t:c+1})
                cases.append(dict(id='Q9_'+stem,task='induced',poset=P['name'],field=field,
                    level=level,modules=dict(L=L,Lp=Lp,N=NN,Np=Np),
                    maps=dict(f=dict(source='Lp',target='L',components=mapped(P,Lp,L,level)),
                              g=dict(source='N',target='Np',components=mapped(P,NN,Np,level+1))),
                    expected_dimensions=dict(LN=[0,2*a*b,a*c],LpN=[0,2*(a+1)*b,(a+1)*c],
                                             LNp=[0,2*a*(b+1),a*(c+1)]),
                    output='induced Ext maps in both arguments, degrees 1 and 2, with native bases'))
                # Retain nonzero structure maps for tensors; use a presentation
                # and interval family, not only semisimple local diamonds.
                family = 'presentation' if level == 1 else 'intervals'
                A,C,certificate = B.family_pair(P,field,family,level,11)
                R = dict(dimensions=A['dimensions'],poset=P['name'],
                         edge_matrices=[G.matrix_strings(G.transpose(m,A['dimensions'][u-1]))
                                        for m,(u,v) in zip(A['edge_matrices'],P['covers'])])
                cases.append(dict(id='Q10_'+stem,task='tensor',poset=P['name'],field=field,
                    level=level,modules=dict(R=R,L=C),maps={},family=family,
                    right_orientation='opposite poset; QPA uses L tensor_(Aop) R and flips elementary factors',
                    output='balanced tensor dimension and coordinates of every vertex elementary tensor'))
    # All bar dimensions and relations checked independently, in each field.
    for f in cases:
        P = next(p for p in posets if p['name']==f['poset'])
        for name,m in f['modules'].items():
            m.update(id=name,field=f['field'])
            if name != 'R': G.all_maps(P,m,f['field'])
        for pair,expected in f.get('expected_dimensions',{}).items():
            names = {'LM':('L','M'),'MN':('M','N'),'LN':('L','N'),
                     'LpN':('Lp','N'),'LNp':('L','Np')}[pair]
            actual,_,_ = G.bar_oracle(P,*(f['modules'][n] for n in names),2,f['field'])
            assert actual == expected,(f['id'],pair,actual,expected)
    return dict(schema='tamerop.qpa_derived.v1',case_count=len(cases),
                core_cases=220,extension_cases=48,higher_tor='not included: no QPA 1.37 public higher-Tor implementation found',
                fields=list(G.FIELDS),posets=posets,cases=cases,
                phases=['native_construction','complete_query','construction_and_query'],
                limits=dict(operation_seconds=60,worker_seconds=900,rss_mib=4096),
                selection='2 fixed posets x 4 fields x 2 input sizes/families x 3 requests; development qualification')

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    manifest=make();raw=(json.dumps(manifest,indent=2)+'\n').encode()
    for name,data in [('fixtures.json',raw),('fixtures.g',('QD_SPEC := '+gap(manifest)+';;\n').encode())]:
        path=a.output/name
        if path.exists() and path.read_bytes()!=data: raise SystemExit(f'Refusing to replace frozen input: {path}')
        path.write_bytes(data)
    print(json.dumps(dict(cases=len(manifest['cases']),sha256=hashlib.sha256(raw).hexdigest())))

if __name__=='__main__':main()
