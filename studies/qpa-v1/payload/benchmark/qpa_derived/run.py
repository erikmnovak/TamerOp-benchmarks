#!/usr/bin/env python3
"""Serial, resumable qualification/confirmation driver with bounded resources."""
import argparse, hashlib, json, os, platform, signal, subprocess, sys, time, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
DEPENDENCIES=(
    'benchmark/qpa_uncached.jl', 'benchmark/qpa_diversity.jl',
    'audit/2026-09-27/qpa_diversity/generate_fixtures.py',
    'audit/2026-09-27/qpa_large_diversity/generate_fixtures.py',
    'Project.toml', 'Manifest.toml', 'linalg_thresholds.toml',
)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def launch(cmd, stem, limits, correctness=False):
    log=stem.with_suffix('.log');monitor=stem.with_suffix('.monitor.jsonl');meta=stem.with_suffix('.process.json')
    if meta.exists():return json.loads(meta.read_text())
    if log.exists() or monitor.exists() or stem.with_suffix('.jsonl').exists():
        raise RuntimeError(f'Interrupted evidence exists; use a new output directory: {stem}')
    start=time.monotonic();last_active=None;active_since=None;peak=0;status=None;offset=0;pending=b'';event=None
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    with log.open('w') as out,(open(os.devnull,'w') if correctness else monitor.open('w')) as mon:
        proc=subprocess.Popen(cmd,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        while proc.poll() is None:
            now=time.monotonic();rss=0
            try:
                values=Path(f'/proc/{proc.pid}/status').read_text().splitlines()
                rss=next(int(x.split()[1]) for x in values if x.startswith('VmRSS:'))
            except (OSError,StopIteration):pass
            peak=max(peak,rss)
            data=stem.with_suffix('.jsonl')
            if data.exists():
                with data.open('rb') as f:
                    f.seek(offset);chunk=f.read();offset+=len(chunk)
                lines=(pending+chunk).split(b'\n');pending=lines.pop()
                for line in lines:
                    if not line:continue
                    row=json.loads(line)
                    if row['kind']=='timer_start':active_since=now;event=row
                    elif row['kind'] in ('timer_end','timing','failure','completed'):active_since=None;event=None
            if not correctness:
                sample=dict(elapsed_seconds=now-start,pid=proc.pid,rss_kib=rss,loadavg=os.getloadavg(),active=event)
                mon.write(json.dumps(sample)+'\n');mon.flush()
            if rss>limits['rss_mib']*1024:status='rss_limit'
            elif now-start>limits['worker_seconds']:status='worker_timeout'
            elif active_since and not event['warmup'] and now-active_since>limits['operation_seconds']:
                status='operation_timeout'
            if status:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                break
            time.sleep(0.5)
        code=proc.wait()
    data=stem.with_suffix('.jsonl');footer=None
    if data.exists():
        try:footer=json.loads(data.read_text().splitlines()[-1])
        except (ValueError,IndexError):pass
    if status is None:status='completed' if code==0 and footer and footer['kind']=='completed' else 'failed'
    result=dict(command=cmd,status=status,exit_code=code,elapsed_seconds=time.monotonic()-start,
                peak_sampled_rss_kib=peak,resource_limits=limits,interrupted_operation=event,
                log=str(log),data=str(data),log_sha256=digest(log),data_sha256=digest(data) if data.exists() else None)
    if correctness:
        result.pop('elapsed_seconds');result.pop('peak_sampled_rss_kib')
        result['regime']='correctness-only; resource limits enforced without recording measurements'
    meta.write_text(json.dumps(result,indent=2)+'\n');return result

def select_cases(spec, fields, requested, mode):
    by_id={f['id']:f for f in spec['cases']}
    if not set(fields)<=set(spec['fields']):raise ValueError('Unknown field')
    if not set(requested)<=by_id.keys():raise ValueError('Unknown case')
    chosen=[f for f in spec['cases'] if f['field'] in fields and (not requested or f['id'] in requested)]
    if requested and any(by_id[x]['field'] not in fields for x in requested):raise ValueError('Selected case outside requested fields')
    if mode=='qualification':
        if requested and any(f.get('split')=='evaluation' for f in chosen):
            raise ValueError('Reserved evaluation cases cannot be timed in qualification; use correctness mode')
        chosen=[f for f in chosen if f.get('split')!='evaluation']
    if not chosen:raise ValueError('No cases selected')
    return [f['id'] for f in chosen]

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--gap',type=Path,required=True)
    p.add_argument('--julia',type=Path,required=True);p.add_argument('--passes',type=int,default=1)
    p.add_argument('--samples',type=int,default=1);p.add_argument('--fields',default='QQ,F2,F3,F101')
    p.add_argument('--tools',default='TamerOp,QPA');p.add_argument('--peer-evidence',type=Path,nargs='*',default=[]);
    p.add_argument('--cases',default='');p.add_argument('--mode',choices=['qualification','confirmation','correctness'],default='qualification')
    p.add_argument('--candidate-record',type=Path,help='Frozen fixture, package and harness hashes, required for integrated confirmation')
    p.add_argument('--correctness-compile',choices=['min','yes'],default='min',help='Compilation policy for untimed checks only')
    args=p.parse_args()
    assert 1<=args.passes<=5 and 1<=args.samples<=3
    requested_tools=args.tools.split(',');assert set(requested_tools)<=set(['TamerOp','QPA']) and requested_tools
    if args.mode=='confirmation':assert set(requested_tools)==set(['TamerOp','QPA']) and not args.peer_evidence
    if args.mode=='confirmation':assert args.passes==5 and args.samples==3,'Confirmation uses five passes and three samples'
    args.fixtures=args.fixtures.resolve();args.output=args.output.resolve()
    spec=json.loads(args.fixtures.read_text());fields=args.fields.split(',');selected=args.cases.split(',') if args.cases else []
    selected=select_cases(spec,fields,selected,args.mode)
    fields=[field for field in fields if any(f['field']==field and f['id'] in selected for f in spec['cases'])]
    if args.mode=='correctness':assert args.passes==args.samples==1,'Correctness checks run once without timings'
    context=dict(mode=args.mode,tools=requested_tools,correctness_compile=args.correctness_compile if args.mode=='correctness' else None,peer_evidence={str(p.resolve()):digest(p) for p in args.peer_evidence},platform=platform.platform(),machine_activity='shared host; not claimed isolated',
                 fixture_sha256=digest(args.fixtures),gap_fixture_sha256=digest(args.fixtures.with_suffix('.g')),
                 dependency_sha256={name:digest(ROOT/name) for name in DEPENDENCIES if (ROOT/name).exists()},
                 package_sha256={str(p.relative_to(ROOT)):digest(p) for base in ('src','ext') for p in sorted((ROOT/base).rglob('*.jl'))},
                 executable_paths=dict(julia=str(args.julia.resolve()),gap=str(args.gap.resolve())),passes=args.passes,samples=args.samples,fields=fields,cases=selected,
                 limits=spec['limits'],harness_sha256={f.name:digest(f) for f in HERE.iterdir() if f.is_file()},
                 allocation_scope='runtime allocated bytes per timer; not retained memory',
                 rss_scope='sampled process RSS, includes runtime and compilation; not retained mathematical storage')
    if args.mode=='confirmation' and spec.get('schema') in ('tamerop.qpa_derived.integrated.v1','tamerop.qpa_core.v1'):
        if not args.candidate_record:raise ValueError('Integrated confirmation requires a frozen candidate record after development')
        frozen=json.loads(args.candidate_record.read_text())
        assert frozen.get('optimization_stopping_condition_met') is True
        for key in ('fixture_sha256','package_sha256','harness_sha256','dependency_sha256'):
            assert frozen[key]==context[key],f'Frozen candidate mismatch: {key}'
        context['candidate_record_sha256']=digest(args.candidate_record)
    if args.mode=='correctness':
        context['allocation_scope']='not measured';context['rss_scope']='not measured; cap enforced only'
    context['selected_splits']={f['id']:f.get('split','historical') for f in spec['cases'] if f['id'] in selected}
    args.output.mkdir(parents=True,exist_ok=True)
    context_file=args.output/'context.json'
    if context_file.exists():assert json.loads(context_file.read_text())==context,'Resume configuration/source changed'
    else:
        context_file.write_text(json.dumps(context,indent=2)+'\n')
        shutil.copytree(HERE,args.output/'harness_snapshot',ignore=shutil.ignore_patterns('__pycache__'))
        for name in DEPENDENCIES:
            source=ROOT/name
            if source.exists():
                target=args.output/'dependency_snapshot'/name
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    results=[];started=time.monotonic()
    for block in range(1,args.passes+1):
        order=fields if block%2 else list(reversed(fields))
        for field in order:
            tools=['TamerOp','QPA'] if block%2 else ['QPA','TamerOp']
            for tool in [t for t in tools if t in requested_tools]:
                stem=args.output/f'{tool.lower()}_pass{block}_{field}'
                if tool=='TamerOp':
                    cmd=[str(args.julia),'--project=.', '--startup-file=no','--threads=1','--compiled-modules=existing' if args.mode=='correctness' else '--compiled-modules=strict',
                         str(HERE/'worker.jl'),str(args.fixtures),str(stem.with_suffix('.jsonl')),field,str(args.samples),str(block)]
                    if args.mode=='correctness':cmd.insert(5,'--compile='+args.correctness_compile)
                    cmd.extend([','.join(selected),args.mode])
                else:
                    wrapper=stem.with_suffix('.g')
                    conf=dict(QD_INPUT=str(args.fixtures.with_suffix('.g')),QD_OUTPUT=str(stem.with_suffix('.jsonl')),
                              QD_FIELD=field,QD_CASES=selected,QD_PASS=block,QD_SAMPLES=args.samples,QD_CORRECTNESS=args.mode=='correctness')
                    text='\n'.join(f'{k}:={json.dumps(v)};;' for k,v in conf.items())+'\nRead('+json.dumps(str(HERE/'worker.g'))+');\n'
                    if wrapper.exists():assert wrapper.read_text()==text
                    else:wrapper.write_text(text)
                    cmd=[str(args.gap),'--bare','-A','-q','--nointeract','--quitonbreak',str(wrapper)]
                print('Running',tool,field,'pass',block,flush=True)
                result=launch(cmd,stem,spec['limits'],correctness=args.mode=='correctness');results.append(result)
                print(result['status'],flush=True)
                if time.monotonic()-started>15*3600:raise SystemExit('Campaign budget reached; existing evidence retained')
    (args.output/'processes.json').write_text(json.dumps(results,indent=2)+'\n')
    good=[r['data'] for r in results if r['status']=='completed']+[str(p.resolve()) for p in args.peer_evidence]
    if good:
        cmd=[sys.executable,str(HERE/'verify.py'),'--fixtures',str(args.fixtures),'--input',*good,
             '--output',str(args.output/'verification.json')]
        subprocess.run(cmd,cwd=ROOT,check=True)
    # No speed headline is produced by a one-pass adapter qualification.
    print('Evidence:',args.output,flush=True)

if __name__=='__main__':main()
