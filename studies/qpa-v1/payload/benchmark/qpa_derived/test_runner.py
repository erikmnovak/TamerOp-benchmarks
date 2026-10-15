#!/usr/bin/env python3
"""Check the operation watchdog at the worker's public JSONL boundary."""
import argparse, importlib.util, json, sys
from pathlib import Path
s=importlib.util.spec_from_file_location('derived_runner',Path(__file__).with_name('run.py'))
R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
CHILD='''import json,sys,time
with open(sys.argv[1], 'w') as f:
 def emit(kind):
  f.write(json.dumps(dict(kind=kind,warmup=False,case="watchdog",phase="query"))+"\\n");f.flush()
 emit("timer_start")
 time.sleep(float(sys.argv[2]))
 emit("timer_end")
 time.sleep(float(sys.argv[3]))
 emit("completed")
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    tests=[]
    for name,inside,outside,worker,expected in [
        ('export_outside_timer',0.1,2.0,5,'completed'),
        ('slow_operation',2.5,0,5,'operation_timeout'),
        ('slow_worker',0.1,2.5,0.75,'worker_timeout')]:
        stem=args.output/name
        result=R.launch([sys.executable,'-c',CHILD,str(stem.with_suffix('.jsonl')),str(inside),str(outside)],
                        stem,dict(rss_mib=128,worker_seconds=worker,operation_seconds=0.6))
        assert result['status']==expected,(name,result)
        tests.append(dict(test=name,status=result['status'],passed=True))
    stem=args.output/'partial';stem.with_suffix('.jsonl').write_text('{"kind":"timer_start"}\n')
    try:R.launch([sys.executable,'-c','pass'],stem,dict(rss_mib=128,worker_seconds=5,operation_seconds=1))
    except RuntimeError:tests.append(dict(test='partial_evidence_not_overwritten',passed=True))
    else:raise AssertionError('Partial evidence was overwritten')
    (args.output/'verification.json').write_text(json.dumps(dict(passed=len(tests),tests=tests),indent=2)+'\n')
    print(tests)

if __name__=='__main__':main()
