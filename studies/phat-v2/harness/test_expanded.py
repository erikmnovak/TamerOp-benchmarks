import json
from pathlib import Path
import tempfile
import unittest
from generate import graph_answer, terminal_betti, specification
import scaling_generators as g
from fixtures import controls
from oracle import barcode, validate_sparse
from protocol import select_cases
from run import check_job

class ExpandedInputs(unittest.TestCase):
    def test_independent_graph_maps_against_rank_oracle(self):
        for variant in range(4):
            cells,_ = g.graph(0,variant,n=32)
            self.assertEqual(graph_answer(cells),barcode(cells))

    def test_terminal_topology_and_known_barcodes(self):
        for family,n in [('simplicial',4),('cubical',3),('algebraic',8)]:
            for variant in range(4):
                cells,known = getattr(g,family)(0,variant,n=n)
                answer = barcode(cells); validate_sparse(cells)
                if known is not None: self.assertEqual(answer,known)
                betti = terminal_betti(family,variant,n)
                if betti is not None:
                    self.assertEqual([sum(b[0]==h for b in answer['essential']) for h in range(len(betti))],betti)

    def test_fixed_coverage_and_pilot(self):
        rows = [dict(id=s['id'],family=s['family'],variant=s['variant']+1,size_level=s['level']+1,
                     split='control' if s['family']=='control' else 'development',pilot=s['level']==2)
                for s in specification()]
        manifest = dict(study='phat_v2',cases=rows)
        self.assertEqual(len(select_cases(manifest,'confirmation','main')),48)
        self.assertEqual(len(select_cases(manifest,'correctness','main')),56)
        self.assertEqual(len(select_cases(manifest,'pilot','main')),16)
        rows[0]['pilot']=True
        with self.assertRaises(AssertionError): select_cases(manifest,'pilot','main')

    def test_streaming_verifier_rejects_bad_or_incomplete_answers(self):
        answer=controls()['edge'][1]
        case={'edge':dict(id='edge',expected=answer)}
        row=dict(event='sample',kind='correctness',case='edge',phase='query',reset_verified=True,answer=answer)
        records=[dict(event='reset_guard',passed=True),row,dict(event='complete')]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'raw.jsonl'
            def write(rows):path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            write(records); self.assertEqual(check_job(path,case,False,1),{('edge','query'):1})
            write(records[:-1])
            with self.assertRaises(AssertionError):check_job(path,case,False,1)
            write([records[0],dict(row,answer=dict(finite=[],essential=[])),records[2]])
            with self.assertRaises(AssertionError):check_job(path,case,False,1)

if __name__=='__main__':unittest.main()
