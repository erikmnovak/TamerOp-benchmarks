# TamerOp benchmarks

This repository contains the executable studies behind the
[TamerOp benchmark reports](https://www.tamerop.com/benchmarks/index.html):
their inputs, native tool calls, mathematical checks and measurements.
The three projects have separate repositories and work together:

| Project | What it contains |
| --- | --- |
| [TamerOp.jl](https://github.com/erikmnovak/TamerOp.jl/blob/main/README.md) | The Julia library, examples and tests |
| [TamerOp-site](https://github.com/erikmnovak/TamerOp-site/blob/main/README.md) | Lessons, guides and benchmark reports for [tamerop.com](https://www.tamerop.com) |
| TamerOp-benchmarks | Runnable comparisons, pinned sources and measurement evidence |

## Questions and contributions

Questions about methods and results go to
[Discussions](https://github.com/erikmnovak/TamerOp.jl/discussions); report
problems and propose studies in the shared
[issue tracker](https://github.com/erikmnovak/TamerOp.jl/issues). Pull requests
for benchmark changes belong here. [Contributing](CONTRIBUTING.md) explains
how to submit measurements from your computer, propose a comparison or improve
the tools.

## Run a study

Use Python 3.12 and Julia 1.12.1 on Linux. Each study records its additional
tools and pinned versions in its own README. Run these commands from this
repository; replace `phat-v2` with another study name to use the same sequence.
Use `python run.py prepare phat-v2 --help` for that study's options.

```sh
python run.py list
python run.py verify phat-v2
python run.py prepare phat-v2
python run.py smoke phat-v2
python run.py measure phat-v2
```

`verify` checks the published files and frozen source. `prepare` creates the
study environment, retrieves the pinned comparator and generates its inputs.
`smoke` computes a small example and checks the answer. `measure` runs the
comparison, preserving individual observations and validation results.

Generated files and fresh measurements go in `_work/STUDY/`. To keep another
run separately, pass `--work /path/to/new/run`. The versioned evidence in
`studies/STUDY/evidence/` remains unchanged. Run one measurement at a time on
an otherwise idle machine; the command prevents two of this repository's
measurement processes from starting together.

## Choose a comparison

| Study | Computation |
| :--- | :--- |
| [qpa-v1](studies/qpa-v1/README.md) | Maps, constructions and derived algebra of finite modules, compared with GAP/QPA |
| [phat-v2](studies/phat-v2/README.md) | Complete ordinary barcodes from supplied boundary matrices, compared with PHAT |
| [ripser-py-v1](studies/ripser-py-v1/README.md) | Rips persistence, representative cocycles and landmark selection, compared with Ripser.py |
| [ripser-cpp-v1](studies/ripser-cpp-v1/README.md) | Rips barcodes from distance files, compared with the original C++ Ripser |
| [cubicalripser-v1](studies/cubicalripser-v1/README.md) | Image and volume barcodes, compared with CubicalRipser |
| [visual-interaction-v1](studies/visual-interaction-v1/README.md) | The time from browser input to a displayed Julia result |

The website's [reproduction recipe](https://www.tamerop.com/recipes/reproduce_benchmarks.html)
walks through the commands and explains the resulting files.
The [measurement account](https://www.tamerop.com/contributing/benchmarking.html)
explains the timing boundaries, validation and statistics.
For designing a comparison, use the [study protocol](PROTOCOL.md). The
[qualification designs](STUDY_DESIGNS.md) preserve the mathematical questions
and findings for PersistenceDiagrams.jl and Skyscraper-Invariant.

## Files and versions

Each study keeps its harness and preparation recipe under `studies/`, together
with the original result files under `evidence/`. Frozen TamerOp source snapshots
are under `sources/`; their checksums identify the measured implementation,
including changes that had not yet belonged to a public library commit.
The visual study's reconstruction record identifies its recovered measurement
code and the native prewarming test supplied from its base commit.
Comparator source is retrieved from its recorded upstream revision. New builds
record their compiler and binary identity separately from the original build.

Elapsed times will vary with the computer and its workload. The validation
checks establish whether the computation answers the same mathematical request;
the saved observations show how long it took on your machine.

The report figures and their presentation code belong to TamerOp-site. The
website publishes copies of the historical evidence so a report and its
downloads remain together. A report identifies the benchmark revision used;
changes to published inputs, methods or evidence receive a new study version
instead of replacing old data.

The [changelog](CHANGELOG.md) records new studies, corrections and significant
changes to measurement procedures or reproduction tools.
