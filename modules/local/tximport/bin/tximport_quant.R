#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(tximport)
  library(readr)
  library(tibble)
  library(SummarizedExperiment)
})

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = NULL) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) return(default)
  args[[idx + 1]]
}

sample_table_file <- get_arg("--sample-table")
tx2gene_file <- get_arg("--tx2gene")
counts_name <- get_arg("--counts-name", "counts_matrix.tsv")
abundance_name <- get_arg("--abundance-name", "tpm_matrix.tsv")
length_name <- get_arg("--length-name", "length_matrix.tsv")
experiment_name <- get_arg("--experiment-name", "summarized_experiment.rds")
metadata_name <- get_arg("--metadata-name", "quant_samples.tsv")

if (is.null(sample_table_file) || is.null(tx2gene_file)) {
  stop("--sample-table and --tx2gene are required")
}

sample_meta <- readr::read_tsv(
  sample_table_file,
  show_col_types = FALSE,
  col_types = cols(.default = col_character())
)
required <- c("import_id", "__source_name")
missing <- setdiff(required, colnames(sample_meta))
if (length(missing) > 0) stop("sample table missing: ", paste(missing, collapse = ", "))
if (any(duplicated(sample_meta$import_id))) stop("duplicated import_id values")

files <- file.path(sample_meta$`__source_name`, "artifact")
missing_files <- files[!file.exists(files)]
if (length(missing_files) > 0) stop("staged quantification artifact missing: ", missing_files[[1]])
names(files) <- sample_meta$import_id

tx2gene <- readr::read_tsv(
  tx2gene_file,
  show_col_types = FALSE,
  col_types = cols(.default = col_character())
)
if (!identical(colnames(tx2gene), c("transcript_id", "gene_id"))) {
  stop("tx2gene must contain transcript_id and gene_id")
}

txi <- tximport(
  files,
  type = "salmon",
  tx2gene = tx2gene,
  countsFromAbundance = "no",
  ignoreTxVersion = TRUE,
  ignoreAfterBar = TRUE
)

matrix_table <- function(x) {
  as.data.frame(x, check.names = FALSE) |>
    tibble::rownames_to_column("gene_id")
}
readr::write_tsv(matrix_table(txi$counts), counts_name)
readr::write_tsv(matrix_table(txi$abundance), abundance_name)
readr::write_tsv(matrix_table(txi$length), length_name)

private_columns <- grepl("^__", colnames(sample_meta))
compatibility_meta <- sample_meta[, !private_columns, drop = FALSE]
readr::write_tsv(compatibility_meta, metadata_name)

col_data <- as.data.frame(compatibility_meta, check.names = FALSE)
rownames(col_data) <- compatibility_meta$import_id
experiment <- SummarizedExperiment::SummarizedExperiment(
  assays = list(counts = txi$counts, abundance = txi$abundance, length = txi$length),
  colData = S4Vectors::DataFrame(col_data)
)
metadata(experiment)$import_provider <- "salmon"
metadata(experiment)$tximport_parameters <- list(
  type = "salmon",
  countsFromAbundance = "no",
  ignoreTxVersion = TRUE,
  ignoreAfterBar = TRUE
)
saveRDS(experiment, experiment_name, version = 3)

statistics <- data.frame(
  metric = c("samples", "genes", "sum_counts", "sum_abundance"),
  value = c(ncol(txi$counts), nrow(txi$counts), sum(txi$counts), sum(txi$abundance)),
  stringsAsFactors = FALSE
)
readr::write_tsv(statistics, "import_statistics.tsv")
