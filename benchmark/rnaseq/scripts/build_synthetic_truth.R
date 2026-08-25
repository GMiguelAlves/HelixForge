#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(jsonlite)
  library(polyester)
})

args <- commandArgs(trailingOnly = TRUE)
read_arg <- function(name) {
  index <- match(name, args)
  if (is.na(index) || index == length(args)) stop("missing argument: ", name)
  args[[index + 1]]
}

design_path <- normalizePath(read_arg("--design"), mustWork = TRUE)
reference_dir <- normalizePath(read_arg("--reference-dir"), mustWork = TRUE)
output_dir <- read_arg("--output-dir")
if (dir.exists(output_dir) || file.exists(output_dir)) stop("output already exists: ", output_dir)
dir.create(output_dir, recursive = TRUE)
truth_dir <- file.path(output_dir, "truth")
fasta_dir <- file.path(output_dir, "polyester_fasta")
dir.create(truth_dir)
dir.create(fasta_dir)

design <- fromJSON(design_path, simplifyVector = FALSE)
stopifnot(
  identical(as.character(packageVersion("polyester")), design$simulator$version),
  as.integer(design$selection$genes) == 1200L,
  as.integer(design$selection$expected_transcripts) == 2400L
)

mapping <- read.delim(file.path(reference_dir, "transcript_to_gene.tsv"), check.names = FALSE,
                      stringsAsFactors = FALSE)
selected <- read.delim(file.path(reference_dir, "selected_transcripts.tsv"), check.names = FALSE,
                       stringsAsFactors = FALSE)
genes <- read.delim(file.path(reference_dir, "selected_genes.tsv"), check.names = FALSE,
                    stringsAsFactors = FALSE)
stopifnot(
  identical(colnames(mapping), c("transcript_id", "gene_id")),
  nrow(mapping) == 2400L,
  length(unique(mapping$gene_id)) == 1200L,
  !anyDuplicated(mapping$transcript_id),
  !anyDuplicated(genes$gene_id)
)

samples <- do.call(rbind, lapply(design$experiment$samples, function(value) {
  data.frame(sample_id = value$sample_id, condition = value$condition,
             replicate = as.integer(value$replicate), stringsAsFactors = FALSE)
}))
stopifnot(nrow(samples) == 6L, table(samples$condition)[["control"]] == 3L,
          table(samples$condition)[["treatment"]] == 3L)

RNGkind("L'Ecuyer-CMRG")
set.seed(as.integer(design$expression$count_seed))
baseline <- 2 ^ rnorm(nrow(genes), mean = design$expression$baseline_log2_mean,
                      sd = design$expression$baseline_log2_sd)
baseline <- pmax(design$expression$baseline_min,
                 pmin(design$expression$baseline_max, baseline))
names(baseline) <- genes$gene_id

isoform_proportion <- numeric(nrow(mapping))
names(isoform_proportion) <- mapping$transcript_id
for (gene in genes$gene_id) {
  transcripts <- mapping$transcript_id[mapping$gene_id == gene]
  draws <- rgamma(length(transcripts), shape = 1, rate = 1)
  isoform_proportion[transcripts] <- draws / sum(draws)
}

true_lfc <- setNames(rep(0, nrow(genes)), genes$gene_id)
state <- setNames(rep("UNCHANGED", nrow(genes)), genes$gene_id)
cursor <- 1L
ordered_genes <- genes$gene_id[order(genes$de_assignment_rank)]
for (group in design$differential_expression$effect_groups) {
  for (direction in c("up", "down")) {
    number <- as.integer(group[[direction]])
    selected_genes <- ordered_genes[cursor:(cursor + number - 1L)]
    effect <- as.numeric(group$absolute_log2_fold_change) * ifelse(direction == "up", 1, -1)
    true_lfc[selected_genes] <- effect
    state[selected_genes] <- toupper(direction)
    cursor <- cursor + number
  }
}
stopifnot(sum(state == "UP") == 120L, sum(state == "DOWN") == 120L,
          sum(state == "UNCHANGED") == 960L)

dispersion <- as.numeric(design$expression$negative_binomial_dispersion)
target <- as.integer(design$library$fragments_per_sample)
count_matrix <- matrix(0L, nrow = nrow(mapping), ncol = nrow(samples),
                       dimnames = list(mapping$transcript_id, samples$sample_id))

largest_remainder <- function(values, total, ids) {
  if (sum(values) <= 0) stop("cannot scale an empty sample")
  raw <- values / sum(values) * total
  base <- floor(raw)
  remaining <- as.integer(total - sum(base))
  if (remaining > 0L) {
    order_index <- order(-(raw - base), ids)
    base[order_index[seq_len(remaining)]] <- base[order_index[seq_len(remaining)]] + 1L
  }
  as.integer(base)
}

for (sample_index in seq_len(nrow(samples))) {
  condition <- samples$condition[[sample_index]]
  gene_multiplier <- if (condition == "treatment") 2 ^ true_lfc else rep(1, length(true_lfc))
  names(gene_multiplier) <- names(true_lfc)
  means <- baseline[mapping$gene_id] * isoform_proportion[mapping$transcript_id] *
    gene_multiplier[mapping$gene_id]
  realized <- rnbinom(length(means), mu = means, size = 1 / dispersion)
  count_matrix[, sample_index] <- largest_remainder(realized, target, mapping$transcript_id)
}
stopifnot(all(colSums(count_matrix) == target))

lengths <- setNames(selected$length, selected$transcript_id)[mapping$transcript_id]
tpm_matrix <- apply(count_matrix, 2, function(values) {
  rate <- values / lengths
  if (sum(rate) == 0) rep(0, length(rate)) else 1e6 * rate / sum(rate)
})
rownames(tpm_matrix) <- mapping$transcript_id

transcript_truth <- do.call(rbind, lapply(seq_len(nrow(samples)), function(index) {
  data.frame(transcript_id = mapping$transcript_id, gene_id = mapping$gene_id,
             transcript_length = lengths, sample_id = samples$sample_id[[index]],
             condition = samples$condition[[index]],
             fragment_count = count_matrix[, index], tpm = tpm_matrix[, index],
             stringsAsFactors = FALSE)
}))

gene_truth <- do.call(rbind, lapply(seq_len(nrow(samples)), function(index) {
  counts <- rowsum(count_matrix[, index], mapping$gene_id, reorder = FALSE)
  tpm <- rowsum(tpm_matrix[, index], mapping$gene_id, reorder = FALSE)
  data.frame(gene_id = rownames(counts), sample_id = samples$sample_id[[index]],
             condition = samples$condition[[index]], fragment_count = as.numeric(counts[, 1]),
             tpm = as.numeric(tpm[, 1]), stringsAsFactors = FALSE)
}))

control_tpm <- aggregate(tpm ~ gene_id, gene_truth[gene_truth$condition == "control", ], mean)
abundance <- setNames(ifelse(control_tpm$tpm == 0, "ZERO",
                      ifelse(control_tpm$tpm < 1, "LOW",
                      ifelse(control_tpm$tpm < 10, "MEDIUM", "HIGH"))), control_tpm$gene_id)
gene_de_truth <- data.frame(
  gene_id = genes$gene_id,
  true_log2fc = true_lfc[genes$gene_id],
  true_state = state[genes$gene_id],
  is_de = state[genes$gene_id] != "UNCHANGED",
  effect_stratum = ifelse(state[genes$gene_id] == "UNCHANGED", "NONE",
                          ifelse(abs(true_lfc[genes$gene_id]) == 0.5, "SMALL",
                          ifelse(abs(true_lfc[genes$gene_id]) == 1, "MEDIUM", "LARGE"))),
  abundance_stratum = abundance[genes$gene_id],
  stringsAsFactors = FALSE
)

write.table(transcript_truth, file.path(truth_dir, "transcript_truth.tsv"), sep = "\t",
            row.names = FALSE, quote = FALSE)
write.table(gene_truth, file.path(truth_dir, "gene_truth.tsv"), sep = "\t",
            row.names = FALSE, quote = FALSE)
write.table(gene_de_truth, file.path(truth_dir, "gene_de_truth.tsv"), sep = "\t",
            row.names = FALSE, quote = FALSE)
write.table(samples, file.path(truth_dir, "sample_table.tsv"), sep = "\t",
            row.names = FALSE, quote = FALSE)
write.table(mapping, file.path(truth_dir, "transcript_to_gene.tsv"), sep = "\t",
            row.names = FALSE, quote = FALSE)
write.table(data.frame(transcript_id = rownames(count_matrix), count_matrix, check.names = FALSE),
            file.path(truth_dir, "polyester_read_matrix.tsv"), sep = "\t", row.names = FALSE, quote = FALSE)

writeLines(c(
  '"POLYESTER_SIMULATION":',
  paste0('    r: "', getRversion(), '"'),
  paste0('    bioconductor: "', design$simulator$bioconductor_version, '"'),
  paste0('    polyester: "', packageVersion("polyester"), '"'),
  paste0('    jsonlite: "', packageVersion("jsonlite"), '"')
), file.path(truth_dir, "versions.yml"))

simulation_manifest <- list(
  schema_version = "1.0",
  benchmark_id = "polyester-ground-truth-v1",
  design_md5 = unname(tools::md5sum(design_path)),
  reference_manifest = file.path(reference_dir, "reference_manifest.json"),
  seeds = list(selection = design$selection$seed, counts = design$expression$count_seed,
               effects = design$differential_expression$selection_seed,
               reads = design$read_generation_seed),
  samples = samples,
  genes = nrow(genes), transcripts = nrow(mapping), fragments_per_sample = target,
  differential_expression = list(up = sum(state == "UP"), down = sum(state == "DOWN"),
                                 unchanged = sum(state == "UNCHANGED"))
)
write_json(simulation_manifest, file.path(truth_dir, "simulation_manifest.pre_fastq.json"),
           pretty = TRUE, auto_unbox = TRUE)

set.seed(as.integer(design$read_generation_seed))
simulate_experiment_countmat(
  fasta = file.path(reference_dir, "transcriptome.fa"),
  readmat = count_matrix,
  outdir = fasta_dir,
  paired = TRUE,
  readlen = as.integer(design$library$read_length),
  distr = "normal",
  fraglen = as.numeric(design$library$fragment_length_mean),
  fragsd = as.numeric(design$library$fragment_length_sd),
  error_model = design$library$polyester_error_model,
  error_rate = as.numeric(design$library$polyester_error_rate),
  bias = "none",
  strand_specific = FALSE,
  seed = as.integer(design$read_generation_seed)
)

for (index in seq_len(nrow(samples))) {
  for (mate in 1:2) {
    source <- file.path(fasta_dir, sprintf("sample_%02d_%d.fasta", index, mate))
    target_name <- file.path(fasta_dir, paste0(samples$sample_id[[index]], "_R", mate, ".fasta"))
    if (!file.exists(source)) stop("expected Polyester output missing: ", source)
    if (!file.rename(source, target_name)) stop("failed to rename Polyester output: ", source)
  }
}
cat(toJSON(list(status = "complete", samples = nrow(samples), genes = nrow(genes),
                transcripts = nrow(mapping), fragments_per_sample = target), auto_unbox = TRUE), "\n")
