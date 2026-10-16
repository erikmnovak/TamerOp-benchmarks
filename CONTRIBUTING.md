# Contributing a benchmark

Measurements from another computer, a useful comparison and improvements to
the reproduction tools all help us understand how TamerOp behaves in practice.
Use the shared [TamerOp issue tracker](https://github.com/erikmnovak/TamerOp.jl/issues)
to propose work or report a problem, and
[Discussions](https://github.com/erikmnovak/TamerOp.jl/discussions) for questions
about methods and results. Include the study name and the command you ran when
reporting a reproduction problem.

For changes to this repository, fork it, create a branch and open a pull request
here. Link the central issue when there is one. Discuss a substantial new study
before investing in a full measurement campaign; a small correction can come
directly as a pull request.

## Run an existing study on your computer

Follow the selected [study's instructions](README.md#choose-a-comparison),
starting with `verify`, `prepare` and `smoke`. The small computation in `smoke`
checks the mathematical answer before you spend time measuring the full study.
The [reproduction tutorial](https://www.tamerop.com/recipes/reproduce_benchmarks.html)
walks through the same process.

When sharing a run, include:

- The benchmark repository revision, selected study and exact commands.
- Software versions, source and build identities, and the CPU, memory and
  operating system used. Include thread settings and relevant background load.
- The generated inputs or their recorded recipes and hashes, answer checks,
  individual observations and run logs, including failures and interrupted runs.
- The generated configuration and integrity records, so the observations can
  be traced to the code and inputs that produced them.

Keep your run separate from the published evidence. The drivers write new
results under `_work/`; attach an archive to the issue or link a durable public
location, and include its SHA-256 checksum. Check the archive for credentials,
private paths and unrelated files before sharing it. A result that is slower
than the published result is useful too. Tell us what changed, if you know,
and keep the recorded observations intact.

## Propose a comparison

Begin with the mathematical question both programs should answer. Describe the
inputs, field, conventions and complete requested output, then identify the
supported public calls you would use. A short example with independently
checked answers is a good starting point. The [protocol](PROTOCOL.md) explains
how to choose a finite suite, set its measurement limits and preserve the
evidence; use its relevant sections as the design develops.

Measure equivalent work, keep competitor implementations unchanged and retain
unfavorable or incomplete outcomes. A new study should use the repository's
`verify`, `prepare`, `smoke` and `measure` commands and run without a private
checkout. Include licenses and citations for reused code, inputs and methods.

For a tool change, describe the problem and test the affected command on a
small case. A change to mathematical validation needs a known answer or an
independent check. Rewriting instructions does not require a new timing campaign.

## Review and related projects

Erik Novak reviews proposals, agrees the comparison's scope and integrates
accepted work. He may help adapt the procedure or report while preserving your
credit. You can submit evidence and an explanation without formatting a complete
website report; Erik handles its final presentation.

Library changes follow the [TamerOp.jl contribution guide](https://github.com/erikmnovak/TamerOp.jl/blob/main/CONTRIBUTING.md).
Lessons and report presentation follow the
[website contribution guide](https://github.com/erikmnovak/TamerOp-site/blob/main/CONTRIBUTING.md).
If you are interested in becoming a maintainer, email
[erikmendesnovak@gmail.com](mailto:erikmendesnovak@gmail.com).
