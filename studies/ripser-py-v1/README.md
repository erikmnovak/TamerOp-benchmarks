# Ripser.py: frozen comparison v1

This study compares complete Vietoris–Rips queries against Ripser.py 0.6.15.
The 31 development requests and six reserved evaluation requests reproduce
the inputs used in the [report](https://www.tamerop.com/benchmarks/ripser.html).
They include dense and sparse distances, weighted vertices, point clouds,
landmark selection and requests retaining representative cocycles.

Run these commands from the repository root on Linux with Python 3.12 and
Julia 1.12.1 installed:

```sh
python run.py verify ripser-py-v1
python run.py prepare ripser-py-v1 --julia /path/to/julia
python run.py smoke ripser-py-v1
python run.py measure ripser-py-v1
```

`prepare` creates `_work/ripser-py-v1`, installs pinned Python dependencies,
builds the unmodified Ripser.py source with its supported Robin Hood option,
instantiates the frozen Julia environment and generates the inputs. Every
input is checked against its historical SHA-256. The generated distance
matrices take about 459 MiB; they are kept in the work directory.

`smoke` computes a complete barcode and retained cocycles for a six-vertex
sphere over F₃ in both programs. The independent verifier checks the intervals,
cocycle equations, nontriviality and represented class spaces. It runs one
process pass and one accepted sample after warmup.

`measure` uses the original four process passes and three samples per request.
A smaller new campaign can select requests and passes:

```sh
python run.py measure ripser-py-v1 --work _work/rips-small \
  --ids dense_circle1024_f2,dense_planar512_f101 --passes 1,2
```

Prepare that same work directory before measuring it. Results go into its
`measure/runs/` directory, and `measure/verification.json` records the independent
checks. Repeating the same command resumes completed case/process checkpoints.
A changed request list needs a fresh work directory.

The primary timer covers the complete query from a native input. Construction
is timed separately; construction plus query is the sum of those two stages
for each sample. Loading, compilation, output export and verification are
outside those timers. The worker retains requested cocycles inside the query
and discards prior mathematical answers before every new computation.

The exact original workers and verifier are in `historical/`. Preparation
makes a working copy whose supervisor uses the selected executable, Python
environment, permitted CPU and Julia depot. `portability.json` records these
changes and hashes; the timed workers are unchanged. The pinned library source
is shared with the C++ study in `sources/ripser-v1`.

The source build downloads Ripser.py 0.6.15 and Robin Hood hashing 3.11.5 from
their official distributions and verifies the archived source hashes. It records
the newly built extension's hash, since machine-specific binary hashes change
when a compiler or environment changes. `--python` is reserved for an existing
environment whose extension matches the original recorded binary and whose
NumPy, SciPy and Ripser versions match the pinned versions. `--skip-instantiate`
uses an already prepared Julia dependency environment. The normal commands
above prepare both environments explicitly.

`evidence/` contains the sealed published observations and checksums. New
measurements remain separate from that evidence, and development/evaluation
populations retain their original identities. The source and worker hashes
can be checked offline with `verify` before preparing dependencies.
