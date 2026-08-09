#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(DESeq2)
  library(ggplot2)
  library(pheatmap)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = NULL) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) return(default)
  args[[idx + 1]]
}

counts_file <- get_arg("--counts")
samples_file <- get_arg("--samples")
spec_file <- get_arg("--spec")
out_dir <- get_arg("--output-dir")
if (any(vapply(list(counts_file, samples_file, spec_file, out_dir), is.null, logical(1)))) {
  stop("--counts, --samples, --spec, and --output-dir are required")
}

spec <- jsonlite::fromJSON(spec_file, simplifyVector = FALSE)
if (!identical(spec$test, "wald")) stop("only the legacy Wald test is supported")
test_var <- spec$variable
covariates <- unlist(spec$covariates, use.names = FALSE)
valid_levels <- unlist(spec$valid_levels, use.names = FALSE)
non_integer_counts <- spec$parameters$non_integer_counts

dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out_dir, "plots"), recursive = TRUE, showWarnings = FALSE)

counts <- read.delim(counts_file, header = TRUE, sep = "\t", check.names = FALSE, stringsAsFactors = FALSE)
if (ncol(counts) < 2) stop("invalid count matrix")
gene_ids <- counts[[1]]
counts <- counts[, -1, drop = FALSE]
rownames(counts) <- gene_ids
counts[] <- lapply(counts, function(x) as.numeric(as.character(x)))
if (anyNA(counts)) stop("count matrix contains non-numeric values")
counts <- as.matrix(counts)
if (any(counts < 0)) stop("count matrix contains negative values")
if (any(counts != round(counts))) {
  if (!identical(non_integer_counts, "round")) {
    stop("fractional counts require parameters.non_integer_counts=round")
  }
  counts <- round(counts)
}
storage.mode(counts) <- "integer"

samples <- read.delim(samples_file, header = TRUE, sep = "\t", check.names = FALSE, stringsAsFactors = FALSE)
if (!"__rowname" %in% colnames(samples)) stop("validated sample metadata lacks __rowname")
rownames(samples) <- samples$`__rowname`
samples$`__rowname` <- NULL
samples <- samples[colnames(counts), , drop = FALSE]

filter_method <- spec$filter$method
if (identical(filter_method, "none")) {
  keep_genes <- rep(TRUE, nrow(counts))
} else if (identical(filter_method, "total_count")) {
  threshold <- as.numeric(spec$filter$threshold)
  totals <- rowSums(counts)
  keep_genes <- if (identical(spec$filter$operator, ">")) totals > threshold else totals >= threshold
} else {
  stop("unsupported gene filter method")
}
counts_filt <- counts[keep_genes, , drop = FALSE]
if (nrow(counts_filt) == 0) stop("no genes passed the configured expression filter")

use_samples <- samples[[test_var]] %in% valid_levels
coldata <- samples[use_samples, , drop = FALSE]
countdata <- counts_filt[, rownames(coldata), drop = FALSE]
coldata[[test_var]] <- factor(coldata[[test_var]], levels = valid_levels)
for (variable in c(covariates, test_var)) coldata[[variable]] <- factor(coldata[[variable]])

design_formula <- as.formula(spec$formula)
model <- model.matrix(design_formula, coldata)
if (qr(model)$rank < ncol(model)) stop("rank-deficient design reached DESeq2 provider")

dds <- DESeqDataSetFromMatrix(countData = countdata, colData = coldata, design = design_formula)
dds <- DESeq(dds, quiet = TRUE)
safe_var <- gsub("[^A-Za-z0-9_.-]+", "_", test_var)
saveRDS(dds, file.path(out_dir, paste0("dds_", safe_var, ".rds")))

norm <- counts(dds, normalized = TRUE)
write.table(norm, file.path(out_dir, paste0("normalized_counts_", safe_var, ".tsv")),
            sep = "\t", quote = FALSE, col.names = NA)
write.table(
  data.frame(gene_id = rownames(dds), dispersion = dispersions(dds), check.names = FALSE),
  file.path(out_dir, paste0("dispersions_", safe_var, ".tsv")),
  sep = "\t", quote = FALSE, row.names = FALSE
)
coefficient_matrix <- coef(dds)
write.table(
  data.frame(gene_id = rownames(coefficient_matrix), coefficient_matrix, check.names = FALSE),
  file.path(out_dir, paste0("coefficients_", safe_var, ".tsv")),
  sep = "\t", quote = FALSE, row.names = FALSE
)

vsd <- tryCatch(vst(dds, blind = FALSE), error = function(e) varianceStabilizingTransformation(dds, blind = FALSE))
assay_data <- assay(vsd)
pca <- prcomp(t(assay_data), center = TRUE, scale. = FALSE)
percent <- round(100 * (pca$sdev^2 / sum(pca$sdev^2)))
plot_meta <- as.data.frame(coldata, check.names = FALSE)
plot_meta$plot_import_id <- rownames(coldata)
plot_meta <- plot_meta[, !duplicated(colnames(plot_meta)), drop = FALSE]
plot_df <- data.frame(PC1 = pca$x[, 1], PC2 = pca$x[, 2], plot_meta, check.names = FALSE)
plot_df <- plot_df[, !duplicated(colnames(plot_df)), drop = FALSE]
shape_var <- if ("dataset" %in% colnames(plot_df) && length(unique(plot_df$dataset)) > 1) "dataset" else if ("batch" %in% colnames(plot_df) && length(unique(plot_df$batch)) > 1) "batch" else NULL
if (!is.null(shape_var)) {
  p <- ggplot(plot_df, aes(x = PC1, y = PC2, color = .data[[test_var]], shape = .data[[shape_var]])) +
    geom_point(size = 3, alpha = 0.85) +
    xlab(paste0("PC1: ", percent[1], "%")) + ylab(paste0("PC2: ", percent[2], "%")) +
    theme_minimal(base_size = 12) + labs(color = test_var, shape = shape_var)
} else {
  p <- ggplot(plot_df, aes(x = PC1, y = PC2, color = .data[[test_var]])) +
    geom_point(size = 3, alpha = 0.85) +
    xlab(paste0("PC1: ", percent[1], "%")) + ylab(paste0("PC2: ", percent[2], "%")) +
    theme_minimal(base_size = 12) + labs(color = test_var)
}
ggsave(file.path(out_dir, "plots", paste0("PCA_", safe_var, ".png")), p, width = 8, height = 6)

if (nrow(vsd) >= 2 && ncol(vsd) >= 2) {
  vars <- matrixStats::rowVars(assay(vsd))
  top_genes <- head(order(vars, decreasing = TRUE), min(100, length(vars)))
  mat <- t(scale(t(assay(vsd)[top_genes, , drop = FALSE])))
  ann_cols <- c(test_var, covariates)
  ann_cols <- ann_cols[ann_cols %in% colnames(coldata)]
  pheatmap(
    mat,
    annotation_col = as.data.frame(coldata[, ann_cols, drop = FALSE]),
    show_rownames = FALSE,
    clustering_method = "ward.D2",
    fontsize_col = 7,
    filename = file.path(out_dir, "plots", paste0("heatmap_top100_", safe_var, ".png"))
  )
}

statistics <- list(
  analysis_id = spec$analysis_id,
  model_id = spec$model_id,
  variable = test_var,
  design = spec$formula,
  valid_levels = valid_levels,
  covariates = covariates,
  samples = nrow(coldata),
  genes_before_filter = nrow(counts),
  genes_after_filter = nrow(counts_filt),
  filter = spec$filter,
  non_integer_counts = non_integer_counts,
  size_factors = as.list(setNames(as.numeric(sizeFactors(dds)), colnames(dds)))
)
jsonlite::write_json(statistics, file.path(out_dir, "model_statistics.json"), auto_unbox = TRUE, pretty = FALSE)
