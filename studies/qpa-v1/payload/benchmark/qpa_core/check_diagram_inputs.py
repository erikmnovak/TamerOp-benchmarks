#!/usr/bin/env python3
"""Build independent block reference objects; optionally identify native outputs."""
import argparse,json
from pathlib import Path
import diagrams as D

def run(spec,answers=()):
 ps={P['name']:P for P in spec['posets']};checks=[];oracles={};matches=[]
 for f in spec['cases']:
  P=ps[f['poset']];k=f['field'];D.check_input(f,P)
  r=dict(case=f['id'],field=k,task=f['task'],split=f['split'],input_modules={n:M['dimensions'] for n,M in f['modules'].items()},all_module_relations_and_maps_verified=True)
  if f['workflow']=='Q6':
   A,B,C=[f['modules'][n] for n in 'ABC'];h,j=[D.parse(f['maps'][n]['components'],k) for n in ['f','g']]
   if f['task']=='pushout':
    S=D.G.direct_sum(P,[B,C]);rel=[x+[[-z for z in row] for row in y] for x,y in zip(h,j)];U,q=D.cokernel(P,A,S,rel,k)
    l=[[row[:d] for row in Q] for Q,d in zip(q,B['dimensions'])];right=[[row[d:] for row in Q] for Q,d in zip(q,B['dimensions'])]
   else:
    S=D.G.direct_sum(P,[A,C]);rel=[[x+[-z for z in y] for x,y in zip(X,Y)] for X,Y in zip(h,j)];U,i=D.kernel(P,S,B,rel,k)
    l=[I[:d] for I,d in zip(i,A['dimensions'])];right=[I[d:] for I,d in zip(i,A['dimensions'])]
   oracle=dict(module=U,left=D.G.matrix_strings_3d(l),right=D.G.matrix_strings_3d(right));oracles[f['id']]=D.verify(f,P,oracle)
   r.update(expected_dimensions=U['dimensions'],independent_universal_object=oracle)
  else:
   ts,ds=D.complex_input(f,'C');dims=[]
   for t,T in enumerate(ts):
    dims.append([d-(D.G.rank(ds[t][v],k,ncols=d) if t<2 else 0)-(D.G.rank(ds[t-1][v],k,ncols=ts[t-1]['dimensions'][v]) if t else 0) for v,d in enumerate(T['dimensions'])])
   r.update(expected_input_homology_dimensions=dims,nonzero_differentials=[any(not D.zero(a) for a in h) for h in ds])
  checks.append(r)
 fs={f['id']:f for f in spec['cases']};seen=set()
 for path in answers:
  rows=[json.loads(line) for line in path.read_text().splitlines()];assert rows[-1]['kind']=='completed'
  for r in rows:
   key=r.get('tool'),r.get('case')
   if r['kind'] not in ('correctness','timing') or r.get('answer') is None or key in seen:continue
   seen.add(key);f=fs[r['case']]
   if f['workflow']=='Q6':
    P=ps[f['poset']];v=D.verify(f,P,r['answer']);x=D.compare(f,P,oracles[f['id']],v)
    matches.append(dict(tool=r['tool'],case=f['id'],reference_isomorphism=x))
 return dict(passed=True,cases=len(checks),checks=checks,native_reference_matches=matches)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--answers',type=Path,nargs='*',default=[]);a=p.parse_args()
 result=run(json.loads(a.fixtures.read_text()),a.answers);a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['cases'],'inputs checked;',len(result['native_reference_matches']),'native block-reference identifications')
