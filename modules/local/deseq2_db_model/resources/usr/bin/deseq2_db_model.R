#!/usr/bin/env Rscript
suppressPackageStartupMessages({ library(DESeq2); library(jsonlite) })

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag) {
  index <- match(flag, args)
  if (is.na(index) || index == length(args)) stop("missing argument: ", flag)
  args[[index + 1]]
}
counts_file <- get_arg("--counts")
samples_file <- get_arg("--samples")
spec_file <- get_arg("--spec")
peak_bed <- get_arg("--peak-bed")
out_dir <- get_arg("--output-dir")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

spec <- jsonlite::fromJSON(spec_file, simplifyVector = FALSE)
if (!identical(spec$provider, "deseq2") || !identical(spec$test, "wald")) stop("only DESeq2 Wald is supported")
if (!identical(spec$normalization, "deseq2_median_of_ratios")) stop("invalid DESeq2 normalization contract")

raw <- read.delim(counts_file, check.names = FALSE, stringsAsFactors = FALSE)
required <- c("peak_id", "chrom", "start", "end")
if (!all(required %in% colnames(raw)) || ncol(raw) <= 4) stop("invalid raw peak count matrix")
if (anyDuplicated(raw$peak_id)) stop("duplicate peak_id in raw count matrix")
coordinates <- raw[, required, drop = FALSE]
count_data <- raw[, setdiff(colnames(raw), required), drop = FALSE]
count_data[] <- lapply(count_data, function(value) as.numeric(as.character(value)))
if (anyNA(count_data) || any(!is.finite(as.matrix(count_data))) || any(count_data < 0)) stop("counts must be finite and non-negative")
if (any(as.matrix(count_data) != round(as.matrix(count_data)))) stop("peak counts must be integers")
counts <- as.matrix(count_data); storage.mode(counts) <- "integer"; rownames(counts) <- raw$peak_id

samples <- read.delim(samples_file, check.names = FALSE, stringsAsFactors = FALSE)
if (anyDuplicated(samples$sample_id) || !setequal(samples$sample_id, colnames(counts))) stop("sample metadata/count columns disagree")
samples <- samples[match(colnames(counts), samples$sample_id), , drop = FALSE]
rownames(samples) <- samples$sample_id

filter_spec <- spec$filter
if (identical(filter_spec$method, "none")) {
  keep <- rep(TRUE, nrow(counts))
} else if (identical(filter_spec$method, "minimum_count")) {
  keep <- rowSums(counts >= as.numeric(filter_spec$min_count)) >= as.integer(filter_spec$min_samples)
} else stop("unsupported peak filter")
filtered <- counts[keep, , drop = FALSE]
if (nrow(filtered) == 0) stop("no peaks passed the explicit filter")

formula_text <- spec$design$formula
formula <- as.formula(formula_text)
for (field in c(unlist(spec$design$covariates), spec$design$variable)) samples[[field]] <- factor(samples[[field]])
model_matrix <- model.matrix(formula, samples)
if (qr(model_matrix)$rank < ncol(model_matrix)) stop("rank-deficient design reached DESeq2")
dds <- DESeqDataSetFromMatrix(countData = filtered, colData = samples, design = formula)
dds <- DESeq(dds, quiet = TRUE)
saveRDS(dds, file.path(out_dir, "dds.rds"))

norm <- as.data.frame(counts(dds, normalized = TRUE), check.names = FALSE)
norm$peak_id <- rownames(norm)
norm <- merge(coordinates, norm, by = "peak_id", sort = FALSE)
write.table(norm, file.path(out_dir, "normalized_peak_counts.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
write.table(data.frame(peak_id = rownames(dds), dispersion = dispersions(dds)), file.path(out_dir, "dispersions.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
coefficients <- coef(dds)
write.table(data.frame(peak_id = rownames(coefficients), coefficients, check.names = FALSE), file.path(out_dir, "coefficients.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
statistics <- list(
  analysis_id = spec$analysis_id, model_id = spec$model_id, design = formula_text,
  samples = ncol(dds), peaks_before_filter = nrow(counts), peaks_after_filter = nrow(dds),
  filter = filter_spec, normalization = spec$normalization,
  size_factors = as.list(setNames(as.numeric(sizeFactors(dds)), colnames(dds))), status = "complete"
)
jsonlite::write_json(statistics, file.path(out_dir, "model_statistics.json"), auto_unbox = TRUE, pretty = TRUE)
