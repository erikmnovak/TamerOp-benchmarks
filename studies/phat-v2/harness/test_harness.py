import tempfile
import unittest
from pathlib import Path
from fixtures import controls, algebraic, cubical, encode, decode
from oracle import barcode, validate
from run import check_row


class Mathematics(unittest.TestCase):
    def test_hand_derived_controls(self):
        for name, (cells, expected) in controls().items():
            with self.subTest(name=name):
                self.assertEqual(barcode(cells), expected)

    def test_filtered_basis_changes(self):
        for v in range(4):
            cells, expected = algebraic(0, v)
            self.assertEqual(barcode(cells), expected)

    def test_torus_betti_numbers(self):
        for variant, betti in ((1, [1, 2, 1]), (3, [1, 3, 3, 1])):
            cells, _ = cubical(0, variant)
            result = barcode(cells)
            self.assertEqual([sum(b[0] == h for b in result["essential"])
                              for h in range(len(betti))], betti)

    def test_reject_noncomplex_and_bad_order(self):
        with self.assertRaisesRegex(AssertionError, "squared"):
            validate([(0, 0, []), (1, 1, [0]), (2, 2, [1])])
        with self.assertRaisesRegex(AssertionError, "filtration order"):
            validate([(0, 1, []), (1, 0, [0])])
        with self.assertRaisesRegex(AssertionError, "noncanonical"):
            validate([(0, 0, []), (1, 1, [0, 0])])

    def test_serialization_and_count_guard(self):
        cells, _ = algebraic(0, 1)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "cells.txt"
            p.write_bytes(encode(cells))
            self.assertEqual(decode(p), cells)
            p.write_text("1\n0 0 2 0\n")
            with self.assertRaises(AssertionError):
                decode(p)

    def test_sample_rejection(self):
        cases = {"edge": {"id": "edge", "expected": controls()["edge"][1]}}
        good = dict(event="sample", case="edge", phase="query", kind="measurement",
                    reset_verified=True, answer=cases["edge"]["expected"], seconds=0.001,
                    compile_seconds=0, recompile_seconds=0)
        check_row(good, cases, True)
        for change in (dict(compile_seconds=0.001), dict(reset_verified=False),
                       dict(answer={"finite": [], "essential": []}), dict(seconds=0)):
            with self.assertRaises(AssertionError):
                check_row(dict(good, **change), cases, True)
        with self.assertRaisesRegex(AssertionError, "timing leaked"):
            check_row(good, cases, False)


class ConfirmationProtocol(unittest.TestCase):
    def test_sparse_validity_matches_original_checks(self):
        from oracle import validate_sparse
        for cells, _ in controls().values():
            validate(cells); validate_sparse(cells)
        cells, _ = algebraic(0, 3)
        validate(cells); validate_sparse(cells)
        invalid = [[(0,0,[]),(1,1,[0]),(2,2,[1])],
                   [(0,1,[]),(1,0,[0])],[(0,0,[]),(1,1,[0,0])],
                   [(0,0,[]),(2,1,[0])]]
        for cells in invalid:
            for check in (validate, validate_sparse):
                with self.assertRaises(AssertionError):check(cells)

    def test_freeze_rejects_every_changed_configuration_component(self):
        import copy
        from protocol import verify_freeze, protocol
        identity = dict(mode='confirmation',suite='main',case_ids=['one'],
                        manifest_sha256='fixtures',source={'owner.jl':'source'},
                        harness={'worker.jl':'harness'},build={'binary_sha256':'executable'},
                        runtime={'julia_version':'1.12.1'},limits={'rss_bytes':4096},
                        samples=3,warmups=2,passes=5,protocol=protocol())
        freeze=dict(schema=2,accepted=True,identity=copy.deepcopy(identity))
        verify_freeze(freeze,identity)
        for key in identity:
            bad=copy.deepcopy(identity);bad[key]='changed'
            with self.subTest(key=key),self.assertRaises(AssertionError):verify_freeze(freeze,bad)
        for key in identity['protocol']:
            bad=copy.deepcopy(identity);bad['protocol'][key]='changed'
            with self.subTest(protocol=key),self.assertRaises(AssertionError):verify_freeze(freeze,bad)
        for key in ('julia_flags','thread_environment','analysis'):
            bad=copy.deepcopy(identity)
            if isinstance(bad['protocol'][key],list):bad['protocol'][key].append('--threads=2')
            else:bad['protocol'][key]['extra']='changed'
            with self.assertRaises(AssertionError):verify_freeze(freeze,bad)
        for acceptance in (False,1,None):
            with self.assertRaises(AssertionError):verify_freeze(dict(freeze,accepted=acceptance),identity)
        with self.assertRaises(AssertionError):verify_freeze(dict(freeze,schema=1),identity)
        bad=copy.deepcopy(identity);bad['samples']=3.0
        with self.assertRaises(AssertionError):verify_freeze(freeze,bad)

    def test_route_gc_thread_and_runtime_guards(self):
        import copy
        from run import check_protocol
        from protocol import protocol, GC_POLICY
        ident=dict(runtime=dict(julia_version='1.12.1'),protocol=protocol(),case_ids=['edge'])
        records=[dict(event='metadata',tool='tamerop',protocol_version=2,gc_policy=GC_POLICY,
                      algorithm='public_persistence_diagram',backend_scope='public_result_provenance',
                      julia='1.12.1',threads=1,
                      blas_threads=1,field='F2',order='sublevel',representatives=False)]
        for phase in ('construction','query','combined'):
            records.extend([dict(event='phase',case='edge',phase=phase,forced_gc=True),
                            dict(event='sample',case='edge',phase=phase,
                                 backend=None if phase=='construction' else 'f2_graph_union_find')])
        check_protocol(records,ident,True)
        for key,value in [('gc_policy','per_request'),('threads',2),('blas_threads',2),
                          ('julia','1.11.0'),('algorithm','public_f2_column_reduction'),
                          ('representatives',True),('field','QQ'),('order','superlevel'),
                          ('backend_scope','inferred_from_dimension')]:
            bad=copy.deepcopy(records);bad[0][key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):check_protocol(bad,ident,True)
        bad=copy.deepcopy(records);bad[1]['forced_gc']=False
        with self.assertRaises(AssertionError):check_protocol(bad,ident,True)
        bad=copy.deepcopy(records);bad[-1]['backend']='f2_clearing'
        with self.assertRaises(AssertionError):check_protocol(bad,ident,True)
        bad=copy.deepcopy(records);bad[-1].pop('backend')
        with self.assertRaises(AssertionError):check_protocol(bad,ident,True)
        with self.assertRaises(AssertionError):check_protocol(records+records[1:2],ident,True)

    def test_suite_selection_preserves_evaluation_boundary(self):
        from protocol import select_cases
        cases=[dict(id=str(i),split='control' if i>=48 else 'reserved' if i<10 else 'development',
                    pilot=10<=i<22) for i in range(56)]
        manifest=dict(cases=cases)
        self.assertEqual(len(select_cases(manifest,'confirmation','main')),48)
        self.assertEqual(len(select_cases(manifest,'correctness','main')),56)
        self.assertEqual(set(select_cases(manifest,'pilot','main')),set(map(str,range(10,22))))
        manifest['cases'][10]['split']='reserved'
        with self.assertRaises(AssertionError):select_cases(manifest,'pilot','main')
        larger=dict(cases=[dict(id=str(i),split='development',scale='larger') for i in range(12)])
        self.assertEqual(len(select_cases(larger,'confirmation','larger')),12)
        larger['cases'][0]['split']='reserved'
        with self.assertRaises(AssertionError):select_cases(larger,'pilot','larger')


class AnalysisContract(unittest.TestCase):
    def test_process_block_intervals_and_failure_denominators(self):
        from analysis import log_ratio_summary,aggregate,classify
        x=log_ratio_summary([2]*5)
        self.assertEqual(x['ci95'],[2.0,2.0])
        self.assertAlmostEqual(x['ratio'],2)
        self.assertEqual(classify(1.05),'near_tie')
        self.assertEqual(classify(.8),'loss')
        cases={str(i):dict(family=('graph' if i<3 else 'cubical')) for i in range(4)}
        rows=[dict(case=k,phase='combined',family=c['family'],phat_over_tamerop=2,
                   pass_ratios=[2]*5) for k,c in cases.items()]
        self.assertTrue(aggregate(rows,cases,5)['generally_faster'])
        partial=aggregate(rows[:-1],cases,5)
        self.assertEqual(partial['fixed_cases'],4)
        self.assertEqual(partial['eligible_cases'],3)
        self.assertIsNone(partial['aggregate'])
        self.assertFalse(partial['generally_faster'])
        self.assertEqual(partial['families']['cubical']['counts']['unresolved'],1)


if __name__ == "__main__":
    unittest.main()
