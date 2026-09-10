# Synthetic ground-truth integration benchmark

## Executive Summary

The frozen 1,000-gene integration benchmark completed twice on Slurm. All
12 frozen `IS*` criteria passed, all deterministic scientific tables were
byte-identical between runs, and the global classification is **PASS**.

## Benchmark Question

Given frozen RNA and ChIP evidence with known truth, does HelixForge preserve,
harmonize, classify, score and summarize those data correctly? **Yes.**

## Frozen Design

- HelixForge scientific target: `dc0218ce902302da476910595bb133c82fee927c`
- Integration workflow: `d0d1e7499e5b42be8294da3d85e402fa90a1cfe2`
- Truth commit: `1b7e2fa`
- Truth SHA-256: `3112615e1d02ecf3d3f98cb31e84e091b53b37f3ee651f90ad0205f548343540`
- Runtime: Nextflow 25.10.7, Slurm `general`, host Python provider runtime

## Synthetic Truth

Exactly 1,000 genes: 400 concordant, 200 discordant, 100 RNA-only,
100 ChIP-only and 200 background/no-change. Difficulty: 270 EASY,
266 MODERATE and 464 HARD.

## Environment

hostname=srv-slurm-mgmt; os=Linux 6.12.101+deb13-amd64 x86_64 GNU/Linux; java=openjdk version "23.0.2-internal" 2025-01-21; python=Python 3.13.5; nextflow=25.10.7

## Fixture Validation

`TRUTH_INTEGRITY`, `SYNTHETIC_FIXTURE_VALIDATION` and
`TRUTH_LEAKAGE_CHECK` all passed. RNA supplied 900 differential rows, ChIP
supplied 800 differential rows and 2,224 peak→gene rows. The fixture contained
40 RNA and 40 ChIP `MISSING` observations and all 16 shared-region cases.

Two pre-result protocol amendments are retained: RNA missingness is encoded in
the differential effect field, and shared peak→gene regions use unique
differential-binding carrier regions because Evidence Model 1.1 keys DB
observations by region/contrast/artifact.

## HelixForge Execution

| run | processes | completed | failed | workflow_wall_seconds | peak_rss_bytes | result_bytes |
|---|---|---|---|---|---|---|
| A | 12 | 12 | 0 | 83.535 | 26948403 | 8980871 |
| B | 12 | 12 | 0 | 83.434 | 42467328 | 8980871 |

Both runs generated Evidence Provider bundles, harmonization maps, Master
Molecular Evidence, regulatory interpretation, statistics, Candidate Score,
functional outputs, SVG visualizations, final HTML report and terminal manifest.

## Entity Preservation

Expected 1,000; observed 1,000; missing 0; unexpected 0; duplicates 0.
Entity recall was 1.0.

## Full Outer Join

RNA-only, ChIP-only, combined and background entities were all preserved.
RNA and ChIP master states were exact for all genes.

## Identifier / Mark / Context Normalization

Exact, `gene:` prefix, explicit alias and opt-in version normalization cases
passed. H3 capitalization, HP1→SmHP1, unknown marks, stage contexts and the
semantic `condition__treated_vs_control` contrast matched the frozen design.

## Missing-State Correctness

Overall scoped accuracy: 1.0 across 4,000 state observations.

| class | support | precision | recall | f1 |
|---|---|---|---|---|
| MEASURED | 3320 | 1.0 | 1.0 | 1.0 |
| MISSING | 80 | 1.0 | 1.0 | 1.0 |
| NOT_APPLICABLE | 300 | 1.0 | 1.0 | 1.0 |
| NOT_MEASURED | 100 | 1.0 | 1.0 | 1.0 |
| NO_PEAK | 200 | 1.0 | 1.0 | 1.0 |

## Regulatory Interpretation

Accuracy, macro precision, macro recall, macro-F1 and weighted-F1 were all 1.0.

| class | support | precision | recall | f1 |
|---|---|---|---|---|
| CHIP_ONLY | 100 | 1.0 | 1.0 | 1.0 |
| CONCORDANT_ACTIVATION | 200 | 1.0 | 1.0 | 1.0 |
| CONCORDANT_REPRESSION | 200 | 1.0 | 1.0 | 1.0 |
| DISCORDANT | 200 | 1.0 | 1.0 | 1.0 |
| INSUFFICIENT_CROSS_ASSAY_EVIDENCE | 100 | 1.0 | 1.0 | 1.0 |
| NO_REGULATORY_INTERPRETATION | 100 | 1.0 | 1.0 | 1.0 |
| RNA_ONLY | 100 | 1.0 | 1.0 | 1.0 |

## Difficulty-Stratified Results

| difficulty | n | accuracy | macro_f1 | missing_state_accuracy |
|---|---|---|---|---|
| EASY | 270 | 1.0 | 1.0 | 1.0 |
| MODERATE | 266 | 1.0 | 1.0 | 1.0 |
| HARD | 464 | 1.0 | 1.0 | 1.0 |

## Mark-Stratified Results

| mark | n | accuracy | macro_f1 |
|---|---|---|---|
| H3K27ac | 198 | 1.0 | 1.0 |
| H3K27me3 | 198 | 1.0 | 1.0 |
| H3K4me3 | 198 | 1.0 | 1.0 |
| H3K9me3 | 198 | 1.0 | 1.0 |
| SYNTHETIC_UNKNOWN_MARK | 4 | 1.0 | 1.0 |
| SmHP1 | 4 | 1.0 | 1.0 |

## Independent Implementation

The independent standard-library evaluator imported no HelixForge integration
code. Entity, missing-state, regulatory-class, statistic and Candidate Score
comparisons all passed.

## Statistical Validation

Fisher cells, right-tail p-values, Haldane–Anscombe odds ratios, BH adjustment,
Pearson and Spearman agreed. Maximum serialized numerical difference was
`2.220446049250313e-16`; all frozen tolerances passed.

## Candidate Score

- Exact component and final-score agreement: yes
- Exact deterministic ranking: `True`
- Spearman with truth priority: `0.8117504335221083`
- HIGH-priority AUPRC: `0.8743535001204731`
- Top-10/25/50/100 recovery: `1.0` / `1.0` / `1.0` / `1.0`

## Determinism

Runs A and B were semantically identical. All 12
scientific TSVs compared were also byte-identical. JSON runtime metadata and
HTML were excluded from inappropriate byte-identity requirements.

## Acceptance Criteria

| criterion_id | metric | status |
|---|---|---|
| IS1 | exact 1,000 canonical entities | PASS |
| IS2 | 100% exact RNA/ChIP master states | PASS |
| IS3 | 100% exact scoped missing states | PASS |
| IS4 | precision/recall/F1 1.0 for critical patterns | PASS |
| IS5 | accuracy and macro-F1 >= 0.995 | PASS |
| IS6 | exact entity/contrast/context/mark maps | PASS |
| IS7 | exact peak counts and complete ID sets | PASS |
| IS8 | Fisher/BH/odds within frozen tolerance | PASS |
| IS9 | Pearson/Spearman within frozen tolerance | PASS |
| IS10 | all score components and tie order exact | PASS |
| IS11 | priority Spearman >= 0.60 | PASS |
| IS12 | HIGH-priority top-100 recovery >= 0.80 | PASS |

## Limitations

The truth is deliberately class-balanced, uses artificial effect tiers and a
finite difficulty model, contains limited biological ambiguity, and abstracts
priority for Candidate Score. This is an integration-level—not FASTQ-level—
benchmark. Those limitations do not weaken the correctness gates exercised.

## Final Classification

```text
TECHNICAL_EXECUTION = PASS
TRUTH_INTEGRITY = PASS
FIXTURE_VALIDATION = PASS
ENTITY_PRESERVATION = PASS
FULL_OUTER_JOIN = PASS
IDENTIFIER_NORMALIZATION = PASS
MISSING_STATE_CORRECTNESS = PASS
REGULATORY_INTERPRETATION = PASS
STATISTICAL_INTEGRATION = PASS
CANDIDATE_SCORE = PASS
INDEPENDENT_CONCORDANCE = PASS
DETERMINISM = PASS

SYNTHETIC_INTEGRATION_BENCHMARK = PASS
```

READY_FOR_REENTRY_EQUIVALENCE
