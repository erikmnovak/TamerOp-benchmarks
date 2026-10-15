#!/usr/bin/env python3
"""Reproduce the fixed QPA study with its unchanged source and mathematical workers."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "sources/qpa-v1"
THREADS = {"JULIA_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
           "JULIA_PKG_PRECOMPILE_AUTO": "0", "JULIA_NUM_PRECOMPILE_TASKS": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}
PARTS = {"core": ("qpa_core", "core/fixtures.json", 96),
         "diagrams": ("qpa_core", "diagrams/fixtures.json", 80),
         "derived": ("qpa_derived", "integrated/derived_fixtures.json", 44)}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_tree(base):
    for line in (base / "SHA256SUMS").read_text().splitlines():
        expected, relative = line.split(maxsplit=1)
        if digest((base / relative).read_bytes()) != expected:
            raise ValueError(f"Checksum mismatch: {base / relative}")


def payload():
    return json.loads((HERE / "payload.json").read_text())


def verify():
    verify_tree(SOURCE)
    verify_tree(HERE / "evidence")
    for path, record in payload().items():
        data = (HERE / path).read_bytes()
        if record["gzip"]:
            data = gzip.decompress(data)
        if digest(data) != record["sha256"]:
            raise ValueError(f"Payload checksum mismatch: {path}")
    for part, (adapter, fixture, _) in PARTS.items():
        frozen = json.loads((HERE / "frozen" / (part + ".json")).read_text())
        for relative, expected in frozen["package_sha256"].items():
            if digest((SOURCE / relative).read_bytes()) != expected:
                raise ValueError(f"Frozen package mismatch: {relative}")
        records = {r["path"]: r["sha256"] for r in payload().values()}
        if records["audit/2026-09-27/qpa_suite_v1/" + fixture] != frozen["fixture_sha256"]:
            raise ValueError(f"Frozen fixture mismatch: {part}")
        for name, expected in frozen["harness_sha256"].items():
            if records[f"benchmark/{adapter}/{name}"] != expected:
                raise ValueError(f"Frozen adapter mismatch: {name}")
        for relative, expected in frozen["dependency_sha256"].items():
            actual = digest((SOURCE / relative).read_bytes()) if (SOURCE / relative).exists() else records[relative]
            if actual != expected:
                raise ValueError(f"Frozen dependency mismatch: {relative}")
    print("QPA source, exact inputs, adapters and result evidence verified.")


def install_bytes(target, data):
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError(f"Existing workspace file differs; use a new --work directory: {target}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def materialize(work):
    project = work / "project"
    for line in (SOURCE / "SHA256SUMS").read_text().splitlines():
        _, relative = line.split(maxsplit=1)
        install_bytes(project / relative, (SOURCE / relative).read_bytes())
    for path, record in payload().items():
        data = (HERE / path).read_bytes()
        install_bytes(project / record["path"], gzip.decompress(data) if record["gzip"] else data)
    return project


def executable(value, label):
    found = shutil.which(value)
    if not found:
        raise ValueError(f"{label} executable not found: {value}. Supply its path with --{label.lower()}.")
    return str(Path(found).resolve())


def runtimes(args, work):
    saved = json.loads((work / "prepared.json").read_text()) if (work / "prepared.json").exists() else {}
    julia = executable(args.julia or saved.get("julia", "julia"), "Julia")
    gap_value = args.gap or saved.get("gap")
    if gap_value is None:
        local = work / "tools/gap-4.16.1/gap"
        if not local.exists():
            raise ValueError("Run prepare to build GAP 4.16.1, or supply --gap /path/to/GAP-4.16.1/gap. See this study's README.")
        gap_value = str(local)
    gap = executable(gap_value, "GAP")
    version = subprocess.check_output([julia, "--startup-file=no", "-e", "print(VERSION)"], text=True).strip()
    if version != "1.12.1":
        raise ValueError(f"This historical study requires Julia 1.12.1; found {version}.")
    probe = 'if LoadPackage("qpa")<>true then Error("QPA missing"); fi; Print(GAPInfo.Version,"\\n",PackageInfo("qpa")[1].Version,"\\n"); QUIT;'
    output = subprocess.check_output([gap, "--bare", "-A", "-q", "--nointeract", "--quitonbreak", "-c", probe], text=True)
    if "4.16.1\n1.37\n" not in output:
        raise ValueError("The selected GAP must be 4.16.1 with QPA 1.37. See the pinned setup recipe.")
    package = next((parent / "pkg/qpa" for parent in Path(gap).parents
                    if (parent / "pkg/qpa").is_dir()), Path(gap).parent / "pkg/qpa")
    for relative, expected in json.loads((HERE / "qpa_source_sha256.json").read_text()).items():
        source = package / relative
        if not source.is_file() or digest(source.read_bytes()) != expected:
            raise ValueError(f"QPA source does not match the measured release at {source}; use prepare --build-gap.")
    return julia, gap


def prepare(args, work, project):
    if args.build_gap or not args.gap:
        subprocess.run([sys.executable, str(HERE / "setup_gap.py"), str(work / "tools")], check=True)
    julia, gap = runtimes(args, work)
    env = dict(os.environ, **THREADS)
    subprocess.run([julia, "--startup-file=no", "--threads=1", f"--project={project}", "-e",
                    "using Pkg; Pkg.instantiate(;allow_autoprecomp=false); Pkg.precompile(); using TamerOp, JSON3"],
                   env=env, check=True)
    # Instantiation must leave the pinned Project and Manifest intact.
    materialize(work)
    clock = project / "benchmark/qpa_suite/clock/preflight.g"
    checked = subprocess.run([gap, "--bare", "-A", "-q", "--nointeract", "--quitonbreak", str(clock)],
                             capture_output=True, text=True, check=True)
    (work / "gap-clock.log").write_text(checked.stdout + checked.stderr)
    if "COMPLETE" not in checked.stdout:
        raise ValueError("GAP's monotonic clock check failed; see gap-clock.log and the pinned setup recipe.")
    record = {"julia": julia, "gap": gap, "julia_version": "1.12.1", "gap_version": "4.16.1", "qpa_version": "1.37"}
    (work / "prepared.json").write_text(json.dumps(record, indent=2) + "\n")
    print("QPA environment prepared. Run smoke before starting the full measurement.")


def run_bounded(command, project, log, seconds):
    """Stop the original runner and its separately grouped workers on expiry."""
    process = subprocess.Popen(command, cwd=project, env=dict(os.environ, **THREADS),
                               stdout=log, stderr=subprocess.STDOUT)
    try:
        code = process.wait(timeout=seconds)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        pairs = subprocess.check_output(["ps", "-eo", "pid=,ppid="], text=True)
        parents = {int(pid): int(parent) for pid, parent in
                   (line.split() for line in pairs.splitlines())}
        selected = {process.pid}
        while True:
            enlarged = selected | {pid for pid, parent in parents.items() if parent in selected}
            if enlarged == selected:
                break
            selected = enlarged
        for pid in sorted(selected, reverse=True):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(1)
        for pid in selected:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        raise
    if code:
        raise subprocess.CalledProcessError(code, command)


def compute(args, work, project, smoke):
    julia, gap = runtimes(args, work)
    output = work / ("smoke-" if smoke else "measurement-")
    output = output.with_name(output.name + time.strftime("%Y%m%dT%H%M%S"))
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    parts = ["core"] if smoke else list(PARTS)
    outcomes = {}
    for part in parts:
        adapter, fixture, count = PARTS[part]
        fixtures = project / "audit/2026-09-27/qpa_suite_v1" / fixture
        command = [sys.executable, str(project / "benchmark" / adapter / "run.py"),
                   "--fixtures", str(fixtures), "--output", str(output / part),
                   "--julia", julia, "--gap", gap]
        if smoke:
            command += ["--mode", "correctness", "--cases", "Q1:hom_basis:cube3_presentation_r1_QQ_s11", "--fields", "QQ"]
        else:
            command += ["--mode", "confirmation", "--passes", "5", "--samples", "3",
                        "--candidate-record", str(HERE / "frozen" / (part + ".json"))]
        with (output / (part + ".log")).open("w") as log:
            run_bounded(command, project, log, 900 if smoke else max(1, 54000 - (time.monotonic() - started)))
        processes = json.loads((output / part / "processes.json").read_text())
        if any(p["status"] != "completed" for p in processes):
            raise ValueError(f"A worker did not complete; inspect {output / part}")
        verified = json.loads((output / part / "verification.json").read_text())
        expected = 1 if smoke else (24 if part == "derived" else count)
        if verified["verified_matched_cases"] != expected:
            raise ValueError(f"Unexpected matched-answer coverage in {part}: see {output / part / 'verification.json'}")
        if smoke and (verified["failures"] or verified["verified_native_cases"] != 2):
            raise ValueError("The QPA smoke must produce both independently checked answers.")
        if not smoke and part == "derived":
            if any(r["tool"] != "QPA" or not r["case"].startswith("Q10") for r in verified["failures"]):
                raise ValueError("Failure outside the documented QPA tensor evaluations")
            if verified["verified_native_cases"] != 68:
                raise ValueError("Incomplete derived coverage; expected all 44 TamerOp answers and 24 QPA answers")
        outcomes[part] = {"matched_cases": verified["verified_matched_cases"], "native_cases": verified["verified_native_cases"]}
    (output / "COMPLETE.json").write_text(json.dumps({"action": "smoke" if smoke else "measure",
        "historical_candidate": "qpa-v1-529681519b5d1b40", "new_measurements": not smoke,
        "outcomes": outcomes, "runtimes": {"julia": julia, "gap": gap}}, indent=2) + "\n")
    print(f"Verified QPA {'smoke' if smoke else 'measurement'}: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "prepare", "smoke", "measure"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--julia", help="Julia 1.12.1 executable")
    parser.add_argument("--gap", help="GAP 4.16.1 executable with QPA 1.37")
    parser.add_argument("--build-gap", action="store_true", help="Build pinned GAP and install its pinned packages during prepare")
    args = parser.parse_args()
    verify()
    if args.action == "verify":
        return
    if not sys.platform.startswith("linux"):
        parser.error("The original resource-monitoring harness requires Linux (/proc).")
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    project = materialize(work)
    if args.action == "prepare":
        prepare(args, work, project)
    else:
        compute(args, work, project, args.action == "smoke")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
