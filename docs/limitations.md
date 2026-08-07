# Limitations of the compatibility skeleton

- Scientific outputs are external side effects from the Nextflow work
  directory. Nextflow caches the step marker, not each BAM, FASTQ, or table.
- ChIP sample fan-out and RNA post-alignment analytical fan-out still occur
  inside existing local-mode coordinator scripts. RNA QC and STAR fan out
  natively.
- The generic compatibility process uses resource classes rather than exact
  per-tool requirements.
- Container and native Conda profiles remain placeholders for legacy tools.
  Native RNA QC and STAR modules have pinned Conda environments and containers.
- Docker runs must bind the configured external `SCRATCH_ROOT` at the same path
  inside the container because compatibility outputs retain their absolute
  legacy paths. Shared HPC filesystems are normally visible to Apptainer.
- Cached native QC tasks track their work-directory outputs. If a user manually
  deletes compatibility copies under `SCRATCH_ROOT`, resume should be avoided
  or the affected task cache should be invalidated.
- Alignment cache and invalidation passed with official Nextflow 26.04.2. The
  locally installed 26.04.6 development artifact did not resume even a minimal
  cache probe and is not validated for production here.
- The deterministic QC mock validates orchestration and byte-preserving merge
  behavior. STAR has a separate real-tool Docker regression; a real-tool QC
  golden dataset still needs to run on Linux/HPC with FastQC 0.12.1, Trim
  Galore 0.6.10, and MultiQC 1.17 available.
- `workflow all` waits for RNA and ChIP before integration, but the existing
  IntegrateSeq config must point to the actual RNA/ChIP result directories.
- The minimal output manifest and Reference Bundle are specified but not yet
  generated automatically.
- Existing `.done` files remain active inside legacy pipelines. Nextflow status
  markers are an additional orchestration layer.
