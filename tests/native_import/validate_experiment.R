#!/usr/bin/env Rscript

suppressPackageStartupMessages(library(SummarizedExperiment))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 5) {
  stop("usage: validate_experiment.R <rds> <counts> <abundance> <lengths> <samples>")
}

read_matrix <- function(path) {
  table <- read.delim(path, check.names = FALSE, stringsAsFactors = FALSE)
  rownames(table) <- table[[1]]
  as.matrix(table[, -1, drop = FALSE])
}

experiment <- readRDS(args[[1]])
expected_names <- c("counts", "abundance", "length")
if (!identical(assayNames(experiment), expected_names)) stop("unexpected assay names")

expected <- list(
  counts = read_matrix(args[[2]]),
  abundance = read_matrix(args[[3]]),
  length = read_matrix(args[[4]])
)
for (name in expected_names) {
  if (!isTRUE(all.equal(assay(experiment, name), expected[[name]], tolerance = 1e-8))) {
    stop("assay mismatch: ", name)
  }
}

samples <- read.delim(args[[5]], check.names = FALSE, stringsAsFactors = FALSE)
if (!identical(colnames(experiment), samples$import_id)) stop("colData sample order mismatch")
cat("assays=counts,abundance,length\n")
cat("genes=", nrow(experiment), "\n", sep = "")
cat("samples=", ncol(experiment), "\n", sep = "")
