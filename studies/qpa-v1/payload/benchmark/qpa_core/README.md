# Q1–Q7: finite-poset algebra, diagrams and complexes

This directory implements **176 existing tasks within the 220-case QPA suite**.
The Q1–Q5 subset below has 96 tasks; [Q6–Q7](DIAGRAMS.md) adds the 80 allocated
pushout, pullback, homology and cone requests. No case, field,
size endpoint, weight, or evaluation reservation is added. Read
[the measurement manual](../../docs/benchmarking.md),
[the suite guide](../qpa_suite/README.md), and
[the fixed plan](../../audit/2026-09-27/qpa_suite_v1/PLAN.md) first.

| Task | Cases | TamerOp request | Unmodified QPA request |
| --- | ---: | --- | --- |
| Q1 | 12 | `basis(Hom(M,N))` | `HomOverAlgebra(M,N)` |
| Q2 | 12 | `dim(Ext(M,N; maxdeg=1),1)` via `DerivedFunctorOptions` | Length of the basis returned by `ExtOverAlgebra(M,N)` |
| Q3 | 12 | Complete Hom maps, projective Ext through D, bases and checked coordinates | Hom maps, successive supported `ExtOverAlgebra` calls with projective-cover reuse, representatives and coordinates |
| Q4 | 20 | Kernel/inclusion, image/inclusion, cokernel/projection; solve for the map onto the image | `KernelInclusion`, `ImageProjectionInclusion`, `CoKernelProjection` |
| Q5 | 40 | 20 projective resolutions of M; 20 injective resolutions of N | `ProjectiveResolution` or `InjectiveResolution`, explicitly evaluated differentials |

The table describes requests; it does not claim identical algorithms. Q2 does
not request representative output, although either native route may construct
representatives internally. The TamerOp Q4 image factorization uses the public
field-aware full-column solver; that solve belongs inside the query timer.
Neither competitor is changed to force a particular internal representation.

Q3 and Q5 use D=3 on the Boolean three-cube, D=2 on the 4×4 grid and capped
crowns. Q5 includes terms 0 through D, all intervening differentials, and the
augmentation/coaugmentation. QPA's projective differential indices are
0,1,…,D; its injective complex indices are 0,−1,…,−D. The exported convention
is respectively P₀→X, Pₖ→Pₖ₋₁ and X→I⁰, Iᵏ⁻¹→Iᵏ. Requested term and map
accessors execute inside the timer. Exactness is checked through D−1; no
unrequested terminal vanishing or minimality is asserted.

## Supplied inputs and exact checks

`generate.py` consumes the allocated coverage rows and certified base pairs.
Q4 uses the original relation map on presentation cases, independent Hom maps
on controls, and the inclusion/projection from nonsplit sequences. The two
interval Hom spaces are zero and deliberately remain zero-map controls.
Other cases include nonzero kernels, images, and cokernels. The 64-bit rational
stress cases transport the presentation and its validation-only quotient map;
large coefficients are retained in the actual timed input. Q5 constructs only
the one module being resolved, rather than charging for an unused partner.

`verify.py` checks complete Hom spans with direct naturality equations. Ext
checks use independent category-bar cochains, and Q3 includes explicit lifts
from the bar resolution into each native resolution followed by invertible
cohomology coordinate transports. Requested checked-coordinate outputs are
recorded separately from the validation export.

For Q4, stalk ranks, naturality and commuting equations certify the kernel,
image, cokernel and image factorization. Explicit natural isomorphisms between
the two tools' universal constructions are checked. For Q5, top/socle
multiplicities certify projective/injective terms; ranks and zero composites
certify exactness. Natural chain maps in both directions lift the identity on
the original module. Bases and nonminimal resolutions need not agree entrywise.
These comparison constructions are independent Python rational/prime-field
linear algebra, outside both timers. Sparse elimination of bar differentials
uses the same canonical RREF convention as the original dense reference and
is checked against it on 256 matrices.

## Execution

`run.py` shares the existing Q8–Q10 orchestration, resource caps, resume checks,
reservation guards and compilation rejection. All three phases start from a
fresh verified reset. Category preparation and scalar parsing are excluded;
native constructors copy the inputs inside the construction phase. Normal
reuse within a complete query is retained. Output conversion and independent
validation are outside the timers. Warmup results are discarded; accepted
Julia samples require zero compilation and recompilation counters. JSON
exports copy dimension vectors so previous output records do not keep native
mathematical cache owners alive.

Regenerate the whole fixed suite rather than maintaining a second allocation:

```sh
python3 benchmark/qpa_suite/integrate.py --output /tmp/qpa-suite-reproduced
python3 benchmark/qpa_suite/verify.py --suite /tmp/qpa-suite-reproduced --negative-tests
```

Set `JULIA` and `GAP` to the installed executables. For exact checks, including
reserved cases without timing them:

```sh
python3 benchmark/qpa_core/run.py \
  --fixtures audit/2026-09-27/qpa_suite_v1/core/fixtures.json \
  --output /tmp/qpa-core-correctness \
  --julia "$JULIA" --gap "$GAP" \
  --mode correctness --correctness-compile yes
```

Correctness mode defaults to minimal compilation; `--correctness-compile yes`
allows normal compilation for larger exact checks. Neither option changes the
timing protocol. To qualify timings, prepare the package image separately,
then use `--mode qualification` and a bounded development `--cases` list.
Evaluation IDs are rejected in that mode. Confirmation requires the reviewed
frozen candidate, five passes, and three samples. No candidate has been frozen.

The shared runner retains errors and process failures. Its completion footer
means the requested worker loop ended; inspect `processes.json`, verification
counts and failure records before claiming every case passed. Superseded
adapter errors remain archived, with corrected runs identified explicitly.

[Implementation evidence](../../audit/2026-09-27/qpa_suite_v1/CORE_IMPLEMENTATION.md)
records qualification results. Q6 and Q7 remain the next 80 allocated tasks.
