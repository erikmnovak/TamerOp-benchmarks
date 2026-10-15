"""Pin/build an unchanged release, then snapshot inputs and the TamerOp candidate."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,tarfile,time,urllib.request,venv
ROOT=Path(__file__).resolve().parents[2]
VERSION='0.0.36'
URL='https://files.pythonhosted.org/packages/fb/b7/c64dc1ced9354a47d68a320669968f4e94e3a9275ac939da393dc8a26f32/cripser-0.0.36.tar.gz'
DIGEST='7e2c60dcf1246e20eac26d1e7688bf136d82ef34977d5a707d07e7a95c88c05c'
PINS=['numpy==2.5.3','nanobind==3.1.0','setuptools==84.0.0','wheel==0.48.0','packaging==26.3','cmake==4.4.4','ninja==1.13.2']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(out):
    envdir=out/'environment';envdir.mkdir(parents=True,exist_ok=True)
    if (envdir/'ready.json').exists():
        print('Existing pinned environment; no rebuild');return
    archive=envdir/f'cripser-{VERSION}.tar.gz'
    if not archive.exists():archive.write_bytes(urllib.request.urlopen(URL).read())
    assert digest(archive)==DIGEST,'source archive hash mismatch'
    source=envdir/f'cripser-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as t:t.extractall(envdir,filter='data')
    src_hashes={str(p.relative_to(source)):digest(p) for p in source.rglob('*') if p.is_file()}
    (envdir/'upstream_hashes.json').write_text(json.dumps(src_hashes,indent=2)+'\n')
    python=envdir/'venv/bin/python'
    if not python.exists():venv.create(envdir/'venv',with_pip=True)
    env=os.environ.copy();env.update(PATH=str(python.parent)+os.pathsep+env['PATH'],CMAKE_BUILD_PARALLEL_LEVEL='2',PIP_DISABLE_PIP_VERSION_CHECK='1')
    commands=[]
    def run(cmd,name,cwd=None):
        commands.append(cmd)
        with (envdir/(name+'.log')).open('w') as log:subprocess.run(cmd,env=env,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,check=True)
    wheelhouse=envdir/'wheelhouse';wheelhouse.mkdir(exist_ok=True)
    run([str(python),'-m','pip','download','--only-binary=:all:','--dest',str(wheelhouse),*PINS],'dependencies_download')
    run([str(python),'-m','pip','install','--no-index','--find-links',str(wheelhouse),*PINS],'dependencies_install')
    # setup.py selects Release; verbose output and the compiler commands remain
    # in the evidence. No compiler flags or upstream source are patched.
    run([str(python),'-m','pip','install','-v','--no-build-isolation','--no-deps',str(source)],'build')
    builddir=next(p.parent for p in (source/'build').rglob('CMakeCache.txt'))
    run([str(python.parent/'cmake'),'--build',str(builddir),'--target','cubicalripser','tcubicalripser','--config','Release','-j','2'],'cli_build')
    for name in ('cubicalripser','tcubicalripser'):shutil.copy2(builddir/name,envdir/name)
    shutil.copy2(builddir/'CMakeCache.txt',envdir/'CMakeCache.txt')
    assert 'CMAKE_BUILD_TYPE:STRING=Release' in (envdir/'CMakeCache.txt').read_text()
    # Packaging may refresh egg-info; the actual competitor sources must match.
    checked=[k for k in src_hashes if k.startswith(('src/','cripser/')) or k in ('CMakeLists.txt','setup.py','pyproject.toml')]
    assert all(digest(source/k)==src_hashes[k] for k in checked)
    installed=json.loads(subprocess.check_output([str(python),'-c',"import cripser,numpy,json,sys;print(json.dumps(dict(cripser=cripser.__version__,numpy=numpy.__version__,python=sys.version,package=cripser.__file__)))"],env=env,text=True))
    assert installed['cripser']==VERSION
    freeze=subprocess.check_output([str(python),'-m','pip','freeze','--all'],env=env,text=True);(envdir/'requirements.lock').write_text(freeze)
    (envdir/'ready.json').write_text(json.dumps(dict(version=VERSION,url=URL,sdist_sha256=DIGEST,installed=installed,commands=commands,release=True,unmodified_sources_verified=len(checked),wheels={p.name:digest(p) for p in wheelhouse.iterdir()},binaries={n:digest(envdir/n) for n in ('cubicalripser','tcubicalripser')},extensions={str(p.relative_to(envdir)):digest(p) for p in (envdir/'venv').rglob('*.so') if 'cripser' in str(p)}),indent=2)+'\n')
    print('Pinned CubicalRipser Release build verified',flush=True)
def snapshot(out):
    if (out/'candidate').exists():raise RuntimeError('Candidate already exists; prepare a new study directory instead of overwriting it')
    dest=out/'candidate'
    for name in ('src','ext'):shutil.copytree(ROOT/name,dest/name)
    for name in ('Project.toml','Manifest.toml','LocalPreferences.toml'):
        if (ROOT/name).exists():shutil.copy2(ROOT/name,dest/name)
    (out/'candidate_hashes.json').write_text(json.dumps({str(p.relative_to(dest)):digest(p) for p in dest.rglob('*') if p.is_file()},indent=2)+'\n')
    from fixtures import prepare
    prepare(out)
    harness=out/'harness';shutil.copytree(Path(__file__).parent,harness/'cubicalripser',ignore=shutil.ignore_patterns('__pycache__'))
    (harness/'phat').mkdir();shutil.copy2(ROOT/'benchmark/phat/oracle.py',harness/'phat/oracle.py')
    (out/'harness_hashes.json').write_text(json.dumps({str(p.relative_to(harness)):digest(p) for p in harness.rglob('*') if p.is_file()},indent=2)+'\n')
    print('Candidate, fixtures and harness snapshotted',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--environment-only',action='store_true');a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    build(a.out)
    if not a.environment_only:snapshot(a.out)
