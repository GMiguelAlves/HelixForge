# HelixForge documentation

This page is the canonical navigation map for the repository documentation.
The GitHub Wiki mirrors the curated user-facing subset; the repository remains
the versioned source of truth.

## User guide

- [Installation and support matrix](installation.md)
- [Runtime and container inventory](runtime-inventory.md)
- [Licensing and third-party software](licensing.md)
- [Quick Start](quickstart.md)
- [Workflows and required inputs](workflows.md)
- [Outputs and terminal manifests](outputs.md)
- [Advanced Nextflow execution and stage modes](nextflow.md)
- [Limitations](limitations.md)
- [Roadmap](roadmap.md)

## Scientific reference

- [Scientific reference index](scientific-reference.md)
- [RNA-seq import policy](rnaseq_import_policy.md)
- [Differential Expression API](differential_expression_api.md)
- [ChIP-seq scientific review](chipseq-scientific-review.md)
- [Evidence model](evidence_model.md)
- [Cross-assay integration](cross_assay_integration.md)
- [Regulatory interpretation](regulatory_interpretation.md)
- [Scientific deviation log](scientific-deviation-log.md)

## Developer guide

- [Developer guide](developer-guide.md)
- [Architecture](architecture.md)
- [ChIP-seq architecture](chipseq-architecture.md)
- [Public API classification](public-api.md)
- [Module contracts](module_contracts.md)
- [Versioning](versioning.md)
- [Integration API](integration_api.md)
- [Terminal manifest contract](terminal_manifests.md)

## Historical and validation records

- [Final validation report](final-validation-report.md)
- [Release-candidate audit](v1-rc-audit.md)
- [Release notes for v1.0.0-rc.1](release-notes-v1.0.0-rc.1.md)
- [RNA-seq final validation](rnaseq-final-validation.md)
- [ChIP-seq full native validation](chipseq-full-native-validation.md)
- [RNA-seq legacy retirement](rnaseq-legacy-retirement.md)
- [ChIP-seq legacy retirement](chipseq-legacy-retirement.md)
- [Integrative legacy retirement](integrative-legacy-retirement.md)

Detailed implementation and regression history is retained for developers and
auditors:

- Architecture and mapping: [consolidation audit](architecture-consolidation-audit.md),
  [legacy script mapping](script-mapping.md).
- RNA-seq implementation records: [QC](native-rnaseq-qc.md),
  [Trim Galore](native-trim-galore.md), [Differential Expression](native-rnaseq-de.md),
  and [reporting](native-rnaseq-report.md).
- ChIP-seq implementation records: [peak calling](native-chipseq-peak-calling.md),
  [Peak QC](native-chipseq-peak-qc.md), [Consensus/IDR](native-chipseq-consensus-idr.md),
  [Differential Binding](native-chipseq-differential-binding.md),
  [Peak Annotation](native-chipseq-peak-annotation.md),
  [tracks](native-chipseq-tracks.md), and [reporting](native-chipseq-report.md).
- Scientific baselines: [ChIP-seq legacy analysis](chipseq-legacy-analysis.md),
  [legacy Differential Binding review](chipseq-differential-binding-review.md),
  [Integrative legacy audit](integrative-legacy-audit.md), and
  [Integrative regression specification](integrative-regression-specification.md).

Historical records describe the evidence available at the time they were
written. They are retained for auditability and are not the primary user guide.
