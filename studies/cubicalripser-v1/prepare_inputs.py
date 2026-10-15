"""Recreate the recorded scalar arrays using the pinned NumPy environment."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "harness/cubicalripser"))
from large_study import case, generate, save, LIMITS


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--inputs", choices=["smoke", "full"], required=True)
    args = p.parse_args()
    if np.__version__ != "2.5.3":
        raise RuntimeError("Input reconstruction requires the recorded NumPy 2.5.3 generator.")
    cases = [generate(args.work, case(d, convention, "noise", [4, 5] if d == 2 else [4, 5, 3],
                                     "smoke", 20261020))
             for d in (2, 3) for convention in ("V", "T")]
    save(args.work / "smoke_manifest.json", {"cases": cases, "samples": 1, "passes": 1, "limits": LIMITS})
    if args.inputs == "full":
        recorded = json.loads((HERE / "evidence/formal_manifest.json").read_text())
        rebuilt = []
        for original in recorded["cases"]:
            entry = {key: original[key] for key in ("id", "shape", "convention", "pattern", "level", "seed", "order", "reserved")}
            generated = generate(args.work, entry)
            if generated["raw_sha256"] != original["raw_sha256"]:
                raise RuntimeError(f"Generated values differ from the recorded input: {entry['id']}")
            rebuilt.append(generated)
        save(args.work / "formal_manifest.json", {**recorded, "cases": rebuilt})
    print("Generated input values and verified the recorded full-array hashes." if args.inputs == "full" else "Generated four small oracle-check inputs.")


if __name__ == "__main__":
    main()
