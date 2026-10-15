"""Fixed confirmation protocol and fail-closed candidate identity checks."""
import json
import shutil
import subprocess
from pathlib import Path
from build import digest

JULIA_FLAGS = ['--startup-file=no', '--threads=1', '--compiled-modules=strict']
THREAD_ENV = dict(JULIA_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
GC_POLICY = 'before_phase_warmup_then_natural'
ANALYSIS = dict(primary_phase='combined',case_weights='equal within equally weighted families',
               point_estimate='geometric mean of paired process-median ratios',
               uncertainty='95% t interval on independent paired-block log ratios; df=passes-1',
               practical_margin=1.10,report_pass_range=True,
               larger_supplement='none: v2 is a single 48-case medium/large suite',
               speed_ratio='PHAT seconds / TamerOp seconds',
               failures='keep fixed denominators; no numeric timeout substitution',
               headline_gate=dict(weighted_practical_wins=0.8,families_favoring=0.8,aggregate_lower_ratio=1.10))


def runtime_identity(julia):
    # No package loading or precompilation here; outside every sample timer.
    output = subprocess.check_output([julia, '--startup-file=no', '--threads=1', '-e',
                                     'println(VERSION); println(Sys.BINDIR)'], text=True, timeout=30)
    version, bindir = output.strip().splitlines()
    executable = Path(bindir) / 'julia'
    return dict(julia_version=version, julia_binary_sha256=digest(executable),
                python_version=__import__('platform').python_version())


def protocol():
    return dict(version=2,field='F2',order='sublevel',representatives=False,
                julia_flags=JULIA_FLAGS,thread_environment=THREAD_ENV,
                gc_policy=GC_POLICY,phat_algorithm='twist',phat_representation='bit_tree_pivot_column',
                tamerop_entrypoint='public_persistence_diagram',
                tamerop_backend_scope='public_result_provenance',
                accepted_backend_families=['f2_graph_union_find','f2_clearing'],
                warmup_policy='two fresh warmups per phase; bounded compilation rejection',
                retry_allowance=3,phases=['construction','query','combined'],
                process_order='PHAT then TamerOp on odd passes; reverse on even passes',
                case_order='manifest order on odd passes; reverse on even passes',
                analysis=ANALYSIS)


def select_cases(manifest, mode, suite):
    if manifest.get('study') == 'phat_v2':
        assert suite == 'main', 'v2 has one primary population'
        all_cases = manifest['cases']
        assert len({c['id'] for c in all_cases}) == len(all_cases) == 56
        scored = [c for c in all_cases if c['split'] != 'control']
        assert len(scored) == 48
        assert {(c['family'], c['variant'], c['size_level']) for c in scored} == {
            (f,v,s) for f in ('graph','simplicial','cubical','algebraic')
            for v in range(1,5) for s in range(1,4)}
        assert all(c['pilot'] == (c['size_level'] == 3) for c in scored)
        cases = {c['id']: c for c in all_cases if mode == 'correctness'
                 or (c['pilot'] if mode == 'pilot' else c['split'] != 'control')}
        assert len(cases) == {'correctness':56,'pilot':16,'confirmation':48}[mode]
        return cases
    if suite == 'larger':
        cases = {c['id']: c for c in manifest['cases']}
        assert len(cases)==12 and all(c['scale']=='larger' and c['split']=='development' for c in cases.values())
    else:
        cases = {c['id']: c for c in manifest['cases'] if mode=='correctness'
                 or (c['pilot'] if mode=='pilot' else c['split']!='control')}
        assert len(cases)=={'correctness':56,'pilot':12,'confirmation':48}[mode]
        if mode=='pilot':assert all(c['split']=='development' for c in cases.values())
    return cases


def verify_freeze(freeze, identity):
    assert freeze.get('schema')==2 and freeze.get('accepted') is True, 'candidate is not accepted'
    assert identity['mode']=='confirmation', 'freeze applies to confirmation only'
    assert json.dumps(freeze['identity'],sort_keys=True)==json.dumps(identity,sort_keys=True), 'frozen source, fixtures, runtime, harness, build or run configuration changed'


def verify_build(build, worker):
    ident=json.loads((build/'identity.json').read_text())
    assert digest(build/'phat_worker')==ident['binary_sha256'], 'PHAT executable changed'
    assert digest(worker)==ident['worker_sha256'], 'PHAT adapter changed'
    assert digest(build/'phat-v1.7.tar.gz')==ident['archive_sha256'], 'PHAT archive changed'
    source=next(build.glob('phat-code-phat-*'))
    assert {str(p.relative_to(source)):digest(p) for p in sorted((source/'include').rglob('*.h'))}==ident['source_headers'], 'PHAT headers changed'
    return ident
