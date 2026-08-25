# HelixForge RNA-seq benchmark report

## Identity

- HelixForge tag / commit:
- Protocol/config digest:
- Execution date and Slurm cluster:
- Nextflow / Java / container identities:

## Dataset and reference

- Benchmark level and case:
- Input/reference checksums:
- Sample/design/contrast:
- Depth and deterministic seed:

## Execution outcome

- Workflow status:
- Failed/retried/cached tasks:
- Missing or unexpected artifacts:

## Quantification

Report transcript- and gene-level Pearson/Spearman correlations, MAE/RMSE,
relative error by abundance stratum and zero/non-zero behavior. Label every
criterion as `RELEASE_GATE`, `SANITY_CHECK`, `EXPECTED_RANGE` or descriptive.

## Differential expression

Report confusion matrix, sensitivity, specificity, precision, F1, observed FDP,
AUROC/AUPRC, direction concordance and log2-fold-change error by effect-size bin.

## Independent reference

Report exact tool versions, numeric tolerance checks and semantic differences.
For GSE52778, publication comparisons are set/biological context only.

## Robustness and reproducibility

Summarize depth curves, clean-repeat agreement, determinism and any `-resume`
observations separately from scientific correctness.

## Performance and storage

Summarize wall time, CPU time, peak RSS, I/O, work/results sizes and scheduler
wait time. Do not compare queue wait as pipeline runtime.

## Planned figures

Use only figures that answer a declared question:

1. truth versus estimated transcript and gene abundance, stratified by truth;
2. truth versus estimated gene log2 fold change with effect-size strata;
3. precision-recall curve with prevalence baseline;
4. DEG overlap/direction for HelixForge and the independent reference;
5. abundance, fold-change and DEG stability across subsampling depths;
6. process runtime and peak memory, with scheduler wait shown separately.

## Central tables

1. dataset/reference/sample characteristics and checksums;
2. transcript- and gene-level quantification metrics;
3. DE truth-recovery/FDR/effect-direction metrics;
4. independent-reference concordance and DEG-set metrics;
5. per-process/workflow resource and storage use.

## Interpretation

- Gate failures:
- Sanity-check deviations:
- Expected-range observations:
- External blockers and limitations:
- Final classification: `PASS`, `PASS_WITH_LIMITATIONS`, `FAIL`, or `BLOCKED`.

## Audit artifacts

- Audit archive path and SHA-256:
- Scratch cleanup status:
- Reviewer notes:
