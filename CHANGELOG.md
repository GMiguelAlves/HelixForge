# Changelog

All notable HelixForge changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) for software releases; scientific
contract/model versions evolve independently as documented in
`docs/versioning.md`.

## [Unreleased]

### Fixed

- Added an explicit, manifest-validated prebuilt Salmon-index path so
  production workflows can guarantee index reuse without relying on
  `-resume` or rebuilding an existing reference.

## [1.0.0] - 2026-09-14

### Added

- Frozen RNA-seq benchmark combining Polyester controlled truth and the full
  GSE52778 biological dataset.
- Frozen ChIP-seq benchmark covering synthetic and real narrow- and broad-peak
  regimes.
- Frozen Integrative benchmark covering synthetic truth, portable manifest
  re-entry, negative contracts, and real RNA/ChIP integration.
- Stable terminal manifests, portable re-entry artifacts, provenance, and HTML
  reporting across the three workflows.

### Changed

- Promoted the validated release candidate to the stable `v1.0.0` software
  release without changing scientific contracts, defaults, thresholds, or
  algorithms.
- Consolidated the overall benchmark decision as `PASS_WITH_LIMITATIONS`.

### Known limitations

- Salmon can show small numerical nondeterminism under some threading
  conditions while preserving the validated scientific conclusions.
- Synthetic broad-domain fragmentation, the non-evaluable RN3 null, and real
  broad replicate asymmetry remain documented ChIP-seq limitations.
- Integrative IB4 remains outside its expected range and IB5 is not evaluable
  under the current directional Fisher contract.
- Top-level `-resume` persistence is environment-dependent in the tested HPC
  setup; Apptainer/Singularity and Conda remain experimental profiles.
- STAR and RNA-seq single-end execution are not certified production paths.

## [1.0.0-rc.1] - 2026-08-24

### Added

- Native RNA-seq production workflow: local metadata/reference validation, QC,
  Salmon quantification, provider-neutral import, DESeq2 and gene reporting.
- Native ChIP-seq production workflow: QC, Bowtie2, BAM processing, MACS3,
  FRiP/peak QC, consensus or optional IDR, differential binding, annotation,
  tracks and reporting.
- Native Integrative workflow with terminal-manifest validation, evidence
  providers, harmonization, molecular linkage, deterministic Candidate Score,
  functional interpretation, visualization and reporting.
- Versioned terminal manifests and portable integration artifacts for all
  assays.
- Pinned container providers, provenance, checksums, schemas, stub, contract,
  functional and regression tests.
- User-first installation, Quick Start, workflow, output and scientific
  documentation.
- Apache License 2.0 project licensing with explicit third-party software and
  container licensing boundaries.

### Changed

- Salmon is the official RNA-seq production path; STAR is explicit and
  experimental.
- Matrix batch correction is excluded from inference. Estimable batch effects
  are represented in the DESeq2 design.
- Data acquisition is outside the scientific workflows.
- Native `full` modes replace retired legacy coordinators.
- Nextflow 25.10.7 with Java 21 is the certified v1 runtime baseline.

### Removed

- Executable RNA-seq, ChIP-seq and Integrative legacy coordinators and runtime
  fallbacks from the active tree. Immutable legacy tags preserve the final
  historical implementations.

### Known limitations

- STAR, Apptainer/Singularity, Conda and externally authored integration
  manifests are experimental surfaces.
- Large-scale technical and scientific benchmarking remains planned for the
  v1 validation cycle.
- Batch Effect Assessment and pathway enrichment are roadmap items.

[Unreleased]: https://github.com/GMiguelAlves/HelixForge/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/GMiguelAlves/HelixForge/releases/tag/v1.0.0
[1.0.0-rc.1]: https://github.com/GMiguelAlves/HelixForge/releases/tag/v1.0.0-rc.1
