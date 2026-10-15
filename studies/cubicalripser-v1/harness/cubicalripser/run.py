"""Bounded serial workers, immutable run folders, observed failures and host load."""
from pathlib import Path
import argparse,json,os,queue,shutil,signal,subprocess,threading,time,resource
from protocol import sha,verify_hashes,read_rows,check_completion
HERE=Path(__file__).resolve().parent

def own_rss(pid):
    total=0;pending=[pid]
    while pending:
        current=pending.pop()
        try:
            total+=int(next(l.split()[1] for l in Path(f'/proc/{current}/status').read_text().splitlines() if l.startswith('VmRSS:')))*1024
            pending.extend(map(int,Path(f'/proc/{current}/task/{current}/children').read_text().split()))
        except (OSError,StopIteration):pass
    return total

def no_core():resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def worker(out,run,tool,pass_id,cases,mode,julia,depot,M,total_start):
    dest=run/f'{tool}_p{pass_id}';dest.mkdir();(dest/'outputs').mkdir()
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',JULIA_NUM_THREADS='1',JULIA_PKG_PRECOMPILE_AUTO='0',PYTHONDONTWRITEBYTECODE='1',CRIPSER_NUM_THREADS='1')
    if depot:env['JULIA_DEPOT_PATH']=depot
    scripts=run/'harness/cubicalripser'
    cmd=([str(out/'environment/venv/bin/python'),str(scripts/'python_worker.py')] if tool=='cubicalripser' else [julia,'--startup-file=no','--compiled-modules=existing','--pkgimages=existing','--heap-size-hint=3G','--project='+str(out/'candidate'),str(scripts/'julia_worker.jl')])
    ids=[c['id'] for c in cases];cmd += [str(out),','.join(ids),mode,str(dest/'outputs')]
    (dest/'launch.json').write_text(json.dumps(dict(command=cmd,ids=ids,tool=tool,pass_id=pass_id,mode=mode,environment={k:env.get(k) for k in ('JULIA_DEPOT_PATH','JULIA_NUM_THREADS','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','CRIPSER_NUM_THREADS')}),indent=2)+'\n')
    q=queue.Queue();begin=time.monotonic();phase_start=begin;phase='startup';current=None;reason=None;last=0
    with (dest/'stdout.ndjson').open('w') as log,(dest/'stderr.log').open('w') as err,(dest/'monitor.ndjson').open('w') as monitor:
        p=subprocess.Popen(cmd,cwd=out,env=env,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1,start_new_session=True,preexec_fn=no_core)
        def read():
            for line in p.stdout:q.put(line)
        t=threading.Thread(target=read);t.start()
        while p.poll() is None or t.is_alive() or not q.empty():
            try:line=q.get(timeout=.2)
            except queue.Empty:line=None
            if line:
                log.write(line);log.flush()
                try:row=json.loads(line)
                except json.JSONDecodeError:row={}
                if row.get('kind')=='start':phase_start=time.monotonic();phase=row['phase'];current=row['case']
                if row.get('kind')=='environment':print(tool,pass_id,'loaded',round(row['load_seconds'],2),'s',flush=True)
                if row.get('kind')=='case_error':print(tool,current,row['error'][:200],flush=True)
            now=time.monotonic()
            if now-last>=1:
                last=now;rss=0
                try:rss=own_rss(p.pid)
                except (OSError,StopIteration):pass
                monitor.write(json.dumps(dict(elapsed_s=now-begin,phase=phase,case=current,rss_bytes=rss,loadavg=os.getloadavg()))+'\n');monitor.flush()
                limits=M['limits'];cap=limits['startup_seconds'] if phase=='startup' else limits['phase_seconds']
                if reason is None and (rss>limits['rss_bytes'] or now-phase_start>cap or now-begin>limits['worker_seconds'] or now-total_start>limits['total_seconds']):
                    reason='rss_limit' if rss>limits['rss_bytes'] else 'time_limit'
                    if p.poll() is None:
                        os.killpg(p.pid,signal.SIGTERM)
                        try:p.wait(timeout=8)
                        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        t.join();code=p.wait()
    error=None
    try:check_completion(read_rows(dest/'stdout.ndjson'),ids,tool,mode,M['samples'],code,reason)
    except Exception as e:error=str(e)
    completion=dict(tool=tool,pass_id=pass_id,ids=ids,returncode=code,reason=reason,protocol_error=error,seconds=time.monotonic()-begin,complete=error is None)
    (dest/'completion.json').write_text(json.dumps(completion,indent=2)+'\n');print(tool,pass_id,'finished',round(completion['seconds'],1),'s',error or '',flush=True)
    return completion

def qualified_selection(selected,outcomes):
    """Reject unsupported output contracts before launching any timed work."""
    lane=lambda c:(len(c['shape']),c['convention'],c['order'],c['representatives'],c['top_only'])
    good={tuple(row['lane']) for row in outcomes if row['status']=='verified'}
    bad={tuple(row['lane']) for row in outcomes if row['status']!='verified'}
    failed_cycles=any(row['status']!='verified' and row['lane'][3] for row in outcomes)
    failed_shortcut=any(row['status']!='verified' and row['lane'][4] for row in outcomes)
    accepted=[];skipped=[]
    for c in selected:
        reason=None
        if c['representatives'] and failed_cycles:reason='interval-generator contract not qualified for representative output'
        elif c['top_only'] and failed_shortcut:reason='top-degree shortcut not qualified'
        elif lane(c) in bad:reason='lane has a failed qualification case'
        elif lane(c) not in good:reason='lane was never qualified'
        if reason:skipped.append(dict(case=c['id'],reason=reason,lane=list(lane(c))))
        else:accepted.append(c)
    return accepted,skipped

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--group',choices=['qualification','smoke','pilot'],default='qualification');p.add_argument('--ids');p.add_argument('--julia',default=os.environ.get('JULIA_BIN',shutil.which('julia') or 'julia'));p.add_argument('--depot',default=os.environ.get('JULIA_DEPOT_PATH'));p.add_argument('--passes',type=int);p.add_argument('--first-tool',choices=['tamerop','cubicalripser'],default='tamerop');a=p.parse_args();out=a.out.resolve()
    M=json.loads((out/'manifest.json').read_text());ready=json.loads((out/'environment/ready.json').read_text())
    verify_hashes(out/'candidate',json.loads((out/'candidate_hashes.json').read_text()))
    verify_hashes(out/'environment',ready['extensions']);verify_hashes(out/'environment',ready['binaries'])
    selected=[c for c in M['cases'] if c['group']==a.group and (a.ids is None or c['id'] in a.ids.split(','))]
    assert selected and (a.ids is None or set(a.ids.split(','))=={c['id'] for c in selected}),'unknown/empty case selection'
    skipped=[]
    if a.group!='qualification':
        # No timing ratios for a lane with failed mathematical qualification.
        qualification=json.loads((out/'qualification.json').read_text())
        assert qualification['manifest_sha256']==sha(out/'manifest.json')
        assert qualification['candidate_manifest_sha256']==sha(out/'candidate_hashes.json')
        assert qualification['environment_sha256']==sha(out/'environment/ready.json')
        assert not qualification['protocol_errors'],'qualification protocol is incomplete'
        for name,value in qualification['worker_hashes'].items():assert sha(HERE/name)==value,'worker/validator changed; repeat qualification'
        qbinding=json.loads((out/qualification['run']/'binding.json').read_text())
        assert sha(HERE.parent/'phat/oracle.py')==qbinding['harness']['phat/oracle.py'],'independent oracle changed; repeat qualification'
        selected,skipped=qualified_selection(selected,qualification['cases'])
    base=out/'runs';base.mkdir(exist_ok=True);index=1+max([int(d.name.split('_')[0]) for d in base.iterdir() if d.is_dir()]+[0]);run=base/f'{index:04d}_{a.group}';run.mkdir()
    shutil.copytree(HERE,run/'harness/cubicalripser',ignore=shutil.ignore_patterns('__pycache__'))
    (run/'harness/phat').mkdir();shutil.copy2(HERE.parent/'phat/oracle.py',run/'harness/phat/oracle.py')
    bindings=dict(manifest_sha256=sha(out/'manifest.json'),candidate_manifest_sha256=sha(out/'candidate_hashes.json'),environment_sha256=sha(out/'environment/ready.json'),harness={str(f.relative_to(run/'harness')):sha(f) for f in (run/'harness').rglob('*') if f.is_file()})
    (run/'binding.json').write_text(json.dumps(bindings,indent=2)+'\n')
    (run/'selection.json').write_text(json.dumps(dict(group=a.group,selected=[c['id'] for c in selected],skipped=skipped,host_context=M['host_context'],cpu_model=next((l.split(':',1)[1].strip() for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),'unknown'),cpu_count=os.cpu_count(),physical_memory=next(l for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemTotal:')),uname=list(os.uname())),indent=2)+'\n')
    start=time.monotonic();completions=[];passes=a.passes or (1 if a.group=='qualification' else M['passes'])
    for pas in range(1,passes+1):
        order=('tamerop','cubicalripser') if pas%2 else ('cubicalripser','tamerop')
        if a.first_tool=='cubicalripser':order=tuple(reversed(order))
        for tool in order:
            if selected and time.monotonic()-start<M['limits']['total_seconds']:completions.append(worker(out,run,tool,pas,selected,a.group,a.julia,a.depot,M,start))
    (run/'run_complete.json').write_text(json.dumps(dict(passes=passes,completions=completions,skipped=skipped,seconds=time.monotonic()-start),indent=2)+'\n')
    print('RUN_DIRECTORY='+str(run),flush=True)
if __name__=='__main__':main()
