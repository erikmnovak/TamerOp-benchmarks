#!/usr/bin/env python3
"""Prepare, verify and run the versioned TamerOp benchmark studies."""
from __future__ import annotations

import argparse
import fcntl
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STUDIES = ("qpa-v1", "phat-v2", "ripser-py-v1", "ripser-cpp-v1", "cubicalripser-v1", "visual-interaction-v1")


def main() -> int:
    if (len(sys.argv) >= 3 and sys.argv[1] in ("verify", "prepare", "smoke", "measure")
            and sys.argv[2] in STUDIES and any(a in ("-h", "--help") for a in sys.argv[3:])):
        return subprocess.call([sys.executable, str(ROOT / "studies" / sys.argv[2] / "driver.py"), "--help"])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "verify", "prepare", "smoke", "measure"))
    parser.add_argument("study", nargs="?", choices=STUDIES)
    parser.add_argument("--work", type=Path, help="Study output directory (default: _work/STUDY)")
    args, extra = parser.parse_known_args()
    if args.action == "list":
        print("\n".join(STUDIES))
        return 0
    if args.study is None and args.action != "verify":
        parser.error("Choose a study; use 'python run.py list' to see their names.")
    if args.work and args.study is None:
        parser.error("--work requires one study")
    studies = (args.study,) if args.study else STUDIES
    # Keep this project's substantial computations serial. This lock neither
    # inspects nor stops processes belonging to other projects.
    (ROOT / "_work").mkdir(exist_ok=True)
    with (ROOT / "_work/run.lock").open("w") as lock:
        if args.action in ("prepare", "smoke", "measure"):
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                parser.error("Another study is running. Wait for it to finish before starting this command.")
        for study in studies:
            work = args.work.resolve() if args.work else ROOT / "_work" / study
            command = [sys.executable, str(ROOT / "studies" / study / "driver.py"),
                       args.action, "--work", str(work), *extra]
            print(f"{args.action}: {study}", flush=True)
            result = subprocess.run(command, cwd=ROOT)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
