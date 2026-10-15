"""Regenerate the historical Rips inputs and verify their exact file hashes."""
from pathlib import Path
import hashlib,json
import numpy as np

def save(path,x):path.write_text(json.dumps(x,indent=2,allow_nan=False)+"\n")
def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(8*1024**2),b""):h.update(block)
    return h.hexdigest()

def pilot_inputs(out):
    OUT=Path(out)
    dest=OUT/'inputs';dest.mkdir(parents=True,exist_ok=True)
    rows=[]
    def add(family,label,shape,n,p,q,keep,threshold=None,m=None):
        case=dict(id=f'{family}_{label}_f{p}',family=family,shape=shape,n=n,prime=p,degree=q,cocycles=keep,threshold=threshold,landmarks=m)
        rng=np.random.default_rng(41004+len(rows))
        if shape=='circle':
            t=np.linspace(0,2*np.pi,n,endpoint=False);points=np.column_stack([np.cos(t),np.sin(t)])
        elif shape=='sphere':
            points=rng.normal(size=(n,3));points/=np.linalg.norm(points,axis=1)[:,None]
        else:points=rng.uniform(size=(n,2))
        if family=='cloud':data=dict(kind='cloud',points=points.tolist())
        elif family=='landmark':
            # Dyadic L-infinity metric: exact shared filtration and metadata.
            points=rng.choice(np.arange(16384),size=(n,2),replace=False)/16384
            matrix=np.max(np.abs(points[:,None,:]-points[None,:,:]),axis=2)
            data=dict(kind='dense',matrix=matrix.tolist())
        elif family=='dense':
            matrix=np.sqrt(np.sum((points[:,None,:]-points[None,:,:])**2,axis=2)).astype(np.float32).astype(float)
            np.fill_diagonal(matrix,0);data=dict(kind='dense',matrix=matrix.tolist())
        else:
            edges=[];births=np.zeros(n)
            if family=='weighted':births=(np.arange(n)%7)/16
            if shape=='grid':
                side=int(np.sqrt(n))
                edges=[(i,i+d) for i in range(n) for d in (1,side) if i+d<n and (d!=1 or i%side<side-1)]
            elif shape in ('octa','crosspoly'):
                block=8 if shape=='crosspoly' else 6
                edges=[(i,j) for i in range(n) for j in range(i+1,n) if i//block==j//block and i//2!=j//2]
                # Delayed antipodal edges fill the sphere.
                edges +=[(i,i+1) for i in range(0,n,2)]
            elif shape=='ties':edges=[(i,j) for i in range(n) for j in range(i+1,n)]
            else:edges=[(i,(i+1)%n) for i in range(n)]
            values=[]
            for i,j in edges:
                v=2.0 if shape in ('octa','crosspoly') and i//2==j//2 else 1.0
                if shape=='zero_ring' and min(i,j)==0:v=0.0
                values.append(v)
            # Diagonal explicitly stored, even zero. Off-diagonal stored once.
            data=dict(kind='sparse',n=n,rows=list(range(n))+[min(i,j) for i,j in edges],cols=list(range(n))+[max(i,j) for i,j in edges],values=births.tolist()+values)
        path=dest/(case['id']+'.json');save(path,data)
        case['input']=str(path.relative_to(OUT));case['sha256']=digest(path)
        case['precision']='Float64 Euclidean versus Float32 endpoints; declared rounding tolerance' if family=='cloud' else 'exact shared Float32-representable filtration values'
        rows.append(case)
    add('cloud','circle96','circle',96,2,1,False)
    add('cloud','circle512_cocycles','circle',512,2,1,True)
    add('cloud','sphere64_cocycles','sphere',64,3,2,True)
    add('cloud','sphere128','sphere',128,101,2,False)
    add('dense','circle256','circle',256,2,1,False)
    add('dense','circle1024','circle',1024,2,1,False)
    add('dense','sphere96_cocycles','sphere',96,3,2,True)
    add('dense','planar128','planar',128,101,2,False)
    add('sparse','grid16','grid',256,2,1,False)
    add('sparse','grid64','grid',4096,2,1,False)
    add('sparse','cycle96_cocycles','cycle',96,3,1,True)
    add('sparse','octa16_cocycles','octa',96,101,2,True)
    add('weighted','grid16_cocycles','grid',256,2,1,True)
    add('weighted','grid64','grid',4096,2,1,False)
    add('weighted','cycle96_cocycles','cycle',96,3,1,True)
    add('weighted','octa16_cocycles','octa',96,101,2,True)
    add('landmark','256_32','planar',256,2,1,False,m=32)
    add('landmark','2048_128','planar',2048,2,1,False,m=128)
    add('landmark','256_64_cocycles','planar',256,3,1,True,m=64)
    add('landmark','512_96_cocycles','planar',512,101,1,True,m=96)
    add('control','sphere3','crosspoly',8,2,3,False)
    add('control','sphere2_cocycles','octa',6,3,2,True)
    add('control','ties','ties',8,101,2,True)
    add('control','stored_zero_cocycles','zero_ring',6,2,1,True,threshold=1.0)
    return rows


def generate(out, evidence):
    out, evidence = Path(out), Path(evidence)
    if np.__version__ != '2.5.3':
        raise RuntimeError('Input generation requires numpy==2.5.3.')
    pilot_inputs(out)
    # The larger planar samples are prefixes of the same original point set.
    points = np.random.default_rng(41011).uniform(size=(512, 2))
    for n in (256, 384, 512):
        a = np.sqrt(np.sum((points[:n, None, :] - points[None, :n, :])**2, axis=2)).astype(np.float32).astype(float)
        np.fill_diagonal(a, 0)
        p = out/'inputs'/f'dense_planar{n}_f101.json'
        with p.open('w') as f:
            json.dump(dict(kind='dense', matrix=a.tolist()), f, separators=(',', ':'), allow_nan=False)
    # All four larger landmark requests share one dyadic metric.
    n = 4096
    points = np.random.default_rng(61005).choice(np.arange(16384), size=(n, 2), replace=False)/16384
    with (out/'inputs/landmark4096.json').open('w') as f:
        f.write('{"kind":"dense","matrix":[')
        for i in range(n):
            if i:
                f.write(',')
            f.write(json.dumps(np.max(np.abs(points-points[i]), axis=1).tolist(), separators=(',', ':')))
        f.write(']}\n')
    reservation = json.loads((evidence/'heldout_reservation.json').read_text())
    for i, fixture in enumerate(reservation['fixtures']):
        rng = np.random.default_rng(reservation['seed']+i)
        n, family, shape = fixture['n'], fixture['family'], fixture['shape']
        if family == 'cloud':
            t = np.arange(n)*2*np.pi/n+rng.uniform(-.2, .2, n)*2*np.pi/n
            x = np.column_stack([np.cos(t), np.sin(t)])
            raw = dict(kind='cloud', points=x.tolist())
        elif family == 'dense':
            x = rng.uniform(size=(n, 2)) if 'planar' in shape else rng.normal(size=(n, 3))
            if 'sphere' in shape:
                x /= np.linalg.norm(x, axis=1)[:, None]
            a = np.sqrt(np.sum((x[:, None, :]-x[None, :, :])**2, axis=2)).astype(np.float32).astype(float)
            np.fill_diagonal(a, 0)
            raw = dict(kind='dense', matrix=a.tolist())
        elif family == 'landmark':
            x = rng.choice(np.arange(16384), size=(n, 2), replace=False)/16384
            a = np.maximum(abs(x[:, 0, None]-x[None, :, 0]), abs(x[:, 1, None]-x[None, :, 1]))
            raw = dict(kind='dense', matrix=a.tolist())
        else:
            name = 'sparse_grid64_f2' if family == 'sparse' else 'weighted_octa16_cocycles_f101'
            raw = json.loads((out/'inputs'/f'{name}.json').read_text())
            perm = rng.permutation(n)
            rows = [int(perm[v]) for v in raw['rows']]
            cols = [int(perm[v]) for v in raw['cols']]
            raw['rows'] = [min(a,b) for a,b in zip(rows,cols)]
            raw['cols'] = [max(a,b) for a,b in zip(rows,cols)]
        name = f'evaluation_{i+1:02d}_{family}_f{fixture["prime"]}'
        (out/'inputs'/f'{name}.json').write_text(json.dumps(raw, separators=(',', ':'))+'\n')
    manifest = json.loads((evidence/'manifest.json').read_text())
    for case in manifest['cases']:
        case['input'] = 'inputs/' + Path(case['input']).name
        actual = digest(out/case['input'])
        if actual != case['sha256']:
            raise RuntimeError(f'Input hash mismatch for {case["id"]}: {actual}')
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    import sys
    m = generate(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f'Exact input hashes verified for {len(m["cases"])} requests.')
