"""Summarize only exact-verified completed cases; preserve every failure."""
from pathlib import Path
import argparse,csv,json,math,statistics as st
from protocol import read_rows,sha

def analyze(out):
    run=out/'formal_run';manifest=json.loads((out/'formal_manifest.json').read_text());v=json.loads((run/'verification.json').read_text());vv={c['case']:c for c in v['cases']}
    records=[];raw=[]
    for c in manifest['cases']:
        rec={k:c[k] for k in ('id','shape','convention','pattern','level','seed','order','reserved')};rec.update(elements=math.prod(c['shape']),dimension=len(c['shape']),verified=vv[c['id']]['verified'],failures=vv[c['id']]['failures'],intervals=vv[c['id']]['intervals'],tools={})
        for tool in ('tamerop','cubicalripser'):
            passes=[]
            for pas in range(1,manifest['passes']+1):
                d=run/f'p{pas}'/(c['id']+'_'+tool)
                if not (d/'completion.json').exists():continue
                complete=json.loads((d/'completion.json').read_text());rows=read_rows(d/'stdout.ndjson');samples=[x for x in rows if x.get('kind')=='sample' and x['accepted']]
                monitor=read_rows(d/'monitor.ndjson');environments=[x for x in rows if x.get('kind')=='environment'];warms=[x for x in rows if x.get('kind')=='warmup']
                for x in samples:raw.append(dict(x, case=c['id'], pass_id=pas))
                if not complete['complete']:continue
                passes.append(dict(pass_id=pas,worker_wall_seconds=complete['seconds'],seconds=st.median(x['seconds'] for x in samples),samples=[x['seconds'] for x in samples],
                    allocation_bytes=st.median(x['allocation_bytes'] for x in samples) if tool=='tamerop' else None,
                    result_bytes=st.median(x['result_bytes'] for x in samples),input_bytes=samples[0]['input_bytes'],
                    process_peak_rss_bytes=max(x['rss_bytes'] for x in monitor),query_peak_rss_bytes=max((x['rss_bytes'] for x in monitor if x['phase']=='query'),default=0),
                    import_seconds=environments[0]['load_seconds'],warmup=warms,
                    loadavg_min=min(x['loadavg'][0] for x in monitor),loadavg_max=max(x['loadavg'][0] for x in monitor)))
            rec['tools'][tool]=dict(passes=passes)
            if len(passes)==manifest['passes']:rec['tools'][tool].update(seconds=st.median(x['seconds'] for x in passes),range_seconds=[min(x['seconds'] for x in passes),max(x['seconds'] for x in passes)])
        if rec['verified']:
            ratios=[b['seconds']/a['seconds'] for a,b in zip(rec['tools']['tamerop']['passes'],rec['tools']['cubicalripser']['passes'],strict=True)]
            rec['ratio']=st.geometric_mean(ratios);rec['ratio_range']=[min(ratios),max(ratios)];rec['similarity']='TamerOp advantage' if rec['ratio']>1.1 else ('similar' if rec['ratio']>=1/1.1 else 'CubicalRipser advantage')
        records.append(rec)
    groups=[]
    for dim in (2,3):
        for conv in ('V','T'):
            for pattern in ('noise','binary','smooth'):
                rows=[c for c in records if c['dimension']==dim and c['convention']==conv and c['pattern']==pattern]
                good=[c for c in rows if c['verified']]
                groups.append(dict(dimension=dim,convention=conv,pattern=pattern,verified=len(good),total=len(rows),ratio=st.geometric_mean(c['ratio'] for c in good) if good else None))
    good=[c for c in records if c['verified']];summary=dict(total=len(records),verified=len(good),accepted_samples=len(raw),groups=groups,
        balanced_ratio=st.geometric_mean(c['ratio'] for c in good) if len(good)==len(records) else None,
        classes={s:sum(c.get('similarity')==s for c in records) for s in ('TamerOp advantage','similar','CubicalRipser advantage')},
        records=records,manifest_sha256=sha(out/'formal_manifest.json'),verification_sha256=sha(run/'verification.json'))
    (out/'analysis.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'samples.json').write_text(json.dumps(raw,indent=2)+'\n')
    with (out/'results.csv').open('w',newline='') as f:
        fields=['case','dimension','convention','pattern','shape','elements','reserved','order','intervals','verified','tamerop_seconds','cubicalripser_seconds','ratio','ratio_min','ratio_max','classification']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in records:
            w.writerow(dict(case=c['id'],dimension=c['dimension'],convention=c['convention'],pattern=c['pattern'],shape='x'.join(map(str,c['shape'])),elements=c['elements'],reserved=c['reserved'],order=c['order'],intervals=c['intervals'],verified=c['verified'],tamerop_seconds=c['tools']['tamerop'].get('seconds'),cubicalripser_seconds=c['tools']['cubicalripser'].get('seconds'),ratio=c.get('ratio'),ratio_min=c.get('ratio_range',[None,None])[0],ratio_max=c.get('ratio_range',[None,None])[1],classification=c.get('similarity','No verified completion')))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('records','groups')}));return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();analyze(a.out.resolve())
