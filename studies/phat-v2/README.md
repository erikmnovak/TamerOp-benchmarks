# Ordinary persistence with PHAT

This study recreates the 48 inputs in the
[PHAT report](https://www.tamerop.com/benchmarks/phat.html), plus eight small
controls with independently known barcodes. It uses the original TamerOp
snapshot and PHAT 1.7 with twist reduction and bit-tree pivot columns.

## Scientific scope

Both tools receive the same filtered boundary matrix over F₂ and return its
complete ordinary barcode, including essential classes and every supplied
homology degree. This request uses TamerOp's direct ordinary persistence
computation. No general finite encoding is required.

The scored population has four equally weighted families: graphs, simplicial
complexes, cubical complexes and algebraically constructed chain complexes.
Each family has four structural variants at three sizes. Variants and sizes
have equal weight within their parent group. Construction, query and directly
measured construction plus query remain separate; the last is the primary
comparison. See the [result definitions](evidence/README.md) for the per-process
statistics and fixed 10% practical margin.

The original development charter reserved ten of its 48 requests and added
eight small controls. PHAT v2 uses a separately declared distribution of
48 medium and large inputs. Its feasibility pilot retained all proposed
endpoints, with no subsequent implementation tuning, favorable selection or
weight changes. The v2 population replaces the earlier public results without
pooling their observations. A change of aggregate across populations is not a
measurement of an implementation improvement.

Independent complete barcode checks cover graph and algebraic inputs and small
controls. Larger simplicial and cubical inputs retain exact chain and filtration
checks, known terminal topology and complete cross-tool barcode agreement.
Those larger inputs do not have a separate oracle for their full barcode.
The original confirmation took 19.1 minutes after a 6.1 minute feasibility pilot,
within the approximately two hour timing allowance; generation, qualification
and report preparation were separate costs.

The [archived development record](https://github.com/erikmnovak/TamerOp-site/blob/4b261c955cf31be0cb9c0e59ad5e333615795eb2/docs/benchmark_suites.md#phat-implementation-and-development-pilot-2026-10-03)
preserves the initial PHAT advantage, changes in garbage collection policy,
rejected compression and workspace variants, and adverse or inconclusive
development measurements. Its [freeze and closure entries](https://github.com/erikmnovak/TamerOp-site/blob/4b261c955cf31be0cb9c0e59ad5e333615795eb2/docs/benchmark_suites.md#phat-candidate-freeze-2026-10-04)
distinguish the original candidate from the later v2 confirmation.

## Reproduce the study

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
