# Metrics specification

All joins use exact versioned IDs after the benchmark reference preparation.
The evaluation script reports `n_total`, `n_compared`, missing IDs and excluded
values for every metric. It rounds display values to at most four significant
digits while retaining full-precision machine-readable tables.

## Quantification against synthetic truth

Transcript and gene levels are evaluated separately.

| Family | Definition |
|---|---|
| Rank | Spearman correlation of true and estimated TPM over all selected features and over expressed features (`true TPM > 0`) |
| Linear | Pearson correlation of `log2(TPM + 1)` |
| Error | MAE and RMSE of `log2(TPM + 1)` |
| Relative error | median and IQR of `abs(estimate-truth) / max(truth, 0.1)` for expressed features |
| Bias | median signed `log2((estimate+0.1)/(truth+0.1))` |
| Count recovery | Spearman/Pearson and MAE/RMSE for `NumReads` against generated fragment counts |

Abundance strata are fixed by true gene TPM: low `(0,1)`, medium `[1,10)`,
high `[10,∞)`, plus a separate zero-expression group. Report the same error,
bias and DE metrics per stratum; do not compute relative error for true zero.

## Differential expression against truth

The tested universe is the intersection of truth genes and genes present in
the DESeq2 result. A primary call is `padj < 0.05`. `NA` padj is not called.

```text
TP = truth DE and called
FP = truth non-DE and called
TN = truth non-DE and not called
FN = truth DE and not called
precision = TP / (TP + FP)
recall = TP / (TP + FN)
specificity = TN / (TN + FP)
F1 = 2 * precision * recall / (precision + recall)
observed FDP = FP / max(TP + FP, 1)
```

AUROC and AUPRC use `-log10(pvalue)` as the unsigned ranking score, with NA
assigned below all finite scores. AUPRC is always shown with the DE prevalence
baseline. No claim is made when only one truth class is present.

Fold-change accuracy uses true versus estimated log2FC: Spearman, Pearson,
MAE, RMSE, median signed error and direction concordance. Direction is correct
when both nonzero signs agree. Report separately for `|true log2FC| = 0.5`,
`1.0` and `2.0`, and for non-DE genes.

FDR calibration is reported at nominal padj thresholds 0.01, 0.05 and 0.10 as
the observed FDP, number called and confidence interval from the observed
binomial proportion. It describes this simulation only.

## HelixForge versus independent reference

| Artifact | Comparison |
|---|---|
| trimmed/merged FASTQ | same files are shared inputs; SHA-256 recorded |
| `quant.sf` | exact row IDs/order and semantic numeric tolerance |
| counts/TPM/length matrices | exact IDs/sample order and semantic numeric tolerance |
| DE table | exact gene/contrast identity; baseMean, log2FC, SE, statistic, pvalue and padj tolerance |
| DEG sets | intersection, union, Jaccard, overlap coefficient, direction concordance |
| rankings | Spearman rank and top-N overlap for N=50, 100, 250 and 500 |

Numeric equivalence is `abs(a-b) <= 1e-8 + 1e-6*abs(reference)`. Values equal
under tighter precision are still reported. NA must match NA. Any tolerance
failure is listed by field and ID rather than hidden in an aggregate.

## Public biological expectations

Comparisons to GSE52778 processed results use gene-symbol/Ensembl mappings
frozen from GENCODE 49 and are labeled:

- `SET_OVERLAP`: DEG Jaccard/overlap and direction among common genes;
- `BIOLOGICAL_EXPECTATION`: direction/rank of the predeclared responsive and
  housekeeping genes;
- never `EXACT` or `NUMERIC` across the publication and RC pipelines.

## Coverage robustness

Each reduced depth is compared to public 100% for:

- transcript/gene TPM Spearman and log-scale RMSE;
- log2FC Spearman, MAE and direction concordance;
- primary and effect-filtered DEG precision/recall/Jaccard relative to 100%;
- top-N overlap at 50, 100, 250 and 500;
- read survival after trimming and Salmon mapping rate.

The synthetic depth series additionally compares every level to ground truth.

## Reproducibility

Classify each artifact as byte, numeric or semantic according to
`docs/outputs.md`. Report changed file count, mismatched IDs/fields and maximum
numeric delta. Volatile paths, run/session IDs and timestamps are normalized by
an explicit allowlist; unknown differences fail comparison.

## Performance

Report per process and workflow:

- wall time, summed task realtime and CPU time;
- peak RSS and VMEM;
- read/write bytes when available;
- task count, retry/failure count and peak concurrency;
- input pairs and pairs surviving trimming;
- work, published result, reference/index and container-cache disk usage.

For repeated seeds/depths report mean, median, standard deviation and range.
Scheduler wait time is reported separately from task runtime.
