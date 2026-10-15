#!/usr/bin/env python3
"""Compare the full RREF, including pivot convention and empty dimensions."""
import argparse,importlib.util,json,random
from fractions import Fraction
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
G=load(ROOT/'audit/2026-09-27/qpa_diversity/generate_fixtures.py','dense_reference')
R=load(HERE/'exact_rref.py','sparse_reference')
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();rng=random.Random(70473);count=0
for field in ['QQ','F2','F3','F101']:
 for m,n in [(0,0),(0,5),(5,0),(1,7),(7,1),(7,7),(9,5),(5,9)]:
  for density in [0,0.15,0.6,1]:
   for singular in [False,True]:
    A=[[Fraction(rng.randrange(-9,10),rng.choice([1,5,7])) if rng.random()<density else Fraction(0) for _ in range(n)] for _ in range(m)]
    if field=='QQ' and A and n:A[0][0]=Fraction(2**67+3,2**61+1)
    if singular and m>1:A[-1]=A[0][:]
    assert R.rref(A,field,ncols=n)==G.rref(A,field,ncols=n),(field,m,n,density,singular)
    count+=1
args.output.write_text(json.dumps(dict(passed=True,matrices=count,fields=['QQ','F2','F3','F101'],checks='full canonical RREF and pivots, singular/empty/rectangular and large rationals'),indent=2)+'\n');print('Passed',count,'exact comparisons')
