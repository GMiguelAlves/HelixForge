# FRIP

Calculates the Peak QC API v1 FRiP metric. SAMtools applies the explicit flag
and MAPQ policy. BEDTools converts eligible alignments to intervals, merges the
temporary peak union, and performs `intersect -u` so each unit is counted once.

Paired-end fragment construction requires one properly paired primary template
per QNAME. Ambiguous or cross-contig BEDPE records fail rather than being
silently discarded.
