# Native ChIP-seq BAM processing tests

`run_functional.sh` builds a tiny coordinate-sorted paired BAM using the local
SAMtools installation and checks real MAPQ/flag selection, duplicate removal,
fragment-level blacklist exclusion, the disabled-blacklist path, final indexes,
two records and cache reuse.

Expected counts are 12 input alignments, 8 selected, 6 after duplicate removal,
and 4 after blacklist removal. The no-blacklist/duplicate-none record retains
8 selected alignments.

`run_invalid_inputs.sh` checks explicit reference-length and blacklist-contig
incompatibility failures. Neither script downloads software.

