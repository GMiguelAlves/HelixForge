# RNASEQ_METADATA

Validates a run-level RNA-seq samplesheet and creates the same FASTQ and output
names used by the legacy QC plan. `fastq_1`/`fastq_2` may be declared explicitly;
otherwise the established `<SCRATCH_ROOT>/<dataset>/fastq_ftp` names are used.

The module performs no download, renaming, or scientific analysis.
