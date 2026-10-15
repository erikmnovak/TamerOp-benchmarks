#!/usr/bin/env python3
"""Reject wrong maps/classes/exactness, even when reported dimensions agree."""
import argparse,copy,importlib.util,json
from pathlib import Path
s=importlib.util.spec_from_file_location('core_validator',Path(__file__).with_name('verify.py'))
V=importlib.util.module_from_spec(s);s.loader.exec_module(V)
G=V.G

def zero(x):
    return [zero(y) for y in x] if isinstance(x,list) else '0'
def nonzero(x):
    return any(nonzero(y) for y in x) if isinstance(x,list) else bool(G.parse_scalar(x,'QQ'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--answers',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    spec=json.loads(a.fixtures.read_text());cases={f['id']:f for f in spec['cases']};ps={P['name']:P for P in spec['posets']}
    rows=[json.loads(line) for path in a.answers for line in path.read_text().splitlines()]
    rows=[r for r in rows if r.get('answer') is not None and r.get('field')=='QQ'];tests=[]
    def reject(name,fn):
        try:fn()
        except AssertionError:tests.append(name)
        else:raise AssertionError('Invalid output passed: '+name)
    def check(row,bad,name):
        f=cases[row['case']];reject(name,lambda:V.verify(f,ps[f['poset']],bad))
    r=next(r for r in rows if r['task']=='hom_basis' and len(r['answer']['hom'])>1)
    b=copy.deepcopy(r['answer']);b['hom'].pop();check(r,b,'incomplete Hom basis')
    b=copy.deepcopy(r['answer']);b['hom'][0]=b['hom'][1];check(r,b,'dependent Hom basis with correct count')
    r=next(r for r in rows if r['task']=='ext1_dimension');b=copy.deepcopy(r['answer']);b['dimension']+=1;check(r,b,'wrong Ext dimension')
    r=next(r for r in rows if r['task']=='full_hom_ext' and any(r['answer']['ext']['dimensions']))
    b=copy.deepcopy(r['answer']);next(xs for xs in b['requested_coordinate_columns'] if xs)[0][0]='2';check(r,b,'wrong checked Ext coordinates')
    b=copy.deepcopy(r['answer']);cs=next(cs for cs in b['ext']['cochains'] if cs);cs[0]=zero(cs[0]);check(r,b,'zero Ext class with unchanged dimensions')
    r=next(r for r in rows if r['task']=='kernel_image_cokernel' and nonzero(r['answer']['image_inclusion']))
    for key in ['image_projection','cokernel_projection']:
        b=copy.deepcopy(r['answer']);b[key]=zero(b[key]);check(r,b,'wrong '+key)
    b=copy.deepcopy(r['answer'])
    b['image_inclusion']=[[[str(-G.parse_scalar(x,'QQ')) for x in row] for row in A] for A in b['image_inclusion']]
    check(r,b,'wrong image factorization with unchanged ranks')
    for task in ['projective','injective']:
        r=next(r for r in rows if r['task']==task and nonzero(r['answer']['differentials']))
        b=copy.deepcopy(r['answer']);i=next(i for i,h in enumerate(b['differentials']) if nonzero(h));b['differentials'][i]=zero(b['differentials'][i]);check(r,b,'nonexact '+task+' prefix')
        b=copy.deepcopy(r['answer']);b['augmentation']=zero(b['augmentation']);check(r,b,'wrong '+task+' augmentation')
        b=copy.deepcopy(r['answer']);b['terms'].pop();check(r,b,'truncated '+task+' prefix')
    P=ps['cube3']
    reject('nonprojective term',lambda:V.term_kind(P,G.simple(P,1),'QQ',False))
    reject('noninjective term',lambda:V.term_kind(P,G.simple(P,P['n']),'QQ',True))
    a.output.write_text(json.dumps(dict(passed=True,count=len(tests),tests=tests),indent=2)+'\n');print(tests)
if __name__=='__main__':main()
