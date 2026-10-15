#!/usr/bin/env python3
"""Audit every predeclared timing cell; retain observations without a suite score."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path

def audit(folder,selection,spec):
 context=json.loads((folder/'context.json').read_text());verification=json.loads((folder/'verification.json').read_text())
 processes=json.loads((folder/'processes.json').read_text());assert all(p['status']=='completed' for p in processes)
 cases={f['id']:f for f in spec['cases']};chosen=set(selection['cases']);phases=spec['phases'];accepted={};rejected=[];warm=0
 assert set(context['cases'])==chosen and context['passes']==selection['passes'] and context['samples']==selection['samples']==1
 assert verification['verified_matched_cases']==len(chosen) and verification['verified_native_cases']==2*len(chosen) and not verification['failures']
 for p in processes:
  rows=[json.loads(line) for line in Path(p['data']).read_text().splitlines()];assert rows[-1]['kind']=='completed'
  assert not any(r['kind']=='failure' for r in rows)
  for r in rows:
   if r['kind']!='timing':continue
   assert r['case'] in chosen and cases[r['case']]['split']=='development'
   assert r['reset_verified']
   if r['tool']=='TamerOp':
    reset=r['reset'];state=reset['after']
    assert reset['verified_empty'] and reset['prior_inputs_and_results_released']
    assert not any(state['global_caches'].values()) and state['live_prior_roots']==0
    assert state['task_local']['metadata_entries']==state['task_local']['owner_payloads']==0
    for s in state['posets'].values():assert s['hom_route_entries']==s['chain_parent_tasks']==s['chain_parent_dense_tasks']==0
   else:
    assert r['reset']['prior_inputs_results_retained']==0
    assert all(not s['mathematical_attributes'] for s in r['reset']['constructor_state'])
   if r['warmup']:warm+=1;continue
   if not r['eligible']:rejected.append({k:r.get(k) for k in ['tool','case','phase','pass','sample','attempt','compile_seconds','recompile_seconds']});continue
   if r['tool']=='TamerOp':assert r['compile_seconds']==r['recompile_seconds']==0
   key=(r['tool'],r['case'],r['phase'],r['pass']);assert key not in accepted;accepted[key]=r
 expected={(tool,case,phase,p) for tool in ['TamerOp','QPA'] for case in chosen for phase in phases for p in range(1,selection['passes']+1)}
 assert set(accepted)==expected,(expected-set(accepted),set(accepted)-expected)
 observations=[]
 for name in selection['cases']:
  for phase in phases:
   entry=dict(case=name,task=cases[name]['task'],field=cases[name]['field'],phase=phase)
   for tool in ['TamerOp','QPA']:
    rs=[accepted[tool,name,phase,p] for p in range(1,selection['passes']+1)]
    ts=[r['seconds'] if tool=='TamerOp' else r['nanoseconds']/1e9 for r in rs]
    assert all(t>0 for t in ts),'Nonpositive elapsed time'
    entry[tool]=dict(pass_seconds=ts,median_seconds=statistics.median(ts),pass_allocated_bytes=[r['bytes'] for r in rs])
   entry['qpa_over_tamerop_pass_ratios']=[q/t for q,t in zip(entry['QPA']['pass_seconds'],entry['TamerOp']['pass_seconds'])]
   observations.append(entry)
 summary=dict(passed=True,accepted_rows=len(accepted),rejected_rows=len(rejected),rejected_samples=rejected,warmup_rows=warm,
  matched_cases=len(chosen),native_cases=2*len(chosen),variants=sorted({cases[n]['task'] for n in chosen}),fields=spec['fields'],phases=phases,passes=selection['passes'],samples_per_phase=1,reserved_timings=0,
  zero_compilation_for_all_accepted_julia_samples=True,recorded_resets_independently_checked=True,
  interpretation='Shared-host protocol qualification; no full-suite score, significance test, or leadership claim.',fixture_sha256=context['fixture_sha256'])
 return summary,dict(scope=summary['interpretation'],allocation_scope=context['allocation_scope'],rss_scope=context['rss_scope'],observations=observations)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--selection',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 s,o=audit(a.run,json.loads(a.selection.read_text()),json.loads(a.fixtures.read_text()));a.output.write_text(json.dumps(s,indent=2)+'\n');a.output.with_name('timing_observations.json').write_text(json.dumps(o,indent=2)+'\n');print(s)
