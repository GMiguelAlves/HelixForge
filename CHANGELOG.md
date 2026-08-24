# Changelog

All notable HelixForge changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) for software releases; scientific
contract/model versions evolve independently as documented in
`docs/versioning.md`.

## [Unreleased]

## [1.0.0-rc.1] - unreleased

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

[Unreleased]: https://github.com/GMiguelAlves/HelixForge/compare/v1.0.0-rc.1...HEAD
[1.0.0-rc.1]: https://github.com/GMiguelAlves/HelixForge/releases/tag/v1.0.0-rc.1
