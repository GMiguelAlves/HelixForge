#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(stringr)
  library(ggplot2)
  library(pheatmap)
})

args <- commandArgs(trailingOnly = TRUE)

get_arg <- function(flag, default = "") {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) return(default)
  args[[idx + 1]]
}

log_info <- function(msg) cat(format(Sys.time(), "[%Y-%m-%d %H:%M:%S]"), msg, "\n")

genes_file <- get_arg("--genes", "genes.txt")
tpm_file <- get_arg("--tpm", Sys.getenv("EXPRESSION_MATRIX_FILE", unset = file.path(Sys.getenv("QUANTIFICATION_DIR", unset = "../050-quantification"), "tpm_matrix.tsv")))
expression_unit <- get_arg("--expression-unit", Sys.getenv("EXPRESSION_UNIT", unset = "TPM"))
samples_file <- get_arg("--samples", file.path(Sys.getenv("QUANTIFICATION_DIR", unset = "../050-quantification"), "quant_samples.tsv"))
metadata_file <- get_arg("--metadata", Sys.getenv("METADATA_FINAL_NEW", unset = Sys.getenv("METADATA_FINAL", unset = "")))
deg_root <- get_arg("--deg-root", Sys.getenv("DEG_DIR", unset = "../060-deg-analysis"))
gff_file <- get_arg("--gff", Sys.getenv("GENE_REPORT_ANNOTATION_FILE", unset = Sys.getenv("REF_GFF3", unset = "")))
out_dir <- get_arg("--output-dir", file.path(Sys.getenv("GENE_REPORT_DIR", unset = "."), "results"))
report_title <- get_arg("--title", "Relatorio exploratorio de genes")
if (is.na(expression_unit) || expression_unit == "") expression_unit <- "TPM"
expression_log_label <- paste0("log2(", expression_unit, "+1)")
expression_mean_log_label <- paste0("Media log2(", expression_unit, "+1)")

if (!file.exists(genes_file)) stop("[ERRO] genes.txt nao encontrado: ", genes_file)
if (!file.exists(tpm_file)) stop("[ERRO] Matriz de expressao nao encontrada: ", tpm_file)
if (!file.exists(samples_file)) warning("[WARN] Tabela de amostras nao encontrada; inferindo metadata minima pelos nomes das colunas da matriz de expressao: ", samples_file)

dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out_dir, "tables"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out_dir, "plots"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out_dir, "genes"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out_dir, "groups"), recursive = TRUE, showWarnings = FALSE)

sanitize <- function(x) {
  x <- as.character(x)
  x[is.na(x) | x == ""] <- "unknown"
  x <- gsub("[^A-Za-z0-9_.-]+", "_", x)
  x <- gsub("^_+|_+$", "", x)
  x[x == ""] <- "unknown"
  x
}

write_tsv2 <- function(df, path) readr::write_tsv(df, path, na = "")

safe_div <- function(x, y) {
  ifelse(is.na(y) | y == 0, NA_real_, x / y)
}

split_env_csv <- function(name, default) {
  value <- Sys.getenv(name, unset = default)
  value <- trimws(value)
  if (value == "") return(character())
  trimws(unlist(strsplit(value, ",")))
}

life_stage_levels <- split_env_csv("LIFE_STAGE_LEVELS", "unknown")
if (!"unknown" %in% life_stage_levels) life_stage_levels <- c(life_stage_levels, "unknown")
stage_synonym_map <- split_env_csv("STAGE_SYNONYM_MAP", "")
organism_specific_reports <- Sys.getenv("ORGANISM_SPECIFIC_REPORTS", unset = "0") %in% c("1", "true", "TRUE", "yes", "YES")

normalize_stage_detail <- function(stage) {
  x <- tolower(trimws(as.character(stage)))
  x <- gsub("[[:space:]_-]+", "_", x)
  x[x %in% c("", "na", "nan", "none", "unknown", "not_available")] <- "unknown"
  if (length(stage_synonym_map) > 0) {
    for (rule in stage_synonym_map) {
      parts <- strsplit(rule, "=", fixed = TRUE)[[1]]
      if (length(parts) == 2 && nzchar(parts[1])) {
        x <- gsub(parts[1], parts[2], x)
      }
    }
  }
  x
}

classify_life_stage <- function(stage_detail) {
  x <- as.character(stage_detail)
  out <- rep("unknown", length(x))
  for (level in setdiff(life_stage_levels, "unknown")) {
    out[grepl(paste0("^", level, "($|_)"), x)] <- level
  }
  out
}

extract_stage_day <- function(stage_detail) {
  x <- as.character(stage_detail)
  day <- stringr::str_match(x, "(?:^|_)([0-9]+(?:\\.[0-9]+)?)(?:_)?d(?:$|_)")[, 2]
  suppressWarnings(as.numeric(day))
}

order_stage_details <- function(stage_detail) {
  details <- unique(as.character(stage_detail))
  stage_df <- tibble::tibble(
    stage = details,
    stage_class = classify_life_stage(details),
    stage_day = extract_stage_day(details)
  ) %>%
    dplyr::mutate(
      stage_class = factor(stage_class, levels = life_stage_levels),
      stage_day_sort = ifelse(is.na(stage_day), Inf, stage_day)
    ) %>%
    dplyr::arrange(stage_class, stage_day_sort, stage)
  stage_df$stage
}

clean_annotation_text <- function(x) {
  x <- as.character(x)
  x[is.na(x)] <- ""
  x <- tryCatch(utils::URLdecode(x), error = function(e) x)
  x <- gsub("[\t\r\n]+", " ", x)
  x <- gsub("\\s+", " ", x)
  trimws(x)
}

shorten_annotation_label <- function(x, max_chars = 80) {
  x <- clean_annotation_text(x)
  too_long <- nchar(x) > max_chars
  x[too_long] <- paste0(substr(x[too_long], 1, max_chars - 3), "...")
  x
}

is_uninformative_gene_name <- function(gene_name, gene_id) {
  gene_name <- clean_annotation_text(gene_name)
  gene_id <- as.character(gene_id)
  gene_name == "" |
    gene_name == gene_id |
    grepl("^gene:", gene_name)
}

make_gene_display_label <- function(gene_name, gene_id, description = "") {
  gene_name <- as.character(gene_name)
  gene_id <- as.character(gene_id)
  description <- as.character(description)
  label <- clean_annotation_text(gene_name)
  desc <- clean_annotation_text(description)
  use_desc <- is_uninformative_gene_name(label, gene_id) & desc != ""
  label[use_desc] <- desc[use_desc]
  label <- shorten_annotation_label(label)
  label[is.na(label) | label == ""] <- gene_id[is.na(label) | label == ""]
  ifelse(label == gene_id, gene_id, paste(label, gene_id, sep = " | "))
}

plot_or_skip <- function(label, plot_fun) {
  ok <- tryCatch(plot_fun(), error = function(e) {
    warning(label, ": ", e$message)
    FALSE
  })
  isTRUE(ok)
}

parse_gene_groups <- function(path) {
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  rows <- list()
  for (line in lines) {
    line <- trimws(line)
    if (line == "" || startsWith(line, "#")) next
    if (!grepl(":", line, fixed = TRUE)) {
      warning("Linha ignorada em genes.txt sem ':': ", line)
      next
    }
    parts <- strsplit(line, ":", fixed = TRUE)[[1]]
    group <- trimws(parts[1])
    genes <- trimws(unlist(strsplit(paste(parts[-1], collapse = ":"), "[,;]")))
    genes <- genes[genes != ""]
    if (length(genes) == 0) next
    rows[[length(rows) + 1]] <- data.frame(group = group, query = genes, stringsAsFactors = FALSE)
  }
  if (length(rows) == 0) stop("[ERRO] Nenhum gene encontrado em ", path)
  dplyr::bind_rows(rows) %>% dplyr::distinct(group, query, .keep_all = TRUE)
}

read_matrix <- function(path) {
  df <- readr::read_tsv(path, show_col_types = FALSE, col_types = cols(.default = col_character()))
  if (ncol(df) < 2) stop("[ERRO] Matriz invalida: ", path)
  colnames(df)[1] <- "gene_id"
  df %>% dplyr::mutate(dplyr::across(-gene_id, ~ suppressWarnings(as.numeric(.x))))
}

read_samples <- function(path, sample_names) {
  if (!file.exists(path)) {
    return(tibble::tibble(
      import_id = sample_names,
      sample_id = sample_names,
      dataset = "unknown"
    ))
  }
  samples <- readr::read_tsv(path, show_col_types = FALSE, col_types = cols(.default = col_character()))
  if (!"import_id" %in% colnames(samples)) {
    if (all(c("dataset", "sample_id") %in% colnames(samples))) {
      combined <- paste(samples$dataset, samples$sample_id, sep = "__")
      samples$import_id <- if (all(sample_names %in% combined)) combined else samples$sample_id
    } else if ("sample_id" %in% colnames(samples)) {
      samples$import_id <- samples$sample_id
    } else {
      stop("[ERRO] Tabela de amostras precisa de import_id ou sample_id.")
    }
  }
  samples <- samples %>% dplyr::distinct(import_id, .keep_all = TRUE)
  missing <- setdiff(sample_names, samples$import_id)
  if (length(missing) > 0) stop("[ERRO] Amostras sem metadata: ", paste(head(missing, 20), collapse = ", "))
  samples[match(sample_names, samples$import_id), , drop = FALSE]
}

empty_annotations <- function() {
  tibble::tibble(
    gene_id = character(),
    gene_name = character(),
    biotype = character(),
    description = character(),
    chromosome = character(),
    gene_start = integer(),
    gene_end = integer(),
    strand = character(),
    location = character()
  )
}

load_annotations <- function(gff_file) {
  if (gff_file == "" || !file.exists(gff_file)) {
    return(empty_annotations())
  }
  if (!requireNamespace("rtracklayer", quietly = TRUE)) {
    warning("Pacote rtracklayer nao encontrado; seguindo sem anotacao GFF3.")
    return(empty_annotations())
  }
  log_info("Lendo anotacao GFF/GTF...")
  gff <- rtracklayer::import(gff_file)
  genes <- as.data.frame(gff[gff$type == "gene"])
  if (nrow(genes) == 0) {
    return(empty_annotations())
  }
  pick_col <- function(df, names, default = NA_character_) {
    found <- intersect(names, colnames(df))
    if (length(found) == 0) return(rep(default, nrow(df)))
    as.character(df[[found[1]]])
  }
  gene_id <- pick_col(genes, c("ID", "gene_id"))
  gene_id <- gsub("^gene:", "", gene_id)
  gene_id <- gsub("\\.[0-9]+$", "", gene_id)
  gene_name <- pick_col(genes, c("gene_name", "symbol", "gene", "Name", "locus_tag"))
  gene_name[is.na(gene_name) | gene_name == ""] <- gene_id[is.na(gene_name) | gene_name == ""]
  biotype <- pick_col(genes, c("biotype", "gene_biotype", "type"), "Unknown")
  biotype[is.na(biotype) | biotype == ""] <- "Unknown"
  description <- clean_annotation_text(pick_col(genes, c("description", "product", "Note", "note"), ""))
  chromosome <- clean_annotation_text(pick_col(genes, c("seqnames", "seqid", "chromosome", "chr"), ""))
  gene_start <- suppressWarnings(as.integer(pick_col(genes, c("start"), NA_character_)))
  gene_end <- suppressWarnings(as.integer(pick_col(genes, c("end"), NA_character_)))
  strand <- clean_annotation_text(pick_col(genes, c("strand"), ""))
  strand[is.na(strand) | strand == "*" | strand == "."] <- ""
  location <- ifelse(
    chromosome != "" & !is.na(gene_start) & !is.na(gene_end),
    paste0(chromosome, ":", gene_start, "-", gene_end, ifelse(strand != "", paste0("(", strand, ")"), "")),
    ""
  )
  tibble::tibble(
    gene_id = gene_id,
    gene_name = gene_name,
    biotype = biotype,
    description = description,
    chromosome = chromosome,
    gene_start = gene_start,
    gene_end = gene_end,
    strand = strand,
    location = location
  ) %>%
    dplyr::distinct(gene_id, .keep_all = TRUE)
}

build_gene_catalog <- function(gene_groups, tpm, annotations) {
  tpm_genes <- tpm$gene_id
  ann <- annotations
  gene_groups %>%
    dplyr::rowwise() %>%
    dplyr::mutate(
      matched_gene_id = dplyr::case_when(
        query %in% tpm_genes ~ query,
        query %in% ann$gene_id ~ query,
        query %in% ann$gene_name ~ ann$gene_id[match(query, ann$gene_name)],
        TRUE ~ query
      ),
      match_type = dplyr::case_when(
        query %in% tpm_genes ~ "gene_id",
        query %in% ann$gene_id ~ "annotation_gene_id",
        query %in% ann$gene_name ~ "gene_name",
        TRUE ~ "unmatched"
      )
    ) %>%
    dplyr::ungroup() %>%
    dplyr::left_join(ann, by = c("matched_gene_id" = "gene_id")) %>%
    dplyr::mutate(
      gene_name = ifelse(is.na(gene_name) | gene_name == "", matched_gene_id, gene_name),
      biotype = ifelse(is.na(biotype) | biotype == "", "Unknown", biotype),
      description = clean_annotation_text(ifelse(is.na(description), "", description)),
      chromosome = ifelse(is.na(chromosome), "", chromosome),
      gene_start = suppressWarnings(as.integer(gene_start)),
      gene_end = suppressWarnings(as.integer(gene_end)),
      strand = ifelse(is.na(strand), "", strand),
      location = ifelse(is.na(location), "", location),
      found_in_tpm = matched_gene_id %in% tpm_genes,
      found_in_expression_matrix = found_in_tpm,
      gene_display_label = make_gene_display_label(gene_name, matched_gene_id, description),
      query_display = ifelse(query == matched_gene_id, gene_display_label, paste(query, "->", gene_display_label))
    ) %>%
    dplyr::distinct(group, query, matched_gene_id, .keep_all = TRUE)
}

gene_display_lookup <- function(gene_catalog) {
  gene_catalog %>%
    dplyr::select(matched_gene_id, gene_name, gene_display_label, description, group) %>%
    dplyr::mutate(
      matched_gene_id = as.character(matched_gene_id),
      gene_name = ifelse(is.na(gene_name) | gene_name == "", matched_gene_id, as.character(gene_name)),
      description = clean_annotation_text(ifelse(is.na(description), "", description)),
      gene_display_label = ifelse(is.na(gene_display_label) | gene_display_label == "", make_gene_display_label(gene_name, matched_gene_id, description), gene_display_label),
      group = ifelse(is.na(group) | group == "", "unknown", as.character(group))
    ) %>%
    dplyr::distinct() %>%
    dplyr::group_by(matched_gene_id) %>%
    dplyr::summarise(
      gene_name = paste(sort(unique(gene_name)), collapse = "; "),
      gene_display_label = paste(sort(unique(gene_display_label)), collapse = "; "),
      description = paste(sort(unique(description[description != ""])), collapse = "; "),
      group = paste(sort(unique(group)), collapse = "; "),
      .groups = "drop"
    )
}

annotate_deg_hits <- function(deg_hits, gene_catalog) {
  lookup <- gene_display_lookup(gene_catalog)
  deg_hits %>%
    dplyr::select(-dplyr::any_of(c("group", "gene_name", "gene_display_label", "description"))) %>%
    dplyr::left_join(lookup, by = c("gene_id" = "matched_gene_id")) %>%
    dplyr::relocate(dplyr::any_of(c("group", "gene_name", "gene_display_label", "description")), .after = gene_id)
}

left_join_gene_catalog <- function(x, y, by) {
  if ("relationship" %in% names(formals(dplyr::left_join))) {
    dplyr::left_join(x, y, by = by, relationship = "many-to-many")
  } else {
    suppressWarnings(dplyr::left_join(x, y, by = by))
  }
}

load_deg_hits <- function(deg_root, gene_catalog) {
  empty_deg <- tibble::tibble(
    gene_id = character(),
    contrast = character(),
    source_file = character(),
    result_dir = character(),
    deg_project = character(),
    deg_mode = character(),
    contrast_label = character(),
    padj_num = numeric(),
    log2FoldChange_num = numeric(),
    neg_log10_padj = numeric(),
    significant = logical()
  )
  files <- list.files(deg_root, pattern = "DEGs(_all)?_results.tsv$", recursive = TRUE, full.names = TRUE)
  if (length(files) == 0) return(empty_deg)
  rows <- lapply(files, function(path) {
    df <- tryCatch(readr::read_tsv(path, show_col_types = FALSE, col_types = cols(.default = col_character())), error = function(e) NULL)
    if (is.null(df) || !"gene_id" %in% colnames(df)) return(NULL)
    if (!"contrast" %in% colnames(df)) df$contrast <- tools::file_path_sans_ext(basename(path))
    rel <- gsub("\\\\", "/", sub(paste0("^", normalizePath(deg_root, winslash = "/", mustWork = FALSE), "/?"), "", normalizePath(path, winslash = "/", mustWork = FALSE)))
    result_dir <- dirname(rel)
    df %>%
      dplyr::filter(gene_id %in% gene_catalog$matched_gene_id) %>%
      dplyr::mutate(
        source_file = rel,
        result_dir = result_dir,
        deg_project = sub("/.*$", "", result_dir),
        deg_mode = ifelse(grepl("/", result_dir), sub("^.*/", "", result_dir), "unknown"),
        contrast_label = paste(result_dir, contrast, sep = " | "),
        padj_num = suppressWarnings(as.numeric(padj)),
        log2FoldChange_num = suppressWarnings(as.numeric(log2FoldChange)),
        neg_log10_padj = ifelse(!is.na(padj_num) & padj_num > 0, -log10(padj_num), NA_real_),
        significant = !is.na(padj_num) & padj_num < 0.05 & abs(log2FoldChange_num) >= 1
      )
  })
  out <- dplyr::bind_rows(rows)
  if (nrow(out) == 0) empty_deg else out
}

complete_sample_fields <- function(samples) {
  for (nm in c("dataset", "sample_id", "stage", "tissue", "sex", "condition", "batch")) {
    if (!nm %in% colnames(samples)) samples[[nm]] <- NA_character_
  }
  out <- samples %>%
    dplyr::mutate(
      dataset = ifelse(is.na(dataset) | dataset == "", "unknown", dataset),
      sample_id = ifelse(is.na(sample_id) | sample_id == "", import_id, sample_id),
      stage_raw = ifelse(is.na(stage) | stage == "", "unknown", as.character(stage)),
      stage = normalize_stage_detail(stage_raw),
      stage_class = classify_life_stage(stage),
      stage_class = ifelse(stage_class %in% life_stage_levels, stage_class, "unknown"),
      stage_class = factor(stage_class, levels = life_stage_levels),
      stage_day = extract_stage_day(stage),
      tissue = ifelse(is.na(tissue) | tissue == "", "unknown", tissue),
      sex = ifelse(is.na(sex) | sex == "", "unknown", sex),
      condition = ifelse(is.na(condition) | condition == "", "unknown", condition),
      batch = ifelse(is.na(batch) | batch == "", dataset, batch)
    )
  out$stage <- factor(out$stage, levels = order_stage_details(out$stage))
  out
}

make_expression_long <- function(tpm, samples, gene_catalog) {
  selected <- tpm %>% dplyr::filter(gene_id %in% gene_catalog$matched_gene_id)
  selected %>%
    tidyr::pivot_longer(-gene_id, names_to = "import_id", values_to = "TPM") %>%
    dplyr::left_join(samples, by = "import_id") %>%
    left_join_gene_catalog(gene_catalog %>% dplyr::select(group, query, matched_gene_id, gene_name, gene_display_label, description, biotype, chromosome, gene_start, gene_end, strand, location), by = c("gene_id" = "matched_gene_id")) %>%
    dplyr::mutate(
      TPM = as.numeric(TPM),
      log2TPM = log2(TPM + 1),
      gene_display_label = ifelse(is.na(gene_display_label) | gene_display_label == "", make_gene_display_label(gene_name, gene_id, description), gene_display_label),
      sample_label = paste(dataset, sample_id, sep = " | "),
      context_full = paste(dataset, batch, condition, stage, tissue, sex, sep = " | "),
      context_biology = paste(condition, stage, tissue, sex, sep = " | ")
    ) %>%
    dplyr::group_by(group, gene_id) %>%
    dplyr::mutate(z_log2TPM = as.numeric(scale(log2TPM))) %>%
    dplyr::ungroup()
}

summarise_expression <- function(expr_long) {
  expr_long %>%
    dplyr::group_by(group, gene_id, gene_name, gene_display_label, dataset, batch, condition, stage_class, stage_day, stage, tissue, sex) %>%
    dplyr::summarise(
      n = dplyr::n(),
      mean_TPM = mean(TPM, na.rm = TRUE),
      median_TPM = median(TPM, na.rm = TRUE),
      mean_log2TPM = mean(log2TPM, na.rm = TRUE),
      fraction_expressed = mean(TPM > 1, na.rm = TRUE),
      .groups = "drop"
    )
}

summarise_gene_descriptives <- function(expr_long, expr_summary, deg_hits, gene_catalog) {
  expr_gene <- expr_long %>%
    dplyr::group_by(group, gene_id, gene_name, gene_display_label) %>%
    dplyr::summarise(
      n_samples = dplyr::n(),
      mean_TPM = mean(TPM, na.rm = TRUE),
      median_TPM = median(TPM, na.rm = TRUE),
      max_TPM = max(TPM, na.rm = TRUE),
      fraction_samples_TPM_gt1 = mean(TPM > 1, na.rm = TRUE),
      n_datasets = dplyr::n_distinct(dataset),
      n_batches = dplyr::n_distinct(batch),
      n_tissues = dplyr::n_distinct(tissue),
      .groups = "drop"
    )
  dominant <- expr_summary %>%
    dplyr::mutate(context = paste(dataset, batch, condition, stage, tissue, sex, sep = " | ")) %>%
    dplyr::group_by(group, gene_id) %>%
    dplyr::arrange(dplyr::desc(mean_log2TPM), .by_group = TRUE) %>%
    dplyr::summarise(context_with_highest_expression = dplyr::first(context), .groups = "drop")
  deg_summary <- if (nrow(deg_hits) > 0) {
    deg_hits %>%
      dplyr::group_by(gene_id) %>%
      dplyr::summarise(
        n_deg_records = dplyr::n(),
        n_significant_contrasts = sum(significant, na.rm = TRUE),
        n_deg_projects = dplyr::n_distinct(deg_project),
        n_deg_modes = dplyr::n_distinct(deg_mode),
        max_abs_log2FC = suppressWarnings(max(abs(log2FoldChange_num), na.rm = TRUE)),
        min_padj = suppressWarnings(min(padj_num, na.rm = TRUE)),
        .groups = "drop"
      ) %>%
      dplyr::mutate(
        max_abs_log2FC = ifelse(is.infinite(max_abs_log2FC), NA_real_, max_abs_log2FC),
        min_padj = ifelse(is.infinite(min_padj), NA_real_, min_padj)
      )
  } else {
    tibble::tibble(
      gene_id = character(),
      n_deg_records = integer(),
      n_significant_contrasts = integer(),
      n_deg_projects = integer(),
      n_deg_modes = integer(),
      max_abs_log2FC = numeric(),
      min_padj = numeric()
    )
  }
  gene_catalog %>%
    dplyr::select(group, query, query_display, matched_gene_id, gene_name, gene_display_label, biotype, description, chromosome, gene_start, gene_end, strand, location, found_in_tpm, found_in_expression_matrix) %>%
    dplyr::rename(gene_id = matched_gene_id) %>%
    dplyr::left_join(expr_gene, by = c("group", "gene_id", "gene_name", "gene_display_label")) %>%
    dplyr::left_join(dominant, by = c("group", "gene_id")) %>%
    dplyr::left_join(deg_summary, by = "gene_id") %>%
    dplyr::mutate(
      dplyr::across(c(n_deg_records, n_significant_contrasts, n_deg_projects, n_deg_modes), ~ ifelse(is.na(.x), 0, .x))
    ) %>%
    dplyr::arrange(group, gene_name, gene_id)
}

heatmap_scale_mode <- function(mat) {
  if (nrow(mat) > 1 && ncol(mat) > 1) "row" else "none"
}

heatmap_has_signal <- function(mat) {
  values <- as.numeric(mat)
  values <- values[is.finite(values)]
  length(unique(values)) > 1
}

plot_expression_heatmap <- function(expr_summary, outfile, title = "Expressao media por contexto") {
  mat_df <- expr_summary %>%
    dplyr::arrange(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex, group, gene_display_label) %>%
    dplyr::mutate(
      label = paste(group, gene_display_label, sep = " | "),
      context = paste(dataset, batch, condition, stage, tissue, sex, sep = " | ")
    ) %>%
    dplyr::group_by(label, context) %>%
    dplyr::summarise(mean_log2TPM = mean(mean_log2TPM, na.rm = TRUE), .groups = "drop") %>%
    tidyr::pivot_wider(names_from = context, values_from = mean_log2TPM, values_fill = 0)
  if (nrow(mat_df) == 0 || ncol(mat_df) < 2) return(FALSE)
  mat <- as.matrix(mat_df[, -1, drop = FALSE])
  rownames(mat) <- mat_df$label
  if (!heatmap_has_signal(mat)) return(FALSE)
  pheatmap::pheatmap(mat, scale = heatmap_scale_mode(mat), border_color = NA,
                     cluster_rows = nrow(mat) > 1,
                     cluster_cols = ncol(mat) > 1,
                     fontsize_row = 7, fontsize_col = 6,
                     main = title, filename = outfile,
                     width = 14, height = max(5, min(18, nrow(mat) * 0.32 + 3)))
  TRUE
}

plot_expression_dotplot <- function(expr_summary, outfile, title = "Expressao media e fracao expressa") {
  df <- expr_summary %>%
    dplyr::arrange(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex, group, gene_display_label) %>%
    dplyr::mutate(
      context = paste(dataset, batch, condition, stage, tissue, sex, sep = " | "),
      gene_label = paste(group, gene_display_label, sep = " | ")
    )
  if (nrow(df) == 0) return(FALSE)
  p <- ggplot(df, aes(x = context, y = gene_label)) +
    geom_point(aes(size = fraction_expressed, color = mean_log2TPM), alpha = 0.85) +
    scale_color_viridis_c(option = "C") +
    theme_bw(base_size = 9) +
    theme(axis.text.x = element_text(angle = 55, hjust = 1), panel.grid.major.y = element_line(color = "gray92")) +
    labs(title = title, x = "Projeto | batch | condicao | estagio | tecido | sexo", y = "Grupo | gene | ID",
         color = expression_mean_log_label, size = paste0("Frac. ", expression_unit, ">1"))
  ggsave(outfile, p, width = 15, height = max(5, min(18, length(unique(df$gene_label)) * 0.32 + 3)), dpi = 300)
  TRUE
}

plot_tissue_sex_heatmap <- function(expr_summary, outfile, title = "Padroes por tecido e sexo") {
  mat_df <- expr_summary %>%
    dplyr::arrange(tissue, sex, stage_class, stage_day, stage, group, gene_display_label) %>%
    dplyr::mutate(context = paste(tissue, sex, sep = " | "),
                  label = paste(group, gene_display_label, sep = " | ")) %>%
    dplyr::group_by(label, context) %>%
    dplyr::summarise(mean_log2TPM = mean(mean_log2TPM, na.rm = TRUE), .groups = "drop") %>%
    tidyr::pivot_wider(names_from = context, values_from = mean_log2TPM, values_fill = 0)
  if (nrow(mat_df) == 0 || ncol(mat_df) < 2) return(FALSE)
  mat <- as.matrix(mat_df[, -1, drop = FALSE])
  rownames(mat) <- mat_df$label
  if (!heatmap_has_signal(mat)) return(FALSE)
  pheatmap::pheatmap(mat, scale = heatmap_scale_mode(mat), border_color = NA,
                     cluster_rows = nrow(mat) > 1,
                     cluster_cols = ncol(mat) > 1,
                     fontsize_row = 7, fontsize_col = 8,
                     main = title, filename = outfile,
                     width = 11, height = max(5, min(18, nrow(mat) * 0.32 + 3)))
  TRUE
}

plot_batch_project_boxplot <- function(expr_long, outfile, title = "Expressao por projeto e batch") {
  if (nrow(expr_long) == 0) return(FALSE)
  df <- expr_long %>% dplyr::mutate(gene_label = paste(group, gene_display_label, sep = " | "))
  p <- ggplot(df, aes(x = batch, y = log2TPM, fill = dataset)) +
    geom_boxplot(outlier.shape = NA, alpha = 0.7) +
    geom_jitter(aes(color = dataset), width = 0.18, alpha = 0.35, size = 1) +
    facet_wrap(~ gene_label, scales = "free_y") +
    theme_bw(base_size = 9) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = title, x = "Batch", y = expression_log_label, fill = "Projeto", color = "Projeto")
  ggsave(outfile, p, width = 14, height = max(6, min(18, length(unique(df$gene_label)) * 1.15 + 3)), dpi = 300)
  TRUE
}

plot_group_sample_heatmap <- function(expr_long, outfile, title = "Amostras individuais") {
  mat_df <- expr_long %>%
    dplyr::mutate(
      gene_label = gene_display_label,
      sample_label = paste(dataset, batch, condition, stage, tissue, sex, sample_id, sep = " | ")
    ) %>%
    dplyr::group_by(gene_label, sample_label) %>%
    dplyr::summarise(log2TPM = mean(log2TPM, na.rm = TRUE), .groups = "drop") %>%
    tidyr::pivot_wider(names_from = sample_label, values_from = log2TPM, values_fill = 0)
  if (nrow(mat_df) == 0 || ncol(mat_df) < 2) return(FALSE)
  mat <- as.matrix(mat_df[, -1, drop = FALSE])
  rownames(mat) <- mat_df$gene_label
  if (!heatmap_has_signal(mat)) return(FALSE)
  pheatmap::pheatmap(mat, scale = heatmap_scale_mode(mat), border_color = NA,
                     cluster_rows = nrow(mat) > 1,
                     cluster_cols = ncol(mat) > 1,
                     fontsize_row = 7, fontsize_col = 5,
                     main = title, filename = outfile,
                     width = 16, height = max(5, min(16, nrow(mat) * 0.35 + 3)))
  TRUE
}

expression_matrix_by_gene <- function(expr_long, include_group = TRUE) {
  mat_df <- expr_long %>%
    dplyr::mutate(gene_label = if (include_group) paste(group, gene_display_label, sep = " | ") else gene_display_label) %>%
    dplyr::group_by(gene_label, import_id) %>%
    dplyr::summarise(log2TPM = mean(log2TPM, na.rm = TRUE), .groups = "drop") %>%
    tidyr::pivot_wider(names_from = import_id, values_from = log2TPM, values_fill = 0)
  if (nrow(mat_df) == 0 || ncol(mat_df) < 2) return(NULL)
  mat <- as.matrix(mat_df[, -1, drop = FALSE])
  rownames(mat) <- mat_df$gene_label
  mat
}

sample_annotation_for_matrix <- function(expr_long, sample_ids) {
  ann <- expr_long %>%
    dplyr::distinct(import_id, dataset, batch, condition, stage, tissue, sex) %>%
    dplyr::filter(import_id %in% sample_ids)
  ann <- ann[match(sample_ids, ann$import_id), , drop = FALSE]
  ann <- as.data.frame(ann[, c("dataset", "batch", "condition", "stage", "tissue", "sex"), drop = FALSE])
  rownames(ann) <- sample_ids
  ann
}

plot_annotated_sample_heatmap <- function(expr_long, outfile, title = "Heatmap gene x amostra anotado") {
  mat <- expression_matrix_by_gene(expr_long, include_group = TRUE)
  if (is.null(mat) || nrow(mat) < 1 || ncol(mat) < 2) return(FALSE)
  if (!heatmap_has_signal(mat)) return(FALSE)
  ann_col <- sample_annotation_for_matrix(expr_long, colnames(mat))
  pheatmap::pheatmap(mat, scale = heatmap_scale_mode(mat), border_color = NA,
                     cluster_rows = nrow(mat) > 1,
                     cluster_cols = ncol(mat) > 1,
                     annotation_col = ann_col,
                     show_colnames = FALSE,
                     fontsize_row = 7,
                     main = title,
                     filename = outfile,
                     width = 15, height = max(5, min(18, nrow(mat) * 0.32 + 4)))
  TRUE
}

plot_gene_correlation <- function(expr_long, outfile, title = "Correlacao entre genes") {
  mat <- expression_matrix_by_gene(expr_long, include_group = TRUE)
  if (is.null(mat) || nrow(mat) < 2 || ncol(mat) < 3) return(FALSE)
  keep <- apply(mat, 1, stats::sd, na.rm = TRUE) > 0
  mat <- mat[keep, , drop = FALSE]
  if (nrow(mat) < 2) return(FALSE)
  cor_mat <- stats::cor(t(mat), use = "pairwise.complete.obs", method = "spearman")
  pheatmap::pheatmap(cor_mat, border_color = NA,
                     color = colorRampPalette(c("#2166ac", "white", "#b2182b"))(101),
                     breaks = seq(-1, 1, length.out = 102),
                     fontsize_row = 7, fontsize_col = 7,
                     main = title,
                     filename = outfile,
                     width = max(6, min(16, nrow(cor_mat) * 0.28 + 4)),
                     height = max(6, min(16, nrow(cor_mat) * 0.28 + 4)))
  TRUE
}

sample_scores_long <- function(expr_long, method = c("pca", "mds")) {
  method <- match.arg(method)
  mat <- expression_matrix_by_gene(expr_long, include_group = TRUE)
  if (is.null(mat) || nrow(mat) < 2 || ncol(mat) < 3) return(tibble::tibble())
  keep <- apply(mat, 1, stats::sd, na.rm = TRUE) > 0
  mat <- mat[keep, , drop = FALSE]
  if (nrow(mat) < 2) return(tibble::tibble())
  sample_mat <- t(mat)
  if (method == "pca") {
    pc <- stats::prcomp(sample_mat, center = TRUE, scale. = TRUE)
    coords <- as.data.frame(pc$x[, 1:2, drop = FALSE])
    names(coords) <- c("Dim1", "Dim2")
    variance <- round(100 * (pc$sdev^2 / sum(pc$sdev^2))[1:2], 1)
    axis_labels <- c(paste0("PC1 (", variance[1], "%)"), paste0("PC2 (", variance[2], "%)"))
  } else {
    d <- stats::dist(sample_mat)
    coords <- as.data.frame(stats::cmdscale(d, k = 2))
    names(coords) <- c("Dim1", "Dim2")
    axis_labels <- c("MDS1", "MDS2")
  }
  coords$import_id <- rownames(sample_mat)
  ann <- expr_long %>% dplyr::distinct(import_id, dataset, batch, condition, stage, tissue, sex)
  coords <- coords %>% dplyr::left_join(ann, by = "import_id")
  vars <- c("dataset", "batch", "condition", "stage", "tissue", "sex")
  out <- dplyr::bind_rows(lapply(vars, function(v) {
    coords %>%
      dplyr::mutate(variable = v, value = as.character(.data[[v]])) %>%
      dplyr::select(import_id, Dim1, Dim2, variable, value)
  }))
  attr(out, "axis_labels") <- axis_labels
  out
}

plot_sample_ordination <- function(expr_long, outfile, method = c("pca", "mds"), title = "Ordenacao de amostras") {
  method <- match.arg(method)
  df <- sample_scores_long(expr_long, method = method)
  if (nrow(df) == 0) return(FALSE)
  axis_labels <- attr(df, "axis_labels")
  p <- ggplot(df, aes(x = Dim1, y = Dim2, color = value)) +
    geom_point(size = 2.2, alpha = 0.9) +
    facet_wrap(~ variable, scales = "free") +
    theme_bw(base_size = 10) +
    labs(title = title, x = axis_labels[1], y = axis_labels[2], color = "Valor")
  ggsave(outfile, p, width = 12, height = 8, dpi = 300)
  TRUE
}

plot_ovary_testis_panel <- function(expr_summary, outfile, title = "Ovario versus testiculo") {
  if (!organism_specific_reports) return(FALSE)
  df <- expr_summary %>%
    dplyr::filter(tissue %in% c("ovary", "testis")) %>%
    dplyr::group_by(group, gene_display_label, dataset, stage, sex, tissue) %>%
    dplyr::summarise(mean_log2TPM = mean(mean_log2TPM, na.rm = TRUE), .groups = "drop") %>%
    tidyr::pivot_wider(names_from = tissue, values_from = mean_log2TPM)
  if (nrow(df) == 0 || !all(c("ovary", "testis") %in% colnames(df))) return(FALSE)
  df <- df %>%
    dplyr::mutate(
      ovary = dplyr::coalesce(ovary, 0),
      testis = dplyr::coalesce(testis, 0),
      ovary_minus_testis = ovary - testis,
      gene_label = paste(group, gene_display_label, sep = " | ")
    )
  p <- ggplot(df, aes(x = testis, y = ovary, color = ovary_minus_testis)) +
    geom_abline(slope = 1, intercept = 0, linetype = "dashed", color = "gray55") +
    geom_point(alpha = 0.85, size = 2) +
    geom_text(aes(label = gene_display_label), check_overlap = TRUE, size = 2.4, vjust = -0.7) +
    facet_grid(dataset ~ sex) +
    scale_color_gradient2(low = "#2166ac", mid = "white", high = "#b2182b") +
    theme_bw(base_size = 9) +
    labs(title = title, x = paste0("Testiculo: media ", expression_log_label), y = paste0("Ovario: media ", expression_log_label), color = "Ovario - testiculo")
  ggsave(outfile, p, width = 12, height = max(5, min(14, length(unique(df$dataset)) * 2.2 + 3)), dpi = 300)
  TRUE
}

plot_group_aggregate_profile <- function(expr_long, outfile, title = "Perfil agregado por grupo") {
  df <- expr_long %>%
    dplyr::group_by(group, dataset, batch, condition, stage_class, stage_day, stage, tissue, sex) %>%
    dplyr::summarise(mean_z_log2TPM = mean(z_log2TPM, na.rm = TRUE), .groups = "drop") %>%
    dplyr::arrange(group, dataset, batch, condition, stage_class, stage_day, stage, tissue, sex)
  if (nrow(df) == 0) return(FALSE)
  line_df <- df %>%
    dplyr::group_by(group, dataset, batch, condition, tissue, sex) %>%
    dplyr::filter(dplyr::n_distinct(stage) > 1) %>%
    dplyr::ungroup()
  p <- ggplot(df, aes(x = stage, y = mean_z_log2TPM, color = condition, shape = sex,
                      group = interaction(dataset, batch, condition, tissue, sex))) +
    geom_hline(yintercept = 0, color = "gray75", linewidth = 0.3) +
    geom_point(size = 2) +
    facet_grid(group + dataset ~ tissue, scales = "free_x", space = "free_x") +
    theme_bw(base_size = 9) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = title, x = "Estagio detalhado", y = paste0("Media z-score ", expression_log_label), color = "Condicao", shape = "Sexo")
  if (nrow(line_df) > 0) p <- p + geom_line(data = line_df, alpha = 0.7)
  ggsave(outfile, p, width = 14, height = max(6, min(18, length(unique(df$group)) * length(unique(df$dataset)) * 1.8 + 3)), dpi = 300)
  TRUE
}

plot_deg_direction_summary <- function(deg_hits, gene_catalog, outfile, title = "Direcao DEG por contraste") {
  if (nrow(deg_hits) == 0) return(FALSE)
  lookup <- gene_display_lookup(gene_catalog)
  df <- deg_hits %>%
    dplyr::left_join(lookup, by = c("gene_id" = "matched_gene_id")) %>%
    dplyr::mutate(
      gene_label = paste(group, gene_display_label, sep = " | "),
      direction = dplyr::case_when(
        significant & log2FoldChange_num > 0 ~ "up",
        significant & log2FoldChange_num < 0 ~ "down",
        TRUE ~ "not_sig"
      )
    )
  if (nrow(df) == 0) return(FALSE)
  if (length(unique(df$contrast_label)) > 90) {
    keep <- df %>%
      dplyr::group_by(contrast_label) %>%
      dplyr::summarise(best = suppressWarnings(min(padj_num, na.rm = TRUE)), .groups = "drop") %>%
      dplyr::arrange(best) %>%
      utils::head(90) %>%
      dplyr::pull(contrast_label)
    df <- df %>% dplyr::filter(contrast_label %in% keep)
  }
  p <- ggplot(df, aes(x = contrast_label, y = gene_label, fill = direction)) +
    geom_tile(color = "white", linewidth = 0.2) +
    scale_fill_manual(values = c("up" = "#b2182b", "down" = "#2166ac", "not_sig" = "gray88")) +
    theme_bw(base_size = 8) +
    theme(axis.text.x = element_text(angle = 60, hjust = 1), panel.grid = element_blank()) +
    labs(title = title, x = "Projeto/modo | contraste", y = "Gene", fill = "Direcao")
  ggsave(outfile, p, width = 15, height = max(5, min(18, length(unique(df$gene_label)) * 0.35 + 3)), dpi = 300)
  TRUE
}

plot_deg_heatmap <- function(deg_hits, gene_catalog, outfile, title = "log2FC em contrastes DEG") {
  if (nrow(deg_hits) == 0) return(FALSE)
  gene_lookup <- gene_display_lookup(gene_catalog)
  df <- deg_hits %>%
    dplyr::group_by(gene_id, contrast_label) %>%
    dplyr::summarise(log2FoldChange_num = mean(log2FoldChange_num, na.rm = TRUE), .groups = "drop") %>%
    tidyr::pivot_wider(names_from = contrast_label, values_from = log2FoldChange_num, values_fill = 0) %>%
    dplyr::left_join(gene_lookup, by = c("gene_id" = "matched_gene_id")) %>%
    dplyr::mutate(label = paste(group, gene_display_label, sep = " | "))
  if (nrow(df) == 0 || ncol(df) <= 4) return(FALSE)
  mat <- as.matrix(df[, setdiff(colnames(df), c("gene_id", "gene_name", "gene_display_label", "description", "group", "label")), drop = FALSE])
  rownames(mat) <- df$label
  if (!heatmap_has_signal(mat)) return(FALSE)
  pheatmap::pheatmap(mat, color = colorRampPalette(c("#2166ac", "white", "#b2182b"))(101),
                     cluster_rows = nrow(mat) > 1,
                     cluster_cols = ncol(mat) > 1,
                     border_color = NA, fontsize_row = 7, fontsize_col = 6,
                     main = title, filename = outfile,
                     width = 14, height = max(5, min(16, nrow(mat) * 0.32 + 3)))
  TRUE
}

plot_deg_context_tile <- function(deg_hits, gene_catalog, outfile, title = "Presenca DEG por contraste/projeto") {
  if (nrow(deg_hits) == 0) return(FALSE)
  gene_lookup <- gene_display_lookup(gene_catalog)
  df <- deg_hits %>%
    dplyr::left_join(gene_lookup, by = c("gene_id" = "matched_gene_id")) %>%
    dplyr::mutate(
      gene_label = paste(group, gene_display_label, sep = " | "),
      sig_label = ifelse(significant, "significativo", "nao_significativo")
    )
  if (nrow(df) == 0) return(FALSE)
  if (length(unique(df$contrast_label)) > 90) {
    keep <- df %>%
      dplyr::group_by(contrast_label) %>%
      dplyr::summarise(best = suppressWarnings(min(padj_num, na.rm = TRUE)), .groups = "drop") %>%
      dplyr::arrange(best) %>%
      utils::head(90) %>%
      dplyr::pull(contrast_label)
    df <- df %>% dplyr::filter(contrast_label %in% keep)
  }
  p <- ggplot(df, aes(x = contrast_label, y = gene_label, fill = log2FoldChange_num, alpha = sig_label)) +
    geom_tile(color = "white", linewidth = 0.2) +
    scale_fill_gradient2(low = "#2166ac", mid = "white", high = "#b2182b", na.value = "gray90") +
    scale_alpha_manual(values = c("significativo" = 1, "nao_significativo" = 0.35)) +
    theme_bw(base_size = 8) +
    theme(axis.text.x = element_text(angle = 60, hjust = 1), panel.grid = element_blank()) +
    labs(title = title, x = "Projeto/modo | contraste", y = "Gene", fill = "log2FC", alpha = "")
  ggsave(outfile, p, width = 15, height = max(5, min(18, length(unique(df$gene_label)) * 0.35 + 3)), dpi = 300)
  TRUE
}

plot_gene_expression_boxplot <- function(df, outfile, label) {
  p <- ggplot(df, aes(x = interaction(tissue, sex, drop = TRUE), y = log2TPM, fill = condition)) +
    geom_boxplot(outlier.shape = NA, alpha = 0.7) +
    geom_jitter(aes(color = batch), width = 0.18, alpha = 0.55, size = 1.5) +
    facet_grid(dataset ~ stage, scales = "free_x", space = "free_x") +
    theme_bw(base_size = 10) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = label, x = "Tecido.sexo", y = expression_log_label, fill = "Condicao", color = "Batch")
  ggsave(outfile, p, width = 13, height = 8, dpi = 300)
  TRUE
}

plot_gene_batch_boxplot <- function(df, outfile, label) {
  p <- ggplot(df, aes(x = batch, y = log2TPM, fill = dataset)) +
    geom_boxplot(outlier.shape = NA, alpha = 0.7) +
    geom_jitter(aes(color = condition), width = 0.18, alpha = 0.55, size = 1.5) +
    facet_grid(tissue ~ sex, scales = "free_y") +
    theme_bw(base_size = 10) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = paste("Batch/projeto:", label), x = "Batch", y = expression_log_label, fill = "Projeto", color = "Condicao")
  ggsave(outfile, p, width = 13, height = 8, dpi = 300)
  TRUE
}

plot_gene_profile_line <- function(df, outfile, label) {
  profile_df <- df %>%
    dplyr::group_by(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex) %>%
    dplyr::summarise(mean_log2TPM = mean(log2TPM, na.rm = TRUE), .groups = "drop")
  line_df <- profile_df %>%
    dplyr::group_by(dataset, batch, condition, tissue, sex) %>%
    dplyr::filter(dplyr::n_distinct(stage) > 1) %>%
    dplyr::ungroup()
  p <- ggplot(profile_df, aes(x = stage, y = mean_log2TPM, color = condition, shape = sex,
                              group = interaction(dataset, batch, condition, tissue, sex))) +
    geom_point(size = 2) +
    facet_grid(dataset + batch ~ tissue, scales = "free_x", space = "free_x") +
    theme_bw(base_size = 9) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = paste("Perfil medio:", label), x = "Estagio", y = expression_mean_log_label, color = "Condicao", shape = "Sexo")
  if (nrow(line_df) > 0) p <- p + geom_line(data = line_df, alpha = 0.75)
  ggsave(outfile, p, width = 14, height = 9, dpi = 300)
  TRUE
}

plot_gene_sample_tile <- function(df, outfile, label) {
  tile_df <- df %>%
    dplyr::mutate(sample_context = paste(dataset, batch, condition, stage, tissue, sex, sample_id, sep = " | ")) %>%
    dplyr::arrange(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex, sample_id)
  p <- ggplot(tile_df, aes(x = sample_context, y = gene_display_label, fill = log2TPM)) +
    geom_tile(color = "white") +
    scale_fill_viridis_c(option = "C") +
    theme_bw(base_size = 8) +
    theme(axis.text.x = element_text(angle = 60, hjust = 1), panel.grid = element_blank()) +
    labs(title = paste("Expressao por amostra:", label), x = "Amostra", y = "", fill = expression_log_label)
  ggsave(outfile, p, width = 15, height = 3.8, dpi = 300)
  TRUE
}

plot_gene_deg_lollipop <- function(deg_df, outfile, label) {
  if (nrow(deg_df) == 0) return(FALSE)
  df <- deg_df %>%
    dplyr::mutate(contrast_display = paste(deg_project, deg_mode, contrast, sep = " | ")) %>%
    dplyr::arrange(log2FoldChange_num)
  if (nrow(df) > 80) {
    df <- df %>%
      dplyr::arrange(padj_num) %>%
      utils::head(80) %>%
      dplyr::arrange(log2FoldChange_num)
  }
  p <- ggplot(df, aes(x = log2FoldChange_num, y = reorder(contrast_display, log2FoldChange_num), color = significant)) +
    geom_vline(xintercept = 0, linetype = "dashed", color = "gray55") +
    geom_segment(aes(x = 0, xend = log2FoldChange_num, yend = contrast_display), linewidth = 0.35) +
    geom_point(aes(size = neg_log10_padj), alpha = 0.85) +
    scale_color_manual(values = c("FALSE" = "gray55", "TRUE" = "#b2182b")) +
    theme_bw(base_size = 8) +
    labs(title = paste("DEG:", label), x = "log2FC", y = "Contraste", color = "Significativo", size = "-log10(padj)")
  ggsave(outfile, p, width = 11, height = max(5, min(18, nrow(df) * 0.25 + 3)), dpi = 300)
  TRUE
}

plot_gene_deg_scatter <- function(deg_df, outfile, label) {
  if (nrow(deg_df) == 0) return(FALSE)
  p <- ggplot(deg_df, aes(x = log2FoldChange_num, y = neg_log10_padj, color = significant, shape = deg_project)) +
    geom_vline(xintercept = c(-1, 1), linetype = "dashed", color = "gray70") +
    geom_hline(yintercept = -log10(0.05), linetype = "dashed", color = "gray70") +
    geom_point(size = 2.4, alpha = 0.85) +
    facet_wrap(~ deg_mode) +
    scale_color_manual(values = c("FALSE" = "gray55", "TRUE" = "#b2182b")) +
    theme_bw(base_size = 10) +
    labs(title = paste("Contrastes DEG:", label), x = "log2FC", y = "-log10(padj)", color = "Significativo", shape = "Projeto")
  ggsave(outfile, p, width = 10, height = 6, dpi = 300)
  TRUE
}

plot_group_outputs <- function(expr_long, expr_summary, deg_hits, gene_catalog, out_dir) {
  groups <- unique(expr_long$group)
  for (grp in groups) {
    group_dir <- file.path(out_dir, "groups", sanitize(grp))
    dir.create(group_dir, recursive = TRUE, showWarnings = FALSE)
    expr_g <- expr_long %>% dplyr::filter(group == grp)
    summary_g <- expr_summary %>% dplyr::filter(group == grp)
    genes_g <- unique(expr_g$gene_id)
    deg_g <- deg_hits %>% dplyr::filter(gene_id %in% genes_g)
    catalog_g <- gene_catalog %>% dplyr::filter(group == grp)
    plot_or_skip(paste("group heatmap", grp), function() plot_expression_heatmap(summary_g, file.path(group_dir, "expression_heatmap.png"), paste("Grupo:", grp)))
    plot_or_skip(paste("group dotplot", grp), function() plot_expression_dotplot(summary_g, file.path(group_dir, "expression_dotplot.png"), paste("Grupo:", grp)))
    plot_or_skip(paste("group sample heatmap", grp), function() plot_group_sample_heatmap(expr_g, file.path(group_dir, "sample_heatmap.png"), paste("Amostras -", grp)))
    plot_or_skip(paste("group annotated sample heatmap", grp), function() plot_annotated_sample_heatmap(expr_g, file.path(group_dir, "sample_heatmap_annotated.png"), paste("Amostras anotadas -", grp)))
    plot_or_skip(paste("group gene correlation", grp), function() plot_gene_correlation(expr_g, file.path(group_dir, "gene_correlation.png"), paste("Correlacao entre genes -", grp)))
    plot_or_skip(paste("group PCA", grp), function() plot_sample_ordination(expr_g, file.path(group_dir, "sample_pca.png"), method = "pca", title = paste("PCA -", grp)))
    plot_or_skip(paste("group MDS", grp), function() plot_sample_ordination(expr_g, file.path(group_dir, "sample_mds.png"), method = "mds", title = paste("MDS -", grp)))
    plot_or_skip(paste("group aggregate profile", grp), function() plot_group_aggregate_profile(expr_g, file.path(group_dir, "aggregate_profile.png"), paste("Perfil agregado -", grp)))
    plot_or_skip(paste("group ovary/testis", grp), function() plot_ovary_testis_panel(summary_g, file.path(group_dir, "ovary_testis_panel.png"), paste("Ovario/testiculo -", grp)))
    plot_or_skip(paste("group batch", grp), function() plot_batch_project_boxplot(expr_g, file.path(group_dir, "batch_project_boxplot.png"), paste("Batch/projeto -", grp)))
    plot_or_skip(paste("group DEG heatmap", grp), function() plot_deg_heatmap(deg_g, catalog_g, file.path(group_dir, "deg_log2fc_heatmap.png"), paste("DEG -", grp)))
    plot_or_skip(paste("group DEG tile", grp), function() plot_deg_context_tile(deg_g, catalog_g, file.path(group_dir, "deg_context_tile.png"), paste("DEG por contraste -", grp)))
    plot_or_skip(paste("group DEG direction", grp), function() plot_deg_direction_summary(deg_g, catalog_g, file.path(group_dir, "deg_direction_summary.png"), paste("Direcao DEG -", grp)))
  }
}

plot_gene_outputs <- function(expr_long, deg_hits, out_dir) {
  gene_keys <- expr_long %>% dplyr::distinct(group, gene_id, gene_name, gene_display_label, biotype)
  for (i in seq_len(nrow(gene_keys))) {
    key <- gene_keys[i, ]
    gene_dir <- file.path(out_dir, "genes", sanitize(key$group), sanitize(key$gene_id))
    dir.create(gene_dir, recursive = TRUE, showWarnings = FALSE)
    df <- expr_long %>% dplyr::filter(group == key$group, gene_id == key$gene_id)
    deg_df <- deg_hits %>% dplyr::filter(gene_id == key$gene_id)
    label <- paste(key$group, key$gene_display_label, sep = " | ")
    plot_or_skip(paste("gene expression", key$gene_id), function() plot_gene_expression_boxplot(df, file.path(gene_dir, "expression_tissue_sex_condition.png"), label))
    plot_or_skip(paste("gene batch", key$gene_id), function() plot_gene_batch_boxplot(df, file.path(gene_dir, "expression_batch_project.png"), label))
    plot_or_skip(paste("gene profile", key$gene_id), function() plot_gene_profile_line(df, file.path(gene_dir, "expression_stage_profile.png"), label))
    plot_or_skip(paste("gene sample tile", key$gene_id), function() plot_gene_sample_tile(df, file.path(gene_dir, "expression_sample_tile.png"), label))
    plot_or_skip(paste("gene DEG lollipop", key$gene_id), function() plot_gene_deg_lollipop(deg_df, file.path(gene_dir, "deg_lollipop.png"), label))
    plot_or_skip(paste("gene DEG scatter", key$gene_id), function() plot_gene_deg_scatter(deg_df, file.path(gene_dir, "deg_scatter.png"), label))
  }
}

html_escape <- function(x) {
  x <- as.character(x)
  x[is.na(x)] <- ""
  x <- gsub("&", "&amp;", x, fixed = TRUE)
  x <- gsub("<", "&lt;", x, fixed = TRUE)
  x <- gsub(">", "&gt;", x, fixed = TRUE)
  x <- gsub("\"", "&quot;", x, fixed = TRUE)
  x <- gsub("'", "&#39;", x, fixed = TRUE)
  x
}

table_to_html <- function(df, max_rows = 30) {
  if (is.null(df) || nrow(df) == 0) return("<p><em>Nenhum registro.</em></p>")
  df <- as.data.frame(df, stringsAsFactors = FALSE)
  if (nrow(df) > max_rows) df <- df[seq_len(max_rows), , drop = FALSE]
  header <- paste0("<tr>", paste0("<th>", html_escape(colnames(df)), "</th>", collapse = ""), "</tr>")
  rows <- apply(df, 1, function(row) {
    row_text <- paste(row, collapse = " ")
    paste0(
      "<tr class='searchable table-row' data-kind='table' data-search='", html_escape(tolower(row_text)), "'>",
      paste0("<td>", html_escape(row), "</td>", collapse = ""),
      "</tr>"
    )
  })
  paste0("<div class='table-wrap'><table>", header, paste(rows, collapse = "\n"), "</table></div>")
}

figure_explanation <- function(caption) {
  caption_l <- tolower(caption)
  dplyr::case_when(
    grepl("pca", caption_l) ~ "Agrupa amostras por similaridade global de expressao nos genes exibidos. Separacoes fortes podem indicar efeito biologico, batch ou amostras discrepantes.",
    grepl("mds", caption_l) ~ "Resume distancias entre amostras; pontos proximos tem perfis de expressao parecidos para este conjunto de genes.",
    grepl("correlacao", caption_l) ~ "Mostra se genes variam juntos entre as amostras. Valores altos sugerem perfis coordenados ou dependencia de um mesmo contexto.",
    grepl("dotplot|fracao expressa", caption_l) ~ "Combina intensidade media de expressao com a proporcao de amostras expressas, ajudando a separar genes altos em poucas amostras de genes consistentes.",
    grepl("heatmap gene x amostra|amostra", caption_l) ~ "Mostra expressao por amostra individual. Use para procurar outliers, padroes por projeto e consistencia entre replicatas.",
    grepl("heatmap|expressao media", caption_l) ~ paste0("Resume log2(", expression_unit, " + 1) medio por contexto. Cores mais intensas indicam maior expressao relativa naquele contexto."),
    grepl("ovario|testiculo", caption_l) ~ "Compara contextos reprodutivos quando a metadata contem esses tecidos; e ignorado quando os dados nao permitem a comparacao.",
    grepl("batch|projeto", caption_l) ~ "Ajuda a avaliar se o sinal de expressao acompanha projeto/batch em vez de contexto biologico.",
    grepl("log2fc|deg|contraste", caption_l) ~ "Resume resultados diferenciais. log2FC positivo/negativo indica direcao do efeito; padj baixo aumenta a confianca estatistica.",
    grepl("perfil agregado|perfil medio", caption_l) ~ "Mostra tendencias medias ao longo de estagios ou contextos, suavizando variacao gene a gene.",
    TRUE ~ "Figura exploratoria para revisar padroes de expressao, consistencia entre amostras e possiveis efeitos tecnicos."
  )
}

img_tag <- function(src, caption) {
  if (!file.exists(file.path(out_dir, src))) return("")
  explanation <- figure_explanation(caption)
  search_text <- paste(caption, explanation, src)
  paste0(
    "<figure class='searchable report-figure' data-kind='figure' data-search='", html_escape(tolower(search_text)), "'>",
    "<img src='", gsub("\\\\", "/", src), "' alt='", html_escape(caption), "'>",
    "<figcaption><strong>", html_escape(caption), "</strong><span>", html_escape(explanation), "</span></figcaption>",
    "</figure>"
  )
}

write_html_report <- function(path, title, catalog, gene_summary, deg_hits, global_plots, expression_unit = "TPM") {
  if (is.na(expression_unit) || expression_unit == "") expression_unit <- "TPM"

  group_links <- paste(vapply(unique(catalog$group), function(grp) {
    paste0("<li><a href='#group_", sanitize(grp), "'>", html_escape(grp), "</a></li>")
  }, character(1)), collapse = "\n")

  gene_index <- paste(vapply(seq_len(nrow(catalog)), function(i) {
    row <- catalog[i, ]
    search_text <- paste(row$group, row$query, row$matched_gene_id, row$gene_name, row$gene_display_label, row$biotype, row$description, row$chromosome, row$location)
    paste0(
      "<a class='searchable gene-chip' data-kind='gene' data-search='", html_escape(tolower(search_text)), "' href='#gene_", sanitize(row$group), "_", sanitize(row$matched_gene_id), "'>",
      "<span>", html_escape(row$gene_display_label), "</span>",
      "<small>", html_escape(row$group), "</small>",
      "</a>"
    )
  }, character(1)), collapse = "\n")

  group_sections <- paste(vapply(unique(catalog$group), function(grp) {
    group_dir <- file.path("groups", sanitize(grp))
    group_catalog <- catalog %>%
      dplyr::filter(group == grp) %>%
      dplyr::select(group, query, query_display, matched_gene_id, gene_name, gene_display_label, biotype, chromosome, gene_start, gene_end, strand, location, found_in_expression_matrix)
    group_search <- paste(group_catalog$group, group_catalog$query, group_catalog$matched_gene_id, group_catalog$gene_name, group_catalog$gene_display_label, group_catalog$biotype, group_catalog$chromosome, group_catalog$location, collapse = " ")
    paste0(
      "<section class='searchable group-section' data-kind='group' data-search='", html_escape(tolower(group_search)), "' id='group_", sanitize(grp), "'><h2>Grupo: ", html_escape(grp), "</h2>",
      table_to_html(group_catalog, 100),
      img_tag(file.path(group_dir, "expression_heatmap.png"), "Expressao media por contexto biologico, projeto e batch"),
      img_tag(file.path(group_dir, "expression_dotplot.png"), "Media de expressao e fracao expressa por contexto"),
      img_tag(file.path(group_dir, "sample_heatmap.png"), "Expressao nas amostras individuais"),
      img_tag(file.path(group_dir, "sample_heatmap_annotated.png"), "Heatmap gene x amostra com anotacoes de projeto, batch e biologia"),
      img_tag(file.path(group_dir, "gene_correlation.png"), "Correlacao de expressao entre genes do grupo"),
      img_tag(file.path(group_dir, "sample_pca.png"), "PCA das amostras usando apenas genes do grupo"),
      img_tag(file.path(group_dir, "sample_mds.png"), "MDS das amostras usando apenas genes do grupo"),
      img_tag(file.path(group_dir, "aggregate_profile.png"), "Perfil agregado medio do grupo"),
      img_tag(file.path(group_dir, "ovary_testis_panel.png"), "Comparacao ovario versus testiculo"),
      img_tag(file.path(group_dir, "batch_project_boxplot.png"), "Distribuicao de expressao por batch e projeto"),
      img_tag(file.path(group_dir, "deg_log2fc_heatmap.png"), "log2FC dos genes do grupo nos contrastes DEG"),
      img_tag(file.path(group_dir, "deg_context_tile.png"), "Consistencia dos sinais DEG por contraste/projeto"),
      img_tag(file.path(group_dir, "deg_direction_summary.png"), "Direcao DEG por contraste/projeto"),
      "</section>"
    )
  }, character(1)), collapse = "\n")

  gene_sections <- paste(vapply(seq_len(nrow(catalog)), function(i) {
    row <- catalog[i, ]
    gene_dir <- file.path("genes", sanitize(row$group), sanitize(row$matched_gene_id))
    deg_table <- deg_hits %>%
      dplyr::filter(gene_id == row$matched_gene_id) %>%
      dplyr::select(gene_display_label, deg_project, deg_mode, contrast, log2FoldChange_num, padj_num, significant) %>%
      dplyr::arrange(padj_num)
    gene_search <- paste(row$group, row$query, row$matched_gene_id, row$gene_name, row$gene_display_label, row$biotype, row$description, row$chromosome, row$location, paste(deg_table$contrast, collapse = " "))
    paste0(
      "<section class='searchable gene' data-kind='gene' data-search='", html_escape(tolower(gene_search)), "' id='gene_", sanitize(row$group), "_", sanitize(row$matched_gene_id), "'>",
      "<h3>", html_escape(row$gene_display_label), "</h3>",
      "<p><b>Grupo:</b> ", html_escape(row$group),
      " | <b>Query:</b> ", html_escape(row$query),
      " | <b>Biotipo:</b> ", html_escape(row$biotype),
      " | <b>Localizacao:</b> ", html_escape(row$location),
      " | <b>Na matriz ", html_escape(expression_unit), ":</b> ", html_escape(row$found_in_expression_matrix), "</p>",
      "<p>", html_escape(row$description), "</p>",
      img_tag(file.path(gene_dir, "expression_tissue_sex_condition.png"), "Expressao por tecido, sexo, condicao, estagio e projeto"),
      img_tag(file.path(gene_dir, "expression_batch_project.png"), "Expressao por batch/projeto"),
      img_tag(file.path(gene_dir, "expression_stage_profile.png"), "Perfil medio por estagio, tecido, batch e condicao"),
      img_tag(file.path(gene_dir, "expression_sample_tile.png"), "Expressao por amostra individual"),
      img_tag(file.path(gene_dir, "deg_lollipop.png"), "Efeito DEG do gene nos contrastes disponiveis"),
      img_tag(file.path(gene_dir, "deg_scatter.png"), "log2FC versus -log10(padj) nos contrastes DEG"),
      "<h4>DEG do gene</h4>",
      table_to_html(deg_table, 50),
      "</section>"
    )
  }, character(1)), collapse = "\n")

  html <- c(
    "<!doctype html><html><head><meta charset='utf-8'>",
    paste0("<title>", html_escape(title), "</title>"),
    "<style>
      body{font-family:Arial,sans-serif;max-width:1320px;margin:32px auto;line-height:1.45;color:#222}
      nav{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:10px 0;margin-bottom:24px;z-index:2}
      nav a{margin-right:16px;color:#1d4e89;text-decoration:none;font-weight:600}
      h1,h2{color:#17324d} h2{border-top:2px solid #e6e6e6;padding-top:22px;margin-top:36px}
      h3{margin-top:30px;color:#17324d}
      .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:18px 0}
      .card{background:#f7f9fb;border:1px solid #dde5ed;border-radius:6px;padding:14px}
      .card .num{font-size:28px;font-weight:700;color:#17324d}
      .toolbar{position:sticky;top:46px;background:#fff;border:1px solid #d8e1ea;border-radius:6px;padding:12px;margin:14px 0 24px 0;z-index:2;box-shadow:0 2px 10px rgba(20,45,70,.06)}
      .toolbar input{box-sizing:border-box;width:100%;font-size:16px;padding:10px 12px;border:1px solid #bdc9d6;border-radius:4px}
      .filters{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:13px;color:#34495e}
      .filters label{display:inline-flex;gap:6px;align-items:center}
      .search-count{font-size:13px;color:#5d6d7e;margin-top:8px}
      .gene-index{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px;margin:14px 0 24px 0}
      .gene-chip{display:block;border:1px solid #d8e1ea;border-radius:6px;padding:9px 10px;text-decoration:none;color:#17324d;background:#fbfcfd}
      .gene-chip span{display:block;font-weight:700;overflow-wrap:anywhere}.gene-chip small{display:block;color:#697b8c;margin-top:2px}
      .guide{background:#fbfcfd;border:1px solid #d8e1ea;border-radius:6px;padding:14px;margin:18px 0}
      .guide h2{border:0;margin-top:0;padding-top:0}.guide dl{display:grid;grid-template-columns:minmax(150px,240px) 1fr;gap:8px 16px;margin:0}.guide dt{font-weight:700;color:#17324d}.guide dd{margin:0}
      .table-wrap{overflow-x:auto}
      table{border-collapse:collapse;width:100%;font-size:12px;margin:10px 0 22px 0}
      th,td{border:1px solid #ddd;padding:5px;vertical-align:top} th{background:#f3f3f3}
      code{background:#f6f6f6;padding:2px 4px}
      figure{margin:18px 0 30px 0} figcaption{font-size:13px;color:#555;margin-top:6px}
      figcaption strong{display:block;color:#2a3f53} figcaption span{display:block;margin-top:3px}
      img{max-width:100%;border:1px solid #ddd;margin:8px 0 18px 0}
      .gene{border-top:1px solid #e6e6e6;padding-top:10px}
      .hidden-by-search{display:none!important}
      ul{columns:2}
    </style>",
    "<script>
      document.addEventListener('DOMContentLoaded', function(){
        var input = document.getElementById('geneSearch');
        var count = document.getElementById('searchCount');
        var toggles = Array.prototype.slice.call(document.querySelectorAll('[data-filter-kind]'));
        var items = Array.prototype.slice.call(document.querySelectorAll('.searchable'));
        function activeKinds(){
          return toggles.filter(function(t){return t.checked;}).map(function(t){return t.getAttribute('data-filter-kind');});
        }
        function applySearch(){
          var query = (input.value || '').trim().toLowerCase();
          var kinds = activeKinds();
          var visible = 0;
          items.forEach(function(el){
            var kind = el.getAttribute('data-kind') || '';
            var text = el.getAttribute('data-search') || el.textContent.toLowerCase();
            var kindOk = kind === '' || kinds.indexOf(kind) !== -1;
            var queryOk = query === '' || text.indexOf(query) !== -1;
            var show = kindOk && queryOk;
            el.classList.toggle('hidden-by-search', !show);
            if (show && kind !== '') visible += 1;
          });
          items.forEach(function(el){
            if (!el.classList.contains('hidden-by-search')) {
              var parent = el.closest('.group-section.hidden-by-search,.gene.hidden-by-search');
              if (parent) parent.classList.remove('hidden-by-search');
            }
          });
          count.textContent = query === '' ? 'Filtro inativo.' : visible + ' itens encontrados para \"' + query + '\".';
        }
        input.addEventListener('input', applySearch);
        toggles.forEach(function(t){t.addEventListener('change', applySearch);});
        applySearch();
      });
    </script>",
    "</head><body>",
    paste0("<h1>", html_escape(title), "</h1>"),
    "<nav><a href='#overview'>Visao geral</a><a href='#guide'>Como ler</a><a href='#groups'>Grupos</a><a href='#genes'>Genes</a><a href='#tables'>Tabelas</a></nav>",
    "<div class='toolbar' role='search'>",
    "<input id='geneSearch' type='search' placeholder='Buscar por gene, ID, grupo, biotipo, descricao ou contraste'>",
    "<div class='filters'>",
    "<label><input type='checkbox' data-filter-kind='gene' checked>Genes</label>",
    "<label><input type='checkbox' data-filter-kind='group' checked>Grupos</label>",
    "<label><input type='checkbox' data-filter-kind='figure' checked>Figuras</label>",
    "<label><input type='checkbox' data-filter-kind='table' checked>Tabelas</label>",
    "</div>",
    "<div class='search-count' id='searchCount'>Filtro inativo.</div>",
    "</div>",
    "<section id='overview'>",
    "<div class='cards'>",
    paste0("<div class='card'><div class='num'>", nrow(catalog), "</div><div>entradas no genes.txt</div></div>"),
    paste0("<div class='card'><div class='num'>", length(unique(catalog$matched_gene_id)), "</div><div>genes unicos</div></div>"),
    paste0("<div class='card'><div class='num'>", length(unique(catalog$group)), "</div><div>grupos</div></div>"),
    paste0("<div class='card'><div class='num'>", length(unique(deg_hits$contrast_label)), "</div><div>contrastes DEG com estes genes</div></div>"),
    "</div>",
    paste0("<p>Este relatorio nao classifica genes. Ele organiza evidencias visuais e tabelas para explorar expressao em ", html_escape(expression_unit), ", localizacao genomica, batch/projeto, contexto biologico e resultados DEG de cada gene e grupo.</p>"),
    "<div class='gene-index'>", gene_index, "</div>",
    img_tag(global_plots$heatmap, "Expressao media integrada por contexto"),
    img_tag(global_plots$dotplot, "Expressao media e fracao expressa"),
    img_tag(global_plots$annotated_sample_heatmap, "Heatmap gene x amostra com anotacoes"),
    img_tag(global_plots$gene_correlation, "Correlacao de expressao entre genes"),
    img_tag(global_plots$sample_pca, "PCA das amostras usando os genes de interesse"),
    img_tag(global_plots$sample_mds, "MDS das amostras usando os genes de interesse"),
    img_tag(global_plots$tissue_sex_heatmap, "Padroes por tecido e sexo"),
    img_tag(global_plots$ovary_testis, "Comparacao ovario versus testiculo"),
    img_tag(global_plots$group_aggregate, "Perfil agregado por grupo"),
    img_tag(global_plots$batch_project, "Distribuicao de expressao por batch e projeto"),
    img_tag(global_plots$deg_heatmap, "log2FC integrado nos contrastes DEG"),
    img_tag(global_plots$deg_tile, "Sinais DEG por contraste/projeto"),
    img_tag(global_plots$deg_direction, "Direcao DEG por contraste/projeto"),
    "</section>",
    "<section class='guide' id='guide'><h2>Como ler as visualizacoes</h2>",
    "<dl>",
    paste0("<dt>", html_escape(expression_unit), " e log2(", html_escape(expression_unit), " + 1)</dt><dd>A matriz de expressao normalizada e usada para comparar padroes entre amostras; a escala log reduz o peso de genes muito altos.</dd>"),
    "<dt>Heatmaps</dt><dd>Use para localizar blocos de alta/baixa expressao e checar se grupos biologicos ou projetos dominam o sinal.</dd>",
    "<dt>PCA/MDS</dt><dd>Servem como controle exploratorio: separacoes por batch/projeto merecem cautela antes de interpretar diferencas biologicas.</dd>",
    "<dt>DEG</dt><dd>log2FC mostra direcao e tamanho do efeito; padj considera multiplos testes. Priorize genes com efeito coerente e padj baixo.</dd>",
    "<dt>Busca</dt><dd>Digite ID, nome, grupo, biotipo, descricao ou contraste para reduzir o relatorio aos itens relevantes.</dd>",
    "</dl></section>",
    "<section id='groups'><h2>Grupos</h2><ul>", group_links, "</ul>", group_sections, "</section>",
    "<section id='genes'><h2>Genes individuais</h2>", gene_sections, "</section>",
    "<section id='tables'><h2>Tabelas</h2>",
    "<p>Arquivos completos: <code>tables/gene_catalog.tsv</code>, <code>tables/gene_expression_summary.tsv</code>, <code>tables/expression_long.tsv</code>, <code>tables/expression_summary_by_context.tsv</code> e <code>tables/deg_hits.tsv</code>.</p>",
    table_to_html(gene_summary, 100),
    "</section>",
    "</body></html>"
  )
  writeLines(html, path, useBytes = TRUE)
}

gene_groups <- parse_gene_groups(genes_file)
tpm <- read_matrix(tpm_file)
samples <- read_samples(samples_file, setdiff(colnames(tpm), "gene_id"))

if (metadata_file != "" && file.exists(metadata_file)) {
  metadata <- readr::read_csv(metadata_file, show_col_types = FALSE, col_types = cols(.default = col_character()))
  if (all(c("dataset", "sample_id") %in% colnames(metadata))) {
    metadata$import_id_combined <- paste(metadata$dataset, metadata$sample_id, sep = "__")
    key <- if (all(samples$import_id %in% metadata$import_id_combined)) "import_id_combined" else "sample_id"
    extra <- metadata[match(samples$import_id, metadata[[key]]), , drop = FALSE]
    add_cols <- setdiff(colnames(extra), colnames(samples))
    samples <- dplyr::bind_cols(samples, extra[, add_cols, drop = FALSE])
  }
}

samples <- complete_sample_fields(samples)
annotations <- load_annotations(gff_file)
gene_catalog <- build_gene_catalog(gene_groups, tpm, annotations)
expr_long <- make_expression_long(tpm, samples, gene_catalog)
expr_summary <- summarise_expression(expr_long)
deg_hits <- load_deg_hits(deg_root, gene_catalog)
deg_hits_annotated <- annotate_deg_hits(deg_hits, gene_catalog)
gene_summary <- summarise_gene_descriptives(expr_long, expr_summary, deg_hits, gene_catalog)

write_tsv2(gene_catalog, file.path(out_dir, "tables", "gene_catalog.tsv"))
write_tsv2(expr_long, file.path(out_dir, "tables", "expression_long.tsv"))
write_tsv2(expr_summary, file.path(out_dir, "tables", "expression_summary_by_context.tsv"))
write_tsv2(deg_hits_annotated, file.path(out_dir, "tables", "deg_hits.tsv"))
write_tsv2(gene_summary, file.path(out_dir, "tables", "gene_expression_summary.tsv"))

global_plots <- list(
  heatmap = file.path("plots", "all_groups_expression_heatmap.png"),
  dotplot = file.path("plots", "all_groups_expression_dotplot.png"),
  annotated_sample_heatmap = file.path("plots", "all_groups_sample_heatmap_annotated.png"),
  gene_correlation = file.path("plots", "all_groups_gene_correlation.png"),
  sample_pca = file.path("plots", "all_groups_sample_pca.png"),
  sample_mds = file.path("plots", "all_groups_sample_mds.png"),
  tissue_sex_heatmap = file.path("plots", "all_groups_tissue_sex_heatmap.png"),
  ovary_testis = file.path("plots", "all_groups_ovary_testis_panel.png"),
  group_aggregate = file.path("plots", "all_groups_aggregate_profile.png"),
  batch_project = file.path("plots", "all_groups_batch_project_boxplot.png"),
  deg_heatmap = file.path("plots", "all_groups_deg_log2fc_heatmap.png"),
  deg_tile = file.path("plots", "all_groups_deg_context_tile.png"),
  deg_direction = file.path("plots", "all_groups_deg_direction_summary.png")
)

invisible(plot_or_skip("global expression heatmap", function() plot_expression_heatmap(expr_summary, file.path(out_dir, global_plots$heatmap), "Todos os grupos - expressao media")))
invisible(plot_or_skip("global expression dotplot", function() plot_expression_dotplot(expr_summary, file.path(out_dir, global_plots$dotplot), "Todos os grupos - expressao media e fracao expressa")))
invisible(plot_or_skip("global annotated sample heatmap", function() plot_annotated_sample_heatmap(expr_long, file.path(out_dir, global_plots$annotated_sample_heatmap), "Todos os grupos - amostras anotadas")))
invisible(plot_or_skip("global gene correlation", function() plot_gene_correlation(expr_long, file.path(out_dir, global_plots$gene_correlation), "Todos os grupos - correlacao entre genes")))
invisible(plot_or_skip("global sample PCA", function() plot_sample_ordination(expr_long, file.path(out_dir, global_plots$sample_pca), method = "pca", title = "Todos os grupos - PCA das amostras")))
invisible(plot_or_skip("global sample MDS", function() plot_sample_ordination(expr_long, file.path(out_dir, global_plots$sample_mds), method = "mds", title = "Todos os grupos - MDS das amostras")))
invisible(plot_or_skip("global tissue/sex heatmap", function() plot_tissue_sex_heatmap(expr_summary, file.path(out_dir, global_plots$tissue_sex_heatmap), "Todos os grupos - tecido e sexo")))
invisible(plot_or_skip("global ovary/testis", function() plot_ovary_testis_panel(expr_summary, file.path(out_dir, global_plots$ovary_testis), "Todos os grupos - ovario versus testiculo")))
invisible(plot_or_skip("global group aggregate profile", function() plot_group_aggregate_profile(expr_long, file.path(out_dir, global_plots$group_aggregate), "Todos os grupos - perfil agregado")))
invisible(plot_or_skip("global batch/project", function() plot_batch_project_boxplot(expr_long, file.path(out_dir, global_plots$batch_project), "Todos os grupos - batch/projeto")))
invisible(plot_or_skip("global DEG heatmap", function() plot_deg_heatmap(deg_hits, gene_catalog, file.path(out_dir, global_plots$deg_heatmap), "Todos os grupos - log2FC DEG")))
invisible(plot_or_skip("global DEG tile", function() plot_deg_context_tile(deg_hits, gene_catalog, file.path(out_dir, global_plots$deg_tile), "Todos os grupos - DEG por contraste")))
invisible(plot_or_skip("global DEG direction", function() plot_deg_direction_summary(deg_hits, gene_catalog, file.path(out_dir, global_plots$deg_direction), "Todos os grupos - direcao DEG")))
plot_group_outputs(expr_long, expr_summary, deg_hits, gene_catalog, out_dir)
plot_gene_outputs(expr_long, deg_hits, out_dir)

write_html_report(file.path(out_dir, "gene_set_report.html"), report_title, gene_catalog, gene_summary, deg_hits_annotated, global_plots, expression_unit)
log_info(paste("[OK] Relatorio 090 concluido:", file.path(out_dir, "gene_set_report.html")))
