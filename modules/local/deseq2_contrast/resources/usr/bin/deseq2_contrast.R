#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(DESeq2)
  library(ggplot2)
  library(ggrepel)
  library(jsonlite)
  library(rtracklayer)
})

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) stop("missing argument: ", flag)
  args[[idx + 1]]
}
model_dir <- get_arg("--model-dir")
model_spec_file <- get_arg("--model-spec")
contrast_spec_file <- get_arg("--contrast-spec")
annotation_file <- get_arg("--annotation")
out_dir <- get_arg("--output-dir")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

sanitize_value <- function(x) {
  x <- as.character(x)
  x[is.na(x) | x == ""] <- "unknown"
  x <- gsub("[^A-Za-z0-9_.-]+", "_", x)
  x <- gsub("^_+|_+$", "", x)
  x[x == ""] <- "unknown"
  x
}
load_annotations <- function(path, genes) {
  fallback <- data.frame(gene_id = genes, gene_name = genes, biotype = "Unknown", stringsAsFactors = FALSE)
  if (path == "" || !file.exists(path) || file.info(path)$size == 0) return(fallback)
  gff <- rtracklayer::import(path)
  gene_rows <- gff[gff$type == "gene"]
  if (length(gene_rows) == 0) return(fallback)
  gene_id <- gsub("\\.[0-9]+$", "", gsub("^gene:", "", as.character(gene_rows$ID)))
  gene_name <- as.character(gene_rows$Name)
  gene_name[is.na(gene_name) | gene_name == ""] <- gene_id[is.na(gene_name) | gene_name == ""]
  biotype <- as.character(gene_rows$biotype)
  biotype[is.na(biotype) | biotype == ""] <- "Unknown"
  out <- data.frame(gene_id = gene_id, gene_name = gene_name, biotype = biotype, stringsAsFactors = FALSE)
  out[!duplicated(out$gene_id), , drop = FALSE]
}
write_tsv <- function(frame, path) write.table(frame, path, sep = "\t", quote = FALSE, row.names = FALSE, na = "")

model_spec <- jsonlite::fromJSON(model_spec_file, simplifyVector = FALSE)
contrast <- jsonlite::fromJSON(contrast_spec_file, simplifyVector = FALSE)
if (!identical(model_spec$test, "wald")) stop("only the legacy Wald test is supported")
if (!identical(contrast$factor, model_spec$variable)) stop("contrast factor does not match model variable")
if (identical(contrast$numerator, contrast$denominator)) stop("contrast numerator equals denominator")
if (!all(c(contrast$numerator, contrast$denominator) %in% unlist(model_spec$valid_levels))) stop("contrast level unavailable")

dds_files <- list.files(model_dir, pattern = "^dds_.*\\.rds$", full.names = TRUE)
if (length(dds_files) != 1) stop("expected exactly one fitted DESeq2 model")
dds <- readRDS(dds_files[[1]])
alpha <- as.numeric(model_spec$parameters$alpha)
lfc_threshold <- as.numeric(model_spec$parameters$lfc_threshold)
res <- results(dds, contrast = c(contrast$factor, contrast$numerator, contrast$denominator), alpha = alpha)
res_df <- as.data.frame(res)
res_df$gene_id <- rownames(res_df)
res_df <- res_df[order(res_df$padj), c("gene_id", setdiff(colnames(res_df), "gene_id")), drop = FALSE]
annotations <- load_annotations(annotation_file, rownames(dds))
res_df <- merge(res_df, annotations, by = "gene_id", all.x = TRUE, sort = FALSE)
res_df$gene_name[is.na(res_df$gene_name) | res_df$gene_name == ""] <- res_df$gene_id[is.na(res_df$gene_name) | res_df$gene_name == ""]
res_df$biotype[is.na(res_df$biotype) | res_df$biotype == ""] <- "Unknown"
res_df$analysis_id <- model_spec$analysis_id
res_df$variable <- model_spec$variable
res_df$level_a <- contrast$numerator
res_df$level_b <- contrast$denominator
res_df$contrast <- contrast$id
res_df <- res_df[, c("analysis_id", "variable", "contrast", "level_a", "level_b",
                     setdiff(colnames(res_df), c("analysis_id", "variable", "contrast", "level_a", "level_b"))), drop = FALSE]
legacy_name <- paste0("DEG_", sanitize_value(contrast$id), ".tsv")
write_tsv(res_df, file.path(out_dir, legacy_name))

common <- res_df[, c("gene_id", "baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj", "contrast"), drop = FALSE]
colnames(common)[colnames(common) == "stat"] <- "statistic"
common$design <- model_spec$formula
write_tsv(common, file.path(out_dir, "common_results.tsv"))

plot_df <- res_df[!is.na(res_df$padj) & !is.na(res_df$log2FoldChange), , drop = FALSE]
if (nrow(plot_df) > 0) {
  plot_df$significant <- plot_df$padj < alpha & abs(plot_df$log2FoldChange) >= lfc_threshold
  top <- head(plot_df[order(plot_df$padj), , drop = FALSE], 10)
  plot <- ggplot(plot_df, aes(x = log2FoldChange, y = -log10(padj), color = significant)) +
    geom_point(alpha = 0.65, size = 1.4) +
    ggrepel::geom_text_repel(data = top, aes(label = gene_id), max.overlaps = 20, size = 3) +
    scale_color_manual(values = c("FALSE" = "gray65", "TRUE" = "red3")) +
    theme_minimal(base_size = 12) +
    labs(title = contrast$id, x = "log2 fold change", y = "-log10 adjusted p-value")
  ggsave(file.path(out_dir, paste0("volcano_", sanitize_value(contrast$id), ".png")), plot, width = 8, height = 6)
}
n_sig <- sum(res_df$padj < alpha & abs(res_df$log2FoldChange) >= lfc_threshold, na.rm = TRUE)
statistics <- list(
  analysis_id = model_spec$analysis_id,
  variable = model_spec$variable,
  contrast = contrast$id,
  numerator = contrast$numerator,
  denominator = contrast$denominator,
  direction = contrast$direction,
  design = model_spec$formula,
  samples = ncol(dds),
  genes = nrow(dds),
  significant = n_sig
)
jsonlite::write_json(statistics, file.path(out_dir, "contrast_statistics.json"), auto_unbox = TRUE)
