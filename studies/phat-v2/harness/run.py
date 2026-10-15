"""Serial, resumable supervisor. All mathematical answers are checked outside timers."""
import argparse
import hashlib
import json
import os
import platform
import selectors
import signal
import subprocess
import time
from pathlib import Path
from build import digest
from fixtures import decode
from oracle import validate, validate_sparse
from protocol import JULIA_FLAGS, THREAD_ENV, GC_POLICY, protocol, runtime_identity, select_cases, verify_freeze, verify_build

PHASES = ("construction", "query", "combined")
LIMITS = dict(operation_seconds=60, worker_seconds=900, rss_bytes=4 * 1024**3,
              pilot_seconds=1200, confirmation_seconds=6000)


def source_identity(repo):
    paths = sorted((repo / "src").rglob("*.jl")) + sorted((repo / "ext").rglob("*.jl"))
    paths += [p for p in (repo / "Project.toml", repo / "Manifest.toml") if p.exists()]
    files = {str(p.relative_to(repo)): digest(p) for p in paths}
    harness = {p.name: digest(p) for p in sorted(Path(__file__).parent.iterdir())
               if p.suffix in (".py", ".jl", ".cpp")}
    return dict(source=files, harness=harness)


def environment():
    cpu = Path("/proc/cpuinfo").read_text()
    return dict(uname=platform.uname()._asdict(),
                cpu_model=next(line.split(":", 1)[1].strip() for line in cpu.splitlines()
                               if line.startswith("model name")),
                logical_cpus=os.cpu_count(), load_average=os.getloadavg(),
                memory=Path("/proc/meminfo").read_text(),
                thread_environment={k: os.environ.get(k) for k in
                                    ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")})


def check_row(row, cases, timing):
    if row.get("event") != "sample":
        return
    case = cases[row["case"]]
    if "backend" in row:
        assert (row['backend'] is None if row['phase']=='construction' else
                row['backend'] in ('f2_graph_union_find','f2_clearing')), 'invalid executed backend' 
    assert row["reset_verified"] is True, "reset not verified"
    assert row["phase"] in PHASES
    if row["phase"] != "construction":
        assert row["answer"] == case["expected"], f"barcode mismatch: {case['id']}"
    if timing and row["kind"] == "measurement":
        assert row["seconds"] > 0 and row["seconds"] <= LIMITS["operation_seconds"]
        assert row["compile_seconds"] == row["recompile_seconds"] == 0, "compiled sample accepted"
    if not timing:
        assert row.get("seconds") is None, "evaluation timing leaked"


def check_job(path, cases, timing, samples):
    # Bound verification memory by a single barcode, not an entire worker log.
    identity_path = path.parent / 'identity.json'
    identity = json.loads(identity_path.read_text()) if identity_path.exists() else None
    protocol_records, counts, warmups, guard, last = [], {}, {}, False, None
    with path.open() as raw:
        for line in raw:
            row = json.loads(line)
            last = row
            check_row(row, cases, timing)
            if row.get('event') == 'reset_guard' and row.get('passed'):
                guard = True
            if row.get('event') in ('metadata','phase','sample'):
                protocol_records.append({k:v for k,v in row.items() if k != 'answer'})
            key = row.get('case'), row.get('phase')
            if row.get('kind') == ('measurement' if timing else 'correctness'):
                counts[key] = counts.get(key, 0) + 1
            if row.get('kind') == 'warmup':
                warmups[key] = warmups.get(key, 0) + 1
    assert last is not None and last['event'] == 'complete', 'incomplete worker'
    assert guard, 'missing negative reset control'
    if identity and identity.get('protocol', {}).get('version') == 2:
        check_protocol(protocol_records, identity, timing)
    expected = {(id, phase): samples if timing else 1 for id in cases
                for phase in (PHASES if timing else ('query',))}
    assert counts == expected, 'accepted sample counts differ'
    if timing and identity:
        assert warmups == {k:identity['warmups'] for k in expected}, 'warmup counts differ'
    return counts


def check_protocol(records, identity, timing):
    metadata = [r for r in records if r['event']=='metadata']
    assert len(metadata)==1, 'missing or duplicate worker metadata'
    meta=metadata[0]
    if meta['tool']=='tamerop':
        assert meta['protocol_version']==2 and meta['gc_policy']==GC_POLICY
        assert meta['algorithm']=='public_persistence_diagram'
        assert meta['backend_scope']==identity['protocol']['tamerop_backend_scope']
        assert meta['julia']==identity['runtime']['julia_version']
        assert meta['threads']==meta['blas_threads']==1
        assert meta['field']=='F2' and meta['order']=='sublevel' and meta['representatives'] is False
        phases=[r for r in records if r['event']=='phase']
        expected={(c,p) for c in identity['case_ids'] for p in (PHASES if timing else ('query',))}
        assert len(phases)==len(expected) and {(r['case'],r['phase']) for r in phases}==expected
        assert all(r['forced_gc'] is timing for r in phases), 'GC placement mismatch'
        routes={}
        for r in records:
            if r['event']!='sample':continue
            assert 'backend' in r, 'missing executed backend'
            if r['phase']=='construction':assert r['backend'] is None
            else:
                assert r['backend'] in identity['protocol']['accepted_backend_families']
                assert routes.setdefault(r['case'],r['backend'])==r['backend'], 'backend changed between samples'
    else:
        assert meta['tool']=='phat'
        assert meta['representation']=='bit_tree_pivot_column'
        assert meta['algorithm'] in (('standard','twist') if not timing else ('twist',))
        assert meta['clock_steady'] is True


def run_identity(repo, fixtures, build, mode, suite, julia='julia'):
    manifest_path=fixtures/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    cases=select_cases(manifest,mode,suite)
    timing=mode!='correctness'
    return dict(manifest_sha256=digest(manifest_path),**source_identity(repo),
                build=verify_build(build,Path(__file__).with_name('worker.cpp')),
                mode=mode,suite=suite,case_ids=list(cases),limits=LIMITS,
                samples=3 if timing else 1,warmups=2 if timing else 0,
                passes={'correctness':1,'pilot':2,'confirmation':5}[mode],
                protocol=protocol(),runtime=runtime_identity(julia))


def launch(command, prefix, cases, timing, samples, repo, env, remaining_seconds=None):
    start = time.monotonic()
    rows_path = prefix.with_suffix(".jsonl")
    err_path = prefix.with_suffix(".stderr")
    peak = 0
    operation_start = None
    active = None
    failure = None
    with rows_path.open("x") as raw, err_path.open("x") as err:
        process = subprocess.Popen(command, cwd=repo, env=env, stdout=subprocess.PIPE,
                                   stderr=err, start_new_session=True)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        buffer = b""
        try:
            while selector.get_map():
                now = time.monotonic()
                if remaining_seconds is not None and now - start > remaining_seconds:
                    raise TimeoutError('campaign wall budget exhausted')
                try:
                    status = Path(f"/proc/{process.pid}/status").read_text()
                    rss = next((int(line.split()[1]) * 1024 for line in status.splitlines()
                                if line.startswith("VmRSS:")), 0)
                    peak = max(peak, rss)
                    if rss > LIMITS["rss_bytes"]:
                        raise TimeoutError("worker RSS limit exceeded")
                except FileNotFoundError:
                    pass
                if now - start > LIMITS["worker_seconds"]:
                    raise TimeoutError("worker wall limit exceeded")
                if operation_start is not None and now - operation_start > LIMITS["operation_seconds"]:
                    raise TimeoutError("operation wall limit exceeded (includes untimed setup/checks)")
                for key, _ in selector.select(timeout=0.05):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    buffer += data
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        raw.write(line.decode() + "\n"); raw.flush()
                        row = json.loads(line)
                        if row["event"] == "begin":
                            operation_start = time.monotonic()
                            active = {k: row[k] for k in ("case", "phase")}
                        elif row["event"] == "sample":
                            check_row(row, cases, timing)
                            operation_start = None
            if buffer:
                raise ValueError("truncated JSON line")
            code = process.wait(timeout=5)
            if code:
                raise RuntimeError(f"worker exit {code}; see {err_path.name}")
            raw.flush()
            check_job(rows_path, cases, timing, samples)
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        finally:
            selector.close()
            process.stdout.close()
    result = dict(command=command, elapsed_seconds=time.monotonic()-start,
                  sampled_peak_worker_rss_bytes=peak, active_at_failure=active if failure else None,
                  failure=failure, environment_after=environment(),
                  raw_sha256=digest(rows_path), stderr_sha256=digest(err_path))
    prefix.with_suffix(".status.json").write_text(json.dumps(result, indent=2) + "\n")
    if failure:
        raise RuntimeError(failure)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--fixtures", type=Path, required=True)
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--julia", default="julia")
    p.add_argument("--mode", choices=("correctness", "pilot", "confirmation"), required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--freeze", type=Path)
    p.add_argument("--suite", choices=("main","larger"), default="main")
    p.add_argument("--check-only", action="store_true", help="verify identities and freeze without launching measurements")
    args = p.parse_args()
    repo, fixtures, build, output = [v.resolve() for v in (args.repo, args.fixtures, args.build, args.output)]
    manifest_path = fixtures / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    timing = args.mode != "correctness"
    cases = select_cases(manifest,args.mode,args.suite)
    for case in cases.values():
        path = fixtures / case['path']
        assert digest(path)==case['sha256'], 'fixture changed'
        (validate_sparse if args.suite=='larger' or manifest.get('study')=='phat_v2' else validate)(decode(path))
    identity = run_identity(repo,fixtures,build,args.mode,args.suite,args.julia)
    if args.mode=='confirmation':
        if args.freeze is None:p.error('confirmation requires a separately reviewed candidate freeze')
        verify_freeze(json.loads(args.freeze.read_text()),identity)
    if args.check_only:
        print(json.dumps(dict(preflight='passed',suite=args.suite,mode=args.mode,cases=len(cases),measurements_started=False)))
        return
    if output.exists():
        assert args.resume, "output exists; use a new run name or verified --resume"
        assert json.loads((output / "identity.json").read_text()) == identity, "resume identity mismatch"
    else:
        output.mkdir(parents=True)
        (output / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
        (output / "environment_before.json").write_text(json.dumps(environment(), indent=2) + "\n")
        if (repo/'SOURCE_ORIGIN.json').exists():
            (output/'source_origin.json').write_bytes((repo/'SOURCE_ORIGIN.json').read_bytes())
            (output/'source.diff').write_bytes((repo/'SOURCE_DIFF.patch').read_bytes())
        else:
            (output / "source.diff").write_bytes(subprocess.check_output(["git", "diff", "--", "src", "ext", "Project.toml", "Manifest.toml"], cwd=repo))
            (output / "git_head.txt").write_bytes(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo))
    env = dict(os.environ, **THREAD_ENV)
    env.setdefault("JULIA_PKG_PRECOMPILE_AUTO", "0")
    commands = {"phat": [str(build / "phat_worker")],
                "tamerop": [args.julia, *JULIA_FLAGS, f"--project={repo}",
                            str(Path(__file__).with_name("worker.jl"))]}
    started = time.monotonic()
    prior_elapsed = sum(json.loads(p.read_text())["elapsed_seconds"]
                        for p in output.glob("*.status.json"))
    for run in range(identity["passes"]):
        case_order = list(cases)
        if run % 2:
            case_order.reverse()
        listpath = output / f"pass{run+1}.tsv"
        expected_list = "".join(f"{id}\t{fixtures / cases[id]['path']}\n" for id in case_order)
        if listpath.exists():
            assert listpath.read_text() == expected_list
        else:
            listpath.write_text(expected_list)
        tools = ["phat", "tamerop"] if run % 2 == 0 else ["tamerop", "phat"]
        if not timing:
            tools.append("phat_standard")
        for tool in tools:
            prefix = output / f"pass{run+1}_{tool}"
            status = prefix.with_suffix(".status.json")
            if status.exists() and not json.loads(status.read_text())["failure"]:
                previous=json.loads(status.read_text())
                assert digest(prefix.with_suffix('.jsonl'))==previous['raw_sha256'], 'completed raw output changed'
                assert digest(prefix.with_suffix('.stderr'))==previous['stderr_sha256'], 'completed stderr changed'
                check_job(prefix.with_suffix(".jsonl"), cases, timing, identity["samples"])
                continue
            if prefix.with_suffix(".jsonl").exists():
                raise RuntimeError("failed/incomplete output retained; use a new run directory")
            budget = LIMITS["confirmation_seconds" if args.mode == "confirmation" else "pilot_seconds"]
            if prior_elapsed + time.monotonic()-started >= budget:
                raise TimeoutError("campaign budget exhausted")
            base = commands["phat" if tool == "phat_standard" else tool]
            command = base + [str(listpath), "timing" if timing else "correctness",
                              str(identity["samples"]), str(identity["warmups"]),
                              "standard" if tool == "phat_standard" else "twist"]
            print(f"Starting pass {run+1} {tool}: {len(cases)} cases", flush=True)
            remaining = budget - prior_elapsed - (time.monotonic() - started)
            launch(command, prefix, cases, timing, identity['samples'], repo, env,
                   remaining_seconds=remaining)
            print(f"Verified pass {run+1} {tool}", flush=True)
    assert source_identity(repo) == {k: identity[k] for k in ("source", "harness")}, "source changed during run"
    (output / "COMPLETE.json").write_text(json.dumps(dict(mode=args.mode, suite=args.suite, cases=len(cases),
        passes=identity["passes"], identity_sha256=digest(output / "identity.json")), indent=2) + "\n")


if __name__ == "__main__":
    main()
