# Release checklist

## Governance

- [ ] Release scope and version approved.
- [x] Apache License 2.0 and project NOTICE present at repository root.
- [ ] `CITATION.cff`, `CHANGELOG.md` and release notes validated.
- [ ] No release tag exists before all gates pass.

## Contracts and science

- [ ] Public schemas resolve and model versions are documented.
- [ ] Scientific policies/defaults match their reviewed API documents.
- [ ] Candidate Score and functional-analysis definitions are unchanged or
      explicitly versioned and reviewed.
- [ ] Known limitations and experimental surfaces are current.
- [ ] No active legacy coordinator or fallback remains.

## Software gates

- [ ] `bin/helixforge-doctor` passes with Java 21 and Nextflow 25.10.7.
- [ ] Unit/contract test discovery executes a non-zero expected suite.
- [ ] `nextflow lint .` has no errors or warnings.
- [ ] Local documentation links resolve.
- [ ] RNA-seq, ChIP-seq, Integrative and `all` stub smokes pass.
- [ ] Reduced real Integrative smoke passes and emits its main output/manifest.
- [ ] Existing reduced real RNA-seq and ChIP-seq evidence remains referenced.
- [ ] Clean-clone validation passes without local caches or untracked files.
- [ ] CI required checks are green.

## Operational evidence

- [ ] Pinned OCI images are available and container certification is current.
- [ ] Project-built images preserve upstream package license metadata and
      notices; repeat the image-content audit when dependencies change.
- [ ] Slurm execution uses Nextflow-only scheduling and site-safe concurrency.
- [ ] `-resume` status and any external runtime limitation are documented.
- [ ] No credentials, private data, personal paths, caches or large generated
      artifacts are committed.

## Publication

- [ ] Create the annotated RC tag only after maintainer approval.
- [ ] Publish GitHub release notes and archive/DOI metadata when available.
- [ ] Verify repository Wiki/navigation.
- [ ] Announce unresolved experimental surfaces without overstating support.
