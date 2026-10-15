"""Summarize only verified zero-compilation measurements; keep failures visible."""
import argparse
import json
import math
import statistics as stats
from pathlib import Path
from run import PHASES, check_job
from build import digest
from protocol import select_cases
from analysis import aggregate, log_ratio_summary, classify


def report(run, fixtures):
    identity = json.loads((run / "identity.json").read_text())
    manifest = json.loads((fixtures / "manifest.json").read_text())
    pilot = identity["mode"] == "pilot"
    assert identity["mode"] in ("pilot", "confirmation")
    cases = select_cases(manifest,identity['mode'],identity.get('suite','main'))
    assert digest(fixtures/'manifest.json')==identity['manifest_sha256']
    records, failures, rejected = {}, [], []
    for path in sorted(run.glob("*.status.json")):
        status = json.loads(path.read_text())
        stem = path.name.removesuffix(".status.json")
        tool = "tamerop" if stem.endswith("tamerop") else "phat"
        if status["failure"]:
            failures.append(dict(job=stem, failure=status["failure"]))
            continue
        raw = run / (stem + ".jsonl")
        assert digest(raw)==status["raw_sha256"], "raw evidence changed"
        check_job(raw, cases, True, identity["samples"])
        data = []
        with raw.open() as stream:
            for line in stream:
                row = json.loads(line)
                if row.get('kind') in ('measurement','compile_rejected'):
                    data.append({k:v for k,v in row.items() if k != 'answer'})
        for row in data:
            if row.get("kind") == "compile_rejected":
                rejected.append(dict(job=stem, case=row["case"], phase=row["phase"],
                                     seconds=row["seconds"], compile_seconds=row["compile_seconds"]))
        for id in cases:
            for phase in PHASES:
                values = [r for r in data if r.get("case") == id and r.get("phase") == phase
                          and r.get("kind") == "measurement"]
                records.setdefault((id, phase, tool), []).append(dict(pass_id=int(stem.split("_")[0][4:]),
                    job=stem, seconds=stats.median(r["seconds"] for r in values),
                    allocation_bytes=stats.median(r["allocation_bytes"] for r in values)
                    if tool == "tamerop" else None))
    summary = []
    for id, case in cases.items():
        for phase in PHASES:
            t, p = records.get((id, phase, "tamerop"), []), records.get((id, phase, "phat"), [])
            if len(t) != identity["passes"] or len(p) != identity["passes"]:
                continue
            # Pair process-pass medians, then summarize their ratios. Each
            # fixture contributes equally within each equally weighted family.
            t=sorted(t,key=lambda r:r['pass_id']);p=sorted(p,key=lambda r:r['pass_id'])
            assert [r['pass_id'] for r in t]==[r['pass_id'] for r in p]==list(range(1,identity['passes']+1))
            ratios = [q["seconds"] / a["seconds"] for a, q in zip(t, p)]
            summary.append(dict(case=id, family=case["family"], phase=phase, cells=case["cells"],
                nonzeros=case["nonzeros"], bars=case["output_bars"],
                tamerop_seconds=stats.median(r["seconds"] for r in t),
                phat_seconds=stats.median(r["seconds"] for r in p),
                phat_over_tamerop=math.exp(stats.mean(math.log(x) for x in ratios)),
                pass_ratios=ratios,uncertainty=log_ratio_summary(ratios),classification=classify(math.exp(stats.mean(math.log(x) for x in ratios))), tamerop_allocation_bytes=stats.median(r["allocation_bytes"] for r in t)))
    result = dict(mode=identity["mode"], complete=(run / "COMPLETE.json").exists(),
                  suite=identity.get('suite','main'),failures=failures, compile_rejected=rejected,
                  comparisons=summary,coverage=aggregate(summary,cases,identity['passes']))
    (run / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    text = ["# PHAT development pilot" if pilot else "# PHAT confirmation", "",
            "These measurements start from decoded filtered boundary data over F₂. "
            "The answer includes every finite nonempty interval and every essential birth, in every supplied degree.", "",
            "Two fresh process passes per tool; three accepted reset samples per phase and case. "
            "Development evidence only; this is not the reserved evaluation or a final suite claim." if pilot else
            "Five fresh process passes per tool; three accepted reset samples per phase and case.", "",
            f"Completion marker: {result['complete']}. Failed jobs: {len(failures)}. "
            f"Compilation-contaminated measurement attempts rejected: {len(rejected)}.", "",
            "Primary measure: native construction plus complete barcode query, timed together. "
            "PHAT/TamerOp below 1 means PHAT was faster.", "",
            "| Case | Cells | Boundary entries | Output bars | TamerOp (ms) | PHAT (ms) | PHAT/TamerOp |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in summary:
        if row["phase"] == "combined":
            text.append(f"| {row['case']} | {row['cells']} | {row['nonzeros']} | {row['bars']} | "
                        f"{row['tamerop_seconds']*1000:.4f} | {row['phat_seconds']*1000:.4f} | {row['phat_over_tamerop']:.3f} |")
    text += ["", "`summary.json` also contains construction-only and query-only results, paired-pass ratios, "
             "and Julia allocations. Raw JSONL retains warmups and rejected attempts. "
             "Per-worker status records sampled peak process RSS; it includes the runtime and compilation. "
             "It is not retained mathematical storage. PHAT allocation/retained-byte measurements are unavailable, "
             "rather than recorded as zero. Julia retained-input and retained-answer sizes are separate raw fields.", ""]
    coverage=result['coverage']
    text += ["", "## Fixed-suite coverage and uncertainty", "",
             f"Eligible primary ratios: {coverage['eligible_cases']}/{coverage['fixed_cases']}. "
             "V2 is one fixed population; no earlier timing samples enter this score.", "",
             "The 95% intervals use paired process-block log ratios; they describe execution "
             "variation on these synthetic inputs, not the probability of winning on arbitrary inputs.", "",
             "| Family | Practical wins | Near ties | Losses | Unresolved | Ratio (95% interval) |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    for family,data in coverage['families'].items():
        c=data['counts'];timing=data.get('timing')
        timing_text='unresolved' if timing is None else f"{timing['ratio']:.3f} ({timing['ci95'][0]:.3f}–{timing['ci95'][1]:.3f})"
        text.append(f"| {family} | {c['win']} | {c['near_tie']} | {c['loss']} | {c['unresolved']} | {timing_text} |")
    if coverage['aggregate'] is not None:
        x=coverage['aggregate'];text += ["", f"Balanced ratio: {x['ratio']:.3f}; 95% interval {x['ci95'][0]:.3f}–{x['ci95'][1]:.3f}. "
            f"Broad 'generally faster' gate passed: {coverage['generally_faster']}. "
            "The pass ranges and equal-case sensitivity results remain in summary.json."]
    if not pilot and result['complete']:
        marker=json.loads((run/'COMPLETE.json').read_text())
        assert marker['identity_sha256']==digest(run/'identity.json')
        assert coverage['eligible_cases']==coverage['fixed_cases']
    (run / "REPORT.md").write_text("\n".join(text))
    print(run / "REPORT.md")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path); p.add_argument("fixtures", type=Path)
    args = p.parse_args(); report(args.run, args.fixtures)
