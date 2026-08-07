# SALMON_INDEX

Implements the Salmon provider for Quantification API `TRANSCRIPTOME_INDEX`.

The command and resources match the legacy RNA-seq pipeline: Salmon 1.10.3,
16 CPUs, 64 GB, 12 hours, and `SALMON_KMER_SIZE` (31 by default). Transcriptome
content and index parameters participate in the deep cache key. A verified
cached index is published at `meta.target_dir` for legacy compatibility.

The OCI and Conda environments use the same Bioconda build,
`salmon=1.10.3=h6dccd9a_2`. See `docs/quantification_api.md` for the provider
contract.
