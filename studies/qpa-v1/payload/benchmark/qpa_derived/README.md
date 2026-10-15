# Products, induced Ext maps, and balanced tensors

A finite module retains maps as well as dimensions. These benchmarks ask how
extension classes compose, how a module map changes those classes, and which
elementary tensors remain after imposing the module relations. Both tools work
in the same finite-poset category. The adapters preserve TamerOp's current API.

Read the [benchmark manual](../../docs/benchmarking.md) and
[bounded-suite guide](../../docs/benchmark_suites.md) first. These adapters now
serve Q8–Q10 inside the **single 220-case suite**. Its active 44 derived cases
comprise 12 products, 12 induced maps and 20 tensors. See the
[integration guide](../qpa_suite/README.md) for allocation, reserved-input guards
and exact regeneration commands. The original 48-case qualification remains
historical evidence: 32 inputs are retained in the suite and 16 supplementary.
The other still-pending core adapters remain separate implementation work.

The [qualification report](../../audit/2026-09-27/qpa_suite_v1/derived/README.md)
records 32 exactly matched product/map cases, 16 verified TamerOp tensor cases,
and QPA errors evaluating its tensor map in those 16 cases. The full development
run and a bounded recheck of corrected timing boundaries are archived. These
results qualify the adapters; the five-pass timing campaign has not run.

## Requests and fixed inputs

| Task | Starting input | Completed answer |
| --- | --- | --- |
| Q8: Yoneda products | Three modules L, M, N | Native Ext bases and the complete Ext¹(M,N) × Ext¹(L,M) → Ext²(L,N) product table in target coordinates |
| Q9: induced Ext maps | L, L′, N, N′ and supplied f:L′→L, g:N→N′ | Induced maps in both arguments in degrees 1 and 2, with native bases |
| Q10: balanced tensor | Right module R and left module L | Dimension and coordinates of every vertex elementary tensor in R ⊗ L |

In the historical qualification, each task has 16 cases: the Boolean three-cube and 4×4 grid, QQ/F₂/F₃/F₁₀₁,
and two fixed sizes or module families. Q8 uses unequal semisimple modules on a
square face, with both nonzero and zero products. Q9 uses rectangular,
nonidentity maps, with ranks computed in the actual field. Q10 uses
projective-presentation and interval families with nonzero structure maps,
dualizing one input to obtain the opposite orientation. Q8 is a degree-(1,1)
comparison, not a survey of arbitrary higher products.

`generate.py` reproduces the historical 48-case JSON and GAP manifests and independently checks
Ext dimensions in each field. It refuses to overwrite different inputs. These
are development qualification cases, not unexposed evaluation cases after this
run. No fixture or weight is chosen from its observed speed.

## Supported routes

TamerOp uses `Ext`, `yoneda_product`, `ext_map_first`, `ext_map_second`, `Tor`,
and their normal representative/coordinate interfaces. The tensor adapter lifts
elementary factors through the Tor₀ resolution augmentation, then uses checked
coordinates. Those solves and evaluations are timed. It adds no production API.

QPA remains unchanged. Products use `ExtOverAlgebra`,
`LiftingMorphismFromProjective`, `MorphismOnKernel`, map composition and the
returned Ext coordinate function. QPA's own `ExtAlgebraGenerators` uses this
public-operation approach. We do not compare bare `YonedaProduct` complex
splicing with the more complete task of producing an Ext-class coordinate.
Induced maps use public lifts and pre/postcomposition, retaining successive
projective covers within the query.

Q10 calls `TensorProductOfModules` and evaluates its returned bilinear function.
QPA describes our covariant L as a right module over the opposite
incidence-algebra convention, so it receives `(L,R)`. Flipping elementary
factors identifies that result with TamerOp's `R ⊗ L`. The balancing relations
verify this identification explicitly.

The pinned release is QPA 1.37 with GAP 4.16.1. Its declarations, implementation,
manual index and loaded global names contain no public higher-Tor implementation
found in this audit. Consequently **no higher-Tor benchmark is included**.
Duality can relate Tor dimensions to Ext, but this does not constitute a QPA
higher-Tor implementation. Tensor products of algebras and torsion-theory
operations are different requests. See the local
[support audit](../../audit/2026-09-27/qpa_suite_v1/derived/qpa_support.json).

## Exact verification

`verify.py` uses independent Python exact arithmetic. It checks native
projectivity, differential compositions, augmentation, exactness in the required
range, and naturality. Explicit lifts from the normalized category-bar
resolution transport every native Ext representative to a common model.
Independence and completeness are checked modulo its boundaries. The evidence
includes invertible coordinate identifications between the two tools' bases.

The bar boundary deletes vertex i with sign (-1)^i. With the unsigned comparison
lifts for extension composition, the degree-(1,1) product has factor -1.
The validator checks this fixed sign exactly; it never accepts equality merely
up to sign. Both induced maps are checked by applying the supplied stalk
matrices directly to bar cochains.

For tensors it independently constructs the relations
`R(u≤v)(r) ⊗ l - r ⊗ L(u≤v)(l)`. Each returned evaluation matrix must annihilate
those relations, have the expected rank, and identify their quotient with the
answer. A cross-tool change of basis is constructed when both tools finish.

Exports and independent checks occur outside timing. Conversions required to
deliver the requested answer occur inside. Validation never supplies retained
mathematical results to a subsequent sample.

## Timing and failures

Each task has independently reset construction, complete-query and directly
measured construction-plus-query phases. Parsing/scalar decoding and defining
the incidence category are excluded. Julia reuses the audited global/task-local
reset inventory, verifies release of prior mathematical roots, and constructs
new inputs. GAP constructs a fresh prepared category per task, checks absence
of derived algebra tables, and constructs fresh modules without old covers,
resolutions, duals or syzygies. Native QPA input matrices are checked against the
manifest outside timing. Reuse within each computation is preserved.

Julia warms all phases and records compilation/recompilation counters. Accepted
samples require both to be zero. Rejected attempts remain in the output, with
at most three reset attempts. GAP warms its interpreter path; Julia compilation
counters are marked unavailable there. Allocated bytes and sampled process RSS
are separate measurements; neither is retained mathematical-object storage.

The runner serializes tools and reverses field/tool/case order by pass. It
records aggregate machine load without inspecting other projects. Limits are
60 seconds per non-warmup operation, 900 seconds per worker, 4096 MiB sampled
RSS and 15 campaign hours. RSS is sampled every 0.5 seconds, not enforced as an
instantaneous allocation cap. Worker and operation timeouts are distinguished.
Every raw failure and traceback is retained. Failed requests have no speed
ratio. A completed worker footer can include explicitly recorded case failures.

Qualification defaults to one pass and one sample; it verifies the harness and
is not a publishable speed campaign. Confirmation requires five paired passes
and three reset samples. No five-pass result is implied by implementing that
command. The remaining integrated-suite adapters retain their pending milestones.

## Run and reproduce

From the project root, restore the external pinned dependencies if needed:

```sh
bash audit/2026-09-27/publication_study/cross_tool/setup_gap.sh /tmp/tamerop-qpa-study
python3 benchmark/qpa_derived/generate.py --output audit/2026-09-27/qpa_suite_v1/derived
```

Then use the installed executable paths:

```sh
python3 benchmark/qpa_derived/run.py \
  --fixtures audit/2026-09-27/qpa_suite_v1/derived/fixtures.json \
  --output audit/2026-09-27/qpa_suite_v1/derived/qualification_new \
  --gap /tmp/tamerop-qpa-study/gap-4.16.1/gap \
  --julia /path/to/julia-1.12.1/bin/julia
```

Use `--fields QQ --cases Q8_cube3_QQ_r1,Q9_cube3_QQ_r1` for a small check.
For confirmation, use a fresh output directory and add
`--mode confirmation --passes 5 --samples 3`.

Each process writes JSONL answers/counters, a log, host/RSS monitoring and its
command/status record. The runner records source/input hashes and a harness
snapshot, plus shared-harness and environment dependency snapshots. Package
source, both fixture formats and shared dependencies enter the resume fingerprint.
Completed processes resume only with identical configuration;
interrupted evidence requires a new directory. Independent verification writes
`verification.json`, including failures and explicit basis transports.

For a bounded adapter recheck, `--tools QPA` or `--tools TamerOp` may be used
with `--peer-evidence` pointing to previously verified answer files. This is
qualification-only; it does not create paired timing evidence. Confirmation
requires both tools and forbids imported peers.

The validator's negative controls and the runner's time-limit checks can be
repeated separately:

```sh
python3 benchmark/qpa_derived/test_validator.py \
  --fixtures audit/2026-09-27/qpa_suite_v1/derived/fixtures.json \
  --answers audit/2026-09-27/qpa_suite_v1/derived/qualification_v1/tamerop_pass1_QQ.jsonl \
  --output /tmp/derived_negative_QQ.json
python3 benchmark/qpa_derived/test_runner.py --output /tmp/derived_runner_check_new
```

Repeat the validator test with the F3 answer file for odd-characteristic signs.
The one-vertex QPA tensor failure can be reproduced with
`gap --bare -A -q --nointeract --quitonbreak benchmark/qpa_derived/tensor_reproducer.g`.

These local `benchmark/` and `audit/` files remain ignored by Git. No commit,
push, competitor patch, or production API change is part of this work.

## Integrated-suite execution

Use `benchmark/qpa_suite/integrate.py` to regenerate the active allocation;
`generate.py` here reproduces only the historical qualification inputs.
With the integrated manifest, qualification automatically selects 36 development
cases and rejects explicitly requested reserved cases. The eight evaluation
cases may be checked using `--mode correctness`, which records exact answers
and failures without timing or allocation/RSS measurements. There is no warmup
loop in correctness mode. Resource ceilings are still enforced.

Confirmation requires five passes, three samples, both tools, and a candidate
record matching source, dependencies, harness and fixture hashes after the
optimization stopping condition is met. Never use correctness output as speed
evidence. Failures retain their tracebacks and receive no speed ratio.
