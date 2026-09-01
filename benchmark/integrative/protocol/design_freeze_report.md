# Integrative benchmark design freeze report

## Scope and scientific target

This design validates the native integration boundary of HelixForge
`v1.0.0-rc.1` without repeating frozen RNA-seq or ChIP-seq validation.

| Identity | Commit/tag |
|---|---|
| Scientific target and current master at freeze | `dc0218ce902302da476910595bb133c82fee927c` |
| Integration workflow implementation | `d0d1e7499e5b42be8294da3d85e402fa90a1cfe2` |
| RC release lineage | `v1.0.0-rc.1` → `fc38ada8f592bb57a13467965a718ce0df7fb6ce` |
| RNA baseline | `rnaseq-benchmark-v1.0.0-rc.1` → `9a4367c3839b4f7f929b14157fcde7011df837e6` |
| ChIP baseline | `chipseq-benchmark-v1.0.0-rc.1` → `1679610f7649c0fcaf98a2e132c96bf76cbbe3b1` |

The different commit identities are administrative lineage, not a hidden
scientific substitution. The integrative benchmark evaluates the current RC
code after both baseline merges.

## Architecture

- **Synthetic:** integration-level, 1,000 genes, independent truth and future
  independent reference implementation.
- **Re-entry:** direct terminal manifests versus relocated manifest-backed
  re-entry with identical evidence bytes and policies.
- **Real:** matched K562 DMSO versus 5 µM GSK343 RNA-seq, H3K27me3, H3K27ac and
  IgG from `GSE133183`.
- **Contracts:** frozen fail/warn/normalize fixtures for API boundaries.
- **Freeze:** dimension-level and global classification followed by a tag only
  after review.

## Synthetic design

The frozen truth contains 200 concordant activation, 200 concordant repression,
200 directional discordance, 100 RNA-only, 100 ChIP-only and 200 background
genes. It includes H3K27ac, H3K4me3, H3K27me3, H3K9me3, HP1 aliasing and an
unknown mark; exact/prefix/version/explicit-alias entity cases; semantic
contrast matching; all supported peak–gene structures; explicit missing
observations; and EASY/MODERATE/HARD tiers.

The Master state truth distinguishes assay-level `MEASURED`, `NO_PEAK` and
`NOT_MEASURED` from observation-level `MISSING` and field-level
`NOT_APPLICABLE`. Multi-peak aggregation compares counts and all IDs; it does
not invent a representative peak score.

## Interpretation, statistics and score

Regulatory classes use the released names and thresholds. Fisher is right-tail,
odds ratios use +0.5, BH uses one `legacy_mark_enrichment_all` family, and
Pearson/Spearman remain descriptive with minimum n=2 and no inferential
p-values. Candidate Score v1 is independently recomputed component-by-component
and ranked by score, statistical support and gene ID. Ranking limitations do
not override core evidence correctness.

## Real dataset selection

Three candidates were reviewed. `GSE133183` was selected because the same
study provides the same cell line and perturbation across RNA-seq, two
complementary histone marks, matched IgG and two biological replicates per
condition. GEO explicitly documents this design and the original publication
supports preregistered directional expectations. Limitations are replication,
broad drug effects and provisional raw download size.

## Metrics and gates

`protocol/metrics.md` freezes definitions and numeric tolerances.
`protocol/interpretation_criteria.md` freezes IS*, IR*, IB* and IC* criteria.
Entity preservation, full outer semantics, scoped missingness, critical
classes, independent numeric agreement, re-entry equivalence, compatibility
rejection and manifest validation are release gates. Real biological
plausibility and performance are not promoted to absolute truth.

## Cost, risks and stop conditions

Synthetic/re-entry/contract arms are compact. The real arm is provisionally
20–40 GB of raw transfer and 100–200 GB scratch until accession-level audit.
Compute must use Slurm and the established cleanup/audit policy. Frozen stop
conditions are `PROTOCOL_IMPLEMENTATION_CONFLICT`,
`DATASET_AVAILABILITY_CONFLICT`, `REFERENCE_COMPATIBILITY_CONFLICT`,
`TRUTH_GENERATION_CONFLICT` and `RESOURCE_BLOCKED`.

## Provenance and current state

The truth, design configuration, biological expectations and scientific target
are versioned and checksummed. No HelixForge output was inspected, no dataset
was downloaded, no workflow was changed, no scientific job was submitted and
no integrative tag was created in this design phase.

```text
INTEGRATIVE_BENCHMARK_DESIGN = FROZEN

SYNTHETIC_TRUTH_DESIGN = FROZEN
REENTRY_DESIGN = FROZEN
NEGATIVE_CONTRACT_DESIGN = FROZEN
REAL_DATASET = FROZEN
BIOLOGICAL_EXPECTATIONS = FROZEN
METRICS = FROZEN
ACCEPTANCE_CRITERIA = FROZEN

SCIENTIFIC_EXECUTION = NOT_STARTED
```
