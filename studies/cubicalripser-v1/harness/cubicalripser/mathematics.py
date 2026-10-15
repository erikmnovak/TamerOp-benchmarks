"""Independent cubical tensor model and rank-invariant/chain validation over F2.

Cell coordinates use the doubled lattice: even = vertex, odd = edge factor.
This does not call either competitor's topology or reduction code.
"""
from pathlib import Path
import importlib.util,itertools as it,math,struct
_ORACLE=Path(__file__).resolve().parent.parent/'phat/oracle.py'
spec=importlib.util.spec_from_file_location('phat_rank_oracle',_ORACLE)
_ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(_ref)
rank=_ref.rank

def coordinates(shape):
    return (tuple(reversed(p)) for p in it.product(*(range(n) for n in reversed(shape))))
def value_table(shape,values):return dict(zip(coordinates(shape),values,strict=True))
def keys_by_dimension(shape,convention):
    n=len(shape);nv=tuple(s+int(convention=='T') for s in shape);groups=[]
    for degree in range(n+1):
        group=[]
        for axes in it.combinations(range(n),degree):
            for origin in coordinates(tuple(nv[a]-int(a in axes) for a in range(n))):
                group.append(tuple(2*origin[a]+int(a in axes) for a in range(n)))
        groups.append(group)
    return groups

def faces(key):
    for axis,x in enumerate(key):
        if x%2:
            for change in (-1,1):
                k=list(key);k[axis]+=change;yield tuple(k)

def tensor_model(case,values):
    shape=case['shape'];n=len(shape);v=value_table(shape,values)
    if case['order']=='superlevel':v={p:-x for p,x in v.items()}
    groups=keys_by_dimension(shape,case['convention']);grades={}
    if case['convention']=='T':
        for key in groups[-1]:grades[key]=v[tuple(k//2 for k in key)]
        for degree in range(n,0,-1):
            for key in groups[degree]:
                for face in faces(key):grades[face]=min(grades.get(face,math.inf),grades[key])
    else:
        for group in groups:
            for key in group:
                corners=it.product(*(((k//2,k//2+1) if k%2 else (k//2,)) for k in key))
                grades[key]=max(v[p] for p in corners)
    ordered=sorted((k for g in groups for k in g),key=lambda k:(grades[k],sum(x%2 for x in k),k))
    lookup={k:i for i,k in enumerate(ordered)}
    cells=[(sum(x%2 for x in k),grades[k],sorted(lookup[f] for f in faces(k))) for k in ordered]
    # Shared independent rank oracle has integer-grade fixtures; study grades
    # are exactly representable integers in Float64, so conversion is exact.
    assert all(g==int(g) for _,g,_ in cells)
    cells=[(d,int(g),b) for d,g,b in cells];_ref.validate(cells)
    return cells,lookup

def canonical(rows):
    answer={'finite':[],'essential':[]}
    for degree,birth,death in rows:
        assert isinstance(degree,int) and degree>=0 and math.isfinite(birth)
        if death is None:answer['essential'].append([degree,float(birth)])
        else:
            assert math.isfinite(death) and death>birth,'positive sublevel interval required'
            answer['finite'].append([degree,float(birth),float(death)])
    return {k:sorted(v) for k,v in answer.items()}

def expected(case,values):
    cells,_=tensor_model(case,values);answer=_ref.barcode(cells)
    if case['top_only']:
        degree=len(case['shape'])-1;answer={k:[r for r in rows if r[0]==degree] for k,rows in answer.items()}
    return answer

def decode_cpp_chain(chain,degree,ndim):
    axes_by_degree={0:(0,),1:(1,2,4,8),2:(3,5,6,9,10,12),3:(7,11,13,14)}
    keys=[]
    for cell in chain:
        assert len(cell)==(5 if ndim==4 else 4)
        origin=cell[:-1];kind=cell[-1]
        assert all(isinstance(x,int) and x>=0 for x in cell)
        assert all(x==0 for x in origin[ndim:]),'out-of-plane cycle cell'
        axes=axes_by_degree[degree][kind]
        assert axes.bit_count()==degree and axes < (1<<ndim),'invalid cell orientation'
        keys.append(tuple(2*origin[a]+int(bool(axes&(1<<a))) for a in range(ndim)))
    return keys

def decode_julia_chain(record,degree,case):
    keys=keys_by_dimension(case['shape'],case['convention'])[degree]
    assert len(record['ids'])==len(record['coefficients'])
    assert all(c==1 for c in record['coefficients'])
    assert all(isinstance(i,int) and 1<=i<=len(keys) for i in record['ids'])
    return [keys[i-1] for i in record['ids']]

def validate_cycles(case,values,result):
    cells,lookup=tensor_model(case,values);rows=result['rows'];chains=result['cycles']
    assert len(chains)==len(rows),'one cycle for every interval, including multiplicity'
    boundaries=[sum(1<<j for j in b) for _,_,b in cells]
    cycles=[]
    for row,encoded in zip(rows,chains,strict=True):
        h,birth,death=row
        keys=decode_cpp_chain(encoded,h,len(case['shape'])) if result['tool']=='cubicalripser' else decode_julia_chain(encoded,h,case)
        assert len(set(keys))==len(keys),'duplicate cycle cell'
        ids=[lookup[k] for k in keys]
        assert ids and all(cells[i][0]==h and cells[i][1]<=birth for i in ids),'cycle must exist at birth'
        chain=sum(1<<i for i in ids);boundary=0
        for i in ids:boundary^=boundaries[i]
        assert boundary==0,'cycle equation'
        for t in sorted({g for _,g,_ in cells if g>=birth}):
            B=[boundaries[i] for i,(d,g,_) in enumerate(cells) if d==h+1 and g<=t]
            nonzero=rank([*B,chain])>rank(B)
            assert nonzero==(death is None or t<death),f'wrong representative lifetime for {row} at {t}'
        cycles.append(chain)
    # A complete simultaneous basis at every critical level is stronger than
    # checking each chain separately or matching the number of returned bars.
    for t in sorted({g for _,g,_ in cells}):
        for h in range(len(case['shape'])):
            active=[z for row,z in zip(rows,cycles) if row[0]==h and row[1]<=t and (row[2] is None or t<row[2])]
            B=[boundaries[i] for i,(d,g,_) in enumerate(cells) if d==h+1 and g<=t]
            assert rank([*B,*active])-rank(B)==len(active),f'dependent representatives at degree {h}, level {t}'
    return len(cycles)

def load_values(out,case):
    data=(out/case['input']).read_bytes()
    import hashlib
    assert hashlib.sha256(data).hexdigest()==case['sha256']
    assert len(data)==8*math.prod(case['shape'])
    return list(struct.unpack('<'+'d'*(len(data)//8),data))
