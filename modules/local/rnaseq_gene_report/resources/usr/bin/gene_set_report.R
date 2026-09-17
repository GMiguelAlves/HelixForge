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
gene_id_version_policy <- get_arg("--gene-id-version-policy", Sys.getenv("GENE_ID_VERSION_POLICY", unset = "preserve"))
out_dir <- get_arg("--output-dir", file.path(Sys.getenv("GENE_REPORT_DIR", unset = "."), "results"))
report_title <- get_arg("--title", "Relatorio exploratorio de genes")
if (is.na(expression_unit) || expression_unit == "") expression_unit <- "TPM"
if (!gene_id_version_policy %in% c("preserve", "strip")) {
  stop("[ERRO] --gene-id-version-policy deve ser preserve ou strip")
}
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

is_placeholder_value <- function(x) {
  tolower(trimws(as.character(x))) %in% c("", ".", "na", "nan", "none", "unknown", "not_declared", "not_available") |
    is.na(x)
}

informative_fields <- function(df, fields, require_variation = TRUE) {
  fields <- intersect(fields, colnames(df))
  selected <- character()
  selected_values <- list()
  for (field in fields) {
    values <- as.character(df[[field]])
    meaningful <- values[!is_placeholder_value(values)]
    if (length(meaningful) == 0) next
    if (require_variation && dplyr::n_distinct(meaningful) < 2) next
    normalized <- ifelse(is_placeholder_value(values), "", values)
    duplicate_field <- any(vapply(selected_values, function(other) identical(normalized, other), logical(1)))
    if (duplicate_field) next
    selected <- c(selected, field)
    selected_values[[field]] <- normalized
  }
  selected
}

metadata_labels <- c(
  dataset = "estudo", batch = "batch", condition = "condicao",
  stage = "estagio", tissue = "tecido", sex = "sexo"
)

compact_context <- function(df, fields = names(metadata_labels), fallback = "contexto unico", include_names = FALSE) {
  active <- informative_fields(df, fields, require_variation = TRUE)
  if (length(active) == 0) return(rep(fallback, nrow(df)))
  pieces <- lapply(active, function(field) {
    values <- as.character(df[[field]])
    values[is_placeholder_value(values)] <- "nao informado"
    if (include_names) paste0(metadata_labels[[field]], "=", values) else values
  })
  do.call(paste, c(pieces, sep = " | "))
}

join_nonempty <- function(...) {
  values <- list(...)
  n <- max(vapply(values, length, integer(1)))
  values <- lapply(values, rep_len, length.out = n)
  vapply(seq_len(n), function(i) {
    row <- vapply(values, function(x) as.character(x[[i]]), character(1))
    row <- row[!is_placeholder_value(row)]
    paste(unique(row), collapse = " | ")
  }, character(1))
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
  if (gene_id_version_policy == "strip") gene_id <- gsub("\\.[0-9]+$", "", gene_id)
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
    root_lexical <- sub("/+$", "", gsub("\\\\", "/", deg_root))
    path_lexical <- gsub("\\\\", "/", path)
    prefix <- paste0(root_lexical, "/")
    rel <- if (startsWith(path_lexical, prefix)) substring(path_lexical, nchar(prefix) + 1) else basename(path_lexical)
    result_dir <- dirname(rel)
    clean_result_dir <- ifelse(result_dir %in% c("", ".", "./"), "", result_dir)
    project_value <- ifelse(clean_result_dir == "", "", sub("/.*$", "", clean_result_dir))
    mode_value <- ifelse(grepl("/", clean_result_dir), sub("^.*/", "", clean_result_dir), "")
    df %>%
      dplyr::filter(gene_id %in% gene_catalog$matched_gene_id) %>%
      dplyr::mutate(
        source_file = rel,
        result_dir = clean_result_dir,
        deg_project = project_value,
        deg_mode = mode_value,
        contrast_label = join_nonempty(project_value, mode_value, contrast),
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
      gene_display_label = as.character(ifelse(is.na(gene_display_label) | gene_display_label == "", make_gene_display_label(gene_name, gene_id, description), gene_display_label)),
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
      max_TPM = if (all(is.na(TPM))) NA_real_ else max(TPM, na.rm = TRUE),
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
  expr_summary$context_compact <- compact_context(expr_summary, include_names = TRUE)
  mat_df <- expr_summary %>%
    dplyr::arrange(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex, group, gene_display_label) %>%
    dplyr::mutate(
      label = paste0(gene_display_label, "  [", group, "]"),
      context = context_compact
    ) %>%
    dplyr::group_by(label, context) %>%
    dplyr::summarise(mean_log2TPM = mean(mean_log2TPM, na.rm = TRUE), .groups = "drop") %>%
    tidyr::pivot_wider(names_from = context, values_from = mean_log2TPM, values_fill = 0)
  if (nrow(mat_df) == 0 || ncol(mat_df) < 2) return(FALSE)
  mat <- as.matrix(mat_df[, -1, drop = FALSE])
  rownames(mat) <- mat_df$label
  if (!heatmap_has_signal(mat)) return(FALSE)
  scale_mode <- heatmap_scale_mode(mat)
  scale_note <- ifelse(scale_mode == "row", "z-score por gene", expression_mean_log_label)
  pheatmap::pheatmap(mat, scale = scale_mode, border_color = NA,
                     cluster_rows = nrow(mat) > 1,
                     cluster_cols = ncol(mat) > 1,
                     fontsize_row = 7, fontsize_col = 6,
                     main = paste0(title, "\nEscala: ", scale_note), filename = outfile,
                     width = 14, height = max(5, min(18, nrow(mat) * 0.32 + 3)))
  TRUE
}

plot_expression_dotplot <- function(expr_summary, outfile, title = "Expressao media e fracao expressa") {
  expr_summary$context_compact <- compact_context(expr_summary, include_names = TRUE)
  df <- expr_summary %>%
    dplyr::arrange(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex, group, gene_display_label) %>%
    dplyr::mutate(
      context = context_compact,
      gene_label = paste0(gene_display_label, "  [", group, "]")
    )
  if (nrow(df) == 0) return(FALSE)
  fraction_varies <- dplyr::n_distinct(round(df$fraction_expressed, 4), na.rm = TRUE) > 1
  p <- ggplot(df, aes(x = context, y = gene_label))
  if (fraction_varies) {
    p <- p + geom_point(aes(size = fraction_expressed, color = mean_log2TPM), alpha = 0.88) +
      labs(size = paste0("Fracao ", expression_unit, ">1"))
  } else {
    p <- p + geom_point(aes(color = mean_log2TPM), size = 3, alpha = 0.88)
  }
  p <- p +
    scale_color_viridis_c(option = "C") +
    theme_bw(base_size = 9) +
    theme(axis.text.x = element_text(angle = 55, hjust = 1), panel.grid.major.y = element_line(color = "gray92")) +
    labs(title = title, x = "Contexto (somente metadados informativos)", y = "Gene [grupo]",
         color = expression_mean_log_label)
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
  fields <- informative_fields(ann, c("condition", "stage", "tissue", "sex", "batch", "dataset"), require_variation = TRUE)
  if (length(fields) == 0) return(NULL)
  ann <- as.data.frame(ann[, fields, drop = FALSE])
  colnames(ann) <- unname(metadata_labels[colnames(ann)])
  rownames(ann) <- sample_ids
  ann
}

plot_annotated_sample_heatmap <- function(expr_long, outfile, title = "Heatmap gene x amostra anotado") {
  mat <- expression_matrix_by_gene(expr_long, include_group = TRUE)
  if (is.null(mat) || nrow(mat) < 1 || ncol(mat) < 2) return(FALSE)
  if (!heatmap_has_signal(mat)) return(FALSE)
  ann_col <- sample_annotation_for_matrix(expr_long, colnames(mat))
  scale_mode <- heatmap_scale_mode(mat)
  scale_note <- ifelse(scale_mode == "row", "z-score por gene", expression_log_label)
  args <- list(
    mat = mat,
    scale = scale_mode,
    border_color = NA,
    cluster_rows = nrow(mat) > 1,
    cluster_cols = ncol(mat) > 1,
    show_colnames = ncol(mat) <= 24,
    fontsize_row = 7,
    fontsize_col = 6,
    main = paste0(title, "\nEscala: ", scale_note),
    filename = outfile,
    width = 15,
    height = max(5, min(18, nrow(mat) * 0.32 + 4))
  )
  if (!is.null(ann_col)) args$annotation_col <- ann_col
  do.call(pheatmap::pheatmap, args)
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
  attr(coords, "axis_labels") <- axis_labels
  coords
}

plot_sample_ordination <- function(expr_long, outfile, method = c("pca", "mds"), title = "Ordenacao de amostras") {
  method <- match.arg(method)
  df <- sample_scores_long(expr_long, method = method)
  if (nrow(df) == 0) return(FALSE)
  axis_labels <- attr(df, "axis_labels")
  fields <- informative_fields(df, c("condition", "stage", "tissue", "sex", "batch", "dataset"), require_variation = TRUE)
  primary <- if (length(fields) > 0) fields[[1]] else NULL
  secondary <- if (length(fields) > 1 && dplyr::n_distinct(df[[fields[[2]]]]) <= 6) fields[[2]] else NULL
  p <- ggplot(df, aes(x = Dim1, y = Dim2))
  if (!is.null(primary) && !is.null(secondary)) {
    p <- p + geom_point(aes(color = .data[[primary]], shape = .data[[secondary]]), size = 3, alpha = 0.9) +
      labs(color = metadata_labels[[primary]], shape = metadata_labels[[secondary]])
  } else if (!is.null(primary)) {
    p <- p + geom_point(aes(color = .data[[primary]]), size = 3, alpha = 0.9) +
      labs(color = metadata_labels[[primary]])
  } else {
    p <- p + geom_point(size = 3, color = "#2b6f9f", alpha = 0.9)
  }
  if (nrow(df) <= 12) {
    p <- p + geom_text(aes(label = import_id), check_overlap = TRUE, size = 2.5, vjust = -0.8, show.legend = FALSE)
  }
  p <- p +
    theme_bw(base_size = 10) +
    labs(title = title, subtitle = "Ordenacao exploratoria calculada somente com os genes candidatos",
         x = axis_labels[1], y = axis_labels[2])
  ggsave(outfile, p, width = 10, height = 7, dpi = 240)
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
  df$context_compact <- compact_context(df, c("condition", "stage", "tissue", "sex"), include_names = FALSE)
  color_fields <- informative_fields(df, c("batch", "dataset"), require_variation = TRUE)
  color_field <- if (length(color_fields) > 0) color_fields[[1]] else NULL
  p <- ggplot(df, aes(x = context_compact, y = log2TPM)) +
    geom_boxplot(outlier.shape = NA, alpha = 0.18, color = "#587187")
  if (!is.null(color_field)) {
    p <- p + geom_jitter(aes(color = .data[[color_field]]), width = 0.16, alpha = 0.72, size = 1.7) +
      labs(color = metadata_labels[[color_field]])
  } else {
    p <- p + geom_jitter(width = 0.16, alpha = 0.72, size = 1.7, color = "#2b6f9f")
  }
  p <- p +
    theme_bw(base_size = 10) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = label, x = "Contexto biologico informativo", y = expression_log_label)
  ggsave(outfile, p, width = 11, height = 6.5, dpi = 240)
  TRUE
}

plot_gene_batch_boxplot <- function(df, outfile, label) {
  fields <- informative_fields(df, c("batch", "dataset"), require_variation = TRUE)
  if (length(fields) == 0) return(FALSE)
  x_field <- fields[[1]]
  color_fields <- informative_fields(df, c("condition", "stage", "tissue", "sex"), require_variation = TRUE)
  color_field <- if (length(color_fields) > 0) color_fields[[1]] else NULL
  p <- ggplot(df, aes(x = .data[[x_field]], y = log2TPM)) +
    geom_boxplot(outlier.shape = NA, alpha = 0.7) +
    theme_bw(base_size = 10)
  if (!is.null(color_field)) {
    p <- p + geom_jitter(aes(color = .data[[color_field]]), width = 0.18, alpha = 0.6, size = 1.6) +
      labs(color = metadata_labels[[color_field]])
  } else {
    p <- p + geom_jitter(width = 0.18, alpha = 0.6, size = 1.6, color = "#2b6f9f")
  }
  p <- p +
    theme_bw(base_size = 10) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = paste("Efeito tecnico:", label), x = metadata_labels[[x_field]], y = expression_log_label)
  ggsave(outfile, p, width = 10, height = 6, dpi = 240)
  TRUE
}

plot_gene_profile_line <- function(df, outfile, label) {
  stage_informative <- length(informative_fields(df, "stage", require_variation = TRUE)) > 0
  if (!stage_informative) return(FALSE)
  profile_df <- df %>%
    dplyr::group_by(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex) %>%
    dplyr::summarise(mean_log2TPM = mean(log2TPM, na.rm = TRUE),
                     se_log2TPM = stats::sd(log2TPM, na.rm = TRUE) / sqrt(dplyr::n()), .groups = "drop")
  color_fields <- informative_fields(profile_df, c("condition", "tissue", "sex", "batch", "dataset"), require_variation = TRUE)
  color_field <- if (length(color_fields) > 0) color_fields[[1]] else NULL
  if (!is.null(color_field)) {
    line_df <- profile_df %>%
      dplyr::group_by(.data[[color_field]]) %>%
      dplyr::filter(dplyr::n_distinct(stage) > 1) %>%
      dplyr::ungroup()
  } else {
    line_df <- profile_df %>%
      dplyr::filter(dplyr::n_distinct(stage) > 1)
  }
  if (!is.null(color_field)) {
    p <- ggplot(profile_df, aes(x = stage, y = mean_log2TPM, color = .data[[color_field]], group = .data[[color_field]])) +
      labs(color = metadata_labels[[color_field]])
  } else {
    p <- ggplot(profile_df, aes(x = stage, y = mean_log2TPM, group = 1))
  }
  p <- p +
    geom_errorbar(aes(ymin = mean_log2TPM - se_log2TPM, ymax = mean_log2TPM + se_log2TPM), width = 0.12, alpha = 0.45, na.rm = TRUE) +
    geom_point(size = 2.4) +
    theme_bw(base_size = 9) +
    theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
    labs(title = paste("Perfil por estagio:", label), subtitle = "Pontos: media; barras: erro-padrao",
         x = "Estagio", y = expression_mean_log_label)
  if (nrow(line_df) > 0) p <- p + geom_line(data = line_df, alpha = 0.75)
  ggsave(outfile, p, width = 10, height = 6, dpi = 240)
  TRUE
}

plot_gene_sample_tile <- function(df, outfile, label) {
  tile_df <- df %>%
    dplyr::mutate(sample_context = as.character(sample_id)) %>%
    dplyr::arrange(dataset, batch, condition, stage_class, stage_day, stage, tissue, sex, sample_id)
  p <- ggplot(tile_df, aes(x = sample_context, y = gene_display_label, fill = log2TPM)) +
    geom_tile(color = "white") +
    scale_fill_viridis_c(option = "C") +
    theme_bw(base_size = 8) +
    theme(axis.text.x = if (nrow(tile_df) <= 40) element_text(angle = 60, hjust = 1) else element_blank(),
          axis.ticks.x = if (nrow(tile_df) <= 40) element_line() else element_blank(), panel.grid = element_blank()) +
    labs(title = paste("Expressao por amostra:", label), x = "Amostra", y = "", fill = expression_log_label)
  ggsave(outfile, p, width = min(14, max(8, nrow(tile_df) * 0.12)), height = 3.3, dpi = 180)
  TRUE
}

plot_gene_deg_lollipop <- function(deg_df, outfile, label) {
  if (nrow(deg_df) == 0) return(FALSE)
  df <- deg_df %>%
    dplyr::mutate(contrast_display = join_nonempty(deg_project, deg_mode, contrast)) %>%
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
  shape_fields <- informative_fields(deg_df, "deg_project", require_variation = TRUE)
  facet_fields <- informative_fields(deg_df, "deg_mode", require_variation = TRUE)
  p <- ggplot(deg_df, aes(x = log2FoldChange_num, y = neg_log10_padj, color = significant)) +
    geom_vline(xintercept = c(-1, 1), linetype = "dashed", color = "gray70") +
    geom_hline(yintercept = -log10(0.05), linetype = "dashed", color = "gray70") +
    scale_color_manual(values = c("FALSE" = "gray55", "TRUE" = "#b2182b")) +
    theme_bw(base_size = 10) +
    labs(title = paste("Contrastes DEG:", label), x = "log2FC", y = "-log10(padj)", color = "Significativo")
  if (length(shape_fields) > 0 && dplyr::n_distinct(deg_df$deg_project) <= 6) {
    p <- p + geom_point(aes(shape = deg_project), size = 2.4, alpha = 0.85) + labs(shape = "Projeto")
  } else {
    p <- p + geom_point(size = 2.4, alpha = 0.85)
  }
  if (length(facet_fields) > 0) p <- p + facet_wrap(~ deg_mode)
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
  gene_keys <- expr_long %>% dplyr::distinct(gene_id, gene_name, gene_display_label, biotype)
  for (i in seq_len(nrow(gene_keys))) {
    key <- gene_keys[i, ]
    gene_dir <- file.path(out_dir, "genes", sanitize(key$gene_id))
    dir.create(gene_dir, recursive = TRUE, showWarnings = FALSE)
    df <- expr_long %>%
      dplyr::filter(gene_id == key$gene_id) %>%
      dplyr::distinct(import_id, .keep_all = TRUE)
    deg_df <- deg_hits %>% dplyr::filter(gene_id == key$gene_id)
    label <- key$gene_display_label
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
    grepl("pca", caption_l) ~ "Ordenação exploratória calculada somente com os genes candidatos. Separações podem refletir biologia, lote técnico ou amostras discrepantes; não substitui uma PCA transcriptômica global.",
    grepl("mds", caption_l) ~ "Resume as distâncias entre amostras usando somente os genes candidatos. Pontos próximos possuem perfis semelhantes dentro deste painel.",
    grepl("correla", caption_l) ~ "Correlação de Spearman entre os perfis dos genes candidatos. Valores altos indicam variação coordenada, não causalidade.",
    grepl("dotplot|fra", caption_l) ~ "Combina expressão média e, quando informativa, a proporção de amostras acima do limiar de expressão.",
    grepl("heatmap gene x amostra|amostra", caption_l) ~ "Expressão por amostra individual. Metadados constantes ou não informados são omitidos para reduzir ruído visual.",
    grepl("heatmap|express", caption_l) ~ paste0("Expressão média por contexto. Quando indicado na figura, as cores representam z-score por gene; caso contrário, representam log2(", expression_unit, " + 1)."),
    grepl("ov.rio|test.culo", caption_l) ~ "Comparação específica entre tecidos reprodutivos, produzida somente quando a metadata permite essa análise.",
    grepl("batch|projeto|efeito t.cnico", caption_l) ~ "Distribuição exploratória por covariáveis técnicas que realmente variam neste estudo.",
    grepl("log2fc|deg|contraste|dire", caption_l) ~ "Efeitos diferenciais por contraste. log2FC informa direção e magnitude; padj representa significância após correção para múltiplos testes.",
    grepl("perfil agregado|perfil por est", caption_l) ~ "Tendência média ao longo dos estágios disponíveis; as barras representam erro-padrão quando há replicação.",
    TRUE ~ "Visualização exploratória para revisar expressão, consistência entre amostras e possíveis efeitos técnicos."
  )
}

img_tag <- function(src, caption, deferred = FALSE, featured = FALSE) {
  if (!file.exists(file.path(out_dir, src))) return("")
  explanation <- figure_explanation(caption)
  search_text <- paste(caption, explanation, src)
  normalized_src <- gsub("\\\\", "/", src)
  image_attribute <- if (deferred) paste0("data-src='", normalized_src, "'") else paste0("src='", normalized_src, "'")
  loading_mode <- if (featured) "eager" else "lazy"
  priority_attribute <- if (featured) " fetchpriority='high'" else ""
  class_name <- if (featured) "report-figure featured" else "report-figure"
  paste0(
    "<figure class='searchable ", class_name, "' data-kind='figure' data-search='", html_escape(tolower(search_text)), "'>",
    "<a class='figure-link' href='", normalized_src, "' target='_blank' rel='noopener' title='Abrir imagem em resolução completa'>",
    "<img ", image_attribute, " loading='", loading_mode, "' decoding='async'", priority_attribute, " alt='", html_escape(caption), "'>",
    "</a>",
    "<figcaption><strong>", html_escape(caption), "</strong><span>", html_escape(explanation), "</span>",
    "<a class='download-link' href='", normalized_src, "' download>Baixar PNG</a></figcaption>",
    "</figure>"
  )
}

write_html_report <- function(path, title, catalog, gene_summary, deg_hits, global_plots, expression_unit = "TPM") {
  if (is.na(expression_unit) || expression_unit == "") expression_unit <- "TPM"
  unique_gene_count <- length(unique(catalog$matched_gene_id))
  found_gene_count <- length(unique(catalog$matched_gene_id[catalog$found_in_expression_matrix %in% TRUE]))
  missing_gene_count <- unique_gene_count - found_gene_count
  sample_count <- if (nrow(gene_summary) == 0 || all(is.na(gene_summary$n_samples))) 0 else max(gene_summary$n_samples, na.rm = TRUE)
  contrast_count <- length(unique(deg_hits$contrast_label[!is_placeholder_value(deg_hits$contrast_label)]))
  significant_gene_count <- length(unique(deg_hits$gene_id[deg_hits$significant %in% TRUE]))

  group_links <- paste(vapply(unique(catalog$group), function(grp) {
    paste0("<li><a href='#group_", sanitize(grp), "'>", html_escape(grp), "</a></li>")
  }, character(1)), collapse = "\n")

  gene_index <- paste(vapply(seq_len(nrow(catalog)), function(i) {
    row <- catalog[i, ]
    search_text <- paste(row$group, row$query, row$matched_gene_id, row$gene_name, row$gene_display_label, row$biotype, row$description, row$chromosome, row$location)
    found <- isTRUE(row$found_in_expression_matrix)
    status_class <- if (found) "found" else "missing"
    status_text <- if (found) "Encontrado" else "Ausente"
    paste0(
      "<a class='searchable gene-chip ", status_class, "' data-kind='gene' data-status='", status_class,
      "' data-search='", html_escape(tolower(search_text)), "' href='#gene_", sanitize(row$group), "_", sanitize(row$matched_gene_id), "'>",
      "<span class='gene-chip-title'>", html_escape(row$gene_display_label), "</span>",
      "<span class='badge ", status_class, "'>", status_text, "</span>",
      "<small>", html_escape(row$group), " · ", html_escape(row$biotype), "</small>",
      "</a>"
    )
  }, character(1)), collapse = "\n")

  group_sections <- paste(vapply(unique(catalog$group), function(grp) {
    group_dir <- file.path("groups", sanitize(grp))
    group_catalog <- catalog %>%
      dplyr::filter(group == grp) %>%
      dplyr::select(group, query, query_display, matched_gene_id, gene_name, gene_display_label, biotype, chromosome, gene_start, gene_end, strand, location, found_in_expression_matrix)
    group_search <- paste(group_catalog$group, group_catalog$query, group_catalog$matched_gene_id, group_catalog$gene_name, group_catalog$gene_display_label, group_catalog$biotype, group_catalog$chromosome, group_catalog$location, collapse = " ")
    found_count <- sum(group_catalog$found_in_expression_matrix, na.rm = TRUE)
    paste0(
      "<details class='searchable group-section disclosure' data-kind='group' data-search='", html_escape(tolower(group_search)), "' id='group_", sanitize(grp), "'>",
      "<summary><span><strong>", html_escape(grp), "</strong><small>", found_count, " de ", nrow(group_catalog), " genes encontrados</small></span><span class='summary-action'>Explorar grupo</span></summary>",
      "<div class='disclosure-body'>",
      "<div class='figure-grid'>",
      img_tag(file.path(group_dir, "expression_heatmap.png"), "Expressão média por contexto biológico", deferred = TRUE),
      img_tag(file.path(group_dir, "expression_dotplot.png"), "Expressão média e fração expressa por contexto", deferred = TRUE),
      img_tag(file.path(group_dir, "sample_heatmap.png"), "Expressão nas amostras individuais", deferred = TRUE),
      img_tag(file.path(group_dir, "sample_heatmap_annotated.png"), "Heatmap gene × amostra com anotações informativas", deferred = TRUE),
      img_tag(file.path(group_dir, "gene_correlation.png"), "Correlação de expressão entre genes do grupo", deferred = TRUE),
      img_tag(file.path(group_dir, "sample_pca.png"), "PCA das amostras usando apenas genes do grupo", deferred = TRUE),
      img_tag(file.path(group_dir, "sample_mds.png"), "MDS das amostras usando apenas genes do grupo", deferred = TRUE),
      img_tag(file.path(group_dir, "aggregate_profile.png"), "Perfil agregado do grupo", deferred = TRUE),
      img_tag(file.path(group_dir, "ovary_testis_panel.png"), "Comparação ovário versus testículo", deferred = TRUE),
      img_tag(file.path(group_dir, "batch_project_boxplot.png"), "Distribuição por covariáveis técnicas", deferred = TRUE),
      img_tag(file.path(group_dir, "deg_log2fc_heatmap.png"), "log2FC dos genes do grupo nos contrastes DEG", deferred = TRUE),
      img_tag(file.path(group_dir, "deg_context_tile.png"), "Significância e efeito por contraste", deferred = TRUE),
      img_tag(file.path(group_dir, "deg_direction_summary.png"), "Direção DEG por contraste", deferred = TRUE),
      "</div>",
      "<details class='data-disclosure'><summary><strong>Catálogo completo do grupo</strong><span>", nrow(group_catalog), " entradas</span></summary><div>",
      table_to_html(group_catalog, 100),
      "</div></details></div></details>"
    )
  }, character(1)), collapse = "\n")

  gene_sections <- paste(vapply(seq_len(nrow(catalog)), function(i) {
    row <- catalog[i, ]
    gene_dir <- file.path("genes", sanitize(row$matched_gene_id))
    deg_table <- deg_hits %>%
      dplyr::filter(gene_id == row$matched_gene_id) %>%
      dplyr::select(gene_display_label, deg_project, deg_mode, contrast, log2FoldChange_num, padj_num, significant) %>%
      dplyr::arrange(padj_num)
    gene_search <- paste(row$group, row$query, row$matched_gene_id, row$gene_name, row$gene_display_label, row$biotype, row$description, row$chromosome, row$location, paste(deg_table$contrast, collapse = " "))
    found <- isTRUE(row$found_in_expression_matrix)
    status_class <- if (found) "found" else "missing"
    status_text <- if (found) "Encontrado na matriz" else "Ausente da matriz"
    figures <- if (found) paste0(
      "<div class='figure-grid'>",
      img_tag(file.path(gene_dir, "expression_tissue_sex_condition.png"), "Distribuição da expressão nos contextos biológicos", deferred = TRUE),
      img_tag(file.path(gene_dir, "expression_batch_project.png"), "Expressão por covariável técnica", deferred = TRUE),
      img_tag(file.path(gene_dir, "expression_stage_profile.png"), "Perfil por estágio", deferred = TRUE),
      img_tag(file.path(gene_dir, "expression_sample_tile.png"), "Expressão por amostra individual", deferred = TRUE),
      img_tag(file.path(gene_dir, "deg_lollipop.png"), "Efeito DEG nos contrastes disponíveis", deferred = TRUE),
      img_tag(file.path(gene_dir, "deg_scatter.png"), "Magnitude e significância nos contrastes DEG", deferred = TRUE),
      "</div>"
    ) else paste0(
      "<div class='missing-note'><strong>Sem figuras de expressão.</strong> O identificador não foi localizado na matriz fornecida. ",
      "Verifique a versão da anotação, aliases e a política de normalização de IDs.</div>"
    )
    paste0(
      "<details class='searchable gene disclosure ", status_class, "' data-kind='gene' data-status='", status_class,
      "' data-search='", html_escape(tolower(gene_search)), "' id='gene_", sanitize(row$group), "_", sanitize(row$matched_gene_id), "'>",
      "<summary><span><strong>", html_escape(row$gene_display_label), "</strong><small>", html_escape(row$group), " · ", html_escape(row$biotype), "</small></span>",
      "<span class='badge ", status_class, "'>", status_text, "</span></summary>",
      "<div class='disclosure-body'>",
      "<p class='gene-meta'><b>Grupo:</b> ", html_escape(row$group),
      " | <b>Query:</b> ", html_escape(row$query),
      " | <b>Localização:</b> ", html_escape(row$location), "</p>",
      "<p>", html_escape(row$description), "</p>",
      figures,
      "<h4>Resultados diferenciais do gene</h4>",
      table_to_html(deg_table, 50),
      "</div></details>"
    )
  }, character(1)), collapse = "\n")

  html <- c(
    "<!doctype html><html><head><meta charset='utf-8'>",
    paste0("<title>", html_escape(title), "</title>"),
    "<style>
      :root{--ink:#152536;--muted:#617385;--navy:#173a5e;--blue:#256a9d;--line:#dce4eb;--soft:#f5f8fa;--success:#167453;--success-bg:#e9f7f0;--warn:#a44b20;--warn-bg:#fff1e8;--shadow:0 12px 35px rgba(20,46,70,.09)}
      *{box-sizing:border-box}html{scroll-behavior:smooth}body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#edf2f5;color:var(--ink);line-height:1.55}
      .page{max-width:1440px;margin:0 auto;background:#fff;min-height:100vh;box-shadow:0 0 55px rgba(20,46,70,.10)}
      .hero{padding:48px 6vw 36px;background:linear-gradient(135deg,#102d49 0%,#1c527d 62%,#287da0 100%);color:#fff}.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:12px;font-weight:800;opacity:.78}.hero h1{font-size:clamp(30px,4vw,52px);line-height:1.08;margin:8px 0 12px}.hero p{max-width:850px;margin:0;color:#dbe9f3;font-size:17px}
      nav{position:sticky;top:0;display:flex;gap:4px;align-items:center;overflow-x:auto;background:rgba(255,255,255,.97);border-bottom:1px solid var(--line);padding:10px 5vw;z-index:20;backdrop-filter:blur(12px)}nav a{white-space:nowrap;padding:8px 11px;border-radius:8px;color:var(--navy);text-decoration:none;font-weight:700;font-size:14px}nav a:hover{background:#eaf2f8}
      main{padding:28px 5vw 70px}section{scroll-margin-top:72px}.section-heading{display:flex;align-items:end;justify-content:space-between;gap:20px;margin:52px 0 18px}.section-heading h2{margin:0;color:var(--navy);font-size:28px}.section-heading p{margin:0;color:var(--muted);max-width:700px}
      .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px;margin:20px 0}.card{background:var(--soft);border:1px solid var(--line);border-radius:14px;padding:18px}.card .num{font-size:32px;line-height:1;font-weight:800;color:var(--navy);margin-bottom:8px}.card.warn{background:var(--warn-bg);border-color:#f2ccb7}.card.warn .num{color:var(--warn)}.card.success{background:var(--success-bg);border-color:#bde6d4}.card.success .num{color:var(--success)}
      .notice{background:#eef6fb;border-left:4px solid var(--blue);padding:15px 18px;border-radius:0 10px 10px 0;margin:22px 0;color:#29465f}.missing-note{background:var(--warn-bg);border:1px solid #f2ccb7;padding:14px 16px;border-radius:10px;color:#713a20}
      .toolbar{position:sticky;top:58px;background:rgba(255,255,255,.97);border:1px solid var(--line);border-radius:12px;padding:12px;margin:18px 0 24px;z-index:15;box-shadow:0 6px 18px rgba(20,45,70,.08);backdrop-filter:blur(10px)}.toolbar-row{display:flex;gap:10px}.toolbar input[type=search]{width:100%;font-size:15px;padding:11px 13px;border:1px solid #b9c7d3;border-radius:8px}.filters{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:13px;color:#34495e}.filters label{display:inline-flex;gap:6px;align-items:center}.search-count{font-size:13px;color:var(--muted);margin-top:8px}
      .gene-index{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:9px}.gene-chip{position:relative;display:block;border:1px solid var(--line);border-radius:10px;padding:12px 92px 11px 12px;text-decoration:none;color:var(--navy);background:#fff;min-height:72px}.gene-chip:hover{transform:translateY(-1px);box-shadow:0 6px 15px rgba(20,45,70,.08)}.gene-chip.missing{background:#fffaf7}.gene-chip-title{display:block;font-weight:750;overflow-wrap:anywhere}.gene-chip small{display:block;color:var(--muted);margin-top:4px}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:800;white-space:nowrap}.gene-chip .badge{position:absolute;right:9px;top:10px}.badge.found{background:var(--success-bg);color:var(--success)}.badge.missing{background:var(--warn-bg);color:var(--warn)}
      .figure-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:18px;align-items:start}.report-figure{margin:0;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 5px 18px rgba(20,45,70,.06)}.report-figure.featured{grid-column:1/-1}.figure-link{display:block;background:#f6f8fa;min-height:180px}.report-figure img{display:block;width:100%;height:auto;border:0;margin:0}.report-figure.featured img{max-height:720px;object-fit:contain}.report-figure img:not([src]){min-height:260px;background:linear-gradient(110deg,#eef2f5 8%,#f7f9fa 18%,#eef2f5 33%);background-size:200% 100%;animation:shimmer 1.4s linear infinite}figcaption{padding:14px 16px 15px;font-size:13px;color:var(--muted)}figcaption strong{display:block;color:var(--ink);font-size:15px}figcaption span{display:block;margin-top:5px}.download-link{display:inline-block;margin-top:10px;color:var(--blue);font-weight:750;text-decoration:none}@keyframes shimmer{to{background-position-x:-200%}}
      .disclosure{border:1px solid var(--line);border-radius:12px;margin:10px 0;background:#fff;overflow:hidden;scroll-margin-top:130px}.disclosure>summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:16px;padding:16px 18px}.disclosure>summary::-webkit-details-marker{display:none}.disclosure>summary:hover{background:var(--soft)}.disclosure>summary strong{display:block;color:var(--navy);font-size:16px}.disclosure>summary small{display:block;color:var(--muted);margin-top:3px}.summary-action{font-size:12px;color:var(--blue);font-weight:800}.disclosure[open]>summary{border-bottom:1px solid var(--line);background:var(--soft)}.disclosure-body{padding:18px}.gene.missing{border-color:#f2ccb7}.data-disclosure{margin-top:20px;border-top:1px solid var(--line);padding-top:10px}.data-disclosure>summary{cursor:pointer;display:flex;justify-content:space-between;color:var(--navy);padding:10px 2px}.data-disclosure>div{padding-top:4px}
      .guide{background:var(--soft);border:1px solid var(--line);border-radius:14px;padding:20px}.guide dl{display:grid;grid-template-columns:minmax(160px,230px) 1fr;gap:10px 18px;margin:0}.guide dt{font-weight:800;color:var(--navy)}.guide dd{margin:0;color:#42576a}
      .table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px;margin:10px 0 22px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border-bottom:1px solid #e6ebef;padding:8px;vertical-align:top;text-align:left}th{position:sticky;top:0;background:#f3f6f8;color:#33495e}tr:last-child td{border-bottom:0}code{background:#eef2f5;padding:2px 5px;border-radius:4px}.hidden-by-search{display:none!important}.group-links{display:flex;flex-wrap:wrap;gap:8px;padding:0;list-style:none}.group-links a{display:block;background:#eef5fa;color:var(--navy);padding:8px 11px;border-radius:8px;text-decoration:none;font-weight:700}
      @media(max-width:720px){.hero{padding:36px 22px 28px}main{padding:22px 16px 55px}nav{padding:8px 12px}.toolbar{top:54px}.guide dl{grid-template-columns:1fr}.figure-grid{grid-template-columns:1fr}.disclosure>summary{align-items:flex-start;flex-direction:column}.gene-chip{padding-right:12px}.gene-chip .badge{position:static;margin-top:8px}}
      @media print{body{background:#fff}.page{box-shadow:none}nav,.toolbar,.download-link{display:none!important}.disclosure:not([open])>.disclosure-body{display:block}.report-figure{break-inside:avoid}}
    </style>",
    "<script>
      document.addEventListener('DOMContentLoaded', function(){
        var input = document.getElementById('geneSearch');
        var count = document.getElementById('searchCount');
        var statusToggles = Array.prototype.slice.call(document.querySelectorAll('[data-filter-status]'));
        var items = Array.prototype.slice.call(document.querySelectorAll('.gene-chip,.group-section,.gene'));
        function hydrate(container){
          Array.prototype.slice.call(container.querySelectorAll('img[data-src]')).forEach(function(img){
            img.setAttribute('src', img.getAttribute('data-src'));
            img.removeAttribute('data-src');
          });
        }
        function applySearch(){
          var query = (input.value || '').trim().toLowerCase();
          var statuses = statusToggles.filter(function(t){return t.checked;}).map(function(t){return t.getAttribute('data-filter-status');});
          var visible = 0;
          items.forEach(function(el){
            var text = el.getAttribute('data-search') || el.textContent.toLowerCase();
            var status = el.getAttribute('data-status') || '';
            var statusOk = status === '' || statuses.indexOf(status) !== -1;
            var queryOk = query === '' || text.indexOf(query) !== -1;
            var show = statusOk && queryOk;
            el.classList.toggle('hidden-by-search', !show);
            if (show && el.classList.contains('gene-chip')) visible += 1;
            if (show && query !== '' && el.tagName === 'DETAILS') el.open = true;
          });
          count.textContent = query === '' ? visible + ' entradas disponíveis.' : visible + ' entradas encontradas para \"' + query + '\".';
        }
        input.addEventListener('input', applySearch);
        statusToggles.forEach(function(t){t.addEventListener('change', applySearch);});
        Array.prototype.slice.call(document.querySelectorAll('details')).forEach(function(detail){
          detail.addEventListener('toggle', function(){if(detail.open) hydrate(detail);});
        });
        document.addEventListener('click', function(event){
          var link = event.target.closest('a[href^=\"#gene_\"],a[href^=\"#group_\"]');
          if(!link) return;
          var target = document.querySelector(link.getAttribute('href'));
          if(target && target.tagName === 'DETAILS'){target.open = true;hydrate(target);}
        });
        if(location.hash){var target=document.querySelector(location.hash);if(target&&target.tagName==='DETAILS'){target.open=true;hydrate(target);}}
        applySearch();
      });
    </script>",
    "</head><body><div class='page'>",
    "<nav aria-label='Navegação do relatório'><a href='#overview'>Visão geral</a><a href='#global'>Evidências globais</a><a href='#genes'>Genes</a><a href='#groups'>Grupos</a><a href='#guide'>Como interpretar</a><a href='#tables'>Dados</a></nav>",
    "<main>",
    "<div class='toolbar' role='search'>",
    "<div class='toolbar-row'><input id='geneSearch' type='search' placeholder='Buscar por gene, ID, grupo, biotipo, descrição ou contraste' aria-label='Buscar no relatório'></div>",
    "<div class='filters'>",
    "<strong>Status:</strong>",
    "<label><input type='checkbox' data-filter-status='found' checked>Encontrados</label>",
    "<label><input type='checkbox' data-filter-status='missing' checked>Ausentes</label>",
    "</div>",
    "<div class='search-count' id='searchCount' aria-live='polite'>Índice completo.</div>",
    "</div>",
    "<section id='overview'>",
    "<div class='section-heading'><div><h2>Visão geral</h2><p>Dimensões do painel e cobertura dos identificadores solicitados.</p></div></div>",
    "<div class='cards'>",
    paste0("<div class='card'><div class='num'>", unique_gene_count, "</div><div>genes únicos solicitados</div></div>"),
    paste0("<div class='card success'><div class='num'>", found_gene_count, "</div><div>encontrados na matriz</div></div>"),
    paste0("<div class='card warn'><div class='num'>", missing_gene_count, "</div><div>ausentes da matriz</div></div>"),
    paste0("<div class='card'><div class='num'>", sample_count, "</div><div>amostras analisadas</div></div>"),
    paste0("<div class='card'><div class='num'>", length(unique(catalog$group)), "</div><div>grupos funcionais</div></div>"),
    paste0("<div class='card'><div class='num'>", contrast_count, "</div><div>contrastes disponíveis</div></div>"),
    paste0("<div class='card'><div class='num'>", significant_gene_count, "</div><div>genes candidatos com sinal DEG</div></div>"),
    "</div>",
    "</section>",
    "<section id='global'>",
    "<div class='section-heading'><div><h2>Evidências globais</h2><p>Primeiro, revise os padrões do painel completo. Clique em qualquer figura para abrir a resolução original.</p></div></div>",
    "<div class='figure-grid'>",
    img_tag(global_plots$annotated_sample_heatmap, "Heatmap gene × amostra com anotações informativas", featured = TRUE),
    img_tag(global_plots$heatmap, "Expressão média integrada por contexto"),
    img_tag(global_plots$sample_pca, "PCA das amostras usando os genes candidatos"),
    img_tag(global_plots$deg_heatmap, "Efeitos diferenciais nos contrastes disponíveis"),
    img_tag(global_plots$dotplot, "Expressão média e fração expressa"),
    img_tag(global_plots$gene_correlation, "Correlação de expressão entre genes"),
    img_tag(global_plots$sample_mds, "MDS das amostras usando os genes candidatos"),
    img_tag(global_plots$tissue_sex_heatmap, "Padrões por tecido e sexo"),
    img_tag(global_plots$ovary_testis, "Comparação ovário versus testículo"),
    img_tag(global_plots$group_aggregate, "Perfil agregado por grupo"),
    img_tag(global_plots$batch_project, "Distribuição por covariáveis técnicas"),
    img_tag(global_plots$deg_tile, "Significância e efeito por contraste"),
    img_tag(global_plots$deg_direction, "Direção DEG por contraste"),
    "</div></section>",
    "<section id='genes'><div class='section-heading'><div><h2>Genes candidatos</h2><p>Use a busca e os filtros de status. Genes ausentes permanecem visíveis para preservar a auditoria da lista solicitada.</p></div></div><div class='gene-index'>", gene_index, "</div>", gene_sections, "</section>",
    "<section id='groups'><div class='section-heading'><div><h2>Grupos funcionais</h2><p>As visualizações detalhadas são carregadas somente quando o grupo é aberto.</p></div></div><ul class='group-links'>", group_links, "</ul>", group_sections, "</section>",
    "<section class='guide' id='guide'><div class='section-heading'><div><h2>Como interpretar</h2><p>Definições essenciais para evitar interpretações além do que os dados permitem.</p></div></div>",
    "<dl>",
    paste0("<dt>", html_escape(expression_unit), " e log2(", html_escape(expression_unit), " + 1)</dt><dd>A transformação logarítmica reduz a dominância dos genes muito abundantes. Quando o heatmap usa z-score por linha, ele compara o padrão relativo de cada gene, não sua abundância absoluta.</dd>"),
    "<dt>Heatmaps</dt><dd>Use para localizar blocos de expressão e avaliar consistência entre replicatas. Metadados invariantes são omitidos automaticamente.</dd>",
    "<dt>PCA/MDS</dt><dd>São ordenações do painel de candidatos, não controles transcriptômicos globais. Separações podem refletir condição, estágio, lote ou confundimento.</dd>",
    "<dt>DEG</dt><dd>log2FC mostra direção e magnitude do efeito; padj considera múltiplos testes. Significância estatística não implica relevância biológica isoladamente.</dd>",
    "<dt>Genes ausentes</dt><dd>Um gene ausente pode refletir versão da referência, alias ou política de normalização de IDs; sua ausência é mantida como evidência auditável.</dd>",
    "<dt>Busca</dt><dd>Digite ID, nome, grupo, biotipo, descrição ou contraste. Abrir uma seção carrega apenas as imagens necessárias.</dd>",
    "</dl></section>",
    "<section id='tables'><div class='section-heading'><div><h2>Dados e auditoria</h2><p>As tabelas completas permanecem disponíveis ao lado do HTML e são a fonte primária para reanálise.</p></div></div>",
    "<p>Arquivos: <code>tables/gene_catalog.tsv</code>, <code>tables/gene_expression_summary.tsv</code>, <code>tables/expression_long.tsv</code>, <code>tables/expression_summary_by_context.tsv</code> e <code>tables/deg_hits.tsv</code>.</p>",
    table_to_html(gene_summary, 100),
    "</section>",
    "</main></div></body></html>"
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
