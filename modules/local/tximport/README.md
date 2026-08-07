# TXIMPORT

Implements the Salmon provider of Import API 1.0. It consumes only validated
manifest-backed sources and preserves all legacy tximport arguments and output
filenames. `length_matrix.tsv` and `summarized_experiment.rds` are additive API
artifacts; existing downstream scripts continue to read `counts_matrix.tsv`,
`tpm_matrix.tsv`, and `quant_samples.tsv`.

The environment pins R 4.3.2, Bioconductor 3.18, tximport 1.30.0,
SummarizedExperiment 1.32.0, readr 2.1.4, data.table 1.14.8, tibble 3.2.1,
dplyr 1.1.4, and jsonlite 1.8.8.
