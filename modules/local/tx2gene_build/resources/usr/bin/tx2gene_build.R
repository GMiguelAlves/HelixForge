#!/usr/bin/env Rscript

suppressPackageStartupMessages(library(rtracklayer))

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = NULL) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) return(default)
  args[[idx + 1]]
}
as_flag <- function(value) tolower(as.character(value)) %in% c("1", "true", "yes")

annotation <- get_arg("--annotation")
output <- get_arg("--output")
if (is.null(annotation) || is.null(output)) {
  stop("--annotation and --output are required")
}

strip_tx_version <- as_flag(get_arg("--strip-transcript-version", "false"))
strip_gene_version <- as_flag(get_arg("--strip-gene-version", "false"))
strip_tx_prefix <- as_flag(get_arg("--strip-transcript-prefix", "false"))
strip_gene_prefix <- as_flag(get_arg("--strip-gene-prefix", "false"))

annotation_data <- as.data.frame(rtracklayer::import(annotation))
if (nrow(annotation_data) == 0) stop("annotation contains no records")

scalar_text <- function(column) {
  vapply(column, function(value) paste(as.character(value), collapse = ","), character(1))
}
pick_column <- function(data, candidates) {
  existing <- candidates[candidates %in% colnames(data)]
  if (length(existing) == 0) return(NULL)
  scalar_text(data[[existing[[1]]]])
}

record_type <- tolower(as.character(annotation_data$type))
candidate <- record_type %in% c("transcript", "mrna")
if (!any(candidate)) {
  candidate <- rep(TRUE, nrow(annotation_data))
}
records <- annotation_data[candidate, , drop = FALSE]

transcript_id <- pick_column(records, c("transcript_id", "transcriptId", "ID"))
gene_id <- pick_column(records, c("gene_id", "geneId", "gene", "Parent"))
if (is.null(transcript_id) || is.null(gene_id)) {
  stop("annotation does not expose transcript and gene identifiers (GTF transcript_id/gene_id or GFF ID/Parent)")
}

if (strip_tx_prefix) transcript_id <- sub("^transcript:", "", transcript_id)
if (strip_gene_prefix) gene_id <- sub("^gene:", "", gene_id)
if (strip_tx_version) transcript_id <- sub("\\.[0-9]+$", "", transcript_id)
if (strip_gene_version) gene_id <- sub("\\.[0-9]+$", "", gene_id)

tx2gene <- data.frame(transcript_id = transcript_id, gene_id = gene_id, stringsAsFactors = FALSE)
complete <- !is.na(tx2gene$transcript_id) & nzchar(tx2gene$transcript_id) &
  !is.na(tx2gene$gene_id) & nzchar(tx2gene$gene_id)
if (any(!complete)) {
  stop(sum(!complete), " transcript records have no explicit gene mapping")
}
tx2gene <- unique(tx2gene)
mapping_count <- tapply(tx2gene$gene_id, tx2gene$transcript_id, function(values) length(unique(values)))
conflicts <- names(mapping_count)[mapping_count > 1]
if (length(conflicts) > 0) {
  stop("transcripts map to multiple genes after normalization: ", paste(head(conflicts, 20), collapse = ", "))
}
if (nrow(tx2gene) == 0) stop("no transcript-to-gene relationships were extracted")

write.table(
  tx2gene, output, sep = "\t", quote = FALSE, row.names = FALSE,
  col.names = TRUE, na = "NA", fileEncoding = "UTF-8"
)
message("tx2gene mappings: ", nrow(tx2gene))
