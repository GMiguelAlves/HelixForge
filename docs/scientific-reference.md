# Scientific reference

This index separates scientific policy from workflow operation. Scientific
defaults, thresholds and formulas are changed only through explicit review and
versioned contracts.

## RNA-seq

- [Import policy](rnaseq_import_policy.md): `countsFromAbundance`, transcript ID
  normalization, `ignoreTxVersion`, and `ignoreAfterBar`.
- [Differential Expression API](differential_expression_api.md): design and
  contrast validation; batch belongs in an estimable model formula.
- [RNA-seq scientific review](rnaseq-scientific-review.md).
- [RNA-seq Report API](rnaseq_report_api.md).

Corrected expression matrices are exploratory outputs only and never enter
DESeq2 automatically. A future Batch Effect Assessment API will quantify batch
and signal preservation; it is tracked in the [roadmap](roadmap.md).

## ChIP-seq

- [ChIP-seq scientific review](chipseq-scientific-review.md).
- [Peak Calling API](peak_calling_api.md).
- [Peak QC API](peak_qc_api.md).
- [Consensus and IDR API](consensus_idr_api.md).
- [Differential Binding API](differential_binding_api.md).
- [Peak Annotation API](peak_annotation_api.md).
- [Track Generation API](track_generation_api.md).

## Cross-assay integration

- [Integration API](integration_api.md).
- [Evidence model](evidence_model.md).
- [Cross-assay integration](cross_assay_integration.md).
- [Regulatory interpretation](regulatory_interpretation.md).

Candidate ranking is deterministic and evidence-driven. Functional enrichment
uses its documented universe, right-tailed Fisher exact tests and Benjamini-
Hochberg adjustment; it is interpretation evidence, not proof of mechanism.

## Deviations and validation

- [Scientific deviation log](scientific-deviation-log.md).
- [Final validation report](final-validation-report.md).
- [Limitations](limitations.md).

The synthetic fixtures exercise contracts and determinism. Public or reviewed
biological benchmarks remain a post-retirement validation activity and are not
silently represented as completed.
