# Limitations of the compatibility skeleton

- Scientific outputs are external side effects from the Nextflow work
  directory. Nextflow caches the step marker, not each BAM, FASTQ, or table.
- RNA and ChIP sample fan-out still occurs inside their existing local-mode
  coordinator scripts. Parallelism is therefore coarse in this version.
- The generic compatibility process uses resource classes rather than exact
  per-tool requirements.
- Container and native Conda profiles are placeholders because legacy RNA
  scripts activate named Conda environments internally.
- `workflow all` waits for RNA and ChIP before integration, but the existing
  IntegrateSeq config must point to the actual RNA/ChIP result directories.
- The minimal output manifest and Reference Bundle are specified but not yet
  generated automatically.
- Existing `.done` files remain active inside legacy pipelines. Nextflow status
  markers are an additional orchestration layer.

