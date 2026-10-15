"""Prepare and run the frozen Ripser.py comparison in a new work directory."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import runtime as rt

STUDY = Path(__file__).resolve().parent


def prepare(args, work):
    work.mkdir(parents=True, exist_ok=True)
    julia = rt.select_julia(args.julia)
    cpu = rt.select_cpu(args.cpu)
    python, versions = rt.prepare_python(work, args.python, need_ripser=True)
    if args.python:
        expected = json.loads((STUDY/'evidence/build_verified.json').read_text())['binaries']
        if rt.digest(versions['extension']) not in expected.values():
            raise RuntimeError('The supplied Python has a different Ripser extension. Omit --python to build the pinned optimized source.')
    rt.init_source(STUDY, work, julia, instantiate=not args.skip_instantiate)
    rt.run([python, STUDY/'fixtures.py', work, STUDY/'evidence'])
    harness = rt.portable_harness(STUDY, work, julia, cpu)
    runner = harness/'run.py'
    text = runner.read_text().replace("str(OUT/'venv/bin/python')", repr(python))
    runner.write_text(text)
    patches = json.loads((work/'portability.json').read_text())
    patches['run.py']['portable_sha256'] = rt.digest(runner)
    patches['run.py']['changes'].append('Explicit pinned Python environment')
    rt.write_json(work/'portability.json', patches)
    rt.write_json(work/'build_verified.json', dict(ripser_version='0.6.15', robinhood='3.11.5',
        optimization='-O3', robinhood_macro_verified=True,
        binaries={versions['extension']:rt.digest(versions['extension'])}))
    rt.write_json(work/'runtime.json', dict(julia=julia, python=python, cpu=cpu, versions=versions,
        historical_binary=(args.python is not None)))
    rt.verify_work(STUDY, work)


def campaign(work, action, passes, ids):
    config = json.loads((work/'runtime.json').read_text())
    manifest = json.loads((work/'manifest.json').read_text())
    if action == 'smoke':
        ids = ['control_sphere2_cocycles_f3']
        passes = [1]
        manifest['samples'] = 1
    if ids:
        known = {c['id'] for c in manifest['cases']}
        if not set(ids) <= known:
            raise RuntimeError('Unknown case IDs: '+', '.join(set(ids)-known))
        manifest['cases'] = [c for c in manifest['cases'] if c['id'] in ids]
    manifest['passes'] = max(passes)
    manifest['reproduction'] = {'action':action,'process_passes':passes,
        'historical_evidence':'Separate sealed evidence directory; these are new measurements.'}
    dest = work/action
    dest.mkdir(exist_ok=True)
    for name in ['candidate','inputs','harness']:
        if not (dest/name).exists():
            (dest/name).symlink_to(work/name, target_is_directory=True)
    for name in ['build_verified.json','candidate_hashes.json']:
        shutil.copy2(work/name, dest/name)
    path = dest/'manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError('This campaign has a different manifest. Choose a fresh --work directory.')
    rt.write_json(path, manifest)
    environment = rt.env();environment['RIPSER_STUDY_DIR'] = str(dest)
    rt.run([config['python'], work/'harness/run.py', '--passes', ','.join(map(str,passes))],
           env=environment, timeout=manifest['limits']['worker_seconds']*len(passes)*2)
    rt.run([config['python'], work/'harness/verify.py'], env=environment,
           timeout=1200)
    print('The selected mathematical outputs passed the independent verifier.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify','prepare','smoke','measure'])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--julia', help='Julia 1.12.1 executable')
    parser.add_argument('--python', help='Reuse the exact original pinned Python build; normally omitted')
    parser.add_argument('--cpu', type=int, help='One permitted logical CPU; defaults to the first permitted CPU')
    parser.add_argument('--passes', default='1,2,3,4', help='Contiguous process passes beginning at 1')
    parser.add_argument('--ids', help='Comma-separated case IDs; omitted means the full historical suite')
    parser.add_argument('--skip-instantiate', action='store_true', help='Use an already prepared Julia dependency environment')
    args = parser.parse_args();work = args.work.resolve()
    try:
        if args.action == 'verify':
            rt.verify_work(STUDY, work)
        elif args.action == 'prepare':
            prepare(args, work)
        else:
            if not (work/'runtime.json').exists():
                raise RuntimeError('Run prepare first with the same --work directory.')
            rt.verify_work(STUDY, work)
            passes = [int(x) for x in args.passes.split(',')]
            if passes != list(range(1,len(passes)+1)):
                raise RuntimeError('--passes must be a contiguous sequence starting at 1, such as 1,2.')
            campaign(work, args.action, passes, args.ids.split(',') if args.ids else None)
    except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, str(exc)+'\n')


if __name__ == '__main__':
    main()
