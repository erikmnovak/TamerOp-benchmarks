#!/usr/bin/env python3
"""Corruption checks of canonical maps, nonzero homology, and cone signs."""
import argparse,copy,json
from pathlib import Path
import diagrams as D

def zero(x):return [zero(y) for y in x] if isinstance(x,list) else '0'
def nz(x):return any(nz(y) for y in x) if isinstance(x,list) else bool(D.G.parse_scalar(x,'QQ'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--answers',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 s=json.loads(a.fixtures.read_text());fs={f['id']:f for f in s['cases']};ps={P['name']:P for P in s['posets']}
 rows=[json.loads(l) for path in a.answers for l in path.read_text().splitlines()];rows=[r for r in rows if r.get('answer') is not None and r.get('field')=='QQ'];tests=[]
 def reject(r,b,label):
  f=fs[r['case']]
  try:D.verify(f,ps[f['poset']],b)
  except AssertionError:tests.append(dict(tool=r['tool'],test=label))
  else:raise AssertionError('Corruption accepted: '+label)
 for tool in ['TamerOp','QPA']:
  rr=[r for r in rows if r['tool']==tool]
  for task in ['pushout','pullback']:
   r=next(r for r in rr if r['task']==task and nz(r['answer']['left']) and nz(r['answer']['right']))
   for side in ['left','right']:
    b=copy.deepcopy(r['answer']);b[side]=zero(b[side]);reject(r,b,task+' missing '+side+' canonical map')
   # A basis-preserving rank corruption must also fail its commuting square.
   candidates=[r for r in rr if r['task']==task]
   caught=False
   for r in candidates:
    b=copy.deepcopy(r['answer']);b['left']=[[[str(-D.G.parse_scalar(x,'QQ')) for x in row] for row in A] for A in b['left']]
    f=fs[r['case']]
    try:D.verify(f,ps[f['poset']],b)
    except AssertionError:tests.append(dict(tool=tool,test=task+' wrong square with unchanged ranks'));caught=True;break
   assert caught
  r=next(r for r in rr if r['task']=='homology' and nz(r['answer']['homology'][1]['quotient']))
  for key in ['inclusion','quotient']:
   b=copy.deepcopy(r['answer']);b['homology'][1][key]=zero(b['homology'][1][key]);reject(r,b,'homology wrong '+key)
  b=copy.deepcopy(r['answer']);b['homology'].pop();reject(r,b,'missing requested homology degree')
  r=next(r for r in rr if r['task']=='mapping_cone' and nz(r['answer']['differentials']))
  b=copy.deepcopy(r['answer']);b['differentials']=zero(b['differentials']);reject(r,b,'zero cone differential with same dimensions')
  b=copy.deepcopy(r['answer']);b['differentials']=[[[[str(-D.G.parse_scalar(x,'QQ')) for x in row] for row in A] for A in h] for h in b['differentials']];reject(r,b,'cone sign error over QQ')
  b=copy.deepcopy(r['answer']);b['degrees']=[0,1,2,3];reject(r,b,'wrong cone degree shift')
  # Change one output module arrow while preserving every stalk dimension.
  found=False
  for r in rr:
   b=copy.deepcopy(r['answer'])
   mods=[b['module']] if r['task'] in ('pushout','pullback') else [h['module'] for h in b['homology']] if r['task']=='homology' else b['terms']
   for M in mods:
    for h in M['edge_matrices']:
     if nz(h):
      h[:]=zero(h);reject(r,b,'wrong output structure map with unchanged dimensions');found=True;break
    if found:break
   if found:break
  assert found
 a.output.write_text(json.dumps(dict(passed=True,count=len(tests),tests=tests),indent=2)+'\n');print(len(tests),'corruptions rejected')
if __name__=='__main__':main()
