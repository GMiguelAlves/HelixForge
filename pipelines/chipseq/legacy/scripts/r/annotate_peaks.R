#!/usr/bin/env Rscript

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  out <- list()
  i <- 1
  while (i <= length(args)) {
    key <- sub("^--", "", args[[i]])
    value <- args[[i + 1]]
    out[[key]] <- value
    i <- i + 2
  }
  out
}

read_bed <- function(path, min_cols = 3) {
  if (!file.exists(path) || file.info(path)$size == 0) {
    return(data.frame())
  }
  x <- read.table(path, sep = "\t", header = FALSE, quote = "", comment.char = "", stringsAsFactors = FALSE)
  if (ncol(x) < min_cols) {
    return(data.frame())
  }
  names(x)[1:3] <- c("chrom", "start", "end")
  if (ncol(x) >= 4) names(x)[4] <- "feature_id"
  if (ncol(x) < 4) x$feature_id <- NA_character_
  x
}

open_table <- function(path, mode = "rt") {
  if (grepl("\\.gz$", path)) gzfile(path, mode) else file(path, mode)
}

read_table_safe <- function(path, header = TRUE) {
  if (!file.exists(path) || file.info(path)$size == 0) {
    return(data.frame())
  }
  con <- open_table(path, "rt")
  on.exit(close(con), add = TRUE)
  read.table(con, sep = "\t", header = header, quote = "", comment.char = "", stringsAsFactors = FALSE, check.names = FALSE)
}

write_table_safe <- function(x, path, header = TRUE) {
  con <- open_table(path, "wt")
  on.exit(close(con), add = TRUE)
  write.table(x, con, sep = "\t", quote = FALSE, row.names = FALSE, col.names = header)
}

overlap_first <- function(peaks, features) {
  hit <- rep(FALSE, nrow(peaks))
  gene <- rep(NA_character_, nrow(peaks))
  if (nrow(peaks) == 0 || nrow(features) == 0) {
    return(list(hit = hit, gene = gene))
  }
  by_chrom <- split(features, features$chrom)
  for (i in seq_len(nrow(peaks))) {
    f <- by_chrom[[peaks$chrom[[i]]]]
    if (is.null(f)) next
    idx <- which(f$start < peaks$end[[i]] & f$end > peaks$start[[i]])
    if (length(idx) > 0) {
      hit[[i]] <- TRUE
      gene[[i]] <- f$feature_id[[idx[[1]]]]
    }
  }
  list(hit = hit, gene = gene)
}

annotate_one <- function(peak_file, annotation_dir, out_file, functional_annotation = "") {
  peaks <- read_bed(peak_file, min_cols = 3)
  if (nrow(peaks) == 0) {
    write_table_safe(data.frame(), out_file)
    return(invisible(NULL))
  }
  peaks$peak_id <- paste(peaks$chrom, peaks$start, peaks$end, sep = ":")

  promoters <- read_bed(file.path(annotation_dir, "promoters.bed"))
  exons <- read_bed(file.path(annotation_dir, "exons.bed"))
  introns <- read_bed(file.path(annotation_dir, "introns.bed"))
  downstream <- read_bed(file.path(annotation_dir, "downstream.bed"))
  genes <- read_bed(file.path(annotation_dir, "genes.bed"))

  classes <- rep("intergenic", nrow(peaks))
  gene_id <- rep(NA_character_, nrow(peaks))

  for (item in list(
    list(name = "gene", bed = genes),
    list(name = "downstream", bed = downstream),
    list(name = "intron", bed = introns),
    list(name = "exon", bed = exons),
    list(name = "promoter", bed = promoters)
  )) {
    ov <- overlap_first(peaks, item$bed)
    idx <- which(ov$hit)
    classes[idx] <- item$name
    gene_id[idx] <- ov$gene[idx]
  }

  out <- data.frame(
    peak_id = peaks$peak_id,
    chrom = peaks$chrom,
    start = peaks$start,
    end = peaks$end,
    class = classes,
    gene_id = gene_id,
    stringsAsFactors = FALSE
  )

  if (!is.null(functional_annotation) && nzchar(functional_annotation) && file.exists(functional_annotation)) {
    fn <- read_table_safe(functional_annotation, header = TRUE)
    if ("gene_id" %in% names(fn)) {
      out <- merge(out, fn, by = "gene_id", all.x = TRUE, sort = FALSE)
    }
  }

  write_table_safe(out, out_file)
}

args <- parse_args()
required <- c("peaks-dir", "consensus-dir", "annotation-dir", "outdir")
missing <- required[!vapply(required, function(x) !is.null(args[[x]]) && nzchar(args[[x]]), logical(1))]
if (length(missing) > 0) {
  stop("Missing required argument(s): ", paste(missing, collapse = ", "))
}

dir.create(args[["outdir"]], recursive = TRUE, showWarnings = FALSE)
table_suffix <- if (!is.null(args[["table-suffix"]])) args[["table-suffix"]] else Sys.getenv("PIPELINE_TABLE_SUFFIX", unset = "")

peak_files <- c(
  list.files(args[["peaks-dir"]], pattern = "_peaks\\.(narrowPeak|broadPeak)$", recursive = TRUE, full.names = TRUE),
  list.files(args[["consensus-dir"]], pattern = "\\.consensus\\.bed$", recursive = FALSE, full.names = TRUE)
)
peak_files <- unique(peak_files[file.exists(peak_files)])

summary_rows <- list()
for (peak_file in peak_files) {
  name <- basename(peak_file)
  name <- sub("_peaks\\.(narrowPeak|broadPeak)$", "", name)
  name <- sub("\\.consensus\\.bed$", "", name)
  out_file <- file.path(args[["outdir"]], paste0(name, ".annotated.tsv", table_suffix))
  annotate_one(
    peak_file = peak_file,
    annotation_dir = args[["annotation-dir"]],
    out_file = out_file,
    functional_annotation = args[["functional-annotation"]]
  )
  x <- read_table_safe(out_file, header = TRUE)
  if (nrow(x) > 0) {
    tab <- as.data.frame(table(x$class), stringsAsFactors = FALSE)
    names(tab) <- c("class", "n")
    tab$peak_set <- name
    summary_rows[[length(summary_rows) + 1]] <- tab[, c("peak_set", "class", "n")]
  }
}

summary <- if (length(summary_rows) > 0) do.call(rbind, summary_rows) else data.frame(peak_set = character(), class = character(), n = integer())
write_table_safe(summary, file.path(args[["outdir"]], paste0("annotation_summary.tsv", table_suffix)))
