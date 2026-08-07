#!/usr/bin/env Rscript

suppressPackageStartupMessages(library(rtracklayer))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop("usage: tx2gene_build.R <annotation> <output>")

annotation <- args[[1]]
output <- args[[2]]

gtf_data <- rtracklayer::import(annotation)
tx2gene <- as.data.frame(gtf_data)
tx2gene <- tx2gene[tx2gene$type == "transcript", c("transcript_id", "gene_id"), drop = FALSE]
tx2gene$transcript_id <- gsub("^transcript:", "", tx2gene$transcript_id)
tx2gene$transcript_id <- gsub("\\.[0-9]+$", "", tx2gene$transcript_id)
tx2gene$gene_id <- ifelse(
  grepl("^transcript:", tx2gene$gene_id),
  gsub("^transcript:", "gene:", tx2gene$gene_id),
  tx2gene$gene_id
)
tx2gene$gene_id <- gsub("^gene:", "", tx2gene$gene_id)
tx2gene$gene_id <- gsub("\\.[0-9]+$", "", tx2gene$gene_id)
tx2gene <- unique(tx2gene)
tx2gene <- tx2gene[
  !is.na(tx2gene$transcript_id) & tx2gene$transcript_id != "" &
    !is.na(tx2gene$gene_id) & tx2gene$gene_id != "",
  ,
  drop = FALSE
]

if (nrow(tx2gene) == 0) stop("[ERRO] Nenhuma relacao transcript-gene extraida do GTF.")

write.table(
  tx2gene,
  output,
  sep = "\t",
  quote = FALSE,
  row.names = FALSE,
  col.names = TRUE,
  na = "NA",
  fileEncoding = "UTF-8"
)
