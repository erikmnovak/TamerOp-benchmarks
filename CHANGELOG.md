# Changelog

Significant changes to the benchmark studies, their evidence and reproduction
tools are recorded here. Dates identify changes in this repository; the linked
studies record the dates and software versions of their measurements.

## 2026-10-15

### Study guidance

- Consolidated the rules for selecting computations, weighting results and
  deciding when a study is complete in the [protocol](PROTOCOL.md).
  The existing studies retain their recorded measurement procedures and results.
- Preserved the mathematical comparison designs and initial findings for
  PersistenceDiagrams.jl and Skyscraper-Invariant in
  [Qualification designs](STUDY_DESIGNS.md).
- Expanded the QPA, PHAT, Ripser.py, C++ Ripser and CubicalRipser instructions with
  their study scopes and interpretation of the recorded comparisons.
- Added a short [contribution guide](CONTRIBUTING.md) for measurements from another
  computer, proposed studies and improvements to the reproduction tools. The
  three project READMEs link to one another, with shared questions and issues
  directed to TamerOp.jl.

These documentation changes are recorded in [PR #2](https://github.com/erikmnovak/TamerOp-benchmarks/pull/2).

### Initial study publication

Published the following studies' original evidence and reproduction tools in
this independent repository:

- [QPA, qpa-v1](studies/qpa-v1/README.md): maps, constructions and derived
  algebra of finite modules.
- [PHAT, phat-v2](studies/phat-v2/README.md): complete ordinary barcodes from
  supplied boundary matrices.
- [Ripser.py, ripser-py-v1](studies/ripser-py-v1/README.md): Rips persistence,
  representative cocycles and landmark selection.
- [C++ Ripser, ripser-cpp-v1](studies/ripser-cpp-v1/README.md): Rips barcodes
  from distance files.
- [CubicalRipser, cubicalripser-v1](studies/cubicalripser-v1/README.md): image
  and volume barcodes.
- [Live interaction, visual-interaction-v1](studies/visual-interaction-v1/README.md):
  time from browser input to a displayed Julia result, with the source
  reconstruction described in the study instructions.

Added common `verify`, `prepare`, `smoke` and `measure` commands, pinned source
snapshots, input recipes and integrity checks. New runs write their results
separately from the published measurements.

The [initial publication](https://github.com/erikmnovak/TamerOp-benchmarks/commit/cc389ab)
records these additions.
