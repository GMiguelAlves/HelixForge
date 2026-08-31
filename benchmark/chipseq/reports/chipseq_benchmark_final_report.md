# HelixForge ChIP-seq Benchmark Final Report

## Executive Summary

All four frozen ChIP-seq benchmark arms completed and are classified
`PASS_WITH_LIMITATIONS`. Across synthetic narrow, synthetic broad, real K562
CTCF and real K562 H3K27me3 data, HelixForge completed the native scientific
paths and reproduced the corresponding independent implementations. No
scientific implementation failure was demonstrated.

The remaining limitations are heterogeneous and nonblocking: signal-class
behavior in the synthetic narrow IDR result, fragmentation in the synthetic
broad model, an RN3 null model that was not evaluable under its frozen control
requirements, and dataset/descriptive constraints in the historical real
broad arm. The global classification is therefore retained as
`PASS_WITH_LIMITATIONS`, not promoted to `PASS`.

## Scope

This is an administrative consolidation of completed evidence. It does not
rerun FASTQ processing, tune parameters, alter thresholds, calculate a new RN3
null, or reclassify an arm. The HelixForge ChIP-seq core was validated under
the frozen v1.0.0-rc.1 design across synthetic narrow, synthetic broad, real
CTCF narrow and real H3K27me3 broad datasets. This does not claim universal
validation for every target, organism, depth or library design.

## Frozen Software Baseline

- HelixForge version: `1.0.0-rc.1`
- Scientific target commit: `0829c7c154dc634ffd4e13672b95ad4fbdc5957f`
- Certified runtime: Nextflow 25.10.7, Java 21 and Slurm
- Administrative branch base: `2062f7695bdb16e5ca48674c474a4548c30d454e`
- Administrative commit: resolved by the annotated tag after merge
- Baseline tag: `chipseq-benchmark-v1.0.0-rc.1` (created after merge)

The scientific target identifies the pipeline code evaluated by all four
arms. Later benchmark and documentation commits preserve evidence and do not
change that target. The final administrative commit is the merged commit that
contains this consolidation and is resolved immutably by the annotated tag.

## Benchmark Design

The design combines controlled truth with public biological plausibility:

| Arm | Regime | Evidence model | Replicate endpoint |
|---|---|---|---|
| Synthetic Narrow | narrow | known peaks and summits | IDR |
| Synthetic Broad | broad | known domains | support=2 consensus |
| Real Narrow | K562 CTCF | motif, replicate and ENCODE context | IDR |
| Real Broad | K562 H3K27me3 | coverage, replicate and ENCODE context | support=2 consensus |

The complete frozen protocol and amendments are under
[`protocol/`](../protocol/). Dataset identities and accessions are preserved in
the [dataset registry](../datasets/dataset_registry.md).

## Benchmark Arms

### Synthetic Narrow

All 40 HelixForge tasks completed. Replicates produced 1,502 and 1,501 peaks;
the final IDR set contained 813 peaks and was byte-identical to the independent
implementation. IDR precision was 1.0, recall 0.542, F1 0.7030, FDP 0 and
median summit error 24 bp. Replicate base Jaccard was 0.8977 and matched-peak
rank Spearman was 0.9132.

The frozen F1 range passed, but STRONG-class recall was 0.548 rather than the
predeclared minimum 0.80. MEDIUM and WEAK recall were 0.996 and 0.082. The
called-signal medians still preserved STRONG > MEDIUM > WEAK. Exact independent
concordance makes this a synthetic-model/IDR interpretation limitation, not an
observed orchestration discrepancy. Classification: `PASS_WITH_LIMITATIONS`.

### Synthetic Broad

All 40 HelixForge tasks completed. The support=2 consensus contained 1,026
regions and recovered all 360 truth domains. Base precision was 0.9965, recall
0.9302, F1 0.9622, global IoU 0.9272 and median domain IoU 0.9226. No call
inappropriately merged truth domains. Replicate peak-set base Jaccard was
0.9806, and HelixForge and the independent implementation agreed exactly.

Fragmentation was 62.8%, above the frozen maximum 30%, with 0% for SHORT,
91.7% for MEDIUM and 96.7% for LONG domains. The criterion was not changed.
Classification: `PASS_WITH_LIMITATIONS`.

### Real Narrow — K562 CTCF

All 37 HelixForge tasks completed. Replicates produced 50,904 and 49,020 peaks,
with FRiP 0.2969 and 0.3527. The final IDR set contained 31,856 peaks. Replicate
base Jaccard was 0.6120 and matched-peak rank Spearman was 0.8792. Replicate
peaks were semantically identical to the independent implementation, and the
IDR output was byte-identical.

Canonical CTCF motif evidence was strong: median maximum PWM log-odds score
was 14.49 in peak windows versus 1.72 in controls, and 74.35% of evaluable
maxima were within ±25 bp of the summit. Descriptive ENCODE overlap Jaccard was
0.4352.

RN3 remains `NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS`: its final
exact-GC null failed the capacity-only preflight before null generation, so no
inferential p-value was calculated. `RN3_METHODS_FOLLOWUP = DEFERRED`; it does
not block this baseline or v1.0.0-rc.1. Classification:
`PASS_WITH_LIMITATIONS`.

### Real Broad — K562 H3K27me3

All 37 HelixForge tasks completed. Replicates produced 37,591 and 353,663
broadPeak records, with FRiP 0.0450 and 0.3157; their support=2 consensus
contained 19,711 domains. HelixForge and the independent implementation had
coordinate-exact replicate and consensus outputs (base Jaccard 1.0).

Genome-wide CPM coverage correlation was Pearson 0.4565 and Spearman 0.3980,
versus 0.0386 and 0.0594 after the frozen chromosome-preserving rotation. The
consensus overlapped 3,359,045 bp of the descriptive ENCODE reference and
exceeded all 100 rotations (`p = 1/101 = 0.00990099`). Contextual fragmentation
was 1.210% among touched external domains.

The historical libraries have limited/mixed read characteristics and strong
replicate asymmetry. External BigWig concordance was not computed and remains
a nonblocking descriptive omission. Classification: `PASS_WITH_LIMITATIONS`.

## Cross-Benchmark Results Matrix

The authoritative machine-readable overview is
[`chipseq_benchmark_matrix.tsv`](../results/chipseq_benchmark_matrix.tsv); the
frozen criteria are consolidated in
[`chipseq_acceptance_matrix.tsv`](../results/chipseq_acceptance_matrix.tsv).

| Arm | Technical execution | Independent concordance | Primary evidence | Classification |
|---|---|---|---|---|
| Synthetic Narrow | PASS | byte-identical IDR | IDR F1 0.7030 | PASS_WITH_LIMITATIONS |
| Synthetic Broad | PASS | exact coordinates | base F1 0.9622 | PASS_WITH_LIMITATIONS |
| Real Narrow | PASS | semantic replicates; byte-identical IDR | 31,856 IDR peaks; CTCF motif | PASS_WITH_LIMITATIONS |
| Real Broad | PASS | exact coordinates | 19,711 domains; ENCODE p=0.0099 | PASS_WITH_LIMITATIONS |

## Technical Execution

Both synthetic arms completed 40/40 Nextflow tasks and both real arms completed
37/37. Required peak products, QC outputs and Nextflow execution records were
produced. Performance measurements came from a shared Slurm/NFS environment
and remain descriptive rather than comparative release gates.

## Independent Reproducibility

Independent paths began from the same raw inputs but rebuilt their own indexes,
alignments, filtered BAMs and downstream products. Final narrow IDR outputs
were byte-identical where applicable. Broad replicate and consensus coordinates
were exact. The evidence supports deterministic orchestration and external
reproducibility within the frozen environments.

## Narrow-Peak Validation

The narrow path aligned and filtered reads, called replicate peaks, applied
IDR and reproduced independent outputs. The synthetic arm measured truth-level
precision, recall, summit error and signal classes. The real arm recovered
strong replicate agreement and canonical CTCF motif localization.

## Broad-Domain Validation

The broad path aligned and filtered reads, called broad regions, constructed a
support-based consensus and reproduced independent coordinates. Synthetic
base-level recovery was strong, while topology fragmentation was length
dependent. Real H3K27me3 showed positive genome-wide replicate coverage and
external-reference concordance.

## Biological Plausibility

CTCF peaks showed strong canonical motif enrichment close to summits. H3K27me3
consensus regions exhibited positive genome-wide replicate coverage and
overlap with an external ENCODE reference beyond all frozen rotations. These
are plausibility and concordance results, not biological ground truth.

## External ENCODE Concordance

ENCODE processed peaks were used as descriptive external references. Real
narrow retained observed overlap but no inferential RN3 result. Real broad
passed its frozen rotation comparison. Dataset age, processing differences and
library properties bound both interpretations.

## Synthetic-to-Real Interpretation

Synthetic broad fragmentation was 62.8%; contextual real broad fragmentation
was 1.21% among touched external domains. The extreme synthetic fragmentation
was not reproduced at comparable magnitude in the real H3K27me3 benchmark.
This leaves it as a documented synthetic/model-specific limitation, not a
demonstrated global failure of broad consensus. The real result does not
retroactively reclassify or relax the synthetic criterion.

## Limitations

The complete separation of limitations is in
[`chipseq_limitations.tsv`](../results/chipseq_limitations.tsv). No item has
evidence supporting classification as a HelixForge scientific implementation
failure. Limitations belong to the synthetic model, dataset, statistical null,
descriptive evidence or external site runtime.

## Deferred Investigations

- RN3 null-model methodology: `DEFERRED_METHODS_INVESTIGATION`.
- Synthetic broad fragmentation mechanism: `POST_V1_METHODS_FOLLOWUP`.
- Real broad external BigWig concordance: `POST_V1_OPTIONAL_EVALUATION`.

These questions are deliberately outside this frozen baseline and are not
blocking bugs.

## Release Assessment

The scientific implementation, independent reproduction and biological
behavior are supported under the frozen design. Documented nonblocking
limitations remain. Accordingly:

```text
CHIPSEQ_BENCHMARK = PASS_WITH_LIMITATIONS
```
## Reproducibility and Provenance

Compact reports, matrices, figures, source tables, execution evidence and
checksums are versioned below `benchmark/chipseq/`. Global provenance is in
[`chipseq_benchmark_freeze_manifest.json`](../provenance/chipseq_benchmark_freeze_manifest.json)
and the public file inventory is in
[`chipseq_artifact_manifest.tsv`](../provenance/chipseq_artifact_manifest.tsv).
The annotated post-merge tag `chipseq-benchmark-v1.0.0-rc.1` resolves the final
administrative commit without creating self-referential checksums.

## Final Classification

```text
CHIPSEQ_BENCHMARK_DESIGN = FROZEN
CHIPSEQ_SCIENTIFIC_EXECUTION = COMPLETE
CHIPSEQ_ADMINISTRATIVE_VALIDATION = PENDING_PR_CI_AND_MERGE
CHIPSEQ_BASELINE = PENDING_POST_MERGE_TAG

SYNTHETIC_NARROW = PASS_WITH_LIMITATIONS
SYNTHETIC_BROAD = PASS_WITH_LIMITATIONS
REAL_NARROW = PASS_WITH_LIMITATIONS
REAL_BROAD = PASS_WITH_LIMITATIONS

CHIPSEQ_BENCHMARK = PASS_WITH_LIMITATIONS
```
