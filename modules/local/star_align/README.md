# STAR_ALIGN

STAR implementation of Alignment API 1.0.

The STAR command preserves the legacy paired-end behavior, coordinate sorting,
GeneCounts mode, read decompression command, extra arguments, filenames, and
resources. SAMtools runs only after STAR to add BAI, stats, flagstat, idxstats,
and MAPQ summaries; it does not rewrite the BAM.

The module emits the common `artifacts`, `reports`, `versions`, `status`,
`execution_metadata`, and partial `manifest` channels. The generic `ALIGNMENT`
dispatcher exposes BAM, BAI, logs, and statistics by semantic role.

Software is pinned to STAR 2.7.11b, SAMtools/HTSlib 1.21, and gawk 5.1.0 using
the same combined container as the nf-core STAR module.
