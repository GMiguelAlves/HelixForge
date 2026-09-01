# Frozen metric definitions

## Synthetic correctness

- Overall accuracy: correct regulatory-pattern rows / 1,000.
- Per-class precision, recall and F1; macro and prevalence-weighted F1.
- Complete confusion matrix for the actual `regulatory_pattern` vocabulary.
- Entity preservation: exact canonical gene set equality.
- Difficulty stratification: all classification metrics repeated for EASY,
  MODERATE and HARD.

## Missing states

Metrics are computed separately for master RNA state, master ChIP state and
observation state. Each receives accuracy and per-state precision/recall/F1.
At least 40 explicit `MISSING` observations and at least 100 examples of
`NO_PEAK`, `NOT_MEASURED` and field-level `NOT_APPLICABLE` are frozen.

## Harmonization and peak aggregation

Compare canonical entity, context, contrast and mark maps exactly. Peak
aggregation compares total, promoter, gene-body and distal counts plus the
complete sorted source-ID sets. One-region→multiple-gene associations must be
preserved for every declared gene.

## Regulatory interpretation

`legacy_evidence_class`, `regulatory_pattern`, direction, significance and
evidence-source IDs are exact categorical comparisons. Critical patterns are
both concordant classes, `DISCORDANT`, `RNA_ONLY` and `CHIP_ONLY`.

## Statistics

An independent standard-library or independently versioned R implementation
calculates right-tailed Fisher/hypergeometric p-values, Haldane–Anscombe
odds ratios, one-family BH adjustment, Pearson and Spearman coefficients.

- finite scalar agreement: absolute tolerance `1e-10`, relative tolerance
  `1e-8`;
- correlation agreement: absolute tolerance `1e-8`;
- empty correlation p/padj and `NOT_COMPUTED_LEGACY`: exact;
- contingency cells, universe, overlap IDs and BH family: exact.

## Candidate Score

Candidate Score v1 is recalculated independently from its frozen components.
Scores use absolute tolerance `1e-8`; rank keys and ties must be exact. Quality
metrics are Spearman correlation with ordinal synthetic priority, recovery of
HIGH-priority entities in top 10/25/50/100 and AUPRC for HIGH priority.

Priority reflects strength and evidence completeness, not concordance alone,
because Candidate Score v1 contains no discordance penalty. This prevents the
benchmark from demanding behavior the released score does not implement.

## Re-entry equivalence

Compare row counts, column sets/order, entity IDs, all missing states,
classification, numeric fields, ranking and top-N sets. Canonicalized
deterministic TSVs require SHA-256 identity. JSON ignores only volatile runtime
timestamps/paths. HTML requires the same sections, source tables and scientific
values, not byte identity.

## Negative contracts

Each fixture is pass/fail against its frozen disposition and error layer.
Message matching uses a stable required substring, not a full stack trace.

## Real biological integration

Descriptive metrics include RNA/ChIP/combined entity counts, unilateral and
no-peak states, regulatory-pattern counts/proportions, Fisher/BH results,
Pearson/Spearman summaries, score distribution and characteristics of the
predeclared review sets. Biological expectations are reported as recovered,
directionally inconsistent, not measured or not evaluable.

## Performance

Future runs record elapsed time, CPU-hours, peak memory, scheduler jobs, input
bytes, work bytes and result bytes. Performance is descriptive on a shared
Slurm cluster and is never a scientific correctness gate.
