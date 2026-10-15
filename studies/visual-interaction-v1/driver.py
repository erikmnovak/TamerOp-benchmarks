"""Prepare and run the retained live-browser interaction scenarios."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "sources/visual-interaction-v1"


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source(base):
    for name, expected in read(HERE / "source_manifest.json").items():
        path = base / name
        if not path.is_file() or digest(path) != expected:
            raise RuntimeError(f"Missing or changed source file: {path}")


def verify():
    verify_source(SOURCE)
    for name, expected in read(HERE / "adapter_sha256.json").items():
        if digest(HERE / name) != expected:
            raise RuntimeError(f"Changed adapter file: {name}")
    for line in (HERE / "evidence/SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if digest(HERE / "evidence" / name) != expected:
            raise RuntimeError(f"Changed evidence file: {name}")
    print("Interaction source reconstruction and original evidence match their recorded hashes.", flush=True)


def configuration(args):
    julia = shutil.which(args.julia)
    if julia is None:
        raise RuntimeError("Julia 1.12.1 is required; supply --julia /path/to/julia.")
    version = subprocess.check_output([julia, "--startup-file=no", "-e", "print(VERSION)"], text=True)
    if version.strip() != "1.12.1":
        raise RuntimeError(f"Expected Julia 1.12.1; found {version}.")
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node is None or npm is None:
        raise RuntimeError("Install Node.js 22 and npm before preparing this study.")
    node_version = subprocess.check_output([node, "--version"], text=True).strip()
    if not node_version.startswith("v22."):
        raise RuntimeError(f"Expected Node.js 22; found {node_version}.")
    return julia, npm, node_version


def environment(args):
    env = os.environ.copy()
    env.update(JULIA_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", JULIA_NUM_PRECOMPILE_TASKS="1",
               npm_config_cache=str(args.work / "npm-cache"))
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(args.work / "chromium"))
    return env


def prepare(args):
    verify()
    julia, npm, node = configuration(args)
    args.work.mkdir(parents=True, exist_ok=True)
    candidate = args.work / "candidate"
    if not candidate.exists():
        shutil.copytree(SOURCE, candidate)
    verify_source(candidate)
    browser = candidate / "test/browser"
    env = environment(args)
    preparation = ("import TamerOp, WGLMakie, JSON3; println(\"Loaded browser dependencies and \", pathof(TamerOp))"
                   if args.reuse_julia_dependencies else
                   "using Pkg; Pkg.instantiate(); Pkg.precompile()")
    image_flags = ["--compiled-modules=existing", "--pkgimages=existing"] if args.reuse_julia_dependencies else []
    subprocess.run([julia, "--startup-file=no", *image_flags, "--project=" + str(browser), "-e", preparation], cwd=candidate,
                   env=env, check=True)
    verify_source(candidate)
    finish_browser_preparation(args, julia, npm, node, browser, env)


def playwright_core(node_modules):
    # npm can install a different top-level core for the MCP package. Resolve
    # the dependency as Playwright itself does, including its nested modules.
    expression = "process.stdout.write(require.resolve('playwright-core/package.json', {paths: [" + \
                 json.dumps(str(node_modules / "playwright")) + "]}))"
    path = Path(subprocess.check_output(["node", "-e", expression], text=True))
    if read(path)["version"] != "1.63.0":
        raise RuntimeError("Playwright must resolve playwright-core version 1.63.0.")
    return path.parent


def finish_browser_preparation(args, julia, npm, node, browser, env):
    if args.reuse_node_modules:
        supplied = args.reuse_node_modules.resolve()
        for package in ("playwright", "@playwright/test"):
            if read(supplied / package / "package.json")["version"] != "1.63.0":
                raise RuntimeError(f"The supplied {package} must be version 1.63.0.")
        target = browser / "node_modules"
        if not target.exists(): target.symlink_to(supplied, target_is_directory=True)
        elif not target.is_symlink() or target.resolve() != supplied:
            raise RuntimeError("Choose a fresh work directory to change the JavaScript dependency source.")
        if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
            raise RuntimeError("Set PLAYWRIGHT_BROWSERS_PATH to the supplied Chromium installation when reusing dependencies.")
    else:
        subprocess.run([npm, "ci"], cwd=browser, env=env, check=True)
        subprocess.run([str(browser / "node_modules/.bin/playwright"), "install", "chromium"],
                       cwd=browser, env=env, check=True)
    core = playwright_core(browser / "node_modules")
    save(args.work / "prepared.json", {"julia": julia, "node": node,
         "source_manifest_sha256": digest(HERE / "source_manifest.json"),
         "browser_manifest_sha256": digest(browser / "Manifest.toml"),
         "package_lock_sha256": digest(browser / "package-lock.json"),
         "playwright_browsers": env["PLAYWRIGHT_BROWSERS_PATH"],
         "playwright_browser_pins": read(core / "browsers.json")["browsers"],
         "reused_julia_dependencies": args.reuse_julia_dependencies,
         "reused_node_modules": str(args.reuse_node_modules) if args.reuse_node_modules else None})
    print("Prepared the reconstructed source, pinned browser packages and Chromium.", flush=True)


def samples_from_report(report):
    samples = []
    executed = 0
    def visit(suite):
        nonlocal executed
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                executed += 1
                if test.get("expectedStatus") != "passed" or not test.get("results"):
                    raise RuntimeError("A selected interaction did not execute as a passing check.")
                for result in test["results"]:
                    if result["status"] != "passed":
                        raise RuntimeError(f"Interaction failed: {spec.get('title')}")
                    for attachment in result.get("attachments", []):
                        if attachment["name"] not in ("interaction-latency.json", "slice-latency.json"):
                            continue
                        if "path" in attachment:
                            value = json.loads(Path(attachment["path"]).read_text())
                        else:
                            value = json.loads(base64.b64decode(attachment["body"]))
                        value["scenario_status"] = "passed"
                        samples.append(value)
        for child in suite.get("suites", []): visit(child)
    if report.get("errors"):
        raise RuntimeError("Browser run contains an uncaught error.")
    for suite in report.get("suites", []): visit(suite)
    return samples, executed


def collect(args, full):
    verify()
    julia, _, node = configuration(args)
    prepared = args.work / "prepared.json"
    if not prepared.exists():
        raise RuntimeError("Run prepare before smoke or measure.")
    candidate = args.work / "candidate"
    browser = candidate / "test/browser"
    verify_source(candidate)
    executable = args.chromium_executable.resolve() if args.chromium_executable else None
    if executable is not None and not executable.is_file():
        raise RuntimeError(f"The supplied Chromium executable does not exist: {executable}")
    destination = args.work / ("measurements" if full else "smoke")
    if destination.exists():
        raise RuntimeError(f"Keep the previous run intact and choose another --work directory: {destination}")
    destination.mkdir()
    env = environment(args)
    env.update(TAMEROP_JULIA=julia, TAMEROP_JULIA_PROJECT=str(browser),
               TAMEROP_BROWSER_OUTPUT=str(destination / "artifacts"),
               TAMEROP_BROWSER_INTERVAL_PORT=str(args.port),
               TAMEROP_BROWSER_SLICE_PORT=str(args.port + 1),
               TAMEROP_BROWSER_STOP_FILE=str(destination / "stop-server"))
    env["PLAYWRIGHT_BROWSERS_PATH"] = read(prepared)["playwright_browsers"]
    env.pop("TAMEROP_BROWSER_REUSE_SERVER", None)
    server = candidate / "docs/benchmarks/visual_interaction_v1/serve_after_checks.jl" if full else browser / "serve.jl"
    command = " ".join(shlex.quote(str(x)) for x in [julia, "--startup-file=no", "--compiled-modules=existing",
                "--threads=1", "--heap-size-hint=2400M", "--project=" + str(browser), server])
    config = destination / "playwright.config.mjs"
    config.write_text(
        "import original from " + json.dumps(str(browser / "playwright.config.mjs")) + ";\n"
        "export default {...original, use: {...original.use, launchOptions: {...original.use.launchOptions, ..." +
        json.dumps({"executablePath": str(executable)} if executable else {}) +
        "}}, reporter: [['json', {outputFile: " + json.dumps(str(destination / "browser.json")) +
        "}], [" + json.dumps(str(browser / "acceptance-reporter.mjs")) + "]], webServer: {...original.webServer, command: " +
        json.dumps(command) + ", reuseExistingServer: false}};\n")
    pattern = r"A123 (continuous(?:-large)? scrubbing|slice handles)" if full else r"A123 continuous scrubbing"
    save(destination / "configuration.json", {"started_unix": time.time(), "julia": julia, "node": node,
         "source_manifest_sha256": digest(HERE / "source_manifest.json"),
         "reconstruction_sha256": digest(HERE / "source_reconstruction.json"),
         "prewarming": "Focused native owner checks; A92 owner from recorded base commit" if full else "No native prewarming; bounded ring correctness check",
         "driver_sha256": digest(Path(__file__)), "server_command": command,
         "chromium_executable": str(executable) if executable else "Playwright default",
         "chromium_executable_sha256": digest(executable) if executable else None,
         "host": {"platform": platform.platform(), "logical_cpus": os.cpu_count(),
                  "cpu": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                               if line.startswith("model name")), platform.processor()),
                  "meminfo": Path("/proc/meminfo").read_text(),
                  "allowed_cpus": sorted(os.sched_getaffinity(0))},
         "threads": {"julia": 1, "blas": 1},
         "viewport": [1440, 1050], "workers": 1, "grep": pattern})
    result = subprocess.run([str(browser / "node_modules/.bin/playwright"), "test", "continuous.spec.mjs",
                             "--config", str(config), "--grep", pattern], cwd=browser, env=env)
    if result.returncode:
        raise RuntimeError(f"Browser check failed; inspect {destination / 'browser.json'}")
    samples, count = samples_from_report(read(destination / "browser.json"))
    expected = 3 if full else 1
    if len(samples) != expected or count != expected:
        raise RuntimeError(f"Expected {expected} complete interaction scenarios, obtained {count} checks and {len(samples)} samples.")
    save(destination / "measurements.json", {"schema_version": 1, "samples": samples,
         "source_reconstruction": read(HERE / "source_reconstruction.json"),
         "configuration_sha256": digest(destination / "configuration.json")})
    print("Verified live interactions and saved their new timing observations in", destination, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["verify", "prepare", "smoke", "measure"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--julia", default=os.environ.get("JULIA_BIN", "julia"))
    parser.add_argument("--port", type=int, default=8848)
    parser.add_argument("--reuse-julia-dependencies", action="store_true")
    parser.add_argument("--reuse-node-modules", type=Path)
    parser.add_argument("--chromium-executable", type=Path,
                        help="Use a supplied Chromium executable; each sample records its actual browser version")
    args = parser.parse_args()
    args.work = args.work.resolve()
    if args.action == "verify": verify()
    elif args.action == "prepare": prepare(args)
    else: collect(args, args.action == "measure")


if __name__ == "__main__": main()
