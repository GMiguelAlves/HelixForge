# Interpretation criteria

Criteria are preclassified so descriptive expectations cannot silently become
release gates after results are seen.

## RELEASE_GATE

1. The run uses the exact RC commit/runtime and emits a valid terminal manifest
   with all expected samples, conditions, reference checksums and artifacts.
2. No task succeeds with missing, duplicated, cross-paired or checksum-invalid
   input; all eight public and six synthetic samples reach the terminal API.
3. HelixForge and the independent same-method harness satisfy the numeric
   tolerance in `metrics.md` for Salmon, Import and DE outputs. Any exception
   must have a demonstrated, documented semantic cause and explicit review.
4. Two clean identical executions are semantically reproducible. Unknown
   differences, sample reordering or effect-direction inversions fail.
5. Synthetic DE is materially informative: AUROC and AUPRC exceed their
   corresponding random/prevalence baselines, and estimated versus true log2FC
   has positive correlation. This gate detects catastrophic behavior; it is
   not a claim of high power.
6. Observed FDP, precision, recall and direction are reported for all declared
   strata. Missing or selectively omitted metrics fail even when aggregate
   values appear favorable.
7. No unexplained scientific divergence is hidden by changing reference,
   trimming, import policy, design, thresholds or universe after execution.

## SANITY_CHECK

These trigger investigation but are not automatic release failures without
root-cause review:

- gene-level true/estimated TPM Spearman below 0.90;
- transcript-level true/estimated TPM Spearman below 0.80;
- correct direction below 0.80 for truth genes with `|log2FC| >= 1`;
- observed FDP above 0.10 at nominal `padj < 0.05`;
- public 100% versus 50% gene-TPM Spearman below 0.95;
- a predeclared glucocorticoid gene has the opposite direction in all donors;
- severe low-expression bias not visible in the global statistic;
- MultiQC omits FastQC, Trim Galore or Salmon sections from a completed run.

These conservative sentinels are deliberately not performance promises. The
report must show raw values and sensitivity to abundance/effect size.

## EXPECTED_RANGE

No fixed release threshold is assigned before the pilot for precision, recall,
F1, AUROC, AUPRC, DEG count, runtime, memory, disk, Jaccard with the publication
or degradation at 25%/10%. Their purpose is characterization. The RC report may
propose future gates only after all primary results are locked, and those gates
apply prospectively rather than retroactively.

## Decision outcomes

| Outcome | Meaning |
|---|---|
| PASS | every release gate passes and sanity deviations are explained |
| PASS_WITH_LIMITATIONS | gates pass; material scope/performance limits are documented |
| FAIL_SCIENTIFIC | a scientific/contract gate fails reproducibly |
| BLOCKED_RUNTIME | the certified runtime cannot be executed on the approved Slurm environment |
| INCONCLUSIVE | required evidence is missing; never converted to PASS |

Publication agreement is supporting evidence only. A failure to reproduce the
published 316-gene count is expected to be possible because reference,
trimming, quantifier and statistical method differ.
