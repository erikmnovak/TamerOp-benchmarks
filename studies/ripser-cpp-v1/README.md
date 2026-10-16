# Original C++ Ripser: frozen comparison v1

This study compares complete ordinary Rips barcodes from supplied distance
files against the upstream C++ Ripser executable. It preserves the ten fixed
requests in the [report](https://www.tamerop.com/benchmarks/ripser_cpp.html):
two sizes each of circles, planar distances over two fields, spheres and
sparse spheres.

The [original scope and closure](https://github.com/erikmnovak/TamerOp-site/blob/4b261c955cf31be0cb9c0e59ad5e333615795eb2/docs/benchmark_suites.md#original-c-ripser-companion-study-2026-10-06)
retain the shared-machine conditions, two earlier memory failures and the
upstream sparse-cutoff failure. Cocycles, landmarks, weighted vertex births and
raw-cloud distance construction are outside this comparison. The executable's
printed dyadic grades are uniquely decoded before exact barcode comparison;
ratios from the separate Ripser.py study are not transferred to this one.

From the repository root on Linux, with Python 3.12, Julia 1.12.1, Git and a
C++11 compiler installed:

```sh
python run.py verify ripser-cpp-v1
python run.py prepare ripser-cpp-v1 --julia /path/to/julia
python run.py smoke ripser-cpp-v1
python run.py measure ripser-cpp-v1
```

`prepare` checks out the recorded upstream and Robin Hood commits, compiles
separate F₂ and odd-prime executables, prepares the frozen Julia environment
and generates the exact distance files. Input hashes must match the original
manifest. Generated inputs occupy about 79 MiB in `_work/ripser-cpp-v1`.
The shared frozen TamerOp source is in `sources/ripser-v1`.

`smoke` computes the full barcode of a six-vertex octahedral sphere over F₃
in both programs and compares both answers with an independent boundary
reducer. It uses one process pass and one accepted sample after warmup.

`measure` runs the ten requests with three process passes and two accepted
samples per tool after warmup. Use `--ids circle_1280_f2 --passes 1` to run a
smaller campaign in a separately prepared work directory. Results and complete
barcode exports are written under `measure/runs/`. An identical invocation
resumes verified case checkpoints. Keep different selections in different work
directories.

Both timers include input-file reading, native construction and complete
barcode output. C++ starts a new process for every call; Julia uses a fresh
worker for each case and pass, with compiled methods and
`--heap-size-hint=4G`. Queries have a 240-second limit and workers have a 6 GiB
resident-memory limit. Each invocation rebuilds its mathematical state.

The sparse files are restricted to the common radius before timing. The
separate sparse-cutoff control in `evidence/` records why this matters for the
pinned upstream executable. It remains separate from accepted speed ratios.

The original measurement supervisor, Julia worker and control tests remain
byte-for-byte in `historical/`. The working supervisor changes only executable,
CPU and depot paths; `portability.json` records those changes. The timed Julia
worker remains unchanged. A new build has its own compiler identity and binary
hashes in `machine_and_build.json`.

For an existing clean checkout at the pinned commits, `prepare` accepts
`--upstream /path/to/ripser`. `--python` selects an existing environment with
NumPy 2.5.3 and SciPy 1.18.1; `--skip-instantiate` uses an already prepared
Julia dependency environment. The default commands build and prepare the
required materials in the work directory.

The original observations in `evidence/` stay separate from new measurements.
Run `verify` to check their SHA-256 files, the frozen library source and the
original measurement workers without starting a benchmark.
