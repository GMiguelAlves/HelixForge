# Limitations of the compatibility skeleton

- Legacy-wrapper outputs remain external side effects. Native QC, STAR, and
  Salmon outputs are content-tracked Nextflow artifacts and compatibility
  copies are published at the existing paths.
- ChIP sample fan-out and RNA post-alignment analytical fan-out still occur
  inside existing local-mode coordinator scripts. RNA QC, STAR, and Salmon fan
  out natively.
- The generic compatibility process uses resource classes rather than exact
  per-tool requirements.
- Container and native Conda profiles remain placeholders for legacy tools.
  Native RNA QC, STAR, and Salmon modules have pinned Conda environments and
  containers.
- Docker runs must bind the configured external `SCRATCH_ROOT` at the same path
  inside the container because compatibility outputs retain their absolute
  legacy paths. Shared HPC filesystems are normally visible to Apptainer.
- Cached native QC tasks track their work-directory outputs. If a user manually
  deletes compatibility copies under `SCRATCH_ROOT`, resume should be avoided
  or the affected task cache should be invalidated.
- Alignment and Quantification cache/invalidation passed with official
  Nextflow 26.04.2. The
  locally installed 26.04.6 development artifact did not resume even a minimal
  cache probe and is not validated for production here.
- The deterministic QC mock validates orchestration and byte-preserving merge
  behavior. STAR and Salmon have separate real-tool Docker regressions; a real-tool QC
  golden dataset still needs to run on Linux/HPC with FastQC 0.12.1, Trim
  Galore 0.6.10, and MultiQC 1.17 available.
- `workflow all` waits for RNA and ChIP before integration, but the existing
  IntegrateSeq config must point to the actual RNA/ChIP result directories.
- The minimal output manifest and Reference Bundle are specified but not yet
  generated automatically.
- Existing `.done` files remain active inside legacy pipelines. Nextflow status
  markers are an additional orchestration layer.
