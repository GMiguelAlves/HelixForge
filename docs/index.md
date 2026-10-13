# HelixForge documentation

This is the navigation map for versioned repository documentation. The
[GitHub Wiki](https://github.com/GMiguelAlves/HelixForge/wiki) mirrors a curated
user-facing subset. Guides and API contracts describe the current interface;
implementation, validation, audit and legacy records preserve the evidence
available when they were written.

## Start here — `guides/`

- [Installation and support matrix](guides/installation.md) ·
  [Quick Start](guides/quickstart.md) ·
  [Workflow guide](guides/workflows.md) ·
  [Output guide](guides/outputs.md)
- [Advanced Nextflow execution](guides/nextflow.md) ·
  [Single-end RNA-seq](guides/rnaseq-single-end.md) ·
  [Runtime and container inventory](guides/runtime-inventory.md)
- [Developer guide](guides/developer-guide.md) ·
  [Limitations](guides/limitations.md) ·
  [Licensing](guides/licensing.md) ·
  [Migrating to v1](guides/migrating-to-v1.md)
- [Roadmap](roadmap.md)

## Scientific policies — `science/`

- [Scientific reference](science/scientific-reference.md) ·
  [RNA-seq Import policy](science/rnaseq_import_policy.md)
- [RNA-seq scientific review](science/rnaseq-scientific-review.md) ·
  [ChIP-seq scientific review](science/chipseq-scientific-review.md)
- [Cross-assay integration](science/cross_assay_integration.md) ·
  [Regulatory interpretation](science/regulatory_interpretation.md)

## Architecture and contracts — `architecture/` and `api/`

- [Platform architecture](architecture/architecture.md) ·
  [ChIP-seq architecture](architecture/chipseq-architecture.md) ·
  [Conceptual data model](architecture/conceptual-data-model.md)
- [Public API classification](api/public-api.md) ·
  [Module contracts](api/module_contracts.md) ·
  [Terminal manifests](api/terminal_manifests.md) ·
  [Evidence model](api/evidence_model.md)
- RNA-seq: [Alignment](api/alignment_api.md) ·
  [Quantification](api/quantification_api.md) ·
  [Import](api/import_api.md) ·
  [Differential Expression](api/differential_expression_api.md) ·
  [Report](api/rnaseq_report_api.md)
- ChIP-seq: [overview](api/chipseq-api.md) ·
  [Peak Calling](api/peak_calling_api.md) ·
  [Peak QC](api/peak_qc_api.md) ·
  [Consensus/IDR](api/consensus_idr_api.md) ·
  [Differential Binding](api/differential_binding_api.md) ·
  [Peak Annotation](api/peak_annotation_api.md) ·
  [Track Generation](api/track_generation_api.md) ·
  [Report](api/chipseq_report_api.md)
- Integration: [Integration API](api/integration_api.md)

## Native implementation records — `implementation/`

- RNA-seq: [QC](implementation/native-rnaseq-qc.md) ·
  [Trim Galore](implementation/native-trim-galore.md) ·
  [Alignment](implementation/native-rnaseq-alignment.md) ·
  [Quantification](implementation/native-rnaseq-quantification.md) ·
  [Import](implementation/native-rnaseq-import.md) ·
  [Differential Expression](implementation/native-rnaseq-de.md) ·
  [Report](implementation/native-rnaseq-report.md)
- ChIP-seq: [BAM processing](implementation/native-chipseq-bam-processing.md) ·
  [Peak Calling](implementation/native-chipseq-peak-calling.md) ·
  [Peak QC](implementation/native-chipseq-peak-qc.md) ·
  [Consensus/IDR](implementation/native-chipseq-consensus-idr.md) ·
  [Differential Binding](implementation/native-chipseq-differential-binding.md) ·
  [Peak Annotation](implementation/native-chipseq-peak-annotation.md) ·
  [Tracks](implementation/native-chipseq-tracks.md) ·
  [Report](implementation/native-chipseq-report.md)
- [Integrative native workflow](implementation/integrative-native-workflow.md) ·
  [Peak annotation optimization](implementation/peak_annotation_optimization.md)

## Validation and audit — `validation/` and `audit/`

- [Final validation plan](validation/final-validation-plan.md) ·
  [Final validation report](validation/final-validation-report.md) ·
  [Nextflow cache diagnostic](validation/resume-cache-diagnostic.md)
- RNA-seq: [foundation](validation/rnaseq-foundation-validation.md) ·
  [final synthetic run](validation/rnaseq-final-validation.md) ·
  [single-end Slurm run](validation/rnaseq-single-end-slurm-validation.md)
- ChIP-seq: [container certification](validation/chipseq-container-certification.md) ·
  [full native run](validation/chipseq-full-native-validation.md)
- [Architecture consolidation audit](audit/architecture-consolidation-audit.md) ·
  [release-candidate audit](audit/v1-rc-audit.md) ·
  [scientific deviation log](audit/scientific-deviation-log.md)
- ChIP-seq historical evidence: [legacy analysis](audit/chipseq-legacy-analysis.md) ·
  [Differential Binding review](audit/chipseq-differential-binding-review.md) ·
  [IDR full-run record](audit/chipseq-idr-full-real-20260813-README.md)
- Integrative historical evidence: [legacy audit](audit/integrative-legacy-audit.md) ·
  [regression specification](audit/integrative-regression-specification.md)

## Releases and legacy migration — `releases/` and `legacy/`

- [v1.1.0 notes](releases/release-notes-v1.1.0.md) ·
  [v1.0.2 notes](releases/release-notes-v1.0.2.md) ·
  [v1.0.1 notes](releases/release-notes-v1.0.1.md) ·
  [v1.0.0 notes](releases/release-notes-v1.0.0.md) ·
  [v1.0.0-rc.1 notes](releases/release-notes-v1.0.0-rc.1.md)
- [v1.0.0 freeze report](releases/v1.0.0_freeze_report.md) ·
  [Release checklist](releases/release-checklist.md) ·
  [Versioning and stability](releases/versioning.md)
- [Legacy script mapping](legacy/script-mapping.md) ·
  [RNA-seq retirement](legacy/rnaseq-legacy-retirement.md) ·
  [ChIP-seq retirement](legacy/chipseq-legacy-retirement.md) ·
  [Integrative retirement](legacy/integrative-legacy-retirement.md)
