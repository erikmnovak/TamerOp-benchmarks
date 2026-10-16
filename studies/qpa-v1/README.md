# Finite module algebra with QPA

This study reproduces the 220 requests in the
[QPA report](https://www.tamerop.com/benchmarks/qpa.html), using the measured
TamerOp snapshot and the original mathematical adapters and exact validators.
The 200 completed comparisons and QPA's 20 tensor evaluation failures remain
separate outcomes. A failed request receives no speed ratio.

## Scientific scope

The fixed suite has 184 development requests and 36 requests reserved before
the candidate freeze, over QQ, F₂, F₃ and F₁₀₁. It covers Hom bases, Ext
dimensions and representatives, kernels, images and cokernels, projective and
injective resolutions, pushouts and pullbacks, homology and mapping cones,
Yoneda products, induced Ext maps, and balanced tensor products with elementary
evaluations. The exact cases, requested outputs and original weights remain in
the frozen inputs and [result data](evidence/README.md).

The primary timer directly measures native construction and the complete query
from the declared prepared finite category and decoded input. Category
construction, scalar decoding, loading and compilation are outside that boundary.
Each sample starts without results from an earlier mathematical query. Outputs
are checked through bases, maps, representatives or evaluations as required by
the request, rather than dimensions alone.

Five paired process passes with three accepted samples per request preserve
the original suite weights and 10% practical margin. All 220 requests remain in
the completion denominator; the 200 matched requests account for 90% of its
original weight. The twenty QPA tensor evaluation failures include four reserved
requests. Their absence from speed aggregates does not remove them from the
study. Construction alone can have a valid timing even when the final query
fails.

The original combined allowance was 15 hours; the final campaign and initial
report used 9.46 hours of the remaining allowance. The recorded findings describe
the fixed synthetic inputs and the shared computer used for measurement.
The [archived development account](https://github.com/erikmnovak/TamerOp-site/blob/4b261c955cf31be0cb9c0e59ad5e333615795eb2/docs/benchmark_suites.md#qpa-results-and-development-record)
preserves the earlier nonmonotonic GAP pilot, interrupted attempts, accepted
small regressions and optimization decisions. The final study uses the checked
monotonic GAP build; earlier pilot observations are not pooled with confirmation.

## Reproduce the study

Run commands from the benchmark repository root on Linux, with Python 3.12 or
later and Julia 1.12.1 available. Preparation restores the pinned Julia
environment and builds GAP 4.16.1 with QPA 1.37 from the pinned sources:

```sh
python run.py verify qpa-v1
python run.py prepare qpa-v1 --julia /path/to/julia
python run.py smoke qpa-v1
python run.py measure qpa-v1
```

Building GAP needs `gcc`, `g++`, `make` and Git. Installing the GMP and zlib
development headers avoids building bundled copies of these libraries; on
Debian or Ubuntu their packages are `libgmp-dev` and `zlib1g-dev`. The
[GAP installation guide](https://github.com/gap-system/gap/blob/v4.16.1/INSTALL.md)
gives the corresponding packages for other systems. The setup script pins
the GAP archive checksum and the QPA, GBNP and GAPDoc commits. Its compiler
setting enables GAP's monotonic timer;
the preparation step checks that clock before allowing measurements. An
existing installation can be selected with `--gap /path/to/gap` instead.

The smoke command computes a complete Hom basis for one fixed input in both
programs and checks the results independently. Measurement runs all three
parts, covering core module operations, diagrams and complexes, and derived
operations, with five paired passes and three fresh samples per request.
It keeps the original operation, worker, memory and whole-campaign limits.
Results appear in a new timestamped directory under `_work/qpa-v1/`.

`sources/qpa-v1/` contains the exact measured package files with their license
and SHA-256 manifest. `payload.json` maps the selected original harness files
and compressed inputs into the relative directory layout expected by those
unchanged scripts. Preparation builds that layout only under `_work/`; it
does not read the author's original folders. The files under `frozen/` retain
the original accepted source and input checks. The old harness README files
are retained solely because they participate in that identity.

`evidence/` contains the published original measurements. New computations
leave those files intact and record their own machine, paths and observations.
The aggregate calculations and figures can be reproduced separately through
the [website's reproduction recipe](https://www.tamerop.com/recipes/reproduce_benchmarks.html).
