# Release checklist

## Governance

- [x] Release scope and version approved.
- [x] `LICENSE` and `NOTICE` reflect the distributed content.
- [x] `CITATION.cff`, `CHANGELOG.md` and release notes validated.
- [x] Release version and tag are consistent with the approved release.

## Contracts and science

- [x] Public schemas resolve and model versions are documented.
- [x] Scientific policies/defaults match their reviewed API documents.
- [x] Candidate Score and functional-analysis definitions are unchanged or
      explicitly versioned and reviewed.
- [x] Known limitations and experimental surfaces are current.
- [x] No active legacy coordinator or fallback remains.

## Software gates

- [x] `bin/helixforge-doctor` passes with Java 21 and Nextflow 25.10.7.
- [x] Unit/contract test discovery executes a non-zero expected suite.
- [x] `nextflow lint .` has no errors or warnings.
- [x] Local documentation links resolve.
- [x] RNA-seq, ChIP-seq, Integrative and `all` stub smokes pass.
- [x] Reduced real Integrative smoke passes and emits its main output/manifest.
- [x] Existing reduced real RNA-seq and ChIP-seq evidence remains referenced.
- [x] Clean-clone validation passes without local caches or untracked files.
- [x] CI required checks are green.

## Operational evidence

- [x] Pinned OCI images are available and container certification is current.
- [x] Project-built images preserve upstream package license metadata and
      notices; repeat the image-content audit when dependencies change.
- [x] Slurm execution uses Nextflow-only scheduling and site-safe concurrency.
- [x] `-resume` status and any external runtime limitation are documented.
- [x] No credentials, private data, personal paths, caches or large generated
      artifacts are committed.

## Publication

- [x] Create the annotated release tag after all required gates pass.
- [x] Publish GitHub release notes; archive/DOI metadata remains conditional on
      an external archive deposit.
- [x] Verify repository Wiki/navigation.
- [x] Announce unresolved experimental surfaces without overstating support.
