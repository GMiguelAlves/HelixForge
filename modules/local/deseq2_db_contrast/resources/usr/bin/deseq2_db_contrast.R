#!/usr/bin/env Rscript
suppressPackageStartupMessages({ library(DESeq2); library(jsonlite) })

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag) {
  index <- match(flag, args)
  if (is.na(index) || index == length(args)) stop("missing argument: ", flag)
  args[[index + 1]]
}
model_dir <- get_arg("--model-dir")
model_spec_file <- get_arg("--model-spec")
contrast_spec_file <- get_arg("--contrast-spec")
peak_bed_file <- get_arg("--peak-bed")
out_dir <- get_arg("--output-dir")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

model_spec <- jsonlite::fromJSON(model_spec_file, simplifyVector = FALSE)
contrast <- jsonlite::fromJSON(contrast_spec_file, simplifyVector = FALSE)
if (!identical(model_spec$provider, "deseq2") || !identical(model_spec$test, "wald")) stop("only DESeq2 Wald is supported")
if (!identical(contrast$factor, model_spec$design$variable)) stop("contrast factor does not match design variable")
if (identical(contrast$numerator, contrast$denominator)) stop("contrast numerator equals denominator")

dds <- readRDS(file.path(model_dir, "dds.rds"))
levels_available <- levels(colData(dds)[[contrast$factor]])
if (!all(c(contrast$numerator, contrast$denominator) %in% levels_available)) stop("contrast level unavailable in fitted model")
peaks <- read.delim(peak_bed_file, header = FALSE, sep = "\t", stringsAsFactors = FALSE)
if (ncol(peaks) < 4) stop("peak BED must contain stable BED4 identity")
colnames(peaks)[1:4] <- c("chrom", "start", "end", "peak_id")
if (anyDuplicated(peaks$peak_id) || !setequal(peaks$peak_id, rownames(dds))) stop("peak BED and fitted model identities disagree")

alpha <- as.numeric(contrast$alpha)
lfc_threshold <- as.numeric(contrast$lfc_threshold)
result <- results(dds, contrast = c(contrast$factor, contrast$numerator, contrast$denominator), alpha = alpha)
frame <- as.data.frame(result)
frame$peak_id <- rownames(frame)
frame <- merge(peaks[, c("peak_id", "chrom", "start", "end")], frame, by = "peak_id", sort = FALSE)
frame$contrast <- contrast$id
frame$numerator <- contrast$numerator
frame$denominator <- contrast$denominator
frame$design <- model_spec$design$formula
frame$significant <- !is.na(frame$padj) & frame$padj < alpha & !is.na(frame$log2FoldChange) & abs(frame$log2FoldChange) >= lfc_threshold
columns <- c("peak_id", "chrom", "start", "end", "baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj", "contrast", "numerator", "denominator", "design", "significant")
frame <- frame[, columns, drop = FALSE]
frame <- frame[order(frame$padj, na.last = TRUE), , drop = FALSE]
write.table(frame, file.path(out_dir, "differential_binding_results.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
write.table(frame[, c("peak_id", "chrom", "start", "end", "baseMean", "log2FoldChange", "padj", "significant")],
            file.path(out_dir, "ma_plot_data.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
statistics <- list(
  analysis_id = model_spec$analysis_id, model_id = model_spec$model_id, contrast = contrast$id,
  numerator = contrast$numerator, denominator = contrast$denominator, design = model_spec$design$formula,
  alpha = alpha, lfc_threshold = lfc_threshold, samples = ncol(dds), peaks = nrow(dds),
  significant = sum(frame$significant), status = "complete"
)
jsonlite::write_json(statistics, file.path(out_dir, "contrast_statistics.json"), auto_unbox = TRUE, pretty = TRUE)
