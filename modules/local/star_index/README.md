# STAR_INDEX

Implements the STAR provider for Alignment API `REFERENCE_INDEX`.

The process preserves the legacy annotated-index command and resources: 16
CPUs, 180 GB, eight hours, `genomeSAindexNbases`, and
`limitGenomeGenerateRAM`. FASTA, GTF, and parameter changes are part of the
Nextflow cache key. Valid index files are published at `meta.target_dir` when
compatibility output is requested. Existing external files never bypass cache
invalidation; reuse is controlled only by Nextflow.

Software is pinned to STAR 2.7.11b, SAMtools/HTSlib 1.21, and gawk 5.1.0. The
container is the combined image maintained for the nf-core STAR module.

See `docs/alignment_api.md` for the channel contract and `tests/` for the
module-local harness.
