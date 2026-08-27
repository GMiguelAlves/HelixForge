#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(tximport)
  library(DESeq2)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
arg <- function(flag) {
  index <- match(flag, args)
  if (is.na(index) || index == length(args)) stop("missing argument: ", flag)
  args[[index + 1]]
}
quant_dir <- normalizePath(arg("--quant-dir"), mustWork = TRUE)
tx2gene_file <- normalizePath(arg("--tx2gene"), mustWork = TRUE)
sample_file <- normalizePath(arg("--samples"), mustWork = TRUE)
output_dir <- arg("--output-dir")
if (dir.exists(output_dir) || file.exists(output_dir)) stop("output exists: ", output_dir)
dir.create(output_dir, recursive = TRUE)

stopifnot(
  identical(as.character(packageVersion("tximport")), "1.30.0"),
  identical(as.character(packageVersion("DESeq2")), "1.42.0")
)
samples <- read.delim(sample_file, stringsAsFactors = FALSE, check.names = FALSE)
required <- c("sample_id", "condition", "batch")
if (!all(required %in% colnames(samples))) stop("sample table lacks required fields")
if (nrow(samples) != 8L || anyDuplicated(samples$sample_id)) stop("expected eight unique samples")
condition_counts <- table(samples$condition)
if (!all(c("dexamethasone", "untreated") %in% names(condition_counts)) ||
    !identical(as.integer(condition_counts[c("dexamethasone", "untreated")]), c(4L, 4L))) {
  stop("expected four dexamethasone and four untreated samples")
}
donor_conditions <- split(samples$condition, samples$batch)
if (length(donor_conditions) != 4L ||
    any(vapply(donor_conditions, function(x) !setequal(x, c("untreated", "dexamethasone")), logical(1)))) {
  stop("each of four donors must contain both conditions")
}
samples$batch <- factor(samples$batch)
samples$condition <- factor(samples$condition, levels = c("untreated", "dexamethasone"))

files <- file.path(quant_dir, samples$sample_id, "quant.sf")
if (any(!file.exists(files))) stop("missing independent quant.sf: ", files[!file.exists(files)][1])
names(files) <- samples$sample_id
tx2gene <- read.delim(tx2gene_file, stringsAsFactors = FALSE, check.names = FALSE)
if (!identical(colnames(tx2gene), c("transcript_id", "gene_id"))) stop("invalid tx2gene columns")
if (anyDuplicated(tx2gene$transcript_id)) stop("duplicated transcript IDs in tx2gene")

txi <- tximport(files, type = "salmon", tx2gene = tx2gene,
                countsFromAbundance = "lengthScaledTPM",
                ignoreTxVersion = FALSE, ignoreAfterBar = FALSE)
write_matrix <- function(value, filename) {
  output <- data.frame(gene_id = rownames(value), value, check.names = FALSE)
  write.table(output, file.path(output_dir, filename), sep = "\t", quote = FALSE, row.names = FALSE)
}
write_matrix(txi$counts, "counts_matrix.tsv")
write_matrix(txi$abundance, "tpm_matrix.tsv")
write_matrix(txi$length, "length_matrix.tsv")

count_data <- round(txi$counts)
storage.mode(count_data) <- "integer"
col_data <- data.frame(
  batch = samples$batch,
  condition = samples$condition,
  row.names = samples$sample_id
)
design_matrix <- model.matrix(~ batch + condition, data = col_data)
if (qr(design_matrix)$rank != ncol(design_matrix)) stop("rank-deficient paired design")
dds <- DESeqDataSetFromMatrix(countData = count_data, colData = col_data,
                              design = ~ batch + condition)
dds <- DESeq(dds, test = "Wald", quiet = TRUE)
result <- as.data.frame(results(
  dds,
  contrast = c("condition", "dexamethasone", "untreated"),
  alpha = 0.05
))
result$gene_id <- rownames(result)
result <- result[, c("gene_id", setdiff(colnames(result), "gene_id")), drop = FALSE]
write.table(result, file.path(output_dir, "de_results.tsv"), sep = "\t", quote = FALSE,
            row.names = FALSE, na = "")
write.table(samples, file.path(output_dir, "sample_table.tsv"), sep = "\t", quote = FALSE,
            row.names = FALSE)
saveRDS(dds, file.path(output_dir, "dds.rds"), version = 3)
capture.output(sessionInfo(), file = file.path(output_dir, "sessionInfo.txt"))
write_json(list(
  status = "complete", samples = ncol(txi$counts), genes = nrow(txi$counts),
  design = "~ batch + condition",
  contrast = c("condition", "dexamethasone", "untreated"),
  countsFromAbundance = "lengthScaledTPM", ignoreTxVersion = FALSE,
  ignoreAfterBar = FALSE, alpha = 0.05,
  versions = list(R = as.character(getRversion()), tximport = as.character(packageVersion("tximport")),
                  DESeq2 = as.character(packageVersion("DESeq2")))
), file.path(output_dir, "analysis_manifest.json"), pretty = TRUE, auto_unbox = TRUE)
