# HelixForge 1.0.0-rc.1 release notes

## Status

This is a draft release candidate. No tag should be created until the release
checklist passes and the maintainer explicitly approves it.

## Highlights

- Complete native RNA-seq production path centered on Salmon, provider-neutral
  import, DESeq2 and candidate-gene reporting.
- Complete native ChIP-seq production path with optional IDR, differential
  binding, annotation, tracks and a self-contained report.
- Native Integrative workflow joining semantic RNA/ChIP evidence into
  deterministic candidate rankings, functional interpretation and report.
- Portable, versioned terminal manifests replace path discovery.
- Pinned provider images, provenance, checksums, resource declarations and
  regression fixtures.
- Certified Nextflow 25.10.7 / Java 21 runtime baseline.
- Apache License 2.0 for HelixForge source, with third-party runtime licensing
  kept explicit and separate.

## Important decisions

- Salmon is the production RNA-seq provider; STAR is experimental.
- Batch effects enter inference through an estimable model formula. Corrected
  matrices are exploratory only.
- Data download is outside scientific execution.
- Synthetic fixtures and public biological datasets have separate evidence and
  interpretation boundaries in the frozen RNA-seq and ChIP-seq baselines.

## Upgrade notes

Read [Migrating to v1](migrating-to-v1.md). Active legacy coordinators are no
longer available on `master`; use the documented immutable legacy tags only for
historical audit or semantic comparison.

## Known limitations

- Apptainer/Singularity and Conda are experimental.
- Externally authored terminal manifests require further interoperability
  certification.
- RNA-seq and ChIP-seq biological benchmark baselines are complete and retain
  `PASS_WITH_LIMITATIONS`; the Integrative benchmark is the next validation
  stage.
