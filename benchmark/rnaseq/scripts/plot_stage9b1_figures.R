args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop("usage: plot_stage9b1_figures.R DATA_DIR OUTPUT_DIR")
if (Sys.getenv("SLURM_JOB_ID") == "") stop("figures must be rendered inside a Slurm job")
data_dir <- args[[1]]
output_dir <- args[[2]]
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

read_table <- function(name) {
  read.delim(file.path(data_dir, name), check.names = FALSE, stringsAsFactors = FALSE)
}

open_png <- function(path, width, height) {
  png(path, width = width * 180, height = height * 180, res = 180, bg = "white")
}

save_figure <- function(name, width, height, draw) {
  open_png(file.path(output_dir, paste0(name, ".png")), width, height)
  draw()
  dev.off()
  pdf(file.path(output_dir, paste0(name, ".pdf")), width = width, height = height, useDingbats = FALSE)
  draw()
  dev.off()
}

blue <- "#0072B2"
orange <- "#E69F00"
green <- "#009E73"
vermillion <- "#D55E00"
purple <- "#CC79A7"
sky <- "#56B4E9"
grey <- "#6B7280"
light_grey <- "#D1D5DB"

gene <- read_table("gene_abundance.tsv")
samples <- unique(gene$sample_id)
stratum_colors <- c(ZERO = light_grey, LOW = sky, MEDIUM = orange, HIGH = blue)
draw_gene <- function() {
  par(mfrow = c(2, 3), mar = c(3.2, 3.4, 2.3, 1), oma = c(2.4, 0.5, 4, 0.5), las = 1)
  for (i in seq_along(samples)) {
    current <- gene[gene$sample_id == samples[[i]], ]
    x <- log10(current$true_tpm + 0.1)
    y <- log10(current$estimated_tpm + 0.1)
    rho <- cor(current$true_tpm, current$estimated_tpm, method = "spearman")
    plot(x, y, pch = 16, cex = 0.43,
         col = adjustcolor(stratum_colors[current$abundance_stratum], alpha.f = 0.48),
         xlab = "", ylab = "", main = samples[[i]],
         xlim = range(c(x, y)), ylim = range(c(x, y)),
         panel.first = grid(col = "#ECEFF1", lty = 1))
    abline(0, 1, col = grey, lwd = 1.2)
    legend("topleft", legend = sprintf("Spearman = %.4f", rho), bty = "n", cex = 0.78)
    if (i == 1) legend("bottomright", legend = names(stratum_colors), col = stratum_colors,
                       pch = 16, bty = "n", cex = 0.68)
  }
  mtext("True gene TPM, log10(TPM + 0.1)", side = 1, outer = TRUE, line = 0.7)
  mtext("Gene abundance recovery across six synthetic samples", side = 3, outer = TRUE, line = 2.1, font = 2)
  mtext("Y axis: estimated gene TPM, log10(TPM + 0.1)", side = 3, outer = TRUE, line = 0.7, cex = 0.82)
}
save_figure("figure_1_gene_abundance", 10, 7.2, draw_gene)

transcript <- read_table("transcript_metrics.tsv")
draw_transcript <- function() {
  par(mfrow = c(1, 2), mar = c(7.2, 4.3, 3, 1), oma = c(0, 0, 2.2, 0), las = 1)
  x <- seq_len(nrow(transcript))
  correlation <- rbind(transcript$tpm_spearman, transcript$tpm_pearson_log2, transcript$fragment_spearman)
  matplot(x, t(correlation), type = "b", pch = c(16, 17, 15), lty = 1,
          col = c(blue, orange, green), ylim = c(0.975, 1), xaxt = "n",
          xlab = "", ylab = "Correlation", main = "Transcript-level agreement",
          panel.first = grid(col = "#ECEFF1"))
  axis(1, at = x, labels = transcript$sample_id, las = 2, cex.axis = 0.78)
  legend("bottomleft", legend = c("TPM Spearman", "log2 TPM Pearson", "Fragments Spearman"),
         col = c(blue, orange, green), pch = c(16, 17, 15), lty = 1, bty = "n", cex = 0.75)
  barplot(transcript$tpm_mae_log2, names.arg = transcript$sample_id, las = 2,
          col = sky, border = NA, ylab = "MAE of log2(TPM + 1)",
          main = "Transcript-level error", ylim = c(0, max(transcript$tpm_mae_log2) * 1.18))
  abline(h = pretty(c(0, transcript$tpm_mae_log2)), col = "#ECEFF1", lty = 1)
  mtext("Summary over 2,376 estimable transcripts per sample", side = 3, outer = TRUE, line = 0.6, font = 2)
}
save_figure("figure_2_transcript_quantification", 10, 5.8, draw_transcript)

de <- read_table("gene_de.tsv")
annotations <- read_table("annotations.tsv")
state_colors <- c(DOWN = blue, UNCHANGED = grey, UP = vermillion)
draw_de <- function() {
  par(mar = c(4.6, 5, 4, 1.5), las = 1)
  called <- de$called == "TRUE"
  plot(de$true_log2fc_jittered[!called], de$estimated_log2fc[!called],
       pch = 1, cex = 0.62, col = adjustcolor(state_colors[de$true_state[!called]], alpha.f = 0.5),
       xlab = "True log2 fold change (deterministic jitter)", ylab = "Estimated log2 fold change",
       main = "Differential-expression effect recovery",
       panel.first = grid(col = "#ECEFF1"), xlim = c(-2.25, 2.25))
  points(de$true_log2fc_jittered[called], de$estimated_log2fc[called], pch = 16, cex = 0.7,
         col = adjustcolor(state_colors[de$true_state[called]], alpha.f = 0.72))
  abline(0, 1, col = "#111827", lwd = 1.2)
  legend("topleft",
         legend = c("True down", "True unchanged", "True up", "padj >= 0.05", "padj < 0.05"),
         col = c(blue, grey, vermillion, "#111827", "#111827"),
         pch = c(16, 16, 16, 1, 16), bty = "n", cex = 0.82)
  legend("bottomright", inset = 0.04, bty = "n", cex = 0.82,
         legend = sprintf("Pearson = %.3f\nSpearman = %.3f\nDE direction = %.3f",
                          annotations$log2fc_pearson, annotations$log2fc_spearman,
                          annotations$direction_concordance))
}
save_figure("figure_3_log2fc_recovery", 7.4, 6.2, draw_de)

pr <- read_table("precision_recall.tsv")
draw_pr <- function() {
  par(mar = c(4.6, 5, 4, 1.5), las = 1)
  plot(pr$recall, pr$precision, type = "l", lwd = 2.2, col = blue,
       xlim = c(0, 1), ylim = c(0, 1), xlab = "Recall", ylab = "Precision",
       main = "Precision-recall curve for synthetic differential expression",
       panel.first = grid(col = "#ECEFF1"))
  abline(h = pr$prevalence[[1]], col = orange, lty = 2, lwd = 1.8)
  legend("topright", bty = "n", lwd = c(2.2, 1.8), lty = c(1, 2), col = c(blue, orange),
         legend = c(sprintf("HelixForge (AUPRC = %.3f)", annotations$auprc),
                    sprintf("Prevalence baseline = %.3f", annotations$prevalence)))
}
save_figure("figure_4_precision_recall", 7.4, 6.2, draw_pr)

repro <- read_table("reproducibility.tsv")
draw_repro <- function() {
  par(mar = c(5.2, 5.2, 4.2, 1.5), las = 1)
  values <- rbind(repro$deg_jaccard, repro$direction_concordance,
                  repro$pvalue_rank_spearman, repro$top100_overlap)
  matplot(seq_len(nrow(repro)), t(values), type = "b", lty = 1,
          pch = c(16, 17, 15, 18), col = c(blue, orange, green, purple),
          xaxt = "n", ylim = c(0.9997, 1.00003), xlab = "", ylab = "",
          main = "Scientific stability across repeat and independent arms",
          panel.first = grid(col = "#ECEFF1"))
  arm_labels <- c("Clean repeat", "Independent shared index", "Same index")
  axis(1, at = seq_len(nrow(repro)), labels = arm_labels, las = 1, cex.axis = 0.82)
  legend("bottomleft", legend = c("DEG Jaccard", "Direction", "P-value rank", "Top-100 overlap"),
         col = c(blue, orange, green, purple), pch = c(16, 17, 15, 18), lty = 1,
         bty = "n", cex = 0.78)
  mtext("Semantic agreement: strict numeric tolerance failed; endpoints remained stable",
        side = 3, line = 0.4, cex = 0.82)
}
save_figure("figure_5_reproducibility", 8.3, 6.2, draw_repro)

perf <- read_table("performance_process.tsv")
workflow <- read_table("performance_workflow.tsv")
case_labels <- c("synthetic-primary-run3" = "Primary", "synthetic-clean-repeat-v2" = "Clean repeat")
process_order <- unique(perf$process)
runtime_matrix <- sapply(names(case_labels), function(case) {
  current <- perf[perf$case == case, ]
  setNames(current$summed_realtime_seconds / 60, current$process)[process_order]
})
memory_matrix <- sapply(names(case_labels), function(case) {
  current <- perf[perf$case == case, ]
  setNames(current$peak_rss_mb, current$process)[process_order]
})
draw_performance <- function() {
  layout(matrix(c(1, 2, 3, 3), nrow = 2, byrow = TRUE), heights = c(1.25, 1))
  runtime_plot <- runtime_matrix[rev(process_order), , drop = FALSE]
  memory_plot <- memory_matrix[rev(process_order), , drop = FALSE]
  process_labels <- rev(process_order)
  process_labels[process_labels == "RNASEQ_QUANTIFICATION_PLAN"] <- "QUANT_PLAN"
  par(mar = c(4.2, 10, 3.2, 1), las = 1)
  barplot(t(runtime_plot), beside = TRUE, horiz = TRUE, names.arg = process_labels,
          col = c(blue, orange), border = NA, xlab = "Summed realtime (minutes)",
          main = "Top process families by task realtime")
  legend("bottomright", legend = unname(case_labels), fill = c(blue, orange), bty = "n", cex = 0.8)
  par(mar = c(4.2, 10, 3.2, 1), las = 1)
  barplot(t(memory_plot), beside = TRUE, horiz = TRUE, names.arg = process_labels,
          col = c(green, purple), border = NA, xlab = "Peak RSS (MB)",
          main = "Peak task memory by process family")
  legend("bottomright", legend = unname(case_labels), fill = c(green, purple), bty = "n", cex = 0.8)
  par(mar = c(4.8, 4.5, 3, 1), las = 1)
  workflow_matrix <- rbind(workflow$wall_seconds / 60, workflow$summed_scheduler_wait_seconds / 60)
  barplot(workflow_matrix, beside = TRUE, names.arg = case_labels[workflow$case],
          col = c(sky, grey), border = NA, ylab = "Minutes",
          main = "Workflow wall time and summed scheduler wait")
  legend("topright", legend = c("Workflow wall", "Summed scheduler wait"),
         fill = c(sky, grey), bty = "n", cex = 0.8)
}
save_figure("figure_6_performance", 11, 9.2, draw_performance)

cat(sprintf('{"status":"pass","figures":6,"slurm_job_id":"%s"}\n', Sys.getenv("SLURM_JOB_ID")))
