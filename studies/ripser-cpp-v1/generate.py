"""Regenerate exact distance files with the original study's fixture routines."""
from pathlib import Path
import json
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ripser-py-v1'))
import runtime as rt


def generate(work,evidence):
    if np.__version__!='2.5.3':raise RuntimeError('Input generation requires numpy==2.5.3.')
    study=rt.load_module(Path(__file__).parent/'historical/study.py','original_cpp_study')
    manifest=json.loads((evidence/'manifest.json').read_text())
    for case in manifest['cases']:
        result=study.fixture(work,case['family'],case['n'],case['prime'])
        if result['sha256']!=case['sha256']:raise RuntimeError('Input hash mismatch: '+case['id'])
    controls=[study.fixture(work,f,n,p,True) for f,n,p in [
        ('octahedron',6,2),('octahedron',6,3),('crosspolytope',8,101),
        ('ties',8,3),('zero_cycle',4,101),('isolated',4,2)]]
    rt.write_json(work/'controls.json',dict(samples=1,cases=controls))
    rt.write_json(work/'manifest.json',manifest)
    print('Exact input hashes verified; independent control answers generated.')


if __name__=='__main__':generate(Path(sys.argv[1]),Path(sys.argv[2]))
