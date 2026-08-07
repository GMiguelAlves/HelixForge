# SALMON_QUANT

Implements the Salmon provider for Quantification API `QUANTIFICATION`.

The native process preserves the legacy command and resources: Salmon 1.10.3,
paired FASTQs, automatic library detection (`-l A`), validation mappings,
8 CPUs, 32 GB, and 12 hours. The complete Salmon directory is published at
`meta.target_dir` without adding provenance files, preserving the existing
`QUANT_DIR/<dataset>/<sample_id>/quant.sf` contract consumed by tximport.

Command, checksums, execution resources, normalized statistics, versions, and
the partial manifest are published separately under `pipeline_info`.
