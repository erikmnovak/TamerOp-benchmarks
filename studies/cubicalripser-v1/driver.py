"""Portable adapter for the recorded CubicalRipser public-call comparison."""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HARNESS = HERE / "harness/cubicalripser"
sys.path.insert(0, str(HARNESS))
import large_study as study
import large_analyze


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read(path):
    return json.loads(path.read_text())


def verify_files(base, manifest):
    for name, expected in manifest.items():
        path = base / name
        if not path.is_file() or study.sha(path) != expected:
            raise RuntimeError(f"Missing or changed file: {path}")


def verify():
    verify_files(ROOT / "sources/cubicalripser-v1", read(HERE / "source_manifest.json"))
    verify_files(HERE, read(HERE / "adapter_sha256.json"))
    for line in (HERE / "evidence/SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        verify_files(HERE / "evidence", {name: digest})
    print("Cubical source snapshot and published evidence match their SHA256 records.", flush=True)


def configure(args):
    if not sys.platform.startswith("linux"):
        raise RuntimeError("This runner needs Linux /proc monitoring and taskset.")
    julia = shutil.which(args.julia)
    if julia is None:
        raise RuntimeError("Julia 1.12.1 is required; supply --julia /path/to/julia.")
    version = subprocess.check_output([julia, "--startup-file=no", "-e", "print(VERSION)"], text=True)
    if version.strip() != "1.12.1":
        raise RuntimeError(f"Expected Julia 1.12.1; found {version}.")
    if shutil.which("taskset") is None:
        raise RuntimeError("Install util-linux to provide taskset.")
    study.JULIA = julia
    study.DEPOT = os.environ.get("JULIA_DEPOT_PATH", str(Path.home() / ".julia"))
    return julia


def prepare(args):
    verify()
    print("Checking Julia and platform requirements.", flush=True)
    julia = configure(args)
    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    candidate = work / "candidate"
    source = ROOT / "sources/cubicalripser-v1"
    expected = read(HERE / "source_manifest.json")
    if not candidate.exists():
        shutil.copytree(source, candidate)
    verify_files(candidate, expected)
    shutil.copy2(HERE / "source_manifest.json", work / "candidate_hashes.json")
    preparation = ("import TamerOp; println(\"Loaded frozen TamerOp source: \", pathof(TamerOp))"
                   if args.reuse_julia_dependencies else
                   "using Pkg; Pkg.instantiate(); Pkg.precompile()")
    image_flags = ["--compiled-modules=existing", "--pkgimages=existing"] if args.reuse_julia_dependencies else []
    print("Loading the frozen Julia package." if args.reuse_julia_dependencies else
          "Instantiating and precompiling the frozen Julia environment.", flush=True)
    subprocess.run([julia, "--startup-file=no", *image_flags, "--project=" + str(candidate), "-e", preparation], check=True,
                   env={**os.environ, "JULIA_NUM_PRECOMPILE_TASKS": "1"})
    verify_files(candidate, expected)
    if args.reuse_environment:
        external = args.reuse_environment.resolve()
        ready = read(external / "ready.json")
        if ready["version"] != "0.0.37" or not ready["release"]:
            raise RuntimeError("The supplied environment is not the pinned Release build.")
        verify_files(external, ready["extensions"])
        verify_files(external, ready["binaries"])
        target = work / "environment"
        if target.exists() or target.is_symlink():
            if not target.is_symlink() or target.resolve() != external:
                raise RuntimeError("Use a fresh work directory for a different environment.")
        else:
            target.symlink_to(external, target_is_directory=True)
    else:
        if sys.version_info[:2] != (3, 12):
            raise RuntimeError("Run preparation with Python 3.12 to build the recorded Python interface.")
        import prepare as upstream_prepare
        build = read(HERE / "evidence/build.json")
        upstream_prepare.VERSION = build["version"]
        upstream_prepare.URL = build["url"]
        upstream_prepare.DIGEST = build["sdist_sha256"]
        upstream_prepare.build(work)
    python = work / "environment/venv/bin/python"
    subprocess.run([str(python), str(HERE / "prepare_inputs.py"),
                    "--work", str(work), "--inputs", args.inputs], check=True)
    save(work / "prepared.json", {"julia": julia, "julia_version": "1.12.1",
         "source_manifest_sha256": study.sha(HERE / "source_manifest.json"),
         "environment_sha256": study.sha(work / "environment/ready.json"),
         "inputs": args.inputs, "reused_julia_dependencies": args.reuse_julia_dependencies,
         "external_environment": str(args.reuse_environment) if args.reuse_environment else None})
    print("Prepared inputs and pinned implementations in", work, flush=True)


def run_measurements(args, stage):
    verify()
    configure(args)
    work = args.work
    prepared = work / "prepared.json"
    if not prepared.exists():
        raise RuntimeError("Run prepare first; use --inputs smoke for the small verification cases.")
    if stage == "formal":
        gate = work / "smoke_run/verification.json"
        if not gate.exists() or read(gate).get("independent_oracle") is not True:
            raise RuntimeError("Run smoke successfully before measure.")
        if not (work / "formal_manifest.json").exists():
            raise RuntimeError("Run prepare --inputs full before measure.")
    manifest = work / f"{stage}_manifest.json"
    data = read(manifest)
    destination = work / f"{stage}_run"
    if destination.exists():
        raise RuntimeError(f"Keep the previous result intact and choose a fresh --work directory: {destination}")
    destination.mkdir()
    scripts = destination / "harness"
    scripts.mkdir()
    for name in ("large_study.py", "large_python.py", "large_outputs.py", "large_julia.jl", "large_analyze.py", "protocol.py", "run.py"):
        shutil.copy2(HARNESS / name, scripts / name)
    save(destination / "binding.json", {
        **study.binding(work), "manifest_sha256": study.sha(manifest),
        "harness": {p.name: study.sha(p) for p in scripts.iterdir()},
        "adapter_sha256": study.sha(Path(__file__)),
        "host": {"uname": list(os.uname()), "logical_cpus": os.cpu_count(),
                 "cpu": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),
                 "meminfo": Path("/proc/meminfo").read_text()},
        "configuration": {"julia": study.JULIA, "depot": study.DEPOT, "limits": study.LIMITS},
    })
    started = time.monotonic()
    for pass_id in range(1, data["passes"] + 1):
        for index, case in enumerate(data["cases"]):
            tools = ("tamerop", "cubicalripser") if (pass_id + index) % 2 else ("cubicalripser", "tamerop")
            for tool in tools:
                result = study.launch(work, destination / f"p{pass_id}" / (case["id"] + "_" + tool),
                                      case, tool, data["samples"], started)
                if not result["complete"]:
                    raise RuntimeError(f"Incomplete worker retained: {case['id']} / {tool}")
    study.verify(work, stage)
    verification = read(destination / "verification.json")
    if verification["verified"] != verification["total"]:
        raise RuntimeError("The two implementations did not return matching complete barcodes.")
    if stage == "smoke":
        # A separate tensor-cell/rank oracle checks the small mathematical answers.
        from mathematics import expected
        from collections import Counter
        for case in data["cases"]:
            raw = gzip.decompress((work / case["input"]).read_bytes())
            import struct
            values = list(struct.unpack("<" + "H" * (len(raw) // 2), raw))
            answer = expected({**case, "top_only": False}, values)
            counts = Counter((d, float(b), float(e)) for d, b, e in answer["finite"])
            counts.update((d, float(b), None) for d, b in answer["essential"])
            output = read(destination / "p1" / (case["id"] + "_tamerop") / "a1.json")
            if {tuple(row[:3]): row[3] for row in output} != counts:
                raise RuntimeError(f"Independent barcode mismatch: {case['id']}")
        verification["independent_oracle"] = True
        save(destination / "verification.json", verification)
        print("Small 2D/3D vertex and top-cell barcodes match the independent rank oracle.", flush=True)
    else:
        large_analyze.analyze(work)
        print("New measurements and summary are in", work, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify", "prepare", "smoke", "measure"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--julia", default=os.environ.get("JULIA_BIN", "julia"))
    parser.add_argument("--inputs", choices=["smoke", "full"], default="full")
    parser.add_argument("--reuse-environment", type=Path,
                        help="Reuse an existing hash-verified CubicalRipser 0.0.37 Release environment")
    parser.add_argument("--reuse-julia-dependencies", action="store_true",
                        help="Load the frozen source using dependencies already present in JULIA_DEPOT_PATH")
    args = parser.parse_args()
    args.work = args.work.resolve()
    if args.action == "verify": verify()
    elif args.action == "prepare": prepare(args)
    else: run_measurements(args, "smoke" if args.action == "smoke" else "formal")


if __name__ == "__main__":
    main()
