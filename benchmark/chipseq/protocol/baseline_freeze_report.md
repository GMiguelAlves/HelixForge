# ChIP-seq baseline freeze report

## Freeze identity

| Field | Value |
|---|---|
| Freeze date | 2026-08-31 |
| HelixForge version | 1.0.0-rc.1 |
| Freeze type | ADMINISTRATIVE_FREEZE |
| Scientific target commit | `0829c7c154dc634ffd4e13672b95ad4fbdc5957f` |
| Administrative branch base | `2062f7695bdb16e5ca48674c474a4548c30d454e` |
| Administrative freeze commit | resolved by annotated tag after merge |
| Tag | `chipseq-benchmark-v1.0.0-rc.1` (pending post-merge) |

The scientific target identifies the tested pipeline. The later administrative
commit consolidates evidence and documentation only.

## Frozen classifications

| Arm | Classification |
|---|---|
| Synthetic Narrow | PASS_WITH_LIMITATIONS |
| Synthetic Broad | PASS_WITH_LIMITATIONS |
| Real Narrow — K562 CTCF | PASS_WITH_LIMITATIONS |
| Real Broad — K562 H3K27me3 | PASS_WITH_LIMITATIONS |
| Global ChIP-seq benchmark | PASS_WITH_LIMITATIONS |

## Administrative gates

| Gate | Status before PR | Evidence |
|---|---|---|
| FOUR_REPORTS_PRESENT | PASS | four arm reports under `benchmark/chipseq/reports/` |
| RESULT_MATRIX | PASS | `results/chipseq_benchmark_matrix.tsv` |
| LIMITATION_MATRIX | PASS | `results/chipseq_limitations.tsv` |
| FINAL_REPORT | PASS | `reports/chipseq_benchmark_final_report.md` |
| SUMMARY_JSON | PASS | `results/chipseq_benchmark_summary.json` |
| PROVENANCE | PASS | freeze and artifact manifests |
| TESTS | PASS | 182 discovered; 177 passed; 5 expected skips; 0 failed |
| LINKS | PASS | local links in benchmark and directly related documentation |
| MANIFESTS | PASS | JSON syntax, required fields and artifact inventory |
| CHECKSUMS | PASS | 25 retained entries; 3 historical absolute scratch entries recorded but not re-resolved |
| HEAVY_FILE_AUDIT | PASS | no tracked file above 10 MB and no forbidden scientific raw-data extension |
| GIT_HYGIENE | PENDING_COMMIT | unrelated local `ui-prototype/` excluded |
| CI | PENDING_PR | checked once after PR creation |

## Validation record

This section is updated from lightweight administrative checks only; no
scientific process is rerun.

- Global tests: 182 discovered, 177 passed, 5 expected skips, 0 failures.
- Nextflow lint: 130 files checked, 0 errors and 0 warnings.
- JSON syntax: 34 benchmark JSON files parsed successfully.
- TSV consistency: all three consolidated matrices have consistent columns.
- Local links: passed for the benchmark tree and directly related documents.
- Historical checksums: 25 relative entries validated; 3 absolute scratch
  entries retained as historical records and not treated as portable inputs.
- Benchmark script syntax: 40 Python and 40 shell scripts parsed successfully.
- Heavy-file audit: 237 staged benchmark files, approximately 6.2 MB; no file
  above 10 MB or 50 MB, no FASTQ/BAM/CRAM/BigWig/archive payload.
- Secrets audit: no credential pattern detected. Machine-specific paths occur
  in 51 declared audit/runtime artifacts and examples, not portable inputs.
- Artifact manifest: 237 entries; the manifest and validation report exclude
  their own checksums to avoid a self-referential cycle.

## Deferred follow-up

- RN3 is `NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS` and its methods
  follow-up is deferred. It blocks neither baseline freeze nor v1.0.0-rc.1.
- Synthetic broad fragmentation remains a post-v1 methods question.
- Real broad external BigWig concordance remains an optional descriptive task.

## Current administrative state

```text
CHIPSEQ_BENCHMARK_DESIGN = FROZEN
CHIPSEQ_SCIENTIFIC_EXECUTION = COMPLETE
CHIPSEQ_ADMINISTRATIVE_VALIDATION = LOCAL_PASS_CI_PENDING
CHIPSEQ_BASELINE = NOT_YET_TAGGED
```
