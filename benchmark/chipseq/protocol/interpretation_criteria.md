# Frozen interpretation criteria

These criteria are fixed before execution. **Acceptance criteria must not be
relaxed after benchmark results are observed solely to convert a failure into
a pass.** A justified change requires a dated protocol amendment containing
the reason, affected arms, old/new rule and impact on comparability.

## Universal release gates

| ID | Type | Criterion |
|---|---|---|
| U1 | `RELEASE_GATE` | The run records target commit `0829c7c...`, Nextflow 25.10.7, Java 21, inputs, checksums, command parameters and Slurm jobs. |
| U2 | `RELEASE_GATE` | Every required process completes on Slurm; required manifests validate and all declared artifacts exist with matching checksums. |
| U3 | `RELEASE_GATE` | Truth files and ENCODE processed references are unavailable to HelixForge scientific processes; only evaluators may read them. |
| U4 | `RELEASE_GATE` | The independent end-to-end path starts from raw FASTQ and does not reuse HelixForge BAMs, peaks, work directories or modules. |
| U5 | `RELEASE_GATE` | No unexplained sample swap, coordinate-system error, control mismatch, empty final set or sign/rank inversion remains. |

## Synthetic narrow

| ID | Type | Criterion |
|---|---|---|
| N1 | `SANITY_CHECK` | STRONG recall is not lower than WEAK recall by more than 0.05. |
| N2 | `EXPECTED_RANGE` | IDR-filtered F1 ≥0.70 and STRONG recall ≥0.80. These are pragmatic controlled-signal expectations, not universal ChIP-seq standards. |
| N3 | `EXPECTED_RANGE` | Median absolute summit error ≤100 bp and observed FDP ≤0.25. |
| N4 | `RELEASE_GATE` | Both replicates and the IDR set are non-empty and can be matched/evaluated with no ambiguous coordinate conversion. |
| N5 | `DESCRIPTIVE` | AUPRC, width error, FRiP, rank concordance and weak-peak recall. |

## Synthetic broad

| ID | Type | Criterion |
|---|---|---|
| B1 | `SANITY_CHECK` | STRONG-domain recall is not lower than WEAK-domain recall by more than 0.05. |
| B2 | `EXPECTED_RANGE` | Replicate-support base F1 ≥0.60 and median per-domain IoU ≥0.40. |
| B3 | `EXPECTED_RANGE` | Fragmentation and merging rates are each ≤0.30; failures trigger topology review, not threshold tuning. |
| B4 | `RELEASE_GATE` | Both replicate broadPeak sets and the support=2 consensus are non-empty and broad metrics run without summit assumptions. |
| B5 | `DESCRIPTIVE` | Boundary error, coverage correlations, width/strength strata and FRiP. |

## Real narrow

| ID | Type | Criterion |
|---|---|---|
| RN1 | `RELEASE_GATE` | Two biological CTCF replicates are correctly associated with Input `ENCSR000AKY` and produce per-replicate peaks plus IDR output. |
| RN2 | `SANITY_CHECK` | Canonical CTCF motif MA0139.1 is significantly enriched around summits versus frozen matched controls (BH-adjusted p<0.05). |
| RN3 | `EXPECTED_RANGE` | HelixForge IDR peaks overlap ENCODE `ENCFF519CXF` more than 100 chromosome/GC-matched random rotations (empirical p≤0.01). |
| RN4 | `EXPECTED_RANGE` | Replicate rank correlation is positive and IDR retains a non-zero reproducible subset. |
| RN5 | `DESCRIPTIVE` | ENCODE QC thresholds, peak count, FRiP and genomic distribution; they are not universal release gates for this legacy-depth dataset. |

## Real broad

| ID | Type | Criterion |
|---|---|---|
| RB1 | `RELEASE_GATE` | Two H3K27me3 biological replicates are correctly associated with Input and produce broadPeak plus support=2 consensus domains. |
| RB2 | `SANITY_CHECK` | Replicate CPM coverage correlation is positive and exceeds the correlation after one frozen chromosome-preserving random rotation. |
| RB3 | `EXPECTED_RANGE` | Consensus domains overlap ENCODE replicated peaks `ENCFF049HUP` more than 100 matched rotations (empirical p≤0.01). |
| RB4 | `DESCRIPTIVE` | Genome-wide annotation distribution is interpreted against the published diversity of H3K27me3 profiles; no post-hoc locus panel becomes a gate. |
| RB5 | `DESCRIPTIVE` | Domain count/width, FRiP and signal-track concordance. |

## Classification

- `PASS`: every applicable release gate passes and no material unresolved
  scientific discrepancy remains.
- `PASS_WITH_LIMITATIONS`: release gates pass, but a documented dataset,
  runtime or descriptive-metric limitation materially narrows interpretation.
- `FAIL`: an applicable release gate fails after input/runtime defects are
  excluded, or a scientific discrepancy remains unexplained.
- `BLOCKED`: required data/runtime cannot be obtained or the run cannot be
  completed for an external reason, so scientific status is unknown.

The global baseline is not the best individual outcome. It is assigned only
after all four arm classifications and explicitly lists any limitations.
