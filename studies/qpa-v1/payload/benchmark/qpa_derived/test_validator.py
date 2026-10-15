#!/usr/bin/env python3
"""Deliberately corrupt valid answers: dimension agreement must not pass."""
import argparse, copy, importlib.util, json
from pathlib import Path
s=importlib.util.spec_from_file_location('derived_verifier',Path(__file__).with_name('verify.py'))
V=importlib.util.module_from_spec(s);s.loader.exec_module(V)

def rejected(f,p,a):
    try:V.verify(f,p,a)
    except AssertionError:return True
    raise AssertionError('A mathematically wrong answer passed verification')

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True)
    p.add_argument('--answers',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    sp=json.loads(args.fixtures.read_text());cases={f['id']:f for f in sp['cases']};ps={p['name']:p for p in sp['posets']}
    rows=[json.loads(l) for l in args.answers.read_text().splitlines()];tests=[]
    for task in ('yoneda','induced','tensor'):
        row=next(r for r in rows if r.get('task')==task and r.get('answer') is not None and r['case'].endswith('_r1'))
        f=cases[row['case']];P=ps[f['poset']];answer=row['answer'];V.verify(f,P,answer)
        if task=='yoneda':
            bad=copy.deepcopy(answer)
            vec=next(v for line in bad['products'] for v in line if any(V.G.parse_scalar(x,f['field']) for x in v))
            vec[:]=[str(-V.G.parse_scalar(x,f['field'])) for x in vec]
            assert rejected(f,P,bad);tests.append('wrong Yoneda sign rejected over '+f['field'])
            bad=copy.deepcopy(answer)
            bad['products'][0][0][0]=str(V.G.parse_scalar(bad['products'][0][0][0],f['field'])+1)
            assert rejected(f,P,bad);tests.append('wrong product with unchanged dimensions rejected')
        elif task=='induced':
            for key in ('first_columns','second_columns'):
                bad=copy.deepcopy(answer);v=bad[key][1][0];v[0]=str(V.G.parse_scalar(v[0],f['field'])+1)
                assert rejected(f,P,bad);tests.append('wrong '+key+' degree-2 map rejected')
        else:
            found=False
            for j in range(len(answer['elementary_columns'])):
                bad=copy.deepcopy(answer)
                if not bad['elementary_columns'][j]:continue
                bad['elementary_columns'][j][0]=str(V.G.parse_scalar(bad['elementary_columns'][j][0],f['field'])+1)
                try:V.verify(f,P,bad)
                except AssertionError:found=True;break
            assert found;tests.append('wrong tensor evaluation with unchanged dimension rejected')
    args.output.write_text(json.dumps(dict(passed=len(tests),tests=tests),indent=2)+'\n');print(tests)
if __name__=='__main__':main()
