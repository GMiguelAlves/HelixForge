	#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(DESeq2)
  library(ggplot2)
  library(pheatmap)
  library(rtracklayer)
  library(ggrepel)
})

args <- commandArgs(trailingOnly = TRUE)

get_arg <- function(flag, default = NULL) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) return(default)
  args[[idx + 1]]
}

split_csv <- function(x) {
  x <- trimws(x)
  if (is.null(x) || x == "") return(character())
  trimws(unlist(strsplit(x, ",")))
}

log_info <- function(msg) cat(format(Sys.time(), "[%Y-%m-%d %H:%M:%S]"), msg, "\n")

counts_file <- get_arg("--counts", "")
samples_file <- get_arg("--samples", "")
metadata_file <- get_arg("--metadata", "")
out_dir <- get_arg("--output-dir", file.path(Sys.getenv("DEG_DIR", unset = getwd()), "run"))
gff_file <- get_arg("--gff", Sys.getenv("REF_GFF3", unset = ""))
analysis_id <- get_arg("--analysis-id", basename(out_dir))
test_variables <- split_csv(get_arg("--test-variables", "condition,stage,sex,tissue,infection_mode"))
design_covariates <- split_csv(get_arg("--design-covariates", ""))
alpha <- as.numeric(get_arg("--alpha", "0.05"))
lfc_threshold <- as.numeric(get_arg("--lfc-threshold", "1"))
min_replicates <- as.integer(get_arg("--min-replicates", "2"))
min_total_count <- as.numeric(get_arg("--min-total-count", "10"))

required <- c(counts = counts_file, samples = samples_file, output_dir = out_dir)
missing_args <- names(required)[required == ""]
if (length(missing_args) > 0) {
  stop("[ERRO] Argumentos obrigatorios ausentes: ", paste(missing_args, collapse = ", "))
}

if (!file.exists(counts_file)) stop("[ERRO] Counts nao encontrado: ", counts_file)
if (!file.exists(samples_file)) stop("[ERRO] Tabela de amostras nao encontrada: ", samples_file)

dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out_dir, "contrasts"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out_dir, "plots"), recursive = TRUE, showWarnings = FALSE)

sanitize_value <- function(x) {
  x <- as.character(x)
  x[is.na(x) | x == ""] <- "unknown"
  x <- gsub("[^A-Za-z0-9_.-]+", "_", x)
  x <- gsub("^_+|_+$", "", x)
  x[x == ""] <- "unknown"
  x
}

make_import_id <- function(samples, count_names) {
  if ("import_id" %in% colnames(samples) && all(count_names %in% samples$import_id)) {
    return(samples$import_id)
  }
  if (all(c("dataset", "sample_id") %in% colnames(samples))) {
    combined <- paste(samples$dataset, samples$sample_id, sep = "__")
    if (all(count_names %in% combined)) return(combined)
  }
  if ("sample_id" %in% colnames(samples) && all(count_names %in% samples$sample_id)) {
    return(samples$sample_id)
  }
  if ("import_id" %in% colnames(samples)) return(samples$import_id)
  if ("sample_id" %in% colnames(samples)) return(samples$sample_id)
  stop("[ERRO] Nao foi possivel inferir import_id/sample_id na tabela de amostras.")
}

read_counts <- function(path) {
  counts <- read.delim(path, header = TRUE, sep = "\t", check.names = FALSE, stringsAsFactors = FALSE)
  if (ncol(counts) < 2) stop("[ERRO] Matriz de counts invalida: ", path)
  gene_ids <- counts[[1]]
  counts <- counts[, -1, drop = FALSE]
  rownames(counts) <- gene_ids
  counts[] <- lapply(counts, function(x) as.numeric(as.character(x)))
  if (anyNA(counts)) stop("[ERRO] Matriz de counts contem valores nao numericos.")
  counts <- round(as.matrix(counts))
  storage.mode(counts) <- "integer"
  counts[counts < 0] <- 0L
  counts
}

read_samples <- function(path, count_names) {
  samples <- read.delim(path, header = TRUE, sep = "\t", check.names = FALSE, stringsAsFactors = FALSE)
  samples$import_id <- make_import_id(samples, count_names)
  samples <- samples[!duplicated(samples$import_id), , drop = FALSE]
  missing_meta <- setdiff(count_names, samples$import_id)
  if (length(missing_meta) > 0) {
    stop("[ERRO] Colunas de counts sem metadata: ", paste(head(missing_meta, 20), collapse = ", "))
  }
  samples <- samples[match(count_names, samples$import_id), , drop = FALSE]
  rownames(samples) <- samples$import_id
  samples
}

load_annotations <- function(gff_file, genes) {
  fallback <- data.frame(gene_id = genes, gene_name = genes, biotype = "Unknown", stringsAsFactors = FALSE)
  if (gff_file == "" || !file.exists(gff_file)) return(fallback)
  log_info("Lendo anotacao GFF3...")
  gff <- rtracklayer::import(gff_file)
  gene_rows <- gff[gff$type == "gene"]
  if (length(gene_rows) == 0) return(fallback)
  gene_id <- as.character(gene_rows$ID)
  gene_id <- gsub("^gene:", "", gene_id)
  gene_id <- gsub("\\.[0-9]+$", "", gene_id)
  gene_name <- as.character(gene_rows$Name)
  gene_name[is.na(gene_name) | gene_name == ""] <- gene_id[is.na(gene_name) | gene_name == ""]
  biotype <- as.character(gene_rows$biotype)
  biotype[is.na(biotype) | biotype == ""] <- "Unknown"
  annotations <- data.frame(gene_id = gene_id, gene_name = gene_name, biotype = biotype, stringsAsFactors = FALSE)
  annotations <- annotations[!duplicated(annotations$gene_id), , drop = FALSE]
  annotations
}

annotate_results <- function(res_df, annotations) {
  out <- merge(res_df, annotations, by = "gene_id", all.x = TRUE, sort = FALSE)
  out$gene_name[is.na(out$gene_name) | out$gene_name == ""] <- out$gene_id[is.na(out$gene_name) | out$gene_name == ""]
  out$biotype[is.na(out$biotype) | out$biotype == ""] <- "Unknown"
  out
}

safe_filename <- function(x) sanitize_value(x)

write_tsv <- function(df, path) {
  write.table(df, path, sep = "\t", quote = FALSE, row.names = FALSE, na = "")
}

plot_pca <- function(vsd, coldata, color_var, shape_var, path) {
  assay_data <- assay(vsd)
  pca <- prcomp(t(assay_data), center = TRUE, scale. = FALSE)
  percent <- round(100 * (pca$sdev^2 / sum(pca$sdev^2)))
  plot_meta <- as.data.frame(coldata, check.names = FALSE)
  plot_meta$plot_import_id <- rownames(coldata)
  plot_meta <- plot_meta[, !duplicated(colnames(plot_meta)), drop = FALSE]
  plot_df <- data.frame(PC1 = pca$x[, 1], PC2 = pca$x[, 2], plot_meta, check.names = FALSE)
  plot_df <- plot_df[, !duplicated(colnames(plot_df)), drop = FALSE]
  color_var <- if (color_var %in% colnames(plot_df)) color_var else NULL
  shape_var <- if (shape_var %in% colnames(plot_df) && length(unique(plot_df[[shape_var]])) > 1) shape_var else NULL
  p <- ggplot(plot_df, aes(x = PC1, y = PC2)) +
    geom_point(size = 3, alpha = 0.85) +
    xlab(paste0("PC1: ", percent[1], "%")) +
    ylab(paste0("PC2: ", percent[2], "%")) +
    theme_minimal(base_size = 12)
  if (!is.null(color_var) && !is.null(shape_var)) {
    p <- ggplot(plot_df, aes(x = PC1, y = PC2, color = .data[[color_var]], shape = .data[[shape_var]])) +
      geom_point(size = 3, alpha = 0.85) +
      xlab(paste0("PC1: ", percent[1], "%")) +
      ylab(paste0("PC2: ", percent[2], "%")) +
      theme_minimal(base_size = 12) +
      labs(color = color_var, shape = shape_var)
  } else if (!is.null(color_var)) {
    p <- ggplot(plot_df, aes(x = PC1, y = PC2, color = .data[[color_var]])) +
      geom_point(size = 3, alpha = 0.85) +
      xlab(paste0("PC1: ", percent[1], "%")) +
      ylab(paste0("PC2: ", percent[2], "%")) +
      theme_minimal(base_size = 12) +
      labs(color = color_var)
  } else if (!is.null(shape_var)) {
    p <- ggplot(plot_df, aes(x = PC1, y = PC2, shape = .data[[shape_var]])) +
      geom_point(size = 3, alpha = 0.85) +
      xlab(paste0("PC1: ", percent[1], "%")) +
      ylab(paste0("PC2: ", percent[2], "%")) +
      theme_minimal(base_size = 12) +
      labs(shape = shape_var)
  }
  ggsave(path, p, width = 8, height = 6)
}

plot_volcano <- function(res_df, path, title, alpha, lfc_threshold) {
  df <- res_df[!is.na(res_df$padj) & !is.na(res_df$log2FoldChange), , drop = FALSE]
  if (nrow(df) == 0) return(FALSE)
  df$significant <- df$padj < alpha & abs(df$log2FoldChange) >= lfc_threshold
  top <- head(df[order(df$padj), , drop = FALSE], 10)
  p <- ggplot(df, aes(x = log2FoldChange, y = -log10(padj), color = significant)) +
    geom_point(alpha = 0.65, size = 1.4) +
    ggrepel::geom_text_repel(data = top, aes(label = gene_id), max.overlaps = 20, size = 3) +
    scale_color_manual(values = c("FALSE" = "gray65", "TRUE" = "red3")) +
    theme_minimal(base_size = 12) +
    labs(title = title, x = "log2 fold change", y = "-log10 adjusted p-value")
  ggsave(path, p, width = 8, height = 6)
  TRUE
}

log_info(paste("Analise:", analysis_id))
log_info(paste("Counts:", counts_file))
log_info(paste("Samples:", samples_file))

counts <- read_counts(counts_file)
samples <- read_samples(samples_file, colnames(counts))

if (metadata_file != "" && file.exists(metadata_file)) {
  metadata <- read.csv(metadata_file, stringsAsFactors = FALSE, check.names = FALSE)
  if (all(c("dataset", "sample_id") %in% colnames(metadata))) {
    metadata$import_id_combined <- paste(metadata$dataset, metadata$sample_id, sep = "__")
    metadata$import_id <- if ("import_id" %in% colnames(metadata)) metadata$import_id else metadata$sample_id
    key <- if (all(samples$import_id %in% metadata$import_id_combined)) "import_id_combined" else "import_id"
    extra <- metadata[match(samples$import_id, metadata[[key]]), , drop = FALSE]
    missing_cols <- setdiff(colnames(extra), colnames(samples))
    samples <- cbind(samples, extra[, missing_cols, drop = FALSE])
  }
}

samples[] <- lapply(samples, sanitize_value)
keep_genes <- rowSums(counts) > min_total_count
counts_filt <- counts[keep_genes, , drop = FALSE]
if (nrow(counts_filt) == 0) stop("[ERRO] Nenhum gene passou o filtro de contagem.")

annotations <- load_annotations(gff_file, rownames(counts_filt))

available_tests <- test_variables[test_variables %in% colnames(samples)]
if (length(available_tests) == 0) {
  stop("[ERRO] Nenhuma variavel de teste encontrada nas amostras: ", paste(test_variables, collapse = ", "))
}

summary_rows <- list()
all_results <- list()

for (test_var in available_tests) {
  level_counts <- table(samples[[test_var]])
  valid_levels <- names(level_counts[level_counts >= min_replicates])
  if (length(valid_levels) < 2) {
    summary_rows[[length(summary_rows) + 1]] <- data.frame(
      analysis_id = analysis_id,
      variable = test_var,
      contrast = "",
      status = "skipped_less_than_two_levels",
      n_samples = nrow(samples),
      n_genes = nrow(counts_filt),
      n_significant = NA_integer_,
      stringsAsFactors = FALSE
    )
    next
  }

  use_samples <- samples[[test_var]] %in% valid_levels
  coldata <- samples[use_samples, , drop = FALSE]
  countdata <- counts_filt[, rownames(coldata), drop = FALSE]
  coldata[[test_var]] <- factor(coldata[[test_var]], levels = valid_levels)

  covariates <- design_covariates[design_covariates %in% colnames(coldata)]
  covariates <- setdiff(covariates, test_var)
  if (length(covariates) > 0) {
    covariates <- covariates[vapply(covariates, function(v) length(unique(coldata[[v]])) > 1, logical(1))]
  }

  for (v in c(covariates, test_var)) {
    coldata[[v]] <- factor(coldata[[v]])
  }

  design_formula <- as.formula(paste("~", paste(c(covariates, test_var), collapse = " + ")))
  model <- model.matrix(design_formula, coldata)
  if (qr(model)$rank < ncol(model)) {
    summary_rows[[length(summary_rows) + 1]] <- data.frame(
      analysis_id = analysis_id,
      variable = test_var,
      contrast = "",
      status = "skipped_rank_deficient_design",
      n_samples = nrow(coldata),
      n_genes = nrow(countdata),
      n_significant = NA_integer_,
      stringsAsFactors = FALSE
    )
    next
  }

  log_info(paste("Rodando DESeq2 para", test_var, "design", deparse(design_formula)))
  dds <- DESeqDataSetFromMatrix(countData = countdata, colData = coldata, design = design_formula)
  dds <- DESeq(dds, quiet = TRUE)
  saveRDS(dds, file.path(out_dir, paste0("dds_", safe_filename(test_var), ".rds")))

  norm <- counts(dds, normalized = TRUE)
  write.table(norm, file.path(out_dir, paste0("normalized_counts_", safe_filename(test_var), ".tsv")),
              sep = "\t", quote = FALSE, col.names = NA)

  vsd <- tryCatch(vst(dds, blind = FALSE), error = function(e) varianceStabilizingTransformation(dds, blind = FALSE))
  shape_var <- if ("dataset" %in% colnames(coldata)) "dataset" else if ("batch" %in% colnames(coldata)) "batch" else NULL
  plot_pca(vsd, coldata, test_var, shape_var, file.path(out_dir, "plots", paste0("PCA_", safe_filename(test_var), ".png")))

  if (nrow(vsd) >= 2 && ncol(vsd) >= 2) {
    vars <- matrixStats::rowVars(assay(vsd))
    top_genes <- head(order(vars, decreasing = TRUE), min(100, length(vars)))
    mat <- t(scale(t(assay(vsd)[top_genes, , drop = FALSE])))
    ann_cols <- c(test_var, covariates)
    ann_cols <- ann_cols[ann_cols %in% colnames(coldata)]
    pheatmap(mat,
             annotation_col = as.data.frame(coldata[, ann_cols, drop = FALSE]),
             show_rownames = FALSE,
             clustering_method = "ward.D2",
             fontsize_col = 7,
             filename = file.path(out_dir, "plots", paste0("heatmap_top100_", safe_filename(test_var), ".png")))
  }

  level_pairs <- combn(valid_levels, 2, simplify = FALSE)
  for (pair in level_pairs) {
    level_a <- pair[[1]]
    level_b <- pair[[2]]
    contrast_name <- paste0(test_var, "__", level_a, "_vs_", level_b)
    res <- results(dds, contrast = c(test_var, level_a, level_b), alpha = alpha)
    res_df <- as.data.frame(res)
    res_df$gene_id <- rownames(res_df)
    res_df <- res_df[order(res_df$padj), c("gene_id", setdiff(colnames(res_df), "gene_id")), drop = FALSE]
    res_df <- annotate_results(res_df, annotations)
    res_df$analysis_id <- analysis_id
    res_df$variable <- test_var
    res_df$level_a <- level_a
    res_df$level_b <- level_b
    res_df$contrast <- contrast_name
    res_df <- res_df[, c("analysis_id", "variable", "contrast", "level_a", "level_b",
                         setdiff(colnames(res_df), c("analysis_id", "variable", "contrast", "level_a", "level_b"))),
                     drop = FALSE]

    contrast_path <- file.path(out_dir, "contrasts", paste0("DEG_", safe_filename(contrast_name), ".tsv"))
    write_tsv(res_df, contrast_path)
    plot_volcano(
      res_df,
      file.path(out_dir, "plots", paste0("volcano_", safe_filename(contrast_name), ".png")),
      contrast_name,
      alpha,
      lfc_threshold
    )

    n_sig <- sum(res_df$padj < alpha & abs(res_df$log2FoldChange) >= lfc_threshold, na.rm = TRUE)
    summary_rows[[length(summary_rows) + 1]] <- data.frame(
      analysis_id = analysis_id,
      variable = test_var,
      contrast = contrast_name,
      status = "ok",
      n_samples = nrow(coldata),
      n_genes = nrow(countdata),
      n_significant = n_sig,
      stringsAsFactors = FALSE
    )
    all_results[[length(all_results) + 1]] <- res_df
  }
}

summary_df <- do.call(rbind, summary_rows)
write_tsv(summary_df, file.path(out_dir, "deg_summary.tsv"))

if (length(all_results) > 0) {
  all_df <- do.call(rbind, all_results)
  write_tsv(all_df, file.path(out_dir, "DEGs_all_results.tsv"))
  sig_df <- all_df[!is.na(all_df$padj) & all_df$padj < alpha & abs(all_df$log2FoldChange) >= lfc_threshold, , drop = FALSE]
  write_tsv(sig_df, file.path(out_dir, "DEGs_significant.tsv"))
} else {
  write_tsv(data.frame(), file.path(out_dir, "DEGs_all_results.tsv"))
  write_tsv(data.frame(), file.path(out_dir, "DEGs_significant.tsv"))
}

sink(file.path(out_dir, "analysis_summary.txt"))
cat("Analise DEG - ", analysis_id, "\n", sep = "")
cat("==============================\n\n")
cat("Data: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n", sep = "")
cat("Counts: ", counts_file, "\n", sep = "")
cat("Samples: ", samples_file, "\n", sep = "")
cat("Genes antes do filtro: ", nrow(counts), "\n", sep = "")
cat("Genes depois do filtro: ", nrow(counts_filt), "\n", sep = "")
cat("Variaveis testadas: ", paste(available_tests, collapse = ", "), "\n", sep = "")
cat("Covariaveis de design: ", paste(design_covariates, collapse = ", "), "\n\n", sep = "")
print(summary_df)
sink()

log_info(paste("[OK] Analise DEG concluida:", out_dir))

