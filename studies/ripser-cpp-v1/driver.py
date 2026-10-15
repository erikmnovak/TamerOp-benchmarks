"""Prepare and run the frozen upstream C++ Ripser comparison."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ripser-py-v1'))
import runtime as rt

STUDY = Path(__file__).resolve().parent
COMMIT = '01add51ff64aaf40889483260cc5c3b7d0f2a1e7'
ROBINHOOD = '7b00237399cec62ee5795f9013cf5df8de596e69'


def prepare(args, work):
    work.mkdir(parents=True, exist_ok=True)
    julia = rt.select_julia(args.julia)
    cpu = rt.select_cpu(args.cpu)
    python, versions = rt.prepare_python(work, args.python)
    rt.init_source(STUDY, work, julia, instantiate=not args.skip_instantiate)
    upstream = args.upstream.resolve() if args.upstream else work/'upstream'
    if not upstream.exists():
        rt.run(['git','clone','https://github.com/Ripser/ripser.git',upstream])
        rt.run(['git','checkout',COMMIT],cwd=upstream)
        rt.run(['git','submodule','update','--init'],cwd=upstream)
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()
    robin = subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream/'robin-hood-hashing',text=True).strip()
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=upstream,text=True)
    if commit != COMMIT or robin != ROBINHOOD or dirty:
        raise RuntimeError('The C++ source or Robin Hood submodule differs from the pinned clean commits.')
    compiler = args.cxx or shutil.which('g++')
    if not compiler:
        raise RuntimeError('Install g++ with C++11 support, or pass --cxx.')
    flags = ['-std=c++11','-O3','-DNDEBUG','-DUSE_ROBINHOOD_HASHMAP']
    for name,extra in [('ripser-f2',[]),('ripser-coeff',['-DUSE_COEFFICIENTS'])]:
        rt.run([compiler,*flags,*extra,upstream/'ripser.cpp','-o',work/name])
    harness = rt.portable_harness(STUDY, work, julia, cpu)
    # Generation uses the original study functions in the pinned NumPy environment.
    rt.run([python, STUDY/'generate.py', work, STUDY/'evidence'])
    rt.write_json(work/'machine_and_build.json', dict(upstream_commit=commit,robinhood_commit=robin,
        compiler=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],flags=flags,
        binaries={name:rt.digest(work/name) for name in ['ripser-f2','ripser-coeff']},
        julia='1.12.1',numpy=versions['numpy'],cpu_affinity=[cpu]))
    rt.write_json(work/'runtime.json',dict(julia=julia,python=python,cpu=cpu,versions=versions))
    rt.verify_work(STUDY,work)


def campaign(work, action, passes, ids):
    config = json.loads((work/'runtime.json').read_text())
    manifest = json.loads((work/('controls.json' if action=='smoke' else 'manifest.json')).read_text())
    if action=='smoke':
        manifest['cases'] = [c for c in manifest['cases'] if c['id']=='octahedron_6_f3']
        manifest['samples']=1;passes=[1]
    if ids:
        known={c['id'] for c in manifest['cases']}
        if not set(ids)<=known:
            raise RuntimeError('Unknown case IDs: '+', '.join(set(ids)-known))
        manifest['cases']=[c for c in manifest['cases'] if c['id'] in ids]
    dest=work/action;dest.mkdir(exist_ok=True)
    for name in ['candidate','inputs','harness']:
        if not (dest/name).exists():(dest/name).symlink_to(work/name,target_is_directory=True)
    for name in ['ripser-f2','ripser-coeff']:
        if not (dest/name).exists():(dest/name).symlink_to(work/name)
    for name in ['candidate_hashes.json','machine_and_build.json','controls.json']:
        shutil.copy2(work/name,dest/name)
    if (dest/'manifest.json').exists() and json.loads((dest/'manifest.json').read_text())!=manifest:
        raise RuntimeError('This campaign has a different manifest. Choose a fresh --work directory.')
    rt.write_json(dest/'manifest.json',manifest)
    rt.run([config['python'],work/'harness/study.py','run','--out',dest,'--tag',action,
            '--passes',','.join(map(str,passes)),'--resume'],env=rt.env())
    for pas in passes:
        result=json.loads((dest/'runs'/f'{action}_p{pas}'/'complete.json').read_text())
        if not result['success']:
            raise RuntimeError(f'Incomplete or incorrect comparisons in pass {pas}: {result["failures"]}')
    print('Complete barcode outputs matched; small controls also matched the independent boundary reducer.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['verify','prepare','smoke','measure'])
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--julia',help='Julia 1.12.1 executable')
    parser.add_argument('--python',help='Existing Python with pinned NumPy and SciPy')
    parser.add_argument('--upstream',type=Path,help='Existing clean checkout of the pinned upstream commits')
    parser.add_argument('--cxx',help='C++ compiler executable')
    parser.add_argument('--cpu',type=int)
    parser.add_argument('--passes',default='1,2,3')
    parser.add_argument('--ids',help='Comma-separated cases; omitted means the full historical suite')
    parser.add_argument('--skip-instantiate',action='store_true',help='Use an already prepared Julia dependency environment')
    args=parser.parse_args();work=args.work.resolve()
    try:
        if args.action=='verify':rt.verify_work(STUDY,work)
        elif args.action=='prepare':prepare(args,work)
        else:
            if not (work/'runtime.json').exists():raise RuntimeError('Run prepare first with the same --work directory.')
            rt.verify_work(STUDY,work)
            passes=[int(x) for x in args.passes.split(',')]
            if passes!=list(range(1,len(passes)+1)):raise RuntimeError('--passes must begin at 1 and be contiguous.')
            campaign(work,args.action,passes,args.ids.split(',') if args.ids else None)
    except (RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__=='__main__':main()
