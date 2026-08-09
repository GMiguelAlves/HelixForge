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
counts_from_abundance <- get_arg("--counts-from-abundance", "no")
ignore_tx_version <- tolower(get_arg("--ignore-tx-version", "false")) %in% c("1", "true", "yes")
ignore_after_bar <- tolower(get_arg("--ignore-after-bar", "false")) %in% c("1", "true", "yes")
unmapped_transcripts <- get_arg("--unmapped-transcripts", "error")

if (is.null(sample_table_file) || is.null(tx2gene_file)) {
  stop("--sample-table and --tx2gene are required")
}
if (!counts_from_abundance %in% c("no", "scaledTPM", "lengthScaledTPM", "dtuScaledTPM")) {
  stop("unsupported countsFromAbundance value: ", counts_from_abundance)
}
if (!unmapped_transcripts %in% c("error", "warn")) {
  stop("--unmapped-transcripts must be error or warn")
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
if (any(is.na(sample_meta$import_id) | sample_meta$import_id == "")) stop("empty import_id values")

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
if (any(is.na(tx2gene$transcript_id) | tx2gene$transcript_id == "" |
        is.na(tx2gene$gene_id) | tx2gene$gene_id == "")) {
  stop("tx2gene contains empty transcript_id or gene_id values")
}
gene_count_by_tx <- tapply(tx2gene$gene_id, tx2gene$transcript_id, function(x) length(unique(x)))
conflicts <- names(gene_count_by_tx)[gene_count_by_tx > 1]
if (length(conflicts) > 0) {
  stop("tx2gene transcripts map to multiple genes: ", paste(head(conflicts, 20), collapse = ", "))
}

normalize_tx <- function(values) {
  result <- as.character(values)
  if (ignore_after_bar) result <- sub("\\|.*$", "", result)
  if (ignore_tx_version) result <- sub("\\.[0-9]+$", "", result)
  result
}
mapped_ids <- normalize_tx(tx2gene$transcript_id)
if (any(duplicated(mapped_ids))) {
  collided <- unique(mapped_ids[duplicated(mapped_ids)])
  stop("tx2gene ID collision after configured normalization: ", paste(head(collided, 20), collapse = ", "))
}
for (quant_file in files) {
  quant_ids <- readr::read_tsv(
    quant_file, show_col_types = FALSE,
    col_types = cols(.default = col_character())
  )[["Name"]]
  if (is.null(quant_ids)) stop("quantification file lacks Name column: ", quant_file)
  normalized_quant_ids <- normalize_tx(quant_ids)
  if (any(duplicated(normalized_quant_ids))) {
    collided <- unique(normalized_quant_ids[duplicated(normalized_quant_ids)])
    stop("quantification ID collision after configured normalization in ", quant_file, ": ",
         paste(head(collided, 20), collapse = ", "))
  }
  missing_ids <- setdiff(normalized_quant_ids, mapped_ids)
  if (length(missing_ids) > 0) {
    message <- paste0(length(missing_ids), " quantified transcripts have no tx2gene mapping in ", quant_file,
                      ": ", paste(head(missing_ids, 20), collapse = ", "))
    if (unmapped_transcripts == "error") stop(message) else warning(message)
  }
}

txi <- tximport(
  files,
  type = "salmon",
  tx2gene = tx2gene,
  countsFromAbundance = counts_from_abundance,
  ignoreTxVersion = ignore_tx_version,
  ignoreAfterBar = ignore_after_bar
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
  countsFromAbundance = counts_from_abundance,
  ignoreTxVersion = ignore_tx_version,
  ignoreAfterBar = ignore_after_bar,
  unmappedTranscripts = unmapped_transcripts
)
saveRDS(experiment, experiment_name, version = 3)

statistics <- data.frame(
  metric = c("samples", "genes", "sum_counts", "sum_abundance"),
  value = c(ncol(txi$counts), nrow(txi$counts), sum(txi$counts), sum(txi$abundance)),
  stringsAsFactors = FALSE
)
readr::write_tsv(statistics, "import_statistics.tsv")
