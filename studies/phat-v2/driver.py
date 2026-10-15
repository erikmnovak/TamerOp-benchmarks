#!/usr/bin/env python3
"""Recreate PHAT inputs and run the unchanged ordinary persistence comparison."""
from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "sources/phat-v2"
HARNESS = HERE / "harness"
THREADS = {"JULIA_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
           "JULIA_PKG_PRECOMPILE_AUTO": "0", "JULIA_NUM_PRECOMPILE_TASKS": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}
sys.dont_write_bytecode = True


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_tree(base):
    for line in (base / "SHA256SUMS").read_text().splitlines():
        expected, relative = line.split(maxsplit=1)
        if digest((base / relative).read_bytes()) != expected:
            raise ValueError(f"Checksum mismatch: {base / relative}")


def manifest_bytes():
    return gzip.decompress((HERE / "inputs/manifest.json.gz").read_bytes())


def verify():
    verify_tree(SOURCE)
    verify_tree(HERE / "evidence")
    original = json.loads((HERE / "origin.json").read_text())
    for name, expected in original["harness_sha256"].items():
        if digest((HARNESS / name).read_bytes()) != expected:
            raise ValueError(f"Frozen PHAT adapter mismatch: {name}")
    if digest(manifest_bytes()) != original["fixture_manifest_sha256"]:
        raise ValueError("Frozen PHAT manifest changed")
    print("PHAT source, original input manifest, adapters and result evidence verified.")


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
    # The original supervisor accepts a source-origin record for an extracted
    # snapshot. This records the new location without needing a synthetic Git repo.
    install_bytes(project / "SOURCE_ORIGIN.json", (HERE / "origin.json").read_bytes())
    install_bytes(project / "SOURCE_DIFF.patch", b"")
    install_bytes(work / "fixtures/manifest.json", manifest_bytes())
    return project


def load(name):
    sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location("phat_original_" + name, HARNESS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate(work, only=None):
    generator = load("generate")
    manifest = json.loads(manifest_bytes())
    specifications = {row["id"]: row for row in generator.specification()}
    for row in manifest["cases"]:
        if only is not None and row["id"] not in only:
            continue
        destination = work / "fixtures" / row["path"]
        if destination.exists():
            if digest(destination.read_bytes()) != row["sha256"]:
                raise ValueError(f"Input changed: {destination}")
            continue
        spec = specifications[row["id"]]
        if spec["family"] == "control":
            cells, known = generator.controls()[spec["id"]]
        else:
            cells, known = getattr(generator.generators, spec["family"])(0, spec["variant"], n=spec["n"])
        generator.validate_sparse(cells)
        encoded = generator.encode(cells)
        if digest(encoded) != row["sha256"]:
            raise ValueError(f"Regenerated input differs from original: {row['id']}")
        if known is not None and known != row["expected"]:
            raise ValueError(f"Known answer differs from original: {row['id']}")
        destination.write_bytes(encoded)
        print("Recreated", row["id"], flush=True)
        del cells, encoded, known
        gc.collect()


def julia_runtime(args, work):
    saved = json.loads((work / "prepared.json").read_text()) if (work / "prepared.json").exists() else {}
    executable = shutil.which(args.julia or saved.get("julia", "julia"))
    if not executable:
        raise ValueError("Julia executable not found; provide --julia /path/to/Julia-1.12.1/bin/julia.")
    executable = str(Path(executable).resolve())
    version = subprocess.check_output([executable, "--startup-file=no", "-e", "print(VERSION)"], text=True).strip()
    if version != "1.12.1":
        raise ValueError(f"This historical study requires Julia 1.12.1; found {version}.")
    return executable


def prepare(args, work, project):
    julia = julia_runtime(args, work)
    if not shutil.which("g++"):
        raise ValueError("Install g++ before building PHAT's pinned C++ adapter.")
    if not (work / "build").exists():
        command = [sys.executable, str(HARNESS / "build.py"), str(work / "build")]
        if args.phat_archive:
            command += ["--archive", str(args.phat_archive.resolve())]
        subprocess.run(command, check=True)
    else:
        load("protocol").verify_build(work / "build", HARNESS / "worker.cpp")
    subprocess.run([julia, "--startup-file=no", "--threads=1", f"--project={project}", "-e",
                    "using Pkg; Pkg.instantiate(;allow_autoprecomp=false); Pkg.precompile(); using TamerOp, JSON3"],
                   env=dict(os.environ, **THREADS), check=True)
    materialize(work)
    generate(work)
    (work / "prepared.json").write_text(json.dumps({"julia": julia, "julia_version": "1.12.1"}, indent=2) + "\n")
    print("PHAT environment and exact inputs prepared. Run smoke before the full measurement.")


def smoke(args, work, project):
    julia = julia_runtime(args, work)
    load("protocol").verify_build(work / "build", HARNESS / "worker.cpp")
    chosen = {"circle", "filled_triangle"}
    generate(work, only=chosen)
    cases = {c["id"]: c for c in json.loads(manifest_bytes())["cases"] if c["id"] in chosen}
    runner = load("run")
    output = work / ("smoke-" + time.strftime("%Y%m%dT%H%M%S"))
    output.mkdir(exist_ok=False)
    listed = output / "inputs.tsv"
    listed.write_text("".join(f"{name}\t{work / 'fixtures' / c['path']}\n" for name, c in cases.items()))
    base = [str(listed), "correctness", "1", "0"]
    commands = {
        "phat": [str(work / "build/phat_worker"), *base, "twist"],
        "phat_standard": [str(work / "build/phat_worker"), *base, "standard"],
        "tamerop": [julia, "--startup-file=no", "--threads=1", "--compiled-modules=existing",
                    "--compile=min", f"--project={project}", str(HARNESS / "worker.jl"), *base, "twist"],
    }
    for tool, command in commands.items():
        runner.launch(command, output / tool, cases, False, 1, project,
                      dict(os.environ, **THREADS), remaining_seconds=900)
    (output / "COMPLETE.json").write_text(json.dumps({"action": "smoke", "cases": sorted(chosen),
        "tools": list(commands), "checked": "Complete barcodes, known answers, native reset guards"}, indent=2) + "\n")
    print(f"Verified PHAT smoke: {output}")


def measure(args, work, project):
    julia = julia_runtime(args, work)
    generate(work)
    runner = load("run")
    identity = runner.run_identity(project, work / "fixtures", work / "build", "confirmation", "main", julia)
    original = json.loads((HERE / "evidence/provenance.json").read_text())
    if identity["source"] != original["source_sha256"] or identity["harness"] != original["harness_sha256"]:
        raise ValueError("Measurement source or harness differs from the published study")
    output = work / ("measurement-" + time.strftime("%Y%m%dT%H%M%S"))
    freeze = work / (output.name + ".freeze.json")
    freeze.write_text(json.dumps({"schema": 2, "accepted": True, "identity": identity,
        "basis": "Historical source and input identities verified; newly built runtime and PHAT binary recorded for this reproduction"}, indent=2) + "\n")
    subprocess.run([sys.executable, str(HARNESS / "run.py"), "--repo", str(project),
                    "--fixtures", str(work / "fixtures"), "--build", str(work / "build"),
                    "--output", str(output), "--julia", julia, "--mode", "confirmation", "--freeze", str(freeze)],
                   env=dict(os.environ, **THREADS), check=True)
    subprocess.run([sys.executable, str(HARNESS / "report.py"), str(output), str(work / "fixtures")],
                   env=dict(os.environ, **THREADS), check=True)
    print(f"Verified PHAT measurement: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "prepare", "smoke", "measure"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--julia", help="Julia 1.12.1 executable")
    parser.add_argument("--phat-archive", type=Path, help="Previously downloaded, checksum-matched PHAT source archive")
    args = parser.parse_args()
    verify()
    if args.action == "verify":
        return
    if not sys.platform.startswith("linux"):
        parser.error("The original resource-monitoring harness requires Linux (/proc).")
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    project = materialize(work)
    {"prepare": prepare, "smoke": smoke, "measure": measure}[args.action](args, work, project)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
