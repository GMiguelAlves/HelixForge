# RNASEQ_METADATA

Validates a run-level RNA-seq samplesheet and creates the same FASTQ and output
names used by the legacy QC plan. `fastq_1`/`fastq_2` may be declared explicitly;
otherwise the established `<SCRATCH_ROOT>/<dataset>/fastq_ftp` names are used.
For single-end input, set `library_layout=single`, leave `fastq_2` empty, and
provide positive `fragment_length_mean` and `fragment_length_sd`. Omitted
`library_layout` retains the legacy paired-end interpretation.

The module performs no download, renaming, or scientific analysis.
