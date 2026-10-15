# Live interaction: reproduce the measurements

This study follows browser input through a live TamerOp viewer to the committed
mathematical readout and picture. The retained evidence contains the ring,
larger image and line-restriction measurements from 12 October 2026. New runs
retain every interaction and its actual browser renderer identity.

From the benchmark repository root:

```sh
python run.py verify visual-interaction-v1
python run.py prepare visual-interaction-v1
python run.py smoke visual-interaction-v1
python run.py measure visual-interaction-v1
```

Preparation needs Linux, Julia 1.12.1, Node.js 22 with npm, and a host that supports
sandboxed Chromium and its system libraries. It installs the pinned Julia
browser environment, JavaScript lockfile and Chromium. Set
`JULIA_BIN=/path/to/julia` when needed. `PLAYWRIGHT_BROWSERS_PATH` can select an
existing Playwright browser installation; otherwise browsers are installed
under the study's ignored work directory.

The pinned Playwright 1.63.0 installation selects Chromium 153.0.8010.12, the
browser recorded in the original observations. Preparation records its revision
in `prepared.json`, and each new observation records the browser version and
renderer it actually used.
To select an installed Chromium explicitly, pass
`--chromium-executable /path/to/chrome` to `smoke` or `measure`. The run records
that executable's SHA256 and keeps Chromium's sandbox enabled.

The smoke check opens the ring viewer, sends actual slider input, verifies the
committed active cells and drawing, checks the exact filling event and linked
viewers, and closes the fixture. It retains the observed latency samples but
uses no preliminary native prewarming. A passing import or a page that merely
opens is not enough for this check.

The measurement action runs the three recorded interaction scenarios. Each
image receives one first input and twenty alternating endpoint selections;
the square module receives one first angle change and twelve new lines.
The scenario code is the recorded code, including its completion checks and
latency attachments. Focused native checks precede the measured browser
scenarios in one Julia process. Existing measurements are preserved, so use
`--work /path/to/another-run` for another series.

The new run contains `browser.json`, screenshots and traces as configured by
the scenario, `configuration.json`, and `measurements.json`. The last file
contains the accepted interaction samples and renderer information. Timing
starts at the input event and ends after the matching committed readout, a
renderer frame after input and two animation frames. Package loading and the
native prewarming occur before those timers.

## Source identity and prewarming

`source_reconstruction.json` records how the runnable snapshot was recovered.
It begins with the reported base commit and restores 116 of the 117 published
file identities exactly, including the visualization implementation, browser
fixtures, interaction scenarios and dependency lockfiles. The one unrecovered
file is `test/test_visualization_a92.jl`, a native prewarming test. Its version
from the reported base commit is included, and both the original identity and
the replacement identity remain recorded.

This makes the selected visualization and browser measurement code available
for a new run while preserving the distinction in compilation history. The
recorded development session itself performed native checks in successive
groups; the supplied driver executes its focused checks in one pass. Each new
run writes that prewarming configuration into its own provenance. Compare the
subsequent interactions and first browser use according to the recorded
configuration rather than treating the latter as process startup.

The complete runnable source reconstruction is checked by
`source_manifest.json`. The unchanged historical evidence and its original
`source_sha256.json` remain under `evidence/`; no replacement source hash is
inserted into that record. The source snapshot retains the library's MIT
license.

For local verification with already installed dependencies, preparation accepts
`--reuse-julia-dependencies` and `--reuse-node-modules /path/to/node_modules`.
The latter verifies the Playwright package versions and requires an explicit
`PLAYWRIGHT_BROWSERS_PATH`. These reuse choices are recorded in `prepared.json`;
they do not replace the default installation procedure.
