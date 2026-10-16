# BOWTIE2_INDEX

Bowtie2 provider for the generic Reference/Alignment API. FASTA content and
index parameters participate in the Nextflow cache key. Annotation is not used.

Real execution additionally publishes a portable schema 1.2 manifest containing
per-shard hashes, FASTA identity, build arguments and Bowtie2 version. Preserve
it with the six index files for subsequent validated reuse via
`BOWTIE2_INDEX_VALIDATE`. Stub manifests cannot certify real index reuse.

