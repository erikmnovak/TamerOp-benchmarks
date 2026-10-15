# Q6–Q7: maps, diagrams and complexes

Once a finite encoding retains the module's maps, we can ask how modules fit
together. A pushout joins two targets along a common source; a pullback finds
pairs with the same image. A complex asks which vectors survive a differential
without coming from the preceding one. These requests exercise the maps that
a table of dimensions alone would lose.

This harness uses **80 already allocated tasks**: 20 pushouts, 20 pullbacks,
20 homology requests and 20 cones. It adds no sizes or scored cases. Inputs are
finite-poset modules, equivalently modules over the specified incidence
algebra. These checks make no claim of invariance under changing an encoding.

| Request | TamerOp | Unmodified QPA | Requested output |
| --- | --- | --- | --- |
| Pushout | `AbelianCategories.pushout` | `PushOut` | Module and both canonical maps |
| Pullback | `AbelianCategories.pullback` | `PullBack` | Module and both canonical maps |
| Homology | `ModuleComplexes.cohomology_module_data` | `HomologyOfComplex` | Modules, with structure maps, in degrees 0, 1, 2 |
| Cone | `ModuleComplexes.mapping_cone` | `MappingCone` | Four terms and three differentials, including structure maps |

QPA's homology call returns only the homology module. Outside its timer, the
validator obtains cycle and quotient witnesses using the same public kernel,
image, lifting and cokernel operations used by that call. It checks that the
witness quotient is in exactly the returned module's coordinates. TamerOp's
native routine already returns those witnesses. No witness work is reused by
another timed sample. Output conversion and independent proofs are untimed;
all requested native terms and differentials are materialized inside timers.

## Inputs and independent checks

The existing base pairs supply presentations, nonsplit extensions, intervals,
projective/injective controls and coefficient-size cases. Q6 reuses the
presentation relation map or the certified nonsplit map where available. Its
second map is a deterministic linear combination from an independently solved
Hom space. Controls can have zero maps; 16/20 inputs in each variant have a
nonzero first map, and 15 pushouts and 12 pullbacks also have a nonzero second
map. These choices precede timing.

For Q7, write the selected map as `h: A → B` and independently construct
`q: B → E = coker(h)`. The source complex is
`A → B ⊕ N → E`, with differentials `(h,0)` and `(q,0)`.
It has `ker(h)` in degree 0 and the original `N` in degree 1 as homology.
For a cone, the target replaces `N` with `M`; the supplied cochain map has
identity components on `A`, `B`, and `E`, and an independently constructed map
`N → M` on the additional summand. This gives nonzero differentials and
surviving classes while retaining the original module structures and exact
rational coefficients. Each variant has 16/20 nonzero first differentials and
19/20 nonzero second differentials. These are bounded synthetic examples,
not a survey of arbitrary long complexes.

`diagrams.py` independently checks every relation and map. Universal properties
are certified by the block map `(f,-g)`, exact ranks, and commuting squares;
explicit invertible natural maps compare the two native constructions.
Homology checks prove that cycles are the full kernel and that the quotient
kills exactly the boundaries, then compare the homology structure maps through
an explicit isomorphism. Wrong dimensions alone cannot conceal a bad map.

Cochain degree `t` is QPA homological degree `n = -t`. TamerOp orders a cone
term as `D^t ⊕ C^(t+1)` and uses the block differential
`[d_D, u; 0, -d_C]`. QPA orders it as `C^(t+1) ⊕ D^t` and uses
`[-d_C, 0; -u, d_D]`. The comparison checks the exact chain isomorphism
`(d,c) ↦ (-c,d)`, including odd characteristic. Neither native convention is
changed, and equality up to an unspecified sign is never accepted.

## Reproduction

Follow [the benchmarking manual](../../docs/benchmarking.md) and
[the suite allocation](../qpa_suite/README.md). `generate.py` reads only existing
coverage rows and certified base pairs. The complete suite generator also
materializes this subset automatically.

```sh
python3 benchmark/qpa_core/generate.py --workflows Q6,Q7 \
  --output audit/2026-09-27/qpa_suite_v1/diagrams
python3 benchmark/qpa_core/run.py \
  --fixtures audit/2026-09-27/qpa_suite_v1/diagrams/fixtures.json \
  --output /tmp/qpa-diagram-correctness \
  --julia "$JULIA" --gap "$GAP" --mode correctness --correctness-compile yes
```

Use `test_diagrams.py` with `--fixtures`, the worker JSONL files under
`--answers`, and `--output` to exercise deliberate corruptions. Tests preserve
stalk dimensions while breaking maps or signs, as well as checking missing
homology degrees.

All three timed phases use independently verified resets. Native construction
includes modules, supplied maps, complexes and the cochain map where present.
QPA creates a fresh incidence category per request; Julia clears the audited
factor/plan caches and checks weak references to previous owners, including
complexes and homology data. Ordinary reuse within the request remains allowed.
Julia samples with compilation or recompilation are rejected. The inherited
60-second operation, 900-second worker and 4096-MiB RSS caps apply. Reserved
inputs can be checked without measurements; timing them requires confirmation
mode and a reviewed frozen candidate. Qualification is not confirmation.
