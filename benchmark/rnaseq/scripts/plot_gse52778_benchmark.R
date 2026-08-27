#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
arg <- function(flag) {
  index <- match(flag, args)
  if (is.na(index) || index == length(args)) stop("missing argument: ", flag)
  args[[index + 1]]
}
helix <- read.delim(arg("--helix-de"), check.names = FALSE)
reference <- read.delim(arg("--reference-de"), check.names = FALSE)
qc <- read.delim(arg("--qc"), check.names = FALSE)
biology <- read.delim(arg("--biology"), check.names = FALSE)
pca <- arg("--pca")
output <- arg("--output-dir")
if (dir.exists(output) || file.exists(output)) stop("output exists: ", output)
dir.create(output, recursive = TRUE)

de <- merge(
  helix[, c("gene_id", "log2FoldChange")],
  reference[, c("gene_id", "log2FoldChange")],
  by = "gene_id", suffixes = c("_helixforge", "_independent")
)
de <- de[is.finite(de$log2FoldChange_helixforge) & is.finite(de$log2FoldChange_independent), ]

draw_concordance <- function() {
  plot(de$log2FoldChange_independent, de$log2FoldChange_helixforge,
       pch = 16, cex = 0.25, col = rgb(0.10, 0.35, 0.70, 0.15),
       xlab = "Independent log2 fold change", ylab = "HelixForge log2 fold change",
       main = "GSE52778 effect concordance")
  abline(0, 1, col = "#B22222", lwd = 2)
  legend("topleft", legend = sprintf("Pearson = %.6f", cor(
    de$log2FoldChange_independent, de$log2FoldChange_helixforge
  )), bty = "n")
}
png(file.path(output, "figure_1_log2fc_concordance.png"), 1800, 1600, res = 180)
draw_concordance(); dev.off()
pdf(file.path(output, "figure_1_log2fc_concordance.pdf"), 7, 6)
draw_concordance(); dev.off()

draw_qc <- function() {
  values <- rbind(qc$retention_percent, qc$salmon_mapping_percent)
  colnames(values) <- qc$sample_id
  barplot(values, beside = TRUE, ylim = c(0, 105), las = 2,
          col = c("#4C78A8", "#F58518"), ylab = "Percent",
          main = "GSE52778 read retention and Salmon mapping", cex.names = 0.65)
  legend("bottomleft", legend = c("Post-trim retention", "Salmon mapping"),
         fill = c("#4C78A8", "#F58518"), bty = "n")
}
png(file.path(output, "figure_2_qc.png"), 2100, 1500, res = 180)
par(mar = c(11, 5, 4, 2)); draw_qc(); dev.off()
pdf(file.path(output, "figure_2_qc.pdf"), 9, 6)
par(mar = c(11, 5, 4, 2)); draw_qc(); dev.off()

draw_biology <- function() {
  colors <- ifelse(biology$expected_direction == "UP", "#54A24B", "#9D755D")
  barplot(biology$log2_fold_change, names.arg = biology$gene, las = 2,
          col = colors, ylab = "HelixForge log2 fold change",
          main = "Predeclared biological expectations")
  abline(h = 0, col = "grey40")
  legend("topleft", legend = c("Expected induced", "Reference control"),
         fill = c("#54A24B", "#9D755D"), bty = "n")
}
png(file.path(output, "figure_3_biological_expectations.png"), 1800, 1500, res = 180)
par(mar = c(8, 5, 4, 2)); draw_biology(); dev.off()
pdf(file.path(output, "figure_3_biological_expectations.pdf"), 8, 6)
par(mar = c(8, 5, 4, 2)); draw_biology(); dev.off()

if (!file.copy(pca, file.path(output, "figure_4_helixforge_pca.png"), overwrite = FALSE)) {
  stop("failed to copy HelixForge PCA")
}
capture.output(sessionInfo(), file = file.path(output, "render_sessionInfo.txt"))
