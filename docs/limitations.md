# Limitations of the compatibility skeleton

- Scientific outputs are external side effects from the Nextflow work
  directory. Nextflow caches the step marker, not each BAM, FASTQ, or table.
- ChIP sample fan-out and RNA analytical fan-out still occur inside their
  existing local-mode coordinator scripts. RNA QC now fans out natively.
- The generic compatibility process uses resource classes rather than exact
  per-tool requirements.
- Container and native Conda profiles remain placeholders for legacy tools.
  Native RNA QC modules have pinned Conda environments and container tags.
- Docker runs must bind the configured external `SCRATCH_ROOT` at the same path
  inside the container because compatibility outputs retain their absolute
  legacy paths. Shared HPC filesystems are normally visible to Apptainer.
- Cached native QC tasks track their work-directory outputs. If a user manually
  deletes compatibility copies under `SCRATCH_ROOT`, resume should be avoided
  or the affected task cache should be invalidated.
- The deterministic mock regression validates orchestration and byte-preserving
  merge behavior. A real-tool golden dataset still needs to run on Linux/HPC
  with FastQC 0.12.1, Trim Galore 0.6.10, and MultiQC 1.17 available.
- `workflow all` waits for RNA and ChIP before integration, but the existing
  IntegrateSeq config must point to the actual RNA/ChIP result directories.
- The minimal output manifest and Reference Bundle are specified but not yet
  generated automatically.
- Existing `.done` files remain active inside legacy pipelines. Nextflow status
  markers are an additional orchestration layer.
