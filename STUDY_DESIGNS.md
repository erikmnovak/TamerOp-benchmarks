# Qualification designs

These designs specify the mathematical questions and checks for comparisons
with PersistenceDiagrams.jl and Skyscraper-Invariant. The completed executable
studies are listed in the [README](README.md#choose-a-comparison). Use the
[protocol](PROTOCOL.md#design-a-bounded-suite) when turning a qualified comparison
into a frozen measurement study.

## PersistenceDiagrams.jl: supplied barcodes

The initial comparison uses unchanged PersistenceDiagrams.jl 0.9.10 to analyze
supplied barcodes. Both tools construct native diagrams and execute public
queries in separate Julia processes. The recorded qualification and development
pilot cover three complete requests:

1. Bottleneck distance with a complete matching, and Wasserstein distances
   with outer exponents 1 and 2 and ground norm L-infinity.
2. The first k sampled landscapes and an unnormalized sum of tents for the
   silhouette, evaluated at identical sample points.
3. Gaussian persistence images with lifetime weights and identical averages
   over each pixel's four corners. TamerOp samples the corner grid, so its query
   is charged for the required normalization and averaging.

These conventions reconcile different image and silhouette defaults. A corner
average is distinct from an exact pixel integral. PersistenceDiagrams' default
bottleneck display lists only pairs of maximal cost, so the comparison obtains
the complete matching through its public accessor. Different optimal matchings
are accepted after checking coverage, multiplicity and achieved cost.

### Fixed inputs and measurement boundaries

The initial manifest contains 37 correctness controls, 36 development requests
and nine reserved requests. Development uses nested, clustered, near-diagonal
and repeated intervals, with three sizes per request family. Distance inputs
have 16, 64 or 192 bars in the first diagram and three quarters as many in the
second. Curve inputs have 64, 512 or 4,096 bars; images have 32, 128 or 512.
Sampling resolution grows with these sizes. Reserved recipes use mixtures of
short and long bars, staircases and independent clustered instances.

Methods are warmed on separate inputs. Each timed computation discards prior
results, reconstructs native diagrams and checks its reset state. Construction
and query samples require zero recorded compilation and recompilation. Their
times and sum remain distinct, alongside allocations, retained objects and
process memory. Small assignments are verified independently, feature formulas
are checked directly, and outputs are compared across tools.

The qualification and pilot limits were 180 seconds per case including warmup,
30 minutes per tool process and 4 GiB of observed process memory. A formal study
must freeze its repetitions, total budget and machine conditions. The pilot
design allows one bounded size adjustment before that freeze, retaining adverse
cases and timeouts. The nine reserved requests belong to candidate evaluation.

### Recorded outcomes and unresolved work

The completed pilot verified 35 paired requests. TamerOp reached the 4 GiB
process limit on the nested 4,096-bar curve request in both passes.
PersistenceDiagrams was faster on every completed pair. All emitted answers
passed the declared checks and accepted samples had zero timed compilation.
Early observations were taken with other work running on the computer;
supplemental family blocks followed checks for an idle machine. The recorded
next scientific work was to investigate TamerOp's major query and allocation
costs before candidate freeze and reserved evaluation.

Qualification also exposed an asymmetric empty-input failure in
PersistenceDiagrams.jl 0.9.10. An empty first diagram against a nonempty second
diagram returned zero for bottleneck and Wasserstein requests; reversing the
arguments gave the expected nonzero answers. With an empty first diagram and
one essential bar, Wasserstein again failed while bottleneck correctly returned
infinity. These failures receive no timing ratio. The harness must preserve
argument order and the unmodified competitor. All 45 planned performance
requests are nonempty, so qualification of that scope does not erase the
empty-input defect.

Betti curves, Wasserstein matching witnesses, entropy curves, plotting and MLJ
pipelines lie outside this initial design. Each needs a qualified common output:
a global barcode entropy differs from an entropy curve, and plotting needs a
defined display result. Close the frozen study after the declared optimization,
evaluation and evidence requirements, preserving favorable and unfavorable
outcomes. The [original pilot record](https://github.com/erikmnovak/TamerOp-site/blob/4b261c955cf31be0cb9c0e59ad5e333615795eb2/docs/benchmark_suites.md#persistencediagramsjl-c16-harness-and-initial-charter)
preserves the earlier account under its historical identifier C16.

## Skyscraper-Invariant: anchors and filtered landscapes

The source review of 15 October 2026 selected Jan Jendrysiak's standalone
[Skyscraper-Invariant](https://github.com/JanJend/Skyscraper-Invariant) for
qualifying the specialist comparison. The inspected revision was version 0.2.1
at [b64cd493](https://github.com/JanJend/Skyscraper-Invariant/tree/b64cd493cd1df2bee259a0bf3365206c6ce764eb).
It exposes decomposition of modules generated at an anchor and reuse across a
grid scan. A separate multipers comparison would measure its integration of
this backend; it would not provide independent algorithmic evidence.

Here an anchor is the chosen parameter from which the invariant is computed.
The output describes the factors in the Harder–Narasimhan filtration, an
ordered sequence of submodules determined by a stability function. Their slopes
and multiplicities determine the filtered ranks to compare. The following
requests define the candidate overlap:

| Request | Common answer and required checks |
| --- | --- |
| One anchor | Factor slopes, multiplicities and filtered ranks for the same module and anchor, recovered from each tool's native output |
| A batch of anchors | Complete output on a fixed common grid, including construction and decomposition; allow the upstream smart scan and TamerOp's preparation within the request |
| Filtered landscapes | Values for the same thresholds, layers, points, direction and radius convention, checked with an independent small oracle and declared tolerance |
| Chambers and subsequent queries | Equivalent working chamber computation through the pinned public interface, with preparation, new queries and their declared batch measured separately |

### Inputs, equivalence and timing

Start with two parameter modules over F₂ and uniform area. Fix a common finite
support window and reconcile normalized area with TamerOp's density convention.
Anchors must have identical coordinates; a stored grid value is not a query at
an arbitrary anchor. Check slope ties, support boundaries, strata of dimension
zero and threshold inclusion. Integer ranks and multiplicities must agree
exactly. Declare numerical tolerances for upstream slopes and landscape values;
TamerOp's rational chambers and landscape enclosures also need independent checks.

Use supplied presentations and modules from representative bifiltrations.
Include direct sums of many thin pieces, thicker induced indecomposables, and
repeated anchors within and across structural cells. Record presentation and
encoding sizes, vector space dimensions, induced summand dimensions, coefficient
sizes and output sizes. Freeze an affordable calibration ladder, final sizes,
reserved cases, repetitions and time and memory limits before confirmation.
Complete computations taking seconds or longer, where feasible, test whether
decomposition and reuse repay their preparation costs.

The primary timer includes conversion from equivalent starting information,
encoding or presentation construction, decomposition and the requested answer.
Native input queries are a separate measurement when preparation differs.
Keep compiled computation with fresh mathematical state, prepared queries and
process startup through the first answer distinct. Allow reuse inside a request
and reset between independent requests. Local decomposition and reuse across
anchors are hypotheses to investigate; earlier internal route measurements do
not establish a speed advantage over this comparator.

### Source qualification

Pin the upstream revision, AIDA, Persistence-Algebra, CGAL and build settings
when freezing the study. Keep upstream algorithms unchanged and recheck supported
interfaces. In the inspected revision, the main program parses `--subdivision`
without passing it to the computation, and the smart scan's subdivision
construction call is disabled. The flag therefore did not establish a working
complete chamber interface. CGAL's exact arrangement constructions also receive
coefficients computed in floating point; account for that in the comparison.

The [companion quiver implementation](https://github.com/marcf-ox/sky-inv-quiv)
could support a separate design for general Harder–Narasimhan computation and
other fields. Arbitrary finite posets, non-Cartesian encodings, nonuniform
densities, additional fields and retained algebraic witnesses remain capability
questions until a matching executable request is established. The
[original source review](https://github.com/erikmnovak/TamerOp-site/blob/4b261c955cf31be0cb9c0e59ad5e333615795eb2/docs/benchmark_suites.md#skyscraper-invariant-c23-planned-scope)
records this design under its historical identifier C23; it contains no
comparative measurements.
