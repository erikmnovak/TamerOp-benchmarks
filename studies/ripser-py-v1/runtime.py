"""Portable setup helpers shared by the two frozen Rips studies."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'sources/ripser-v1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def run(args, **kwargs):
    print('+', ' '.join(str(x) for x in args), flush=True)
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_sources(study):
    hashes = json.loads((study/'evidence/candidate_hashes.json').read_text())
    for rel, expected in hashes.items():
        if digest(SOURCE/rel) != expected:
            raise RuntimeError(f'Frozen source hash mismatch: {rel}')
    historical = json.loads((study/'evidence/harness_hashes.json').read_text())
    for p in (study/'historical').iterdir():
        if p.is_file() and p.name in historical and digest(p) != historical[p.name]:
            raise RuntimeError(f'Historical worker hash mismatch: {p.name}')
    checksums = study/'evidence/SHA256SUMS'
    for line in checksums.read_text().splitlines():
        expected, rel = line.split(None, 1)
        if digest(study/'evidence'/rel.lstrip('*')) != expected:
            raise RuntimeError(f'Evidence checksum mismatch: {rel}')
    print('Frozen source, historical workers and published evidence verified.')


def env():
    result = os.environ.copy()
    result.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                  MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
                  JULIA_NUM_THREADS='1', JULIA_PKG_PRECOMPILE_AUTO='0')
    return result


def select_julia(value):
    executable = value or os.environ.get('JULIA') or shutil.which('julia')
    if not executable:
        raise RuntimeError('Install Julia 1.12.1, then pass --julia /path/to/julia.')
    executable = str(Path(executable).resolve())
    version = subprocess.check_output([executable, '--startup-file=no', '-e', 'print(VERSION)'], text=True)
    if version.strip() != '1.12.1':
        raise RuntimeError(f'Julia 1.12.1 is required; found {version!r}. Use --julia.')
    return executable


def init_source(study, work, julia, instantiate=True):
    verify_sources(study)
    work.mkdir(parents=True, exist_ok=True)
    candidate = work/'candidate'
    if not candidate.exists():
        shutil.copytree(SOURCE, candidate)
    for rel, expected in json.loads((study/'evidence/candidate_hashes.json').read_text()).items():
        if digest(candidate/rel) != expected:
            raise RuntimeError(f'Working source hash mismatch: {rel}')
    shutil.copy2(study/'evidence/candidate_hashes.json', work/'candidate_hashes.json')
    if instantiate:
        run([julia, '--startup-file=no', f'--project={candidate}', '-e',
             'using Pkg; Pkg.instantiate(); Pkg.precompile()'], env=env(), timeout=1200)
        # Pkg may update a copied Manifest during resolution; reject source drift.
        for rel, expected in json.loads((study/'evidence/candidate_hashes.json').read_text()).items():
            if digest(candidate/rel) != expected:
                raise RuntimeError(f'Environment preparation changed frozen {rel}')


def select_cpu(value):
    if sys.platform != 'linux':
        raise RuntimeError('The historical resource supervisor requires Linux (/proc and taskset).')
    if not shutil.which('taskset'):
        raise RuntimeError('Install util-linux for taskset before preparing this study.')
    allowed = sorted(os.sched_getaffinity(0))
    cpu = allowed[0] if value is None else value
    if cpu not in allowed:
        raise RuntimeError(f'CPU {cpu} is unavailable; choose from {allowed}.')
    return cpu


def download(url, dest, expected):
    if not dest.exists():
        print('Downloading', url, flush=True)
        with urllib.request.urlopen(url) as response, dest.open('wb') as f:
            shutil.copyfileobj(response, f)
    if digest(dest) != expected:
        raise RuntimeError(f'Download checksum mismatch: {dest}')


def extract(archive, directory):
    with tarfile.open(archive) as f:
        f.extractall(directory, filter='data')


def python_versions(python, ripser=False):
    imports = 'import numpy,scipy' + (',ripser,pyRipser' if ripser else '')
    fields = "{'numpy':numpy.__version__,'scipy':scipy.__version__}"
    code = imports+';import json;v='+fields
    if ripser:
        code += ";v.update(ripser=ripser.__version__,extension=pyRipser.__file__)"
    return json.loads(subprocess.check_output([python, '-c', code+';print(json.dumps(v))'], text=True))


def prepare_python(work, existing=None, need_ripser=False):
    if existing:
        # Do not resolve the venv executable symlink: its directory selects its environment.
        python = str(Path(existing).absolute())
    else:
        venv = work/'venv'
        if not (venv/'bin/python').exists():
            run([sys.executable, '-m', 'venv', venv])
        python = str(venv/'bin/python')
        run([python, '-m', 'pip', 'install', 'numpy==2.5.3', 'scipy==1.18.1'])
        if need_ripser:
            run([python, '-m', 'pip', 'install', 'Cython==3.3.0', 'setuptools', 'wheel',
                 'scikit-learn==1.9.1', 'persim==0.3.8'])
            vendor = work/'downloads';vendor.mkdir(exist_ok=True)
            release = json.load(urllib.request.urlopen('https://pypi.org/pypi/ripser/0.6.15/json'))
            url = next(x['url'] for x in release['urls'] if x['packagetype']=='sdist')
            tar = vendor/'ripser-0.6.15.tar.gz'
            download(url, tar, 'bc0e340f778df0fc6a6e85ac081d2073db1af109a729bc81821af7214da15af4')
            robin = vendor/'robin-hood-hashing-3.11.5.tar.gz'
            download('https://github.com/martinus/robin-hood-hashing/archive/refs/tags/3.11.5.tar.gz',
                     robin, '3693e44dda569e9a8b87ce8263f7477b23af448a3c3600c8ab9004fe79c20ad0')
            source = vendor/'ripser-0.6.15'
            if not source.exists():
                extract(tar, vendor)
            if not (source/'robinhood').exists():
                extract(robin, vendor)
                shutil.copytree(vendor/'robin-hood-hashing-3.11.5', source/'robinhood')
            # The supported setup detects robinhood/src/include/robin_hood.h.
            build_env = env();build_env.update(CFLAGS='-O3', CXXFLAGS='-O3')
            run([python, '-m', 'pip', 'install', '--no-build-isolation', '--no-deps', str(source)], env=build_env)
    versions = python_versions(python, need_ripser)
    expected = {'numpy':'2.5.3','scipy':'1.18.1'}
    if need_ripser:
        expected['ripser'] = '0.6.15'
    for key,value in expected.items():
        if versions[key] != value:
            raise RuntimeError(f'{key}=={value} is required; {python} has {versions[key]}.')
    return python, versions


def portable_harness(study, work, julia, cpu):
    dest = work/'harness';dest.mkdir(exist_ok=True)
    changes = {}
    for source in (study/'historical').iterdir():
        if source.suffix not in ('.py','.jl'):
            continue
        text = source.read_text()
        original = text
        if source.name in ('run.py','study.py'):
            text = text.replace("ROOT=Path('/home/eriknovak/Documents/projects/TamerOp.jl')", f'ROOT=Path({str(work)!r})')
            text = text.replace("JULIA='/home/eriknovak/.julia/juliaup/julia-1.12.1+0.x64.linux.gnu/bin/julia'", f'JULIA={julia!r}')
            text = text.replace("JULIA_DEPOT_PATH='/tmp/tamerop-q6q7-depot:/home/eriknovak/.julia'", "JULIA_DEPOT_PATH=os.environ.get('JULIA_DEPOT_PATH',str(Path.home()/'.julia'))")
            text = text.replace("['taskset','-c','0'", f"['taskset','-c',{str(cpu)!r}")
        if source.name in ('run.py','verify.py'):
            text = text.replace(
                "OUT=Path(os.environ.get('RIPSER_STUDY_DIR',str(ROOT/'audit/2026-10-04/ripser_pilot')))",
                "OUT=Path(os.environ['RIPSER_STUDY_DIR'])")
        if source.name in ('run.py','study.py','verify.py') and '/home/eriknovak/' in text:
            raise RuntimeError(f'Unadapted workstation path in {source.name}')
        (dest/source.name).write_text(text)
        if text != original:
            changes[source.name] = dict(original_sha256=digest(source), portable_sha256=digest(dest/source.name),
                changes=(['Explicit study-directory environment variable'] if source.name == 'verify.py'
                         else ['Work-directory path','Julia executable','Julia depot selection','Allowed CPU affinity']))
    write_json(work/'portability.json', changes)
    return dest


def verify_work(study, work):
    verify_sources(study)
    if not (work/'manifest.json').exists():
        return
    for case in json.loads((work/'manifest.json').read_text())['cases']:
        if digest(work/case['input']) != case['sha256']:
            raise RuntimeError(f'Input hash mismatch: {case["id"]}')
    print('Prepared input files match the original study hashes.')
