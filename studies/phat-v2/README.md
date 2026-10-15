# Ordinary persistence with PHAT

This study recreates the 48 inputs in the
[PHAT report](https://www.tamerop.com/benchmarks/phat.html), plus eight small
controls with independently known barcodes. It uses the original TamerOp
snapshot and PHAT 1.7 with twist reduction and bit-tree pivot columns.

From the benchmark repository root on Linux, with Python 3.12 or later,
Julia 1.12.1 and `g++` available, run:

```sh
python run.py verify phat-v2
python run.py prepare phat-v2 --julia /path/to/julia
python run.py smoke phat-v2
python run.py measure phat-v2
```

Preparation downloads the pinned PHAT source archive and checks its SHA-256,
builds the original C++ adapter, restores the pinned Julia environment, and
recreates the boundary inputs from their deterministic generators. Every
generated boundary file must match the original input hash. You can reuse a
downloaded archive with `--phat-archive /path/to/phat-v1.7.tar.gz`.

The smoke command computes the complete barcodes of a circle and a filled
triangle with TamerOp and PHAT's twist and standard reductions. It checks the
known answers and reset guards. The measurement command runs the original
48 scored inputs with five paired passes, two warmups and three accepted
samples per phase. Limits remain 60 seconds per operation, 900 seconds per
worker and 4 GiB sampled resident process memory. Results go into a fresh
timestamped directory under `_work/phat-v2/`.

`sources/phat-v2/` contains the exact measured package files, their license and
SHA-256 manifest. `harness/` preserves the original mathematical workers,
generators and checks. `inputs/manifest.json.gz` is the unchanged original
manifest, compressed to keep the repository small; it records every input's
hash and expected barcode. The drivers use only those selected materials,
without access to the author's original working folders.

`evidence/` contains the original published observations. New runs retain
those files and record new compiler, binary, runtime and machine identities.
The recorded source and input identities must agree with the original study;
a newly built executable receives its own hash. For reconstructing the
reported aggregates and figures from observations, follow the
[website's reproduction recipe](https://www.tamerop.com/recipes/reproduce_benchmarks.html).
