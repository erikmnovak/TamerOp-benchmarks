"""Generate and qualify the fixed candidate inputs serially, outside timers."""
import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import scaling_generators as generators
from fixtures import controls, encode, decode
from oracle import barcode, validate_sparse
from build import digest

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / 'audit/2026-10-04/phat_v2'
FROZEN = ARCHIVE.parent / 'phat_freeze'
SIZES = {
    'graph': [(4096,16384,65536)] * 4,
    'simplicial': [(32,64,128),(32,128,256),(1024,4096,16384),(28,40,56)],
    'cubical': [(64,256,512),(64,256,512),(12,20,32),(12,20,32)],
    'algebraic': [(192,384,768)] * 4,
}

def save(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, separators=(',', ':'))+'\n')
    temporary.replace(path)

def graph_answer(cells):
    """Independent DFS component-map ranks and graph cycle counts at every grade."""
    levels = sorted({g for d,g,b in cells})
    vertices = [i for i,(d,g,b) in enumerate(cells) if d == 0]
    ranks, beta = {}, []
    for j,t in enumerate(levels):
        adjacent = {v:[] for v in vertices if cells[v][1] <= t}
        edges = 0
        for d,g,b in cells:
            if d == 1 and g <= t:
                a,z = b
                adjacent[a].append(z); adjacent[z].append(a); edges += 1
        seen, births = set(), []
        for vertex in adjacent:
            if vertex in seen: continue
            seen.add(vertex); stack = [vertex]; birth = cells[vertex][1]
            while stack:
                v = stack.pop(); birth = min(birth,cells[v][1])
                for w in adjacent[v]:
                    if w not in seen: seen.add(w); stack.append(w)
            births.append(birth)
        for i,s in enumerate(levels[:j+1]): ranks[i,j] = sum(b <= s for b in births)
        beta.append(edges - len(adjacent) + len(births))
    rank = lambda i,j: 0 if i < 0 else ranks[i,j]
    answer = dict(finite=[], essential=[])
    for i,b in enumerate(levels):
        answer['essential'] += [[0,b]]*(rank(i,len(levels)-1)-rank(i-1,len(levels)-1))
        answer['essential'] += [[1,b]]*(beta[i]-(beta[i-1] if i else 0))
        for j in range(i+1,len(levels)):
            count = rank(i,j-1)-rank(i-1,j-1)-rank(i,j)+rank(i-1,j)
            assert count >= 0
            answer['finite'] += [[0,b,levels[j]]]*count
    return {k:sorted(v) for k,v in answer.items()}

def terminal_betti(family, variant, n):
    if family == 'simplicial':
        return ([1,0,math.comb(n-1,3)] if variant == 0 else [1,0,0] if variant == 1
                else [1,0,n] if variant == 2 else [1,0,0,math.comb(n-1,4)])
    if family == 'cubical':
        dim = 2 if variant < 2 else 3
        return [math.comb(dim,h) if variant % 2 else int(h==0) for h in range(dim+1)]
    return None

def specification():
    specs = []
    for family, ladders in SIZES.items():
        for level in range(3):
            for variant, ladder in enumerate(ladders):
                specs.append(dict(id=f'{family}_s{level+1}_v{variant+1}', family=family,
                                  level=level, variant=variant, n=ladder[level]))
    for name in controls(): specs.append(dict(id=name, family='control', level=-1, variant=-1, n=None))
    return specs

def one(spec):
    started = time.monotonic()
    dest = ARCHIVE / 'fixtures'
    dest.mkdir(exist_ok=True)
    metadata = dest / (spec['id']+'.json')
    assert not metadata.exists(), 'case already completed'
    family, variant, n = spec['family'], spec['variant'], spec['n']
    if family == 'control':
        cells, known = controls()[spec['id']]
    else:
        cells, known = getattr(generators,family)(0,variant,n=n)
    validate_sparse(cells)
    if family == 'control':
        assert barcode(cells) == known
        check = 'independent complete rank-invariant barcode oracle'
    elif family == 'graph':
        known = graph_answer(cells)
        check = 'independent complete DFS component-map ranks and graph cycle ranks'
    elif family == 'algebraic':
        assert known is not None
        check = 'known complete barcode preserved by filtered chain isomorphisms'
    else:
        check = 'chain identities, known terminal Betti numbers, complete cross-tool barcode agreement'
    path = dest/(spec['id']+'.txt')
    path.write_bytes(encode(cells))
    listpath = dest/(spec['id']+'.tsv')
    listpath.write_text(spec['id']+'\t'+str(path)+'\n')
    baseline = None
    for algorithm in ('twist','standard'):
        prefix = dest / (spec['id']+'_'+algorithm)
        command = [str(FROZEN/'build/phat_worker'),str(listpath),'correctness','1','0',algorithm]
        with prefix.with_suffix('.jsonl').open('x') as out, prefix.with_suffix('.stderr').open('x') as err:
            subprocess.run(command, stdout=out, stderr=err, check=True, timeout=60)
        sample = None; guard = False; last = None
        with prefix.with_suffix('.jsonl').open() as raw:
            for line in raw:
                row = json.loads(line); last = row
                if row['event'] == 'reset_guard': guard = row['passed']
                if row.get('kind') == 'correctness':
                    assert sample is None and row['case'] == spec['id'] and row['reset_verified']
                    assert row.get('seconds') is None
                    sample = row['answer']
        assert guard and sample is not None and last['event'] == 'complete'
        if known is not None: assert sample == known, 'independent barcode disagrees'
        if baseline is not None: assert sample == baseline, 'PHAT algorithms disagree'
        baseline = sample
    betti = terminal_betti(family,variant,n)
    if betti is not None:
        assert [sum(b[0] == h for b in baseline['essential']) for h in range(len(betti))] == betti
        assert not any(b[0] >= len(betti) for b in baseline['essential'])
    row = dict(id=spec['id'],family=family,size_level=spec['level']+1,variant=variant+1,
               parameter=n,split='control' if family=='control' else 'development',
               pilot=spec['level']==2,scale='medium_large',path=path.name,
               sha256=digest(path),cells=len(cells),nonzeros=sum(len(b) for d,g,b in cells),
               max_degree=max((d for d,g,b in cells),default=0),grades=len({g for d,g,b in cells}),
               expected=baseline,output_bars=sum(map(len,baseline.values())),mathematical_check=check,
               terminal_betti=betti,preparation_seconds=time.monotonic()-started)
    save(metadata,row)
    print(spec['id'],row['cells'],row['nonzeros'],row['output_bars'],round(row['preparation_seconds'],2),flush=True)

def all_cases():
    dest = ARCHIVE / 'fixtures'; dest.mkdir(exist_ok=True)
    specs = specification()
    save(ARCHIVE/'candidate_specification.json',dict(study='phat_v2',cases=specs))
    rows = []
    for spec in specs:
        metadata = dest/(spec['id']+'.json')
        if not metadata.exists():
            command = [sys.executable,str(Path(__file__).resolve()),'--case',spec['id']]
            subprocess.run(command,check=True,timeout=300)
        row = json.loads(metadata.read_text())
        assert row['parameter']==spec['n'] and digest(dest/row['path'])==row['sha256']
        rows.append(row)
        save(dest/'manifest.partial.json',dict(schema=2,study='phat_v2',field='F2',cases=rows))
    assert len(rows)==56
    save(dest/'manifest.json',dict(schema=2,study='phat_v2',field='F2',cases=rows))
    print('Prepared all 48 scored inputs and eight independent controls.',flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--case'); args = parser.parse_args()
    if args.case: one(next(s for s in specification() if s['id']==args.case))
    else: all_cases()
