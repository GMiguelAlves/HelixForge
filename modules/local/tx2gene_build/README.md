# TX2GENE_BUILD

Builds `tx2gene.tsv` independently from quantification import. The module keeps
the exact ID normalization and first-occurrence order of the legacy
`txtimport_quant.R` implementation. Its only scientific input is the annotation,
so changes to quantification files do not invalidate this task.

Default resources match the former combined import job: 2 CPUs, 32 GB, and 6
hours. Outputs are published at `meta.target_dir` and provenance is kept under
`pipeline_info/native_import/tx2gene_build`.
