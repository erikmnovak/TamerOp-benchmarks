# Cubical barcodes: reproduce the comparison

This study computes complete ordinary barcodes from the same scalar arrays in
TamerOp and CubicalRipser 0.0.37. The retained evidence is the 11 October 2026
comparison. New runs write their inputs, checks and measurements under `_work/`.

Run these commands from the benchmark repository root:

```sh
python run.py verify cubicalripser-v1
python run.py prepare cubicalripser-v1
python run.py smoke cubicalripser-v1
python run.py measure cubicalripser-v1
```

Preparation needs Linux, Python 3.12, Julia 1.12.1, a C++ compiler, `taskset`
(from util-linux), `gzip`, and network access for the pinned dependencies.
Set `JULIA_BIN=/path/to/julia` if Julia is not on the command path. Use
`JULIA_DEPOT_PATH` for a separately prepared Julia dependency directory.

`prepare` builds the unmodified CubicalRipser source archive identified in
`evidence/build.json`, using its Release configuration and pinned Python build
dependencies. The adapter takes the release number, download address and SHA256
from that record. The preserved preparation helper's older default constants
are overridden before any download or build. TamerOp's 225 measured source
files are retained in `sources/cubicalripser-v1/`; `source_manifest.json`
checks them byte for byte. The binary cubical lookup table is package data and
is included in that source snapshot. Each snapshot retains the library's MIT
license.

The full input preparation regenerates the 48 declared requests with the
recorded NumPy 2.5.3 generator. It checks the SHA256 of the uncompressed array
values against `evidence/formal_manifest.json`. Compression can differ between
zlib versions while those values remain identical; each new compressed file
receives its own checksum. The largest arrays contain tens of millions of
values, so preparing the full study needs disk space for the input files.

For a small installation check, prepare only the smoke inputs:

```sh
python run.py prepare cubicalripser-v1 --inputs smoke
python run.py smoke cubicalripser-v1
```

These four small arrays exercise vertex and top-cell input in two and three
dimensions. The tools must return identical complete interval multisets, and
an independent calculation using ranks of cellular boundary maps must give
the same answer. The smoke run retains both tools' native output and verification
records. Run `prepare --inputs full` afterward to generate the formal inputs.

`measure` requires a successful smoke result. It uses the preserved public-call
workers, three fresh process passes and three accepted samples per request and
tool, with alternating tool order. Every call starts from a loaded array and
recomputes the mathematical result after warmup. The supervisor pins workers
to one available logical CPU, uses one numerical thread, and applies the
recorded memory and duration limits. An incomplete worker remains a failure;
its partial timings do not enter the summary.

The new `analysis.json`, `samples.json`, `results.csv`, process logs, input
hashes and verification records appear in the selected work directory. Use
`--work /path/to/new-study` for another independent run. Existing result
directories are preserved rather than overwritten. New timing values describe
the reader's machine and its observed background activity.

An existing pinned environment can be reused with
`--reuse-environment /path/to/environment`. The adapter checks its version,
Release-build record and recorded extension/binary hashes, then links it only
inside the ignored work directory. This option supports local verification;
the default preparation downloads and builds from the public source pins.

The `harness/` files preserve the original query, array-generation, interval
canonicalization, resource-monitoring and analysis code. `driver.py` supplies
portable paths, a common command interface, fixed-input reconstruction and the
small independent-oracle gate. The original qualification outcomes, including
singleton-axis failures outside the timed scope, remain in `evidence/`.

For a local check with already installed Julia dependencies,
`--reuse-julia-dependencies` loads the frozen package using the study's existing
package-image mode. It does not install or update dependencies and records that
choice in `prepared.json`.
