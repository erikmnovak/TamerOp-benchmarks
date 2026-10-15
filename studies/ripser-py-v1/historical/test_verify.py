import unittest
import numpy as np
from verify import independent_diagram,witness_check,compare_diagrams,rank
class OracleTests(unittest.TestCase):
    def test_sphere_fields(self):
        a=np.ones((6,6));np.fill_diagonal(a,0)
        for i in range(0,6,2):a[i,i+1]=a[i+1,i]=2
        for p in (2,3,101):
            d=independent_diagram(a,list(range(6)),2,p,np.inf)
            self.assertEqual(d[2],[[1.0,2.0]])
            self.assertEqual(sum(x[1] is None for x in d[0]),1)
    def test_signs(self):
        a=np.ones((3,3));np.fill_diagonal(a,0)
        bad=dict(degree=1,scale=1,terms=[[0,1,1]])
        for p in (2,3,101):
            with self.assertRaisesRegex(AssertionError,'coboundary'):witness_check(bad,a,list(range(3)),p)
    def test_gradient_rejected(self):
        a=np.array([[0,1,np.inf],[1,0,1],[np.inf,1,0]])
        w=dict(degree=1,scale=1,terms=[[0,1,1],[1,2,1]])
        with self.assertRaisesRegex(AssertionError,'coboundary representative'):witness_check(w,a,list(range(3)),3)
    def test_exact_mismatch_rejected(self):
        with self.assertRaises(AssertionError):compare_diagrams([[[0,1]]],[[[0,1.00001]]],False)
    def test_absent_edges_stay_absent_at_infinite_cutoff(self):
        a=np.full((4,4),np.inf);np.fill_diagonal(a,0)
        for i,j in ((0,1),(1,2),(2,3),(0,3)):a[i,j]=a[j,i]=1
        for p in (2,3,101):
            self.assertEqual(independent_diagram(a,list(range(4)),1,p,np.inf)[1],[[1.0,None]])
            w=dict(degree=1,scale=1,terms=[[1,0,p-1]])
            self.assertTrue(witness_check(w,a,list(range(4)),p)['nontrivial_verified'])
    def test_prime_rank(self):
        a=np.array([[1,1],[1,4]])
        self.assertEqual(rank(a,3),1);self.assertEqual(rank(a,101),2)
if __name__=='__main__':unittest.main()

class SparseCertificateTests(unittest.TestCase):
    def test_sparse_solver_agrees_with_dense_rank(self):
        from verify import coboundary_inconsistent,cells,boundary
        rng=np.random.default_rng(417)
        a=np.ones((6,6));np.fill_diagonal(a,0)
        for i in range(0,6,2):a[i,i+1]=a[i+1,i]=2
        for p in (2,3,101):
            cs=cells(a,list(range(6)),2,1);prev=cells(a,list(range(6)),1,1)
            delta=boundary(prev,cs,p).T
            for _ in range(12):
                v=rng.integers(p,size=len(cs));terms={s:int(x) for s,x in zip(cs,v) if x}
                expected=rank(np.column_stack((delta,v)),p)>rank(delta,p)
                self.assertEqual(coboundary_inconsistent(a,list(range(6)),2,1,terms,p)['nontrivial_verified'],expected)
            v=delta@rng.integers(p,size=len(prev))%p;terms={s:int(x) for s,x in zip(cs,v) if x}
            self.assertFalse(coboundary_inconsistent(a,list(range(6)),2,1,terms,p)['nontrivial_verified'])
    def test_connected_large_sphere_and_exact_cochain(self):
        from verify import cells,boundary
        # Suspension of a 25-cycle: a connected flag 2-sphere on 27 vertices.
        a=np.full((27,27),np.inf);np.fill_diagonal(a,0)
        for i in range(25):a[i,(i+1)%25]=a[(i+1)%25,i]=1
        for i in range(25):
            for j in (25,26):a[i,j]=a[j,i]=1
        for p in (2,3,101):
            w=dict(degree=2,scale=1,terms=[[0,1,25,1]])
            self.assertTrue(witness_check(w,a,list(range(27)),p)['nontrivial_verified'])
            cs=cells(a,list(range(27)),2,1);prev=cells(a,list(range(27)),1,1)
            v=boundary(prev,cs,p).T[:,0]
            exact=dict(degree=2,scale=1,terms=[list(s)+[int(x)] for s,x in zip(cs,v) if x])
            with self.assertRaisesRegex(AssertionError,'coboundary representative'):witness_check(exact,a,list(range(27)),p)
