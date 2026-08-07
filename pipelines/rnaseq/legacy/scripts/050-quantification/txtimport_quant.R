#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(tximport)
  library(readr)
  library(dplyr)
  library(rtracklayer)
  library(tibble)
})

args <- commandArgs(trailingOnly = TRUE)

get_arg <- function(flag, default = NULL) {
  idx <- match(flag, args)
  if (is.na(idx) || idx == length(args)) {
    return(default)
  }
  args[[idx + 1]]
}

has_flag <- function(flag) {
  flag %in% args
}

project <- get_arg("--project", Sys.getenv("PROJECT", unset = ""))
metadata_file <- get_arg("--metadata", Sys.getenv("METADATA_FINAL_NEW", unset = ""))
quant_root <- get_arg("--quant-root", Sys.getenv("QUANT_DIR", unset = ""))
gtf_file <- get_arg("--gtf", Sys.getenv("REF_GTF", unset = ""))
out_dir <- get_arg("--output-dir", Sys.getenv("QUANTIFICATION_DIR", unset = getwd()))
counts_name <- get_arg("--counts-name", ifelse(project == "", "counts_matrix.tsv", paste0(project, "_counts_matrix.tsv")))
tpm_name <- get_arg("--tpm-name", ifelse(project == "", "tpm_matrix.tsv", paste0(project, "_tpm_matrix.tsv")))
sample_table_name <- get_arg("--sample-table-name", ifelse(project == "", "quant_samples.tsv", paste0(project, "_quant_samples.tsv")))
tx2gene_out <- get_arg("--tx2gene-out", file.path(out_dir, "tx2gene.tsv"))
allow_missing <- has_flag("--allow-missing")

required_paths <- c(
  metadata = metadata_file,
  quant_root = quant_root,
  gtf = gtf_file
)

missing_args <- names(required_paths)[required_paths == ""]
if (length(missing_args) > 0) {
  stop("[ERRO] Argumentos/caminhos ausentes: ", paste(missing_args, collapse = ", "))
}

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

cat("[INFO] Metadata: ", metadata_file, "\n", sep = "")
cat("[INFO] Quant root: ", quant_root, "\n", sep = "")
cat("[INFO] GTF: ", gtf_file, "\n", sep = "")
cat("[INFO] Output dir: ", out_dir, "\n", sep = "")

metadata <- readr::read_csv(metadata_file, show_col_types = FALSE, col_types = cols(.default = col_character()))

required_cols <- c("dataset", "sample_id")
missing_cols <- setdiff(required_cols, colnames(metadata))
if (length(missing_cols) > 0) {
  stop("[ERRO] Metadata sem colunas obrigatorias: ", paste(missing_cols, collapse = ", "))
}

sample_meta <- metadata %>%
  filter(!is.na(sample_id), sample_id != "") %>%
  distinct(dataset, sample_id, .keep_all = TRUE)

if (project != "") {
  sample_meta <- sample_meta %>% filter(dataset == project)
}

if (nrow(sample_meta) == 0) {
  stop("[ERRO] Nenhuma amostra encontrada no metadata", ifelse(project == "", ".", paste0(" para ", project, ".")))
}

sample_meta <- sample_meta %>%
  arrange(dataset, sample_id) %>%
  mutate(
    import_id = ifelse(project == "", paste(dataset, sample_id, sep = "__"), sample_id),
    quant_file = file.path(quant_root, dataset, sample_id, "quant.sf"),
    quant_exists = file.exists(quant_file)
  )

if (any(duplicated(sample_meta$import_id))) {
  duplicated_ids <- unique(sample_meta$import_id[duplicated(sample_meta$import_id)])
  stop("[ERRO] IDs de importacao duplicados: ", paste(head(duplicated_ids, 20), collapse = ", "))
}

missing_quant <- sample_meta %>% filter(!quant_exists)
if (nrow(missing_quant) > 0 && !allow_missing) {
  stop(
    "[ERRO] quant.sf ausente para ", nrow(missing_quant), " amostras, ex.: ",
    paste(head(missing_quant$sample_id, 20), collapse = ", "),
    "\nUse --allow-missing apenas se quiser importar o subconjunto existente."
  )
}

if (nrow(missing_quant) > 0 && allow_missing) {
  warning("[WARN] Ignorando ", nrow(missing_quant), " amostras sem quant.sf.")
  sample_meta <- sample_meta %>% filter(quant_exists)
}

if (nrow(sample_meta) == 0) {
  stop("[ERRO] Nenhum quant.sf disponivel para importar.")
}

cat("[INFO] Amostras importadas: ", nrow(sample_meta), "\n", sep = "")

cat("[INFO] Extraindo relacao transcript-gene do GTF...\n")
gtf_data <- rtracklayer::import(gtf_file)
tx2gene <- as.data.frame(gtf_data) %>%
  filter(type == "transcript") %>%
  select(transcript_id, gene_id) %>%
  mutate(
    transcript_id = gsub("^transcript:", "", transcript_id),
    transcript_id = gsub("\\.[0-9]+$", "", transcript_id),
    gene_id = ifelse(
      grepl("^transcript:", gene_id),
      gsub("^transcript:", "gene:", gene_id),
      gene_id
    ),
    gene_id = gsub("^gene:", "", gene_id),
    gene_id = gsub("\\.[0-9]+$", "", gene_id)
  ) %>%
  distinct() %>%
  filter(!is.na(transcript_id), transcript_id != "", !is.na(gene_id), gene_id != "")

if (nrow(tx2gene) == 0) {
  stop("[ERRO] Nenhuma relacao transcript-gene extraida do GTF.")
}

readr::write_tsv(tx2gene, tx2gene_out)

files <- sample_meta$quant_file
names(files) <- sample_meta$import_id

cat("[INFO] Rodando tximport...\n")
txi <- tximport(
  files,
  type = "salmon",
  tx2gene = tx2gene,
  countsFromAbundance = "no",
  ignoreTxVersion = TRUE,
  ignoreAfterBar = TRUE
)

counts_out <- file.path(out_dir, counts_name)
tpm_out <- file.path(out_dir, tpm_name)
sample_table_out <- file.path(out_dir, sample_table_name)

cat("[INFO] Salvando matrizes...\n")
write_tsv(as.data.frame(txi$counts) %>% rownames_to_column("gene_id"), counts_out)
write_tsv(as.data.frame(txi$abundance) %>% rownames_to_column("gene_id"), tpm_out)
write_tsv(sample_meta, sample_table_out)

cat("[OK] Counts: ", counts_out, "\n", sep = "")
cat("[OK] TPM: ", tpm_out, "\n", sep = "")
cat("[OK] Sample table: ", sample_table_out, "\n", sep = "")
