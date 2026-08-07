# Limitations of the compatibility skeleton

- Scientific outputs are external side effects from the Nextflow work
  directory. Nextflow caches the step marker, not each BAM, FASTQ, or table.
- ChIP sample fan-out and most RNA fan-out still occur inside their existing
  local-mode coordinator scripts. RNA Trim Galore now fans out natively per run.
- The generic compatibility process uses resource classes rather than exact
  per-tool requirements.
- Container and native Conda profiles remain placeholders for legacy tools.
  Trim Galore is the exception and has a pinned Conda environment and container.
- Docker runs must bind the configured external `SCRATCH_ROOT` at the same path
  inside the container because compatibility outputs retain their absolute
  legacy paths. Shared HPC filesystems are normally visible to Apptainer.
- A cached native trimming task tracks its work-directory outputs. If a user
  manually deletes the compatibility copies under `SCRATCH_ROOT`, resume should
  be avoided or the affected task cache should be invalidated.
- `workflow all` waits for RNA and ChIP before integration, but the existing
  IntegrateSeq config must point to the actual RNA/ChIP result directories.
- The minimal output manifest and Reference Bundle are specified but not yet
  generated automatically.
- Existing `.done` files remain active inside legacy pipelines. Nextflow status
  markers are an additional orchestration layer.
