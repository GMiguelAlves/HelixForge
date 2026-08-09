# BAM_INDEX_QC

Final integrity boundary for BAM processing. It verifies or explicitly sorts,
requires exact reference contig names and lengths, creates the matching index,
and emits the compact QC metrics required by later peak/FRiP stages. It never
filters reads, handles duplicates, or applies blacklist intervals.

