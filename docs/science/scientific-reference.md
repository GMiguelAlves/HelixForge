# Scientific reference

This index separates scientific policy from workflow operation. Scientific
defaults, thresholds and formulas are changed only through explicit review and
versioned contracts.

## RNA-seq

- [Import policy](rnaseq_import_policy.md): `countsFromAbundance`, transcript ID
  normalization, `ignoreTxVersion`, and `ignoreAfterBar`.
- [Differential Expression API](../api/differential_expression_api.md): design and
  contrast validation; batch belongs in an estimable model formula.
- [RNA-seq scientific review](rnaseq-scientific-review.md).
- [RNA-seq Report API](../api/rnaseq_report_api.md).

Corrected expression matrices are exploratory outputs only and never enter
DESeq2 automatically. A future Batch Effect Assessment API will quantify batch
and signal preservation; it is tracked in the [roadmap](../roadmap.md).

## ChIP-seq

- [ChIP-seq scientific review](chipseq-scientific-review.md).
- [Peak Calling API](../api/peak_calling_api.md).
- [Peak QC API](../api/peak_qc_api.md).
- [Consensus and IDR API](../api/consensus_idr_api.md).
- [Differential Binding API](../api/differential_binding_api.md).
- [Peak Annotation API](../api/peak_annotation_api.md).
- [Track Generation API](../api/track_generation_api.md).
- [Frozen ChIP-seq benchmark baseline](../../benchmark/chipseq/reports/chipseq_benchmark_final_report.md).

## Cross-assay integration

- [Integration API](../api/integration_api.md).
- [Evidence model](../api/evidence_model.md).
- [Cross-assay integration](cross_assay_integration.md).
- [Regulatory interpretation](regulatory_interpretation.md).

Candidate ranking is deterministic and evidence-driven. Functional enrichment
uses its documented universe, right-tailed Fisher exact tests and Benjamini-
Hochberg adjustment; it is interpretation evidence, not proof of mechanism.

## Deviations and validation

- [Scientific deviation log](../audit/scientific-deviation-log.md).
- [Final validation report](../validation/final-validation-report.md).
- [Limitations](../guides/limitations.md).

Synthetic fixtures exercise contracts, determinism and controlled truth. The
completed public biological RNA-seq and ChIP-seq benchmarks are represented
explicitly by their frozen reports and limitations; no result is generalized
beyond its registered dataset and acceptance criteria.
