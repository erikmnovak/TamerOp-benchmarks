import tempfile,unittest
from pathlib import Path
import numpy as np
from study import fixture,oracle,grade_decoder,parse_cpp

class Correctness(unittest.TestCase):
    def test_spheres_and_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            for n in [6,8]:
                for p in [2,3,101]:
                    c=fixture(Path(folder),'octahedron' if n==6 else 'crosspolytope',n,p,True)
                    expected=[[[0.,1.]]*(n-1)+[[0.,None]]]+[[] for _ in range(n//2-2)]+[[[1.,2.]]]
                    self.assertEqual(c['expected'],expected)
    def test_sparse_zeros_and_disconnected_threshold(self):
        with tempfile.TemporaryDirectory() as folder:
            c=fixture(Path(folder),'zero_cycle',4,101,True)
            self.assertEqual(c['expected'],[[[0.,1.],[0.,1.],[0.,None]],[[1.,None]]])
            c=fixture(Path(folder),'truncated',4,2,True)
            self.assertEqual(c['expected'],[[[0.,1.],[0.,1.],[0.,None],[0.,None]],[]])
            c=fixture(Path(folder),'isolated',4,2,True)
            self.assertEqual(c['expected'],[[[0.,1.],[0.,1.],[0.,None],[0.,None]],[]])
    def test_exact_cli_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            c=fixture(Path(folder),'circle',16,3)
            lookup=grade_decoder(Path(folder)/c['input'],c['format'])
            grade=next(x for x in lookup.values() if x>0)
            txt=f'persistence intervals in dim 0:\n [0,{grade:.6g})\n [0, )\npersistence intervals in dim 1:\n'
            self.assertEqual(parse_cpp(txt,c,lookup),[[[0.,grade],[0.,None]],[]])
            with self.assertRaises(KeyError):parse_cpp(txt.replace(f'{grade:.6g}','987.654'),c,lookup)

if __name__=='__main__':unittest.main()
