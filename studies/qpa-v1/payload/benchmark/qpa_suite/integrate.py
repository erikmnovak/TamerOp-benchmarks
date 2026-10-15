#!/usr/bin/env python3
"""Regenerate the fixed 220-case allocation using coverage, never timing ranks."""
import argparse, collections, copy, csv, hashlib, json
from fractions import Fraction
from pathlib import Path
import fixtures as F
ROOT=F.ROOT;BASE=ROOT/'audit/2026-09-27/qpa_suite_v1';G,B=F.G,F.B
SELECTION={
 'Q1':[0,2,4,20,21,24,27,29,12,15,30,33],
 'Q2':[1,5,7,11,17,19,25,26,12,15,34,35],
 'Q3':[0,5,6,8,17,19,36,39,14,13,31,32],
 'Q4':[0,7,2,9,5,10,12,15,17,19,20,23,24,25,26,29,30,33,34,35],
}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dumps(x):return json.dumps(x,indent=2)+'\n'
def write(p,text):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
def record_hash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def tensor_dimension(P,f):
 R,L=f['modules']['R'],f['modules']['L'];field=f['field'];rd,ld=R['dimensions'],L['dimensions'];offs=[0]
 for a,b in zip(rd,ld):offs.append(offs[-1]+a*b)
 rel=[]
 for e,(u,v) in enumerate(P['covers']):
  u-=1;v-=1;rm=F.V.parse(R['edge_matrices'][e],field);lm=F.V.parse(L['edge_matrices'][e],field)
  for j in range(rd[v]):
   for i in range(ld[u]):
    vec=[G.normalize(0,field) for _ in range(offs[-1])]
    for k in range(rd[u]):vec[offs[u]+k*ld[u]+i]+=rm[k][j]
    for k in range(ld[v]):vec[offs[v]+j*ld[v]+k]-=lm[k][i]
    rel.append(F.V.norm(vec,field))
 rank=G.rank(F.V.columns(rel,offs[-1]),field,ncols=len(rel))
 return dict(dimension=offs[-1]-rank,elementary_count=offs[-1],relation_count=len(rel),relation_rank=rank)

def build(output):
 old=json.loads((BASE/'history/revision3/scope.json').read_text());slots=copy.deepcopy(old['slots'])
 prior=json.loads((BASE/'derived/fixtures.json').read_text());src=json.loads((BASE.parent/'qpa_large_diversity/fixtures.json').read_text())
 modules={m['id']:m for m in src['modules']};records={f['case']:f for f in src['fixtures']};posets={p['name']:p for p in src['posets']}
 pairs={};certifications=[]
 for slot in slots:
  name=slot['case'];field=slot['field']
  if slot['input_exists']:
   f=records[name];pairs[name]=dict(case=name,poset=f['poset'],field=field,maxdegree=slot['maxdegree'],split=slot['split'],
    modules=dict(M=modules[f['source']],N=modules[f['target']]),expected_ext=f['expected_ext'],certificate=f['certificate'],prior_Q3_timing=slot['prior_Q3_timing'])
  else:
   P=F.crown(int(slot['poset'].replace('capped_crown','')));posets[P['name']]=P;seed=37 if slot['split']=='evaluation' else 11
   M,cm=F.presentation(P,field,1,seed);N,cn=F.presentation(P,field,2,seed+7);N=G.direct_sum(P,[N,G.simple(P,P['n'])])
   M.update(id=name+'_M',field=field);N.update(id=name+'_N',field=field)
   expected,hom,oracle=G.bar_oracle(P,M,N,2,field)
   pairs[name]=dict(case=name,poset=P['name'],field=field,maxdegree=2,split=slot['split'],modules=dict(M=M,N=N),expected_ext=expected,
     certificate=dict(source=cm,target=cn,extra_simple=P['n'],bar_oracle=oracle),prior_Q3_timing=False)
   slot.update(input_exists=True,recipe_status='certified_crown_pair; task_specific_maps_pending',integration_pair_sha256=record_hash(pairs[name]))
   certifications.append(dict(case=name,check='natural projective-presentation cokernels; exact bar Ext dimensions',passed=True))
   print('Certified base',name,flush=True)
 # Select two old controls per field and operation, alternating multiplicity levels across posets.
 selected=[];disposition=[]
 for f0 in prior['cases']:
  f=copy.deepcopy(f0);idx=F.FIELDS.index(f['field']);cube_level=2-idx%2
  keep=f['task']=='tensor' or f['level']==(cube_level if f['poset']=='cube3' else 3-cube_level)
  disposition.append(dict(case=f['id'],operation=f['task'],field=f['field'],poset=f['poset'],level=f['level'],
    disposition='main_220_development' if keep else 'supplementary_historical',reason='fixed cyclic field/poset/level coverage rule; no timing input',record_sha256=record_hash(f0)))
  if keep:f.update(split='development',prior_qualification=True,selection_role='known_failure_tensor' if f['task']=='tensor' else 'semisimple_control');selected.append(f)
 for task in ['yoneda','induced']:
  for field in F.FIELDS:
   poset='cube3' if field in ['QQ','F101'] else 'grid4'
   split='evaluation' if (field in ['F2','F101'])==(task=='yoneda') else 'development'
   f=F.mixed(posets[poset],field,task,split);f['selection_role']='nonzero_structure_maps';selected.append(f)
   certifications.append(dict(case=f['id'],check='exact nonsplit sequences; bar dimensions and product witness/natural maps',passed=True))
   print('Certified derived',f['id'],split,flush=True)
 for index in [30,33,34,35]:
  pair=pairs[slots[index]['case']];P=posets[pair['poset']]
  f=F.tensor(P,pair['field'],pair['case'],pair['modules']['M'],pair['modules']['N']);f['selection_role']='reserved_presentation'
  f['expected_tensor']=tensor_dimension(P,f);selected.append(f)
  certifications.append(dict(case=f['id'],check='balanced-relation quotient',passed=True))
 # Preserve original Q5-Q7 assignments and IDs, reduce Q1-Q4 using explicit coverage selections.
 original=list(csv.DictReader((BASE/'history/revision3/coverage.csv').open()));rows=[]
 candidates=[dict(r) for r in original if r['workflow'] not in SELECTION]
 originals={(r['workflow'],r['case']):r for r in original}
 for w,indices in SELECTION.items():
  template=next(r for r in original if r['workflow']==w)
  for i in indices:
   slot=slots[i];name=slot['case'];row=dict(template)
   row.update(task_id=f"{w}:{template['variant']}:{name}",case=name,field=slot['field'],split=slot['split'],role=slot['role'],
    historical_evidence=originals.get((w,name),{}).get('historical_evidence','not independently timed for this task'))
   candidates.append(row)
 for row in candidates:
  w=row['workflow']
  row.update(base_input_status='exists',input_manifest='base_pairs.json',input_record=row['case'],adapter_status='pending' if w!='Q3' else 'existing_Q3_harness; suite_adapter_pending')
  if row['input_recipe']=='pair':row['task_input_status']='pair_ready'
  row['qualification_status']='historical_Q3' if w=='Q3' and pairs[row['case']]['prior_Q3_timing'] else 'pending'
  rows.append(row)
 for f in selected:
  w={'yoneda':'Q8','induced':'Q9','tensor':'Q10'}[f['task']]
  status=('tamerop_verified_qpa_evaluation_failure' if w=='Q10' else 'matched_exact_verified') if f.get('prior_qualification') else 'input_certified; consult_integrated/native_verification.json'
  rows.append(dict(task_id=f['id'],area='A2' if w=='Q10' else 'A1',workflow=w,variant=f['task'],case=f['id'],field=f['field'],split=f['split'],
   role=f['selection_role'],weight='',input_recipe=f['family'] if f.get('family') else 'semisimple_control',base_input_status='exists',task_input_status='generated_and_exactly_checked',
   confirmation_status='pending',historical_evidence='derived qualification archive' if f.get('prior_qualification') else 'none',
   input_manifest='integrated/derived_fixtures.json',input_record=f['id'],adapter_status='implemented',qualification_status=status))
 variants={a:sorted({r['variant'] for r in rows if r['area']==a}) for a in ['A1','A2','A3','A4','A5']}
 counts=collections.Counter((r['area'],r['variant'],r['field']) for r in rows)
 for r in rows:r['weight']=str(Fraction(1,5*len(variants[r['area']])*4*counts[r['area'],r['variant'],r['field']]))
 scope=copy.deepcopy(old);scope.update(revision=4,revision_note='User-approved integration: 220 total including products, induced maps, and balanced tensors; no add-on campaign.',
  status='integrated_220_manifest_ready; derived_adapters_implemented; other_adapters_pending',design_selection='coverage-only allocation revised after historical qualification; no claim of preregistration for historical data')
 scope.pop('authorized_extensions',None);scope['historical_derived_archive']=dict(path='derived/fixtures.json',cases=48,retained_main=32,supplementary=16)
 scope['slots']=slots;scope['query_input_ids_by_workflow']={w:[slots[i]['case'] for i in indices] for w,indices in SELECTION.items()};scope.pop('query_input_ids',None)
 workflows=scope['workflows']
 for w in workflows:w['task_cases']=sum(r['workflow']==w['id'] for r in rows)
 for w,area,task,n,out in [('Q8','A1','yoneda',12,'complete Ext1 x Ext1 product table in Ext2 coordinates'),('Q9','A1','induced',12,'induced Ext maps in both arguments and degrees 1,2'),('Q10','A2','tensor',20,'balanced tensor quotient and elementary evaluation')]:
  workflows.append(dict(id=w,area=area,variants=[task],task_cases=n,output=out))
 for a in scope['workflow_families']:
  a['workflows']=[w['id'] for w in workflows if w['area']==a['id']]
  if a['id']=='A1':a['name']='Hom, Ext, products and induced maps'
  if a['id']=='A2':a['name']='Module and tensor constructions'
 scope['counts'].update(existing_inputs=40,new_inputs=0,query_input_slots=None,scored_task_cases=len(rows),scored_development_cases=sum(r['split']=='development' for r in rows),
   scored_evaluation_cases=sum(r['split']=='evaluation' for r in rows),task_case_fields=dict(collections.Counter(r['field'] for r in rows)),
   task_cases_by_area=dict(collections.Counter(r['area'] for r in rows)),task_cases_by_workflow=dict(collections.Counter(r['workflow'] for r in rows)),historical_derived_scored=32,new_derived_scored=12)
 scope['score_gate']['aggregation_unit']='mathematical areas A1-A5, including Q8-Q10'
 scope['score_gate']['missing_ratio_policy']='Keep failures in full completion denominator. Report completed-pair speeds with explicit weights and denominator; the unchanged full-suite speed gate requires all primary ratios valid.'
 scope['score_gate']['tensor_failures']='No infinite ratios, imputation or survivor-only full-suite speed claim.'
 scope['qualification']['status']='historical 48-case qualification archived; 32 retained; 12 new exact fixtures generated; native correctness checks separate'
 scope['task_input_recipes'].update(yoneda='certified triple with product witness',induced='certified module maps',tensor='opposite/forward presentation or interval pair')
 scope['selection_rule']=dict(queries_and_constructions=SELECTION,semisimple_controls='fields QQ,F2,F3,F101; cube levels 2,1,2,1; grid levels 1,2,1,2; both operations use the same rule',
    timing_files_read=False,reserved_count=36,new_derived_evaluation_count=8)
 spec=dict(schema='tamerop.qpa_derived.integrated.v1',suite_cases=220,case_count=len(selected),fields=F.FIELDS,
   posets=[posets[n] for n in sorted({f['poset'] for f in selected})],cases=selected,phases=prior['phases'],limits=prior['limits'],
   reserved_policy='Qualification timings exclude evaluation cases; correctness-only checks contain no timers; confirmation requires a frozen candidate.',suite_scope='../scope.json')
 # Write only after construction and exact assertions finish.
 assert len(rows)==220 and sum(r['split']=='evaluation' for r in rows)==36
 output.mkdir(parents=True,exist_ok=True)
 write(output/'scope.json',dumps(scope));write(output/'integrated/derived_fixtures.json',dumps(spec));write(output/'integrated/derived_fixtures.g','QD_SPEC := '+F.D.gap(spec)+';;\n')
 write(output/'base_pairs.json',dumps(dict(schema='tamerop.qpa_base_pairs.v1',posets=[posets[n] for n in sorted({s['poset'] for s in slots})],cases=list(pairs.values()))))
 for name,data in [('coverage.csv',rows),('integrated/historical_disposition.csv',disposition)]:
  target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
  with target.open('w',newline='') as handle:w=csv.DictWriter(handle,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 write(output/'integrated/input_verification.json',dumps(dict(all_passed=True,checks=certifications,retained_fixture_records_verified=True,timing_results_used_for_selection=False)))
 manifest=dict(schema='tamerop.qpa_execution_manifest.v1',suite='qpa-v1',revision=4,case_count=220,source_frozen=False,
  definition_sha256={'scope.json':digest(output/'scope.json'),'coverage.csv':digest(output/'coverage.csv'),'base_pairs.json':digest(output/'base_pairs.json'),
    'integrated/derived_fixtures.json':digest(output/'integrated/derived_fixtures.json')},tasks=rows)
 write(output/'manifest.json',dumps(manifest))
 # Core adapter implementation is an execution revision; allocation is unchanged.
 core=F.load(ROOT/'benchmark/qpa_core/generate.py','suite_core_generate')
 core.build(output/'core',['Q1','Q2','Q3','Q4','Q5'],suite=output)
 for row in rows:
  if row['workflow'] in ('Q1','Q2','Q3','Q4','Q5'):
   row.update(input_manifest='core/fixtures.json',input_record=row['task_id'],adapter_status='implemented',
    task_input_status='generated_and_exactly_checked',qualification_status='see_core/native_verification.json; timings_not_confirmed')
 scope.update(revision=5,revision_note='Implement Q1-Q5 on the existing 96 allocations; counts, weights and holdouts unchanged.',
              status='Q1_Q5_and_Q8_Q10_implemented; Q6_Q7_pending; confirmation_pending')
 scope['qualification']['status']='Derived checks archived; Q1-Q5 correctness/protocol evidence in core; no full-suite confirmation.'
 write(output/'scope.json',dumps(scope))
 with (output/'coverage.csv').open('w',newline='') as handle:
  w=csv.DictWriter(handle,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 manifest.update(revision=5,tasks=rows)
 for name in ('scope.json','coverage.csv','core/fixtures.json'):
  manifest['definition_sha256'][name]=digest(output/name)
 write(output/'manifest.json',dumps(manifest))
 implement_diagrams(output)
 print('Wrote integrated suite',output,flush=True)


def implement_diagrams(output):
 """Finish the existing 80 allocations without changing selection or weights."""
 core=F.load(ROOT/'benchmark/qpa_core/generate.py','suite_diagram_generate')
 core.build(output/'diagrams',['Q6','Q7'],suite=output)
 rows=list(csv.DictReader((output/'coverage.csv').open()))
 for r in rows:
  if r['workflow'] in ('Q6','Q7'):
   r.update(input_manifest='diagrams/fixtures.json',input_record=r['task_id'],adapter_status='implemented',
     task_input_status='generated_and_exactly_checked',qualification_status='see_diagrams/native_verification.json; timings_not_confirmed')
 scope=json.loads((output/'scope.json').read_text())
 scope.update(revision=6,revision_note='Implement Q6-Q7 on the existing 80 allocations; all 220 adapters present; no selection, weight or holdout changes.',
   status='all_220_adapters_implemented; confirmation_pending')
 scope['qualification']['status']='Derived, core and diagram correctness/protocol evidence archived separately; no full-suite confirmation.'
 write(output/'scope.json',dumps(scope))
 with (output/'coverage.csv').open('w',newline='') as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 manifest=json.loads((output/'manifest.json').read_text());manifest.update(revision=6,tasks=rows)
 for name in ('scope.json','coverage.csv','diagrams/fixtures.json'):
  manifest['definition_sha256'][name]=digest(output/name)
 write(output/'manifest.json',dumps(manifest))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=BASE);args=p.parse_args();build(args.output)
