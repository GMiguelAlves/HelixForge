#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("The R package ggplot2 is required for visualization.")
  }
})

library(ggplot2)

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(flag, default = "") {
  idx <- match(flag, args)
  if (is.na(idx) || idx >= length(args)) {
    return(default)
  }
  args[[idx + 1]]
}

project_dir <- normalizePath(get_arg("--project-dir", "."), mustWork = FALSE)
outdir <- normalizePath(get_arg("--outdir", file.path(project_dir, "090-visualizations")), mustWork = FALSE)
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

manifest <- data.frame(figure = character(), status = character(), stringsAsFactors = FALSE)

add_manifest <- function(figure, status = "created") {
  manifest <<- rbind(manifest, data.frame(figure = figure, status = status, stringsAsFactors = FALSE))
}

read_tsv <- function(path) {
  if (!file.exists(path) || file.info(path)$size == 0) {
    return(data.frame(stringsAsFactors = FALSE))
  }
  con <- if (grepl("\\.gz$", path)) gzfile(path, "rt") else file(path, "rt")
  on.exit(close(con), add = TRUE)
  tryCatch(
    read.delim(
      con,
      sep = "\t",
      header = TRUE,
      quote = "",
      comment.char = "",
      check.names = FALSE,
      stringsAsFactors = FALSE
    ),
    error = function(e) {
      warning(sprintf("Could not read %s: %s", path, e$message))
      data.frame(stringsAsFactors = FALSE)
    }
  )
}

as_num <- function(x) {
  suppressWarnings(as.numeric(x))
}

safe_col <- function(df, name, default = "") {
  if (name %in% names(df)) {
    return(df[[name]])
  }
  rep(default, nrow(df))
}

trim_label <- function(x, n = 42) {
  x <- as.character(x)
  ifelse(nchar(x) > n, paste0(substr(x, 1, n - 3), "..."), x)
}

safe_filename <- function(x) {
  gsub("[^A-Za-z0-9_.-]+", "_", as.character(x))
}

stage_order <- c("adult", "eggs", "cercariae", "miracidia", "schistosomula", "sporocysts", "all_stages", "unknown")

clean_text <- function(x, default = "unknown") {
  if (length(x) == 0) {
    return(character())
  }
  y <- trimws(as.character(x))
  missing <- is.na(y)
  present <- !missing
  missing[present] <- y[present] == "" | tolower(y[present]) %in% c("na", "n/a", "nan", "none", "null", "not_available")
  y[missing] <- default
  y
}

canonical_stage_one <- function(x) {
  y <- clean_text(x, "unknown")
  raw <- tolower(y)
  tokens <- unlist(strsplit(gsub("[^a-z0-9]+", " ", raw), "\\s+"))
  tokens <- tokens[tokens != ""]
  if (length(tokens) == 0 || raw %in% c("unknown", "na", "n/a")) {
    return("unknown")
  }
  if (grepl("all[_ -]?stages|all[_ -]?projects|pooled|combined", raw) || any(tokens %in% c("all", "allstage", "allstages"))) {
    return("all_stages")
  }
  if (any(grepl("adult", tokens))) {
    return("adult")
  }
  if (any(grepl("egg", tokens))) {
    return("eggs")
  }
  if (any(grepl("cercar", tokens))) {
    return("cercariae")
  }
  if (any(grepl("miracid", tokens))) {
    return("miracidia")
  }
  if (any(grepl("schistosomul", tokens))) {
    return("schistosomula")
  }
  if (any(grepl("sporocyst", tokens))) {
    return("sporocysts")
  }
  "unknown"
}

canonical_stage <- function(x) {
  vapply(x, canonical_stage_one, character(1), USE.NAMES = FALSE)
}

stage_factor <- function(x) {
  x <- canonical_stage(x)
  factor(x, levels = unique(c(stage_order, x)))
}

canonical_mark_one <- function(x) {
  y <- clean_text(x, "unknown")
  lower <- tolower(y)
  if (grepl("(^|[^a-z0-9])(sm[-_ ]?)?hp1([^a-z0-9]|$)", lower) ||
      grepl("(^|[^a-z0-9])smp[-_]?179650([^a-z0-9]|$)", lower) ||
      grepl("(^|[^a-z0-9])(sm[-_ ]?)?cbx([^a-z0-9]|$)", lower)) {
    return("SmHP1")
  }
  known_marks <- c("SmHP1", "H3K27me3", "H3K4me3", "H3K9ac", "H3K9me3")
  for (mark in known_marks) {
    if (grepl(tolower(mark), lower, fixed = TRUE)) {
      return(mark)
    }
  }
  if (grepl("unknown", lower) || lower == "chip") {
    return("unknown_ChIP")
  }
  y <- sub("__all\\.tsv(\\.gz)?$", "", y, ignore.case = TRUE)
  y <- sub("\\.tsv(\\.gz)?$", "", y, ignore.case = TRUE)
  y
}

canonical_mark <- function(x) {
  vapply(x, canonical_mark_one, character(1), USE.NAMES = FALSE)
}

collapse_expression_by_stage <- function(expr) {
  if (nrow(expr) == 0) {
    return(expr)
  }
  expr$stage_or_condition <- canonical_stage(safe_col(expr, "stage_or_condition", safe_col(expr, "context", "unknown")))
  expr$mean_TPM <- as_num(safe_col(expr, "mean_TPM", safe_col(expr, "mean_expression", 0)))
  expr$n_samples <- as_num(safe_col(expr, "n_samples", 1))
  expr$n_samples[is.na(expr$n_samples) | expr$n_samples <= 0] <- 1
  expr <- expr[!is.na(expr$mean_TPM), , drop = FALSE]
  if (nrow(expr) == 0) {
    return(expr)
  }
  expr$weighted_TPM <- expr$mean_TPM * expr$n_samples
  collapsed <- aggregate(cbind(weighted_TPM, n_samples) ~ stage_or_condition, expr, sum, na.rm = TRUE)
  collapsed$mean_TPM <- collapsed$weighted_TPM / collapsed$n_samples
  collapsed$mean_log2TPM <- log2(collapsed$mean_TPM + 1)
  collapsed$stage_or_condition <- factor(collapsed$stage_or_condition, levels = unique(c(stage_order, collapsed$stage_or_condition)))
  collapsed
}

save_plot <- function(plot, stem, width = 8, height = 5) {
  outputs <- c("png", "pdf", "svg")
  for (ext in outputs) {
    rel <- gsub("\\\\", "/", paste0(stem, ".", ext))
    path <- file.path(outdir, paste0(stem, ".", ext))
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    ok <- tryCatch({
      if (ext == "png") {
        png(path, width = width, height = height, units = "in", res = 160)
      } else if (ext == "pdf") {
        pdf(path, width = width, height = height)
      } else {
        svg(path, width = width, height = height)
      }
      print(plot)
      dev.off()
      TRUE
    }, error = function(e) {
      if (dev.cur() > 1) {
        dev.off()
      }
      warning(sprintf("Could not write %s: %s", basename(path), e$message))
      FALSE
    })
    add_manifest(rel, if (ok) "created" else "error")
  }
}

save_gene_panel <- function(gid, width = 13.5, height = 12.5) {
  env_width <- suppressWarnings(as.numeric(Sys.getenv("GENE_PANEL_WIDTH", "")))
  env_height <- suppressWarnings(as.numeric(Sys.getenv("GENE_PANEL_HEIGHT", "")))
  if (!is.na(env_width) && env_width > 0) {
    width <- env_width
  }
  if (!is.na(env_height) && env_height > 0) {
    height <- env_height
  }

  panel_theme <- theme(
    plot.title = element_text(size = 11, margin = margin(b = 6)),
    axis.title = element_text(size = 9),
    axis.text = element_text(size = 8),
    legend.position = "right",
    legend.box = "vertical",
    legend.title = element_text(size = 8),
    legend.text = element_text(size = 7),
    legend.key.size = grid::unit(0.34, "cm"),
    plot.margin = margin(5, 8, 5, 5)
  )

  score_row <- if ("gene_id" %in% names(candidate_scores)) candidate_scores[candidate_scores$gene_id == gid, , drop = FALSE] else data.frame(stringsAsFactors = FALSE)
  score_row <- if (nrow(score_row) > 0) score_row[1, , drop = FALSE] else data.frame(stringsAsFactors = FALSE)
  ev <- if ("gene_id" %in% names(gene_mark_evidence)) gene_mark_evidence[gene_mark_evidence$gene_id == gid, , drop = FALSE] else data.frame(stringsAsFactors = FALSE)
  links_g <- if ("gene_id" %in% names(gene_mark_links)) gene_mark_links[gene_mark_links$gene_id == gid, , drop = FALSE] else data.frame(stringsAsFactors = FALSE)
  expr <- if ("gene_id" %in% names(rna_context)) rna_context[rna_context$gene_id == gid, , drop = FALSE] else data.frame(stringsAsFactors = FALSE)
  if (nrow(expr) == 0 && nrow(ev) > 0 && "rna_mean_TPM_in_stage" %in% names(ev)) {
    expr <- unique(data.frame(
      gene_id = gid,
      stage_or_condition = safe_col(ev, "stage_or_condition", ""),
      mean_TPM = safe_col(ev, "rna_mean_TPM_in_stage", ""),
      mean_log2TPM = log2(as_num(safe_col(ev, "rna_mean_TPM_in_stage", 0)) + 1),
      stringsAsFactors = FALSE
    ))
  }

  gene_name <- if (nrow(score_row) > 0 && "gene_name" %in% names(score_row) && score_row$gene_name[[1]] != "") {
    score_row$gene_name[[1]]
  } else if (nrow(ev) > 0 && "gene_name" %in% names(ev) && ev$gene_name[[1]] != "") {
    ev$gene_name[[1]]
  } else {
    gid
  }
  gene_label <- trim_label(ifelse(gene_name != gid, paste0(gene_name, " (", gid, ")"), gid), 70)
  score <- if (nrow(score_row) > 0 && "candidate_score" %in% names(score_row)) score_row$candidate_score[[1]] else ""
  klass <- if (nrow(score_row) > 0 && "integrative_class" %in% names(score_row)) score_row$integrative_class[[1]] else ""
  group <- if (nrow(score_row) > 0 && "machinery_group" %in% names(score_row)) score_row$machinery_group[[1]] else ""
  title <- paste0(gene_label, " | score=", score, " | ", klass, ifelse(group != "", paste0(" | ", group), ""))

  if (nrow(expr) > 0) {
    expr <- collapse_expression_by_stage(expr)
    if (nrow(expr) > 0) {
      p_expr <- ggplot(expr, aes(x = stage_or_condition, y = mean_TPM)) +
        geom_col(fill = "#2563eb", width = 0.7) +
        geom_point(aes(y = mean_TPM), color = "#111827", size = 1.8) +
        labs(title = "RNA-seq expression by life-cycle stage", x = NULL, y = "Mean TPM") +
        theme_integrative(10) +
        panel_theme +
        theme(axis.text.x = element_text(angle = 25, hjust = 1), legend.position = "none")
    } else {
      p_expr <- empty_plot("RNA-seq expression by life-cycle stage", "No numeric RNA-seq expression rows for this gene.")
    }
  } else {
    p_expr <- empty_plot("RNA-seq expression by life-cycle stage", "No expression-by-context rows for this gene.")
  }

  if (nrow(ev) > 0) {
    ev$stage_or_condition <- stage_factor(safe_col(ev, "stage_or_condition", "unknown"))
    ev$mark_or_factor <- canonical_mark(safe_col(ev, "mark_or_factor", "unknown"))
    ev$n_peaks <- as_num(safe_col(ev, "n_peaks", 0))
    ev$n_promoter_peaks <- as_num(safe_col(ev, "n_promoter_peaks", 0))
    ev$promoter_fraction <- ifelse(ev$n_peaks > 0, ev$n_promoter_peaks / ev$n_peaks, 0)
    p_chip <- ggplot(ev, aes(x = stage_or_condition, y = mark_or_factor)) +
      geom_point(aes(size = n_peaks, fill = promoter_fraction), shape = 21, color = "#111827", alpha = 0.85) +
      scale_fill_gradient(low = "#fef3c7", high = "#dc2626", limits = c(0, 1)) +
      scale_size_continuous(range = c(2.5, 9), name = "Peaks") +
      labs(title = "Linked ChIP-seq marks", x = NULL, y = "Mark", fill = "Promoter fraction") +
      theme_integrative(10) +
      panel_theme +
      theme(axis.text.x = element_text(angle = 25, hjust = 1))
  } else {
    p_chip <- empty_plot("Linked ChIP-seq marks", "No gene-mark-stage rows for this gene.")
  }

  if (nrow(links_g) > 0) {
    links_g$stage_or_condition <- canonical_stage(safe_col(links_g, "stage_or_condition", "unknown"))
    links_g$mark_or_factor <- canonical_mark(safe_col(links_g, "mark_or_factor", "unknown"))
    links_g$promoter_flag <- safe_col(links_g, "promoter_flag", "false")
    loc <- tolower(safe_col(links_g, "peak_location", ""))
    links_g$position_class <- ifelse(
      grepl("promoter|tss", loc) | links_g$promoter_flag == "true",
      "promoter/TSS",
      ifelse(
        grepl("exon|intron|gene_body|gene body|genic", loc),
        "gene body",
        ifelse(grepl("distal|intergenic|upstream|downstream", loc), "distal/intergenic", "other/annotated")
      )
    )
    pos_df <- aggregate(
      peak_id ~ stage_or_condition + mark_or_factor + position_class,
      links_g,
      length
    )
    names(pos_df)[names(pos_df) == "peak_id"] <- "n_peaks"
    pos_df$stage_or_condition <- factor(pos_df$stage_or_condition, levels = unique(c(stage_order, pos_df$stage_or_condition)))
    pos_df$position_class <- factor(pos_df$position_class, levels = c("promoter/TSS", "gene body", "distal/intergenic", "other/annotated"))
    p_pos <- ggplot(pos_df, aes(x = mark_or_factor, y = position_class, color = stage_or_condition)) +
      geom_point(aes(size = n_peaks), alpha = 0.85) +
      scale_size_continuous(range = c(2, 8), name = "Peaks") +
      labs(title = "Peak position classes", x = "Mark", y = "Position class", color = "Stage") +
      theme_integrative(10) +
      panel_theme +
      theme(axis.text.x = element_text(angle = 25, hjust = 1))
  } else {
    p_pos <- empty_plot("Peak position classes", "No peak-level rows for this gene.")
  }

  flags <- data.frame(
    evidence = c("Epigenetic machinery", "WGCNA", "Mfuzz", "DTU", "Splicing"),
    present = c(
      ifelse(nrow(score_row) > 0, safe_col(score_row, "is_epigenetic_machinery", "false")[[1]], "false"),
      ifelse(nrow(score_row) > 0, safe_col(score_row, "wgcna_hit", "false")[[1]], "false"),
      ifelse(nrow(score_row) > 0, safe_col(score_row, "mfuzz_hit", "false")[[1]], "false"),
      ifelse(nrow(score_row) > 0, safe_col(score_row, "dtu_hit", "false")[[1]], "false"),
      ifelse(nrow(score_row) > 0, safe_col(score_row, "splicing_hit", "false")[[1]], "false")
    ),
    stringsAsFactors = FALSE
  )
  flags$present <- tolower(flags$present) == "true"
  p_flags <- ggplot(flags, aes(x = "Evidence", y = evidence, fill = present)) +
    geom_tile(color = "white", linewidth = 0.7) +
    geom_text(aes(label = ifelse(present, "yes", "no")), color = "#111827", size = 3.4) +
    scale_fill_manual(values = c("FALSE" = "#e5e7eb", "TRUE" = "#16a34a"), guide = "none") +
    labs(title = "RNA/regulatory evidence flags", x = NULL, y = NULL) +
    theme_integrative(10) +
    panel_theme +
    theme(axis.text.x = element_blank(), axis.text.y = element_text(size = 8.5), panel.grid = element_blank(), legend.position = "none")

  stem <- file.path("gene_panels", paste0(safe_filename(gid), "_gene_panel"))
  rels <- character()
  for (ext in c("png", "pdf", "svg")) {
    rel <- gsub("\\\\", "/", paste0(stem, ".", ext))
    path <- file.path(outdir, paste0(stem, ".", ext))
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    ok <- tryCatch({
      if (ext == "png") {
        png(path, width = width, height = height, units = "in", res = 160)
      } else if (ext == "pdf") {
        pdf(path, width = width, height = height)
      } else {
        svg(path, width = width, height = height)
      }
      grid::grid.newpage()
      grid::grid.text(title, x = 0.035, y = 0.988, just = c("left", "top"), gp = grid::gpar(fontsize = 13, fontface = "bold", col = "#111827"))
      print(p_expr, vp = grid::viewport(x = 0.05, y = 0.755, width = 0.91, height = 0.205, just = c("left", "bottom")))
      print(p_chip, vp = grid::viewport(x = 0.05, y = 0.515, width = 0.91, height = 0.205, just = c("left", "bottom")))
      print(p_pos, vp = grid::viewport(x = 0.05, y = 0.275, width = 0.91, height = 0.205, just = c("left", "bottom")))
      print(p_flags, vp = grid::viewport(x = 0.05, y = 0.055, width = 0.91, height = 0.165, just = c("left", "bottom")))
      dev.off()
      TRUE
    }, error = function(e) {
      if (dev.cur() > 1) {
        dev.off()
      }
      warning(sprintf("Could not write %s: %s", basename(path), e$message))
      FALSE
    })
    add_manifest(rel, if (ok) "created" else "error")
    if (ok) {
      rels <- c(rels, rel)
    }
  }
  data.frame(
    gene_id = gid,
    gene_name = gene_name,
    candidate_score = score,
    integrative_class = klass,
    figure_png = gsub("\\\\", "/", paste0(stem, ".png")),
    stringsAsFactors = FALSE
  )
}

empty_plot <- function(title, message) {
  ggplot() +
    annotate("text", x = 0, y = 0.1, label = title, fontface = "bold", size = 5) +
    annotate("text", x = 0, y = -0.08, label = message, size = 3.5) +
    xlim(-1, 1) +
    ylim(-1, 1) +
    theme_void()
}

theme_integrative <- function(base_size = 11) {
  theme_minimal(base_size = base_size) +
    theme(
      plot.title = element_text(face = "bold", color = "#111827"),
      plot.subtitle = element_text(color = "#4b5563"),
      panel.grid.minor = element_blank(),
      axis.title = element_text(color = "#374151"),
      axis.text = element_text(color = "#374151"),
      strip.text = element_text(face = "bold", color = "#111827"),
      legend.position = "bottom",
      plot.margin = margin(10, 18, 10, 10)
    )
}

palette_marks <- c(
  "#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed",
  "#0f766e", "#db2777", "#64748b", "#0891b2", "#ea580c"
)

class_counts <- read_tsv(file.path(project_dir, "070-integrated-tables", "integrative_class_counts.tsv"))
candidate_scores <- read_tsv(file.path(project_dir, "080-candidate-scoring", "candidate_gene_scores.tsv"))
catalog <- read_tsv(file.path(project_dir, "030-id-harmonization", "epigenetic_machinery_catalog.tsv"))
chip_mark_stage <- read_tsv(file.path(project_dir, "060-chipseq-summary", "chip_mark_stage_metadata.tsv"))
rna_context <- read_tsv(file.path(project_dir, "050-rnaseq-summary", "rna_expression_by_context.tsv"))
gene_mark_summary <- read_tsv(file.path(project_dir, "070-integrated-tables", "gene_mark_stage_summary.tsv"))
gene_mark_links <- read_tsv(file.path(project_dir, "070-integrated-tables", "gene_mark_stage_links.tsv"))
stage_mark_comparison <- read_tsv(file.path(project_dir, "080-candidate-scoring", "stage_mark_comparison.tsv"))
gene_mark_evidence <- read_tsv(file.path(project_dir, "080-candidate-scoring", "ranked_gene_mark_stage_evidence.tsv"))
mark_enrichment <- read_tsv(file.path(project_dir, "080-candidate-scoring", "mark_enrichment_tests.tsv"))
gene_mark_correlations <- read_tsv(file.path(project_dir, "080-candidate-scoring", "gene_mark_stage_correlations.tsv"))

if (nrow(class_counts) > 0 && all(c("integrative_class", "n_genes") %in% names(class_counts))) {
  class_counts$n_genes <- as_num(class_counts$n_genes)
  p <- ggplot(class_counts, aes(x = reorder(integrative_class, n_genes), y = n_genes, fill = integrative_class)) +
    geom_col(width = 0.72, show.legend = FALSE) +
    coord_flip() +
    scale_fill_manual(values = rep(palette_marks, length.out = nrow(class_counts))) +
    labs(title = "Integrative classes", x = NULL, y = "Genes") +
    theme_integrative()
} else {
  p <- empty_plot("Integrative classes", "No integrated class table was found.")
}
save_plot(p, "barplot_integrative_classes", 8, 4.8)

if (nrow(candidate_scores) > 0 && "candidate_score" %in% names(candidate_scores)) {
  candidate_scores$candidate_score <- as_num(candidate_scores$candidate_score)
  candidate_scores <- candidate_scores[order(-candidate_scores$candidate_score), , drop = FALSE]
  top <- head(candidate_scores, 30)
  top$gene_label <- trim_label(ifelse(safe_col(top, "gene_name") != "", safe_col(top, "gene_name"), safe_col(top, "gene_id")))
  p <- ggplot(top, aes(x = reorder(gene_label, candidate_score), y = candidate_score)) +
    geom_col(fill = "#16a34a", width = 0.72) +
    coord_flip() +
    labs(title = "Top candidate genes", x = NULL, y = "Candidate score") +
    theme_integrative()
} else {
  p <- empty_plot("Top candidate genes", "No candidate scoring table was found.")
}
save_plot(p, "top_candidate_scores", 8.5, 6)

if (nrow(catalog) > 0) {
  group <- safe_col(catalog, "machinery_group", "unknown")
  groups <- as.data.frame(sort(table(group), decreasing = TRUE), stringsAsFactors = FALSE)
  names(groups) <- c("machinery_group", "n_genes")
  p <- ggplot(groups, aes(x = reorder(machinery_group, n_genes), y = n_genes)) +
    geom_col(fill = "#0f766e", width = 0.72) +
    coord_flip() +
    labs(title = "Epigenetic machinery catalog", x = NULL, y = "Genes") +
    theme_integrative()
} else {
  p <- empty_plot("Epigenetic machinery catalog", "No epigenetic machinery catalog was found.")
}
save_plot(p, "epigenetic_catalog_groups", 8, 5)

plot_heatmap <- function(df, row_col, col_col, value_col, title, fill_label, empty_message) {
  if (nrow(df) == 0 || !(row_col %in% names(df)) || !(col_col %in% names(df))) {
    return(empty_plot(title, empty_message))
  }
  if (value_col %in% names(df)) {
    value <- as_num(df[[value_col]])
  } else {
    value <- rep(1, nrow(df))
  }
  plot_df <- data.frame(row = canonical_mark(df[[row_col]]), col = canonical_stage(df[[col_col]]), value = value, stringsAsFactors = FALSE)
  plot_df <- aggregate(value ~ row + col, plot_df, sum, na.rm = TRUE)
  plot_df$col <- factor(plot_df$col, levels = unique(c(stage_order, plot_df$col)))
  ggplot(plot_df, aes(x = col, y = row, fill = value)) +
    geom_tile(color = "white", linewidth = 0.6) +
    geom_text(aes(label = value), size = 3, color = "#111827") +
    scale_fill_gradient(low = "#e0f2fe", high = "#075985") +
    labs(title = title, x = "Stage or condition", y = "Mark or factor", fill = fill_label) +
    theme_integrative() +
    theme(axis.text.x = element_text(angle = 35, hjust = 1))
}

p <- plot_heatmap(
  chip_mark_stage,
  "mark_or_factor",
  "stage_or_condition",
  "n_samples",
  "ChIP-seq marks by life-cycle stage",
  "Samples",
  "No ChIP mark-stage metadata was found."
)
save_plot(p, "chip_mark_stage_matrix", 8.5, 6)

p <- plot_heatmap(
  gene_mark_summary,
  "mark_or_factor",
  "stage_or_condition",
  "n_peaks",
  "Gene-mark-stage links",
  "Peaks",
  "No gene-mark-stage links were found."
)
save_plot(p, "gene_mark_stage_matrix", 8.5, 6)

if (nrow(stage_mark_comparison) > 0 && all(c("mark_or_factor", "stage_or_condition") %in% names(stage_mark_comparison))) {
  stage_mark_comparison$mark_or_factor <- canonical_mark(safe_col(stage_mark_comparison, "mark_or_factor", "unknown"))
  stage_mark_comparison$stage_or_condition <- stage_factor(safe_col(stage_mark_comparison, "stage_or_condition", "unknown"))
  stage_mark_comparison$n_deg_linked_genes <- as_num(safe_col(stage_mark_comparison, "n_deg_linked_genes", 0))
  stage_mark_comparison$n_epigenetic_machinery_genes <- as_num(safe_col(stage_mark_comparison, "n_epigenetic_machinery_genes", 0))
  stage_mark_comparison$n_wgcna_hits <- as_num(safe_col(stage_mark_comparison, "n_wgcna_hits", 0))
  stage_mark_comparison$n_mfuzz_hits <- as_num(safe_col(stage_mark_comparison, "n_mfuzz_hits", 0))
  stage_mark_comparison$n_dtu_hits <- as_num(safe_col(stage_mark_comparison, "n_dtu_hits", 0))
  stage_mark_comparison$n_splicing_hits <- as_num(safe_col(stage_mark_comparison, "n_splicing_hits", 0))
  stage_mark_comparison$integrated_evidence <- with(
    stage_mark_comparison,
    n_deg_linked_genes + n_epigenetic_machinery_genes + n_wgcna_hits + n_mfuzz_hits + n_dtu_hits + n_splicing_hits
  )
  p <- ggplot(stage_mark_comparison, aes(x = stage_or_condition, y = mark_or_factor, fill = integrated_evidence)) +
    geom_tile(color = "white", linewidth = 0.6) +
    geom_text(aes(label = integrated_evidence), size = 3, color = "#111827") +
    scale_fill_gradient(low = "#ecfeff", high = "#0f766e") +
    labs(
      title = "Integrated evidence by stage and mark",
      subtitle = "DE-linked genes + machinery + WGCNA/Mfuzz/DTU/splicing hits.",
      x = "Stage or condition",
      y = "Mark or factor",
      fill = "Evidence"
    ) +
    theme_integrative() +
    theme(axis.text.x = element_text(angle = 35, hjust = 1))
} else {
  p <- empty_plot("Integrated evidence by stage and mark", "Run scoring to populate stage-mark comparisons.")
}
save_plot(p, "stage_mark_integrated_evidence", 10.5, 6.2)

if (nrow(mark_enrichment) > 0 && all(c("target_set", "feature_scope", "mark_or_factor", "stage_or_condition") %in% names(mark_enrichment))) {
  enrich <- mark_enrichment
  enrich$mark_or_factor <- canonical_mark(safe_col(enrich, "mark_or_factor", "unknown"))
  raw_enrichment_stage <- clean_text(safe_col(enrich, "stage_or_condition", "unknown"))
  enrich$stage_or_condition <- canonical_stage(raw_enrichment_stage)
  enrich$stage_or_condition[raw_enrichment_stage == "all_observed_stages"] <- "all_observed_stages"
  enrich$feature_scope <- clean_text(safe_col(enrich, "feature_scope", "any_peak"))
  enrich$target_set <- clean_text(safe_col(enrich, "target_set", "target"))
  enrich$q_value <- as_num(safe_col(enrich, "q_value", 1))
  enrich$p_value <- as_num(safe_col(enrich, "p_value", 1))
  enrich$fold_enrichment <- as_num(safe_col(enrich, "fold_enrichment", 0))
  enrich$overlap_genes <- as_num(safe_col(enrich, "overlap_genes", 0))
  enrich <- enrich[!is.na(enrich$p_value) & enrich$overlap_genes > 0, , drop = FALSE]
  if (nrow(enrich) > 0) {
    enrich$score <- -log10(pmax(enrich$q_value, 1e-300))
    if (all(enrich$score == 0 | is.na(enrich$score))) {
      enrich$score <- -log10(pmax(enrich$p_value, 1e-300))
    }
    enrich$plot_label <- paste(enrich$target_set, enrich$feature_scope, enrich$mark_or_factor, enrich$stage_or_condition, sep = " | ")
    enrich <- enrich[order(-enrich$score, -enrich$fold_enrichment, -enrich$overlap_genes), , drop = FALSE]
    enrich <- head(enrich, 30)
    enrich$plot_label <- factor(enrich$plot_label, levels = rev(enrich$plot_label))
    p <- ggplot(enrich, aes(x = plot_label, y = score, fill = target_set)) +
      geom_col(width = 0.72) +
      geom_text(aes(label = paste0("n=", overlap_genes, "; FE=", round(fold_enrichment, 2))), hjust = -0.04, size = 2.7, color = "#111827") +
      coord_flip(clip = "off") +
      scale_fill_manual(values = c("#2563eb", "#16a34a", "#f59e0b", "#dc2626")) +
      labs(
        title = "Formal mark enrichment tests",
        subtitle = "DEG and epigenetic machinery gene sets tested against linked ChIP marks.",
        x = NULL,
        y = "-log10 adjusted p-value",
        fill = "Target set"
      ) +
      theme_integrative() +
      theme(plot.margin = margin(10, 70, 10, 10))
  } else {
    p <- empty_plot("Formal mark enrichment tests", "No DEG or machinery overlap with linked marks was available.")
  }
} else {
  p <- empty_plot("Formal mark enrichment tests", "Run the score step to create mark_enrichment_tests.tsv.")
}
save_plot(p, "mark_enrichment_tests", 11, 7)

if (nrow(gene_mark_correlations) > 0 && all(c("gene_id", "mark_or_factor", "max_abs_correlation") %in% names(gene_mark_correlations))) {
  corr <- gene_mark_correlations
  corr$max_abs_correlation <- as_num(safe_col(corr, "max_abs_correlation", NA))
  corr$n_stage_points <- as_num(safe_col(corr, "n_stage_points", 0))
  corr$mark_or_factor <- canonical_mark(safe_col(corr, "mark_or_factor", "unknown"))
  corr$correlation_direction <- clean_text(safe_col(corr, "correlation_direction", "unknown"))
  corr <- corr[!is.na(corr$max_abs_correlation) & corr$n_stage_points >= 2, , drop = FALSE]
  if (nrow(corr) > 0) {
    corr$gene_label <- trim_label(ifelse(safe_col(corr, "gene_name") != "" & safe_col(corr, "gene_name") != safe_col(corr, "gene_id"), paste0(safe_col(corr, "gene_name"), " (", safe_col(corr, "gene_id"), ")"), safe_col(corr, "gene_id")), 34)
    corr$plot_label <- paste(corr$gene_label, corr$mark_or_factor, sep = " | ")
    corr <- corr[order(-corr$max_abs_correlation, -as_num(safe_col(corr, "candidate_score", 0))), , drop = FALSE]
    corr <- head(corr, 30)
    corr$plot_label <- factor(corr$plot_label, levels = rev(corr$plot_label))
    p <- ggplot(corr, aes(x = plot_label, y = max_abs_correlation, fill = correlation_direction)) +
      geom_col(width = 0.72) +
      geom_text(aes(label = paste0("stages=", n_stage_points)), hjust = -0.06, size = 2.8, color = "#111827") +
      coord_flip(clip = "off") +
      scale_fill_manual(values = c("positive" = "#16a34a", "negative" = "#dc2626", "zero" = "#64748b", "unknown" = "#94a3b8"), drop = FALSE) +
      ylim(0, min(1.08, max(corr$max_abs_correlation, na.rm = TRUE) + 0.12)) +
      labs(
        title = "RNA-ChIP stage correlations",
        subtitle = "Per gene-mark pair; zeros are included only for stages where that mark was assayed.",
        x = NULL,
        y = "Maximum absolute correlation",
        fill = "Direction"
      ) +
      theme_integrative() +
      theme(plot.margin = margin(10, 70, 10, 10))
  } else {
    p <- empty_plot("RNA-ChIP stage correlations", "No gene-mark pairs had at least two assayed stages with RNA expression.")
  }
} else {
  p <- empty_plot("RNA-ChIP stage correlations", "Run the score step to create gene_mark_stage_correlations.tsv.")
}
save_plot(p, "gene_mark_stage_correlations", 10.5, 7)

gene_position_map_top_n <- suppressWarnings(as.integer(Sys.getenv("GENE_POSITION_MAP_TOP_N", "14")))
if (is.na(gene_position_map_top_n) || gene_position_map_top_n < 1) {
  gene_position_map_top_n <- 14
}
gene_position_map_width <- suppressWarnings(as.numeric(Sys.getenv("GENE_POSITION_MAP_WIDTH", "12")))
if (is.na(gene_position_map_width) || gene_position_map_width <= 0) {
  gene_position_map_width <- 12
}
gene_position_map_height <- suppressWarnings(as.numeric(Sys.getenv("GENE_POSITION_MAP_HEIGHT", "")))
gene_position_map_render_height <- gene_position_map_height
if (is.na(gene_position_map_render_height) || gene_position_map_render_height <= 0) {
  gene_position_map_render_height <- 6.8
}

if (nrow(gene_mark_links) > 0) {
  links <- gene_mark_links
  links$gene_id <- safe_col(links, "gene_id", "")

  keep_ids <- character()
  if (nrow(candidate_scores) > 0 && all(c("gene_id", "candidate_score") %in% names(candidate_scores))) {
    candidate_scores$candidate_score <- as_num(candidate_scores$candidate_score)
    ranked_ids <- candidate_scores$gene_id[order(-candidate_scores$candidate_score)]
    keep_ids <- ranked_ids[ranked_ids %in% unique(links$gene_id)]
  }
  if (length(keep_ids) == 0) {
    gene_counts <- sort(table(links$gene_id), decreasing = TRUE)
    keep_ids <- names(gene_counts)
  }
  keep_ids <- head(keep_ids, gene_position_map_top_n)
  links <- links[links$gene_id %in% keep_ids, , drop = FALSE]

  links$mark_or_factor <- canonical_mark(safe_col(links, "mark_or_factor", "unknown"))
  links$stage_or_condition <- canonical_stage(safe_col(links, "stage_or_condition", "unknown"))
  links$promoter_flag <- safe_col(links, "promoter_flag", "false")
  links$peak_location <- safe_col(links, "peak_location", "")
  links$peak_chrom <- safe_col(links, "peak_chrom", "")
  links$peak_start <- as_num(safe_col(links, "peak_start", NA))
  links$peak_end <- as_num(safe_col(links, "peak_end", NA))
  links$peak_midpoint <- as_num(safe_col(links, "peak_midpoint", NA))
  links$distance_to_tss <- as_num(safe_col(links, "distance_to_tss", NA))
  if (any(!(links$stage_or_condition %in% c("unknown", "all_stages")))) {
    links <- links[!(links$stage_or_condition %in% c("unknown", "all_stages")), , drop = FALSE]
  }
  links$gene_label <- ifelse(
    safe_col(links, "gene_name") != "" & safe_col(links, "gene_name") != safe_col(links, "gene_id"),
    paste0(safe_col(links, "gene_name"), " (", safe_col(links, "gene_id"), ")"),
    safe_col(links, "gene_id")
  )
  links$gene_label <- trim_label(links$gene_label, 38)

  label_by_gene <- links[!duplicated(links$gene_id), c("gene_id", "gene_label"), drop = FALSE]
  ordered_labels <- label_by_gene$gene_label[match(keep_ids, label_by_gene$gene_id)]
  ordered_labels <- ordered_labels[!is.na(ordered_labels)]
  links$gene_label <- factor(links$gene_label, levels = rev(ordered_labels))

  loc <- tolower(links$peak_location)
  links$position_class <- ifelse(
    grepl("promoter|tss", loc) | links$promoter_flag == "true",
    "promoter/TSS",
    ifelse(
      grepl("exon|intron|gene_body|gene body|genic", loc),
      "gene body",
      ifelse(grepl("distal|intergenic|upstream|downstream", loc), "distal/intergenic", "other/annotated")
    )
  )
  links$position_class <- factor(links$position_class, levels = c("promoter/TSS", "gene body", "distal/intergenic", "other/annotated"))
  links$stage_or_condition <- factor(links$stage_or_condition, levels = unique(c(stage_order, links$stage_or_condition)))
  plot_df <- aggregate(
    peak_id ~ gene_label + stage_or_condition + mark_or_factor + position_class + promoter_flag,
    links,
    length
  )
  names(plot_df)[names(plot_df) == "peak_id"] <- "n_peaks"

  if (nrow(plot_df) > 0) {
    shown_gene_count <- length(unique(as.character(plot_df$gene_label)))
    if (is.na(gene_position_map_height) || gene_position_map_height <= 0) {
      gene_position_map_render_height <- max(6.8, min(18, 3.8 + 0.28 * shown_gene_count))
    }
    p <- ggplot(plot_df, aes(x = position_class, y = gene_label, color = mark_or_factor)) +
      geom_point(aes(size = n_peaks, shape = promoter_flag), alpha = 0.86, position = position_jitter(width = 0.08, height = 0.08)) +
      facet_wrap(~stage_or_condition, nrow = 1) +
      scale_color_manual(values = rep(palette_marks, length.out = length(unique(plot_df$mark_or_factor)))) +
      scale_size_continuous(range = c(2, 7), breaks = c(1, 5, 20, 100), name = "Peaks") +
      labs(
        title = "Gene-position-mark associations",
        subtitle = paste0("Top ", shown_gene_count, " candidate genes; x = peak position class, color = epigenetic mark."),
        x = "Peak position class",
        y = "Gene",
        color = "Mark",
        shape = "Promoter"
      ) +
      theme_integrative() +
      theme(axis.text.x = element_text(angle = 30, hjust = 1))
  } else {
    p <- empty_plot("Gene-position-mark associations", "The link table exists, but no top candidate links were available.")
  }
} else {
  p <- empty_plot("Gene-position-mark associations", "Run integration after peak-gene mapping to populate this figure.")
}
save_plot(p, "gene_position_mark_map", gene_position_map_width, gene_position_map_render_height)

gene_panel_top_n <- suppressWarnings(as.integer(Sys.getenv("GENE_PANEL_TOP_N", "12")))
if (is.na(gene_panel_top_n)) {
  gene_panel_top_n <- 12
}
gene_panel_top_n <- max(0, gene_panel_top_n)
explicit_genes <- unlist(strsplit(Sys.getenv("GENE_PANEL_GENES", ""), "[,;[:space:]]+"))
explicit_genes <- explicit_genes[explicit_genes != ""]
panel_genes <- character()
if (nrow(candidate_scores) > 0 && all(c("gene_id", "candidate_score") %in% names(candidate_scores))) {
  candidate_scores$candidate_score <- as_num(candidate_scores$candidate_score)
  linked_ids <- unique(c(safe_col(gene_mark_links, "gene_id", ""), safe_col(gene_mark_evidence, "gene_id", "")))
  ranked <- candidate_scores$gene_id[order(-candidate_scores$candidate_score)]
  panel_genes <- ranked[ranked %in% linked_ids]
}
if (length(panel_genes) == 0 && nrow(gene_mark_evidence) > 0 && "gene_id" %in% names(gene_mark_evidence)) {
  panel_genes <- unique(gene_mark_evidence$gene_id)
}
panel_genes <- unique(c(explicit_genes, head(panel_genes, gene_panel_top_n)))
panel_genes <- panel_genes[panel_genes != ""]
panel_index <- data.frame(gene_id = character(), gene_name = character(), candidate_score = character(), integrative_class = character(), figure_png = character(), stringsAsFactors = FALSE)
if (length(panel_genes) > 0) {
  for (gid in panel_genes) {
    panel_index <- rbind(panel_index, save_gene_panel(gid))
  }
}
write.table(
  panel_index,
  file = file.path(outdir, "gene_panel_index.tsv"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE
)

workflow <- data.frame(
  xmin = c(0.05, 0.05, 0.38, 0.72),
  xmax = c(0.27, 0.27, 0.60, 0.94),
  ymin = c(0.60, 0.18, 0.39, 0.39),
  ymax = c(0.82, 0.40, 0.66, 0.66),
  title = c("RNA-seq", "ChIP-seq", "Integration", "Outputs"),
  body = c("expression + DEG", "marks + peaks", "gene x position x mark", "figures + HTML report"),
  fill = c("#dbeafe", "#dcfce7", "#fef3c7", "#ede9fe"),
  stringsAsFactors = FALSE
)

p <- ggplot() +
  geom_rect(
    data = workflow,
    aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax, fill = fill),
    color = "#374151",
    linewidth = 0.5,
    show.legend = FALSE
  ) +
  scale_fill_identity() +
  annotate("text", x = (workflow$xmin + workflow$xmax) / 2, y = workflow$ymax - 0.07, label = workflow$title, fontface = "bold", size = 4) +
  annotate("text", x = (workflow$xmin + workflow$xmax) / 2, y = workflow$ymin + 0.07, label = workflow$body, size = 3.2) +
  annotate("segment", x = 0.27, xend = 0.38, y = 0.71, yend = 0.54, arrow = grid::arrow(length = grid::unit(0.018, "npc")), color = "#374151") +
  annotate("segment", x = 0.27, xend = 0.38, y = 0.29, yend = 0.51, arrow = grid::arrow(length = grid::unit(0.018, "npc")), color = "#374151") +
  annotate("segment", x = 0.60, xend = 0.72, y = 0.525, yend = 0.525, arrow = grid::arrow(length = grid::unit(0.018, "npc")), color = "#374151") +
  labs(title = "Integrative analysis workflow") +
  xlim(0, 1) +
  ylim(0, 1) +
  theme_void() +
  theme(plot.title = element_text(face = "bold", hjust = 0.5, color = "#111827"))
save_plot(p, "integrative_workflow_overview", 9, 3.6)

write.table(
  manifest,
  file = file.path(outdir, "visualization_manifest.tsv"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE
)
