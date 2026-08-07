#!/usr/bin/env Rscript

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  out <- list()
  i <- 1
  while (i <= length(args)) {
    key <- sub("^--", "", args[[i]])
    value <- ""
    if (i + 1 <= length(args) && !grepl("^--", args[[i + 1]])) {
      value <- args[[i + 1]]
      i <- i + 1
    }
    out[[key]] <- value
    i <- i + 1
  }
  out
}

first_existing <- function(path) {
  candidates <- unique(c(path, paste0(path, ".gz"), sub("\\.gz$", "", path)))
  existing <- candidates[file.exists(candidates)]
  if (length(existing) == 0) return(NA_character_)
  existing[[1]]
}

open_table <- function(path, mode = "rt") {
  if (grepl("\\.gz$", path)) gzfile(path, mode) else file(path, mode)
}

read_tsv_safe <- function(path, header = TRUE) {
  existing <- first_existing(path)
  if (is.na(existing) || file.info(existing)$size == 0) return(data.frame())
  con <- open_table(existing, "rt")
  on.exit(close(con), add = TRUE)
  read.table(con, sep = "\t", header = header, quote = "", comment.char = "", stringsAsFactors = FALSE, check.names = FALSE)
}

write_tsv_safe <- function(x, path) {
  con <- open_table(path, "wt")
  on.exit(close(con), add = TRUE)
  write.table(x, con, sep = "\t", quote = FALSE, row.names = FALSE)
}

read_lines_safe <- function(path) {
  existing <- first_existing(path)
  if (is.na(existing) || file.info(existing)$size == 0) return(character())
  con <- if (grepl("\\.gz$", existing)) gzfile(existing, "rt") else file(existing, "rt")
  on.exit(close(con), add = TRUE)
  readLines(con, warn = FALSE)
}

count_lines_safe <- function(path) {
  existing <- first_existing(path)
  if (is.na(existing) || file.info(existing)$size == 0) return(NA_integer_)
  con <- if (grepl("\\.gz$", existing)) gzfile(existing, "rt") else file(existing, "rt")
  on.exit(close(con), add = TRUE)
  length(readLines(con, warn = FALSE))
}

num_or_na <- function(x) {
  x <- suppressWarnings(as.numeric(x))
  ifelse(length(x) == 0, NA_real_, x)
}

percent <- function(x, digits = 2) {
  ifelse(is.na(x), "NA", paste0(format(round(x, digits), nsmall = digits, trim = TRUE), "%"))
}

fmt_num <- function(x) {
  ifelse(is.na(x), "NA", format(x, big.mark = ",", scientific = FALSE, trim = TRUE))
}

extract_flagstat <- function(path) {
  lines <- read_lines_safe(path)
  if (length(lines) == 0) {
    return(c(total = NA, mapped = NA, mapped_pct = NA, duplicates = NA, duplicate_pct = NA))
  }
  total <- suppressWarnings(as.numeric(sub(" .*", "", lines[1])))
  mapped_line <- grep(" mapped \\(", lines, value = TRUE)
  mapped <- if (length(mapped_line)) suppressWarnings(as.numeric(sub(" .*", "", mapped_line[1]))) else NA_real_
  mapped_pct <- if (length(mapped_line)) suppressWarnings(as.numeric(sub(".*\\(([^%]+)%.*", "\\1", mapped_line[1]))) else NA_real_
  dup_line <- grep(" duplicates$", lines, value = TRUE)
  duplicates <- if (length(dup_line)) suppressWarnings(as.numeric(sub(" .*", "", dup_line[1]))) else NA_real_
  duplicate_pct <- if (!is.na(duplicates) && !is.na(total) && total > 0) duplicates / total * 100 else NA_real_
  c(total = total, mapped = mapped, mapped_pct = mapped_pct, duplicates = duplicates, duplicate_pct = duplicate_pct)
}

extract_samtools_stats <- function(path) {
  lines <- read_lines_safe(path)
  keys <- c(
    total_sequences = "raw total sequences",
    filtered_sequences = "filtered sequences",
    reads_mapped = "reads mapped",
    reads_duplicated = "reads duplicated",
    reads_mq0 = "reads MQ0",
    average_length = "average length",
    insert_size_average = "insert size average"
  )
  out <- setNames(rep(NA_real_, length(keys)), names(keys))
  sn <- lines[grepl("^SN\t", lines)]
  for (nm in names(keys)) {
    hit <- grep(paste0("^SN\t", keys[[nm]], ":\t"), sn, value = TRUE)
    if (length(hit)) out[[nm]] <- suppressWarnings(as.numeric(strsplit(hit[[1]], "\t", fixed = TRUE)[[1]][[3]]))
  }
  out
}

extract_bowtie2_log <- function(path) {
  lines <- read_lines_safe(path)
  if (length(lines) == 0) {
    return(c(aligner_input_reads = NA, unaligned_reads = NA, unique_aligned_reads = NA,
             multi_aligned_reads = NA, overall_alignment_pct = NA))
  }
  total_line <- grep(" reads; of these:$", lines, value = TRUE)
  total <- if (length(total_line)) suppressWarnings(as.numeric(sub("^\\s*([0-9,]+).*", "\\1", gsub(",", "", total_line[[1]])))) else NA_real_
  unaligned_line <- grep("aligned 0 times", lines, value = TRUE)
  unique_line <- grep("aligned exactly 1 time", lines, value = TRUE)
  multi_line <- grep("aligned >1 times", lines, value = TRUE)
  rate_line <- grep("overall alignment rate", lines, value = TRUE)
  parse_first_int <- function(x) if (length(x)) suppressWarnings(as.numeric(sub("^\\s*([0-9,]+).*", "\\1", gsub(",", "", x[[1]])))) else NA_real_
  rate <- if (length(rate_line)) suppressWarnings(as.numeric(sub("^\\s*([^%]+)%.*", "\\1", rate_line[[1]]))) else NA_real_
  c(
    aligner_input_reads = total,
    unaligned_reads = parse_first_int(unaligned_line),
    unique_aligned_reads = parse_first_int(unique_line),
    multi_aligned_reads = parse_first_int(multi_line),
    overall_alignment_pct = rate
  )
}

json_number <- function(text, path) {
  pattern <- paste0('"', paste(path, collapse = '"[[:space:]]*:[[:space:]]*\\{[^}]*"'), '"[[:space:]]*:[[:space:]]*([0-9.]+)')
  hit <- regexpr(pattern, text, perl = TRUE)
  if (hit[[1]] < 0) return(NA_real_)
  value <- regmatches(text, hit)
  suppressWarnings(as.numeric(sub(".*:[[:space:]]*([0-9.]+)$", "\\1", value)))
}

extract_fastp_json <- function(path) {
  existing <- first_existing(path)
  keys <- c(raw_reads = NA_real_, raw_bases = NA_real_, trimmed_reads = NA_real_, trimmed_bases = NA_real_, q30_rate_after = NA_real_)
  if (is.na(existing) || file.info(existing)$size == 0) return(keys)
  text <- paste(read_lines_safe(existing), collapse = "")
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    x <- tryCatch(jsonlite::fromJSON(existing), error = function(e) NULL)
    if (!is.null(x)) {
      keys[["raw_reads"]] <- num_or_na(x$summary$before_filtering$total_reads)
      keys[["raw_bases"]] <- num_or_na(x$summary$before_filtering$total_bases)
      keys[["trimmed_reads"]] <- num_or_na(x$summary$after_filtering$total_reads)
      keys[["trimmed_bases"]] <- num_or_na(x$summary$after_filtering$total_bases)
      keys[["q30_rate_after"]] <- num_or_na(x$summary$after_filtering$q30_rate) * 100
      return(keys)
    }
  }
  keys[["raw_reads"]] <- json_number(text, c("before_filtering", "total_reads"))
  keys[["raw_bases"]] <- json_number(text, c("before_filtering", "total_bases"))
  keys[["trimmed_reads"]] <- json_number(text, c("after_filtering", "total_reads"))
  keys[["trimmed_bases"]] <- json_number(text, c("after_filtering", "total_bases"))
  q30 <- json_number(text, c("after_filtering", "q30_rate"))
  keys[["q30_rate_after"]] <- ifelse(is.na(q30), NA_real_, q30 * 100)
  keys
}

find_peak_file <- function(peaks_dir, sample_id) {
  files <- list.files(file.path(peaks_dir, sample_id), pattern = "_peaks\\.(narrowPeak|broadPeak)$", full.names = TRUE)
  if (length(files) == 0) return(NA_character_)
  files[[1]]
}

peak_type_from_file <- function(path) {
  if (is.na(path)) return(NA_character_)
  if (grepl("\\.broadPeak$", path)) "broad" else "narrow"
}

markdown_table <- function(x, con, max_rows = Inf) {
  if (nrow(x) == 0) {
    writeLines("No rows available.", con)
    return(invisible(NULL))
  }
  y <- x
  if (is.finite(max_rows) && nrow(y) > max_rows) y <- head(y, max_rows)
  y[] <- lapply(y, function(col) {
    col <- as.character(col)
    col[is.na(col)] <- "NA"
    gsub("\\|", "/", col)
  })
  writeLines(paste0("| ", paste(names(y), collapse = " | "), " |"), con)
  writeLines(paste0("| ", paste(rep("---", ncol(y)), collapse = " | "), " |"), con)
  apply(y, 1, function(row) writeLines(paste0("| ", paste(row, collapse = " | "), " |"), con))
  if (is.finite(max_rows) && nrow(x) > max_rows) {
    writeLines(paste0("\nShowing first ", max_rows, " of ", nrow(x), " rows."), con)
  }
}

html_escape <- function(x) {
  x <- as.character(x)
  x[is.na(x)] <- "NA"
  x <- gsub("&", "&amp;", x, fixed = TRUE)
  x <- gsub("<", "&lt;", x, fixed = TRUE)
  x <- gsub(">", "&gt;", x, fixed = TRUE)
  x <- gsub('"', "&quot;", x, fixed = TRUE)
  x
}

html_table <- function(x, max_rows = Inf) {
  if (nrow(x) == 0) return("<p>No rows available.</p>")
  y <- x
  suffix <- ""
  if (is.finite(max_rows) && nrow(y) > max_rows) {
    y <- head(y, max_rows)
    suffix <- paste0("<p class=\"muted\">Showing first ", max_rows, " of ", nrow(x), " rows.</p>")
  }
  y[] <- lapply(y, html_escape)
  header <- paste0("<tr>", paste0("<th>", html_escape(names(y)), "</th>", collapse = ""), "</tr>")
  rows <- apply(y, 1, function(row) paste0("<tr>", paste0("<td>", row, "</td>", collapse = ""), "</tr>"))
  paste0("<table>", header, paste(rows, collapse = "\n"), "</table>", suffix)
}

write_plot <- function(path, width = 1200, height = 800, plot_fun) {
  ok <- FALSE
  tryCatch({
    png(path, width = width, height = height, res = 120)
    plot_fun()
    ok <<- TRUE
  }, error = function(e) {
    writeLines(paste("Plot skipped:", conditionMessage(e)), paste0(path, ".txt"))
  }, finally = {
    if (names(dev.cur()) != "null device") dev.off()
  })
  if (ok && file.exists(path)) basename(path) else NA_character_
}

plot_report_figures <- function(report_dir, sample_summary, annotation_totals, consensus_summary, diff_summary) {
  figures_dir <- file.path(report_dir, "figures")
  dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)
  figures <- list()

  if (any(!is.na(sample_summary$aligner_overall_alignment_pct))) {
    x <- sample_summary[!is.na(sample_summary$aligner_overall_alignment_pct), , drop = FALSE]
    x <- x[order(x$aligner_overall_alignment_pct), , drop = FALSE]
    figures$alignment <- write_plot(file.path(figures_dir, "alignment_rate_by_sample.png"), 1200, 1100, function() {
      op <- par(mar = c(5, 12, 4, 2))
      on.exit(par(op), add = TRUE)
      cols <- ifelse(x$aligner_overall_alignment_pct < 70, "#b23a48", "#256d85")
      barplot(x$aligner_overall_alignment_pct, horiz = TRUE, las = 1, names.arg = x$sample_id,
              xlim = c(0, 100), col = cols, border = NA, cex.names = 0.65,
              xlab = "Overall alignment rate (%)", main = "Alignment rate by sample")
      abline(v = 70, lty = 2, col = "#b23a48")
      legend("bottomright", legend = c(">=70%", "<70%"), fill = c("#256d85", "#b23a48"), bty = "n")
    })
  }

  if (any(!is.na(sample_summary$peak_count))) {
    x <- sample_summary[!is.na(sample_summary$peak_count) & !sample_summary$is_control, , drop = FALSE]
    x <- x[order(x$peak_count), , drop = FALSE]
    marks <- sort(unique(x$mark_or_factor))
    base_cols <- c("#256d85", "#7b8f3a", "#b55d3a", "#6d5a8d", "#4f6f52", "#9a6b2f")
    palette <- setNames(rep(base_cols, length.out = length(marks)), marks)
    figures$peaks <- write_plot(file.path(figures_dir, "peak_counts_by_sample.png"), 1200, 1100, function() {
      op <- par(mar = c(5, 12, 4, 2))
      on.exit(par(op), add = TRUE)
      barplot(log10(x$peak_count + 1), horiz = TRUE, las = 1, names.arg = x$sample_id,
              col = palette[x$mark_or_factor], border = NA, cex.names = 0.65,
              xlab = "log10(peak count + 1)", main = "Peak counts by sample")
      legend("bottomright", legend = names(palette), fill = palette, bty = "n", cex = 0.8)
    })
  }

  if (nrow(annotation_totals) > 0) {
    a <- annotation_totals[order(annotation_totals$n, decreasing = TRUE), , drop = FALSE]
    figures$annotation <- write_plot(file.path(figures_dir, "peak_annotation_classes.png"), 1000, 700, function() {
      op <- par(mar = c(8, 5, 4, 2))
      on.exit(par(op), add = TRUE)
      barplot(a$n, names.arg = a$class, las = 2, col = "#6d5a8d", border = NA,
              ylab = "Annotated peaks", main = "Peak annotation classes")
    })
  }

  if (nrow(consensus_summary) > 0) {
    c <- consensus_summary[order(consensus_summary$consensus_peak_count, decreasing = TRUE), , drop = FALSE]
    c <- head(c, 20)
    figures$consensus <- write_plot(file.path(figures_dir, "consensus_peak_sets.png"), 1200, 900, function() {
      op <- par(mar = c(5, 14, 4, 2))
      on.exit(par(op), add = TRUE)
      barplot(c$consensus_peak_count, horiz = TRUE, las = 1, names.arg = c$peak_set,
              col = "#7b8f3a", border = NA, cex.names = 0.7,
              xlab = "Consensus peaks", main = "Consensus peak sets")
    })
  }

  if (nrow(diff_summary$by_mark) > 0) {
    d <- diff_summary$by_mark[order(diff_summary$by_mark$significant_padj_0_05, decreasing = TRUE), , drop = FALSE]
    figures$differential <- write_plot(file.path(figures_dir, "differential_significant_by_mark.png"), 1000, 700, function() {
      op <- par(mar = c(8, 5, 4, 2))
      on.exit(par(op), add = TRUE)
      vals <- rbind(padj_0_05 = d$significant_padj_0_05, padj_0_10 = d$significant_padj_0_10)
      barplot(vals, beside = TRUE, names.arg = d$mark_or_factor, las = 2,
              col = c("#256d85", "#b55d3a"), border = NA,
              ylab = "Significant regions", main = "Differential regions by mark")
      legend("topright", legend = c("padj < 0.05", "padj < 0.10"), fill = c("#256d85", "#b55d3a"), bty = "n")
    })
  }

  Filter(function(x) !is.na(x), figures)
}

write_html_report <- function(path, report_dir, outdir, metadata, sample_display, group_summary,
                              annotation_totals, annotation_summary, consensus_summary,
                              count_summary, diff_summary, recommendations, figures,
                              sample_summary_file, diff_summary_file, diff_peak_set_file) {
  fig_path <- function(name) paste0("figures/", figures[[name]])
  fig_block <- function(name, title) {
    if (is.null(figures[[name]]) || is.na(figures[[name]])) return("")
    paste0("<figure><img src=\"", fig_path(name), "\" alt=\"", html_escape(title),
           "\"><figcaption>", html_escape(title), "</figcaption></figure>")
  }
  consensus_display <- if (nrow(consensus_summary) > 0) {
    consensus_summary[order(consensus_summary$consensus_peak_count, decreasing = TRUE), , drop = FALSE]
  } else {
    consensus_summary
  }
  css <- paste(
    "body{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f7f8f6;color:#202124}",
    "header{background:#263238;color:white;padding:28px 36px}",
    "main{padding:24px 36px;max-width:1320px;margin:auto}",
    "section{background:white;border:1px solid #ddd;margin:18px 0;padding:20px;border-radius:6px}",
    "h1,h2,h3{margin-top:0}",
    ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}",
    ".metric{background:#eef3f3;border-left:5px solid #256d85;padding:12px;border-radius:4px}",
    ".warn{background:#fff4e8;border-left:5px solid #b55d3a;padding:12px;border-radius:4px}",
    "table{border-collapse:collapse;width:100%;font-size:13px;margin-top:10px}",
    "th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}",
    "th{background:#edf0f2}",
    "img{max-width:100%;height:auto;border:1px solid #ddd;background:white}",
    "figure{margin:12px 0}figcaption{font-size:13px;color:#555;margin-top:6px}",
    ".muted{color:#666;font-size:13px}",
    "a{color:#256d85}",
    sep = "\n"
  )
  html <- c(
    "<!doctype html>",
    "<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
    "<title>ChIP-seq final report</title>",
    paste0("<style>", css, "</style></head><body>"),
    "<header><h1>ChIP-seq final report</h1>",
    paste0("<p>Generated: ", html_escape(format(Sys.time(), "%Y-%m-%d %H:%M:%S")), "</p>"),
    paste0("<p>Work directory: ", html_escape(outdir), "</p></header><main>"),
    "<section><h2>Run overview</h2><div class=\"grid\">",
    paste0("<div class=\"metric\"><b>Total samples</b><br>", nrow(metadata), "</div>"),
    paste0("<div class=\"metric\"><b>IP samples</b><br>", sum(!tolower(as.character(metadata$is_control)) %in% c("true", "1", "yes", "y")), "</div>"),
    paste0("<div class=\"metric\"><b>Control/input samples</b><br>", sum(tolower(as.character(metadata$is_control)) %in% c("true", "1", "yes", "y")), "</div>"),
    paste0("<div class=\"metric\"><b>Marks/factors</b><br>", length(unique(metadata$mark_or_factor)), "</div>"),
    "</div></section>",
    "<section><h2>Automatic recommendations</h2>",
    paste0("<div class=\"warn\">", paste(paste0("<p>", html_escape(recommendations), "</p>"), collapse = "\n"), "</div></section>"),
    "<section><h2>Figures</h2>",
    fig_block("alignment", "Alignment rate by sample"),
    fig_block("peaks", "Peak counts by sample"),
    fig_block("differential", "Differential regions by mark"),
    fig_block("annotation", "Peak annotation classes"),
    fig_block("consensus", "Consensus peak sets"),
    "</section>",
    "<section><h2>Group summary</h2>", html_table(group_summary, 100), "</section>",
    "<section><h2>Sample QC summary</h2>",
    paste0("<p class=\"muted\">Full table: <a href=\"", basename(sample_summary_file), "\">", basename(sample_summary_file), "</a></p>"),
    html_table(sample_display, 200), "</section>",
    "<section><h2>Peak annotation</h2>",
    if (nrow(annotation_totals) > 0) html_table(annotation_totals[order(annotation_totals$n, decreasing = TRUE), , drop = FALSE], 50) else "<p>No annotation totals available.</p>",
    "<h3>Annotation by peak set</h3>", html_table(annotation_summary, 80), "</section>",
    "<section><h2>Consensus peaks</h2>",
    html_table(consensus_display, 50),
    "<h3>Count matrices</h3>", html_table(count_summary, 50), "</section>",
    "<section><h2>Differential binding</h2>",
    if (nrow(diff_summary$overall) > 0) html_table(diff_summary$overall, 10) else "<p>No differential results available.</p>",
    "<h3>By mark/factor</h3>", html_table(diff_summary$by_mark, 50),
    "<h3>By peak set</h3>", html_table(diff_summary$by_peak_set, 50),
    "<h3>By contrast</h3>", html_table(diff_summary$by_contrast, 50),
    paste0("<p class=\"muted\">Full contrast summary: <a href=\"", basename(diff_summary_file), "\">", basename(diff_summary_file), "</a></p>"),
    paste0("<p class=\"muted\">Full peak-set summary: <a href=\"", basename(diff_peak_set_file), "\">", basename(diff_peak_set_file), "</a></p>"),
    "</section>",
    "</main></body></html>"
  )
  writeLines(html, path, useBytes = TRUE)
}

summarise_diff <- function(diff_results) {
  if (nrow(diff_results) == 0) {
    return(list(overall = data.frame(), by_contrast = data.frame(), by_method = data.frame(),
                by_mark = data.frame(), by_peak_set = data.frame(), by_peak_set_contrast = data.frame()))
  }
  padj <- if ("padj" %in% names(diff_results)) suppressWarnings(as.numeric(diff_results$padj)) else rep(NA_real_, nrow(diff_results))
  pvalue <- if ("pvalue" %in% names(diff_results)) suppressWarnings(as.numeric(diff_results$pvalue)) else rep(NA_real_, nrow(diff_results))
  overall <- data.frame(
    tested_rows = nrow(diff_results),
    rows_with_pvalue = sum(!is.na(pvalue)),
    rows_with_padj = sum(!is.na(padj)),
    significant_padj_0_05 = sum(padj < 0.05, na.rm = TRUE),
    significant_padj_0_10 = sum(padj < 0.10, na.rm = TRUE),
    stringsAsFactors = FALSE
  )
  if ("contrast" %in% names(diff_results)) {
    by_contrast <- do.call(rbind, lapply(split(seq_len(nrow(diff_results)), diff_results$contrast), function(idx) {
      p <- padj[idx]
      data.frame(
        contrast = as.character(diff_results$contrast[idx[[1]]]),
        tested_rows = length(idx),
        rows_with_padj = sum(!is.na(p)),
        significant_padj_0_05 = sum(p < 0.05, na.rm = TRUE),
        significant_padj_0_10 = sum(p < 0.10, na.rm = TRUE),
        stringsAsFactors = FALSE
      )
    }))
    by_contrast <- by_contrast[order(by_contrast$significant_padj_0_05, decreasing = TRUE), , drop = FALSE]
  } else {
    by_contrast <- data.frame()
  }
  summarise_by <- function(cols) {
    if (!all(cols %in% names(diff_results))) return(data.frame())
    key <- interaction(diff_results[, cols, drop = FALSE], drop = TRUE, sep = "\r")
    out <- do.call(rbind, lapply(split(seq_len(nrow(diff_results)), key), function(idx) {
      p <- padj[idx]
      row <- as.data.frame(as.list(diff_results[idx[[1]], cols, drop = FALSE]), stringsAsFactors = FALSE)
      row$tested_rows <- length(idx)
      row$rows_with_padj <- sum(!is.na(p))
      row$significant_padj_0_05 <- sum(p < 0.05, na.rm = TRUE)
      row$significant_padj_0_10 <- sum(p < 0.10, na.rm = TRUE)
      row
    }))
    out[order(out$significant_padj_0_05, decreasing = TRUE), , drop = FALSE]
  }
  by_mark <- summarise_by(c("mark_or_factor"))
  by_peak_set <- summarise_by(c("peak_set", "mark_or_factor"))
  by_peak_set_contrast <- summarise_by(c("peak_set", "mark_or_factor", "contrast"))
  if ("method" %in% names(diff_results)) {
    by_method <- as.data.frame(table(diff_results$method), stringsAsFactors = FALSE)
    names(by_method) <- c("method", "rows")
  } else {
    by_method <- data.frame()
  }
  list(overall = overall, by_contrast = by_contrast, by_method = by_method,
       by_mark = by_mark, by_peak_set = by_peak_set, by_peak_set_contrast = by_peak_set_contrast)
}

args <- parse_args()
metadata <- read_tsv_safe(args[["metadata"]])
outdir <- args[["output-dir"]]
report <- args[["report"]]
report_dir <- dirname(report)
dir.create(report_dir, recursive = TRUE, showWarnings = FALSE)
table_suffix <- Sys.getenv("PIPELINE_TABLE_SUFFIX", unset = "")

required_cols <- c("sample_id", "condition", "mark_or_factor", "is_control")
missing_cols <- setdiff(required_cols, names(metadata))
if (length(missing_cols) > 0) {
  stop("Metadata is missing required columns for report: ", paste(missing_cols, collapse = ", "))
}

is_control <- tolower(as.character(metadata$is_control)) %in% c("true", "1", "yes", "y")
sample_ids <- metadata$sample_id

fastp_metrics <- t(vapply(sample_ids, function(sid) {
  extract_fastp_json(file.path(outdir, "040-trimming", sid, paste0(sid, ".fastp.json")))
}, numeric(5)))

aligner_metrics <- t(vapply(sample_ids, function(sid) {
  logs <- list.files(file.path(outdir, "050-alignment", sid), pattern = "\\.(bowtie2|bwa)\\.log$", full.names = TRUE)
  if (length(logs) == 0) {
    return(c(aligner_input_reads = NA, unaligned_reads = NA, unique_aligned_reads = NA,
             multi_aligned_reads = NA, overall_alignment_pct = NA))
  }
  if (grepl("\\.bowtie2\\.log$", logs[[1]])) extract_bowtie2_log(logs[[1]]) else c(
    aligner_input_reads = NA, unaligned_reads = NA, unique_aligned_reads = NA,
    multi_aligned_reads = NA, overall_alignment_pct = NA
  )
}, numeric(5)))

final_flagstat <- t(vapply(sample_ids, function(sid) {
  extract_flagstat(file.path(outdir, "060-filtering", sid, paste0(sid, ".flagstat.txt")))
}, numeric(5)))

aligned_flagstat <- t(vapply(sample_ids, function(sid) {
  extract_flagstat(file.path(outdir, "050-alignment", sid, paste0(sid, ".aligned.flagstat.txt")))
}, numeric(5)))

final_stats <- t(vapply(sample_ids, function(sid) {
  extract_samtools_stats(file.path(outdir, "060-filtering", sid, paste0(sid, ".stats.txt")))
}, numeric(7)))

peak_files <- vapply(sample_ids, function(sid) find_peak_file(file.path(outdir, "080-peak-calling"), sid), character(1))
peak_counts <- vapply(peak_files, count_lines_safe, integer(1))
peak_types <- vapply(peak_files, peak_type_from_file, character(1))

sample_summary <- data.frame(
  sample_id = sample_ids,
  condition = metadata$condition,
  mark_or_factor = metadata$mark_or_factor,
  replicate = if ("replicate" %in% names(metadata)) metadata$replicate else NA,
  is_control = is_control,
  control_id = if ("control_id" %in% names(metadata)) metadata$control_id else NA,
  raw_reads_fastp = fastp_metrics[, "raw_reads"],
  trimmed_reads_fastp = fastp_metrics[, "trimmed_reads"],
  trim_retained_pct = ifelse(!is.na(fastp_metrics[, "raw_reads"]) & fastp_metrics[, "raw_reads"] > 0,
                             fastp_metrics[, "trimmed_reads"] / fastp_metrics[, "raw_reads"] * 100, NA_real_),
  q30_after_trim_pct = fastp_metrics[, "q30_rate_after"],
  aligner_input_reads = aligner_metrics[, "aligner_input_reads"],
  aligner_overall_alignment_pct = aligner_metrics[, "overall_alignment_pct"],
  aligned_bam_reads = aligned_flagstat[, "total"],
  aligned_bam_mapped_pct = aligned_flagstat[, "mapped_pct"],
  aligned_bam_duplicate_pct = aligned_flagstat[, "duplicate_pct"],
  final_filtered_reads = final_flagstat[, "total"],
  final_mapped_pct = final_flagstat[, "mapped_pct"],
  final_duplicate_pct = final_flagstat[, "duplicate_pct"],
  final_average_read_length = final_stats[, "average_length"],
  final_insert_size_average = final_stats[, "insert_size_average"],
  peak_type = peak_types,
  peak_count = peak_counts,
  peak_file = peak_files,
  filtered_bam = file.exists(file.path(outdir, "060-filtering", sample_ids, paste0(sample_ids, ".filtered.bam"))),
  stringsAsFactors = FALSE
)

annotation_summary <- read_tsv_safe(file.path(outdir, "090-peak-annotation", "annotation_summary.tsv"))
diff_results <- read_tsv_safe(file.path(outdir, "120-differential-binding", "differential_binding_results.tsv"))
diff_summary <- summarise_diff(diff_results)

consensus_files <- list.files(file.path(outdir, "110-consensus-peaks", "groups"), pattern = "\\.consensus\\.bed$", full.names = TRUE)
consensus_summary <- if (length(consensus_files) > 0) {
  data.frame(
    peak_set = sub("\\.consensus\\.bed$", "", basename(consensus_files)),
    consensus_peak_count = vapply(consensus_files, count_lines_safe, integer(1)),
    stringsAsFactors = FALSE
  )
} else {
  data.frame()
}

count_files <- list.files(file.path(outdir, "110-consensus-peaks", "counts"), pattern = "\\.counts\\.tsv(\\.gz)?$", full.names = TRUE)
count_summary <- if (length(count_files) > 0) {
  data.frame(
    count_matrix = basename(count_files),
    rows = vapply(count_files, count_lines_safe, integer(1)),
    stringsAsFactors = FALSE
  )
} else {
  data.frame()
}

annotation_totals <- if (nrow(annotation_summary) > 0 && all(c("class", "n") %in% names(annotation_summary))) {
  aggregate(n ~ class, annotation_summary, sum)
} else {
  data.frame()
}

group_summary <- aggregate(
  sample_id ~ condition + mark_or_factor,
  sample_summary[!sample_summary$is_control, , drop = FALSE],
  length
)
names(group_summary)[names(group_summary) == "sample_id"] <- "ip_replicates"
group_peaks <- aggregate(
  peak_count ~ condition + mark_or_factor,
  sample_summary[!sample_summary$is_control, , drop = FALSE],
  function(x) paste(c("min" = min(x, na.rm = TRUE), "median" = median(x, na.rm = TRUE), "max" = max(x, na.rm = TRUE)), collapse = " / ")
)
names(group_peaks)[names(group_peaks) == "peak_count"] <- "peak_count_min_median_max"
group_summary <- merge(group_summary, group_peaks, by = c("condition", "mark_or_factor"), all.x = TRUE)

recommendations <- character()
if (sum(sample_summary$is_control) == 0) {
  recommendations <- c(recommendations, "No input/control samples were provided. MACS peak calls should be interpreted as no-control calls with higher background risk.")
}
missing_control <- sample_summary$sample_id[!sample_summary$is_control & (is.na(sample_summary$control_id) | sample_summary$control_id == "")]
if (length(missing_control) > 0 && sum(sample_summary$is_control) > 0) {
  recommendations <- c(recommendations, paste("Some IP samples have no matched control_id:", paste(missing_control, collapse = ", ")))
}
low_mapping <- sample_summary$sample_id[!is.na(sample_summary$aligner_overall_alignment_pct) & sample_summary$aligner_overall_alignment_pct < 70]
if (length(low_mapping) > 0) {
  recommendations <- c(recommendations, paste("Inspect low aligner mapping rate samples:", paste(low_mapping, collapse = ", ")))
}
low_trim <- sample_summary$sample_id[!is.na(sample_summary$trim_retained_pct) & sample_summary$trim_retained_pct < 70]
if (length(low_trim) > 0) {
  recommendations <- c(recommendations, paste("Inspect samples with low read retention after trimming:", paste(low_trim, collapse = ", ")))
}
if (all(is.na(sample_summary$raw_reads_fastp)) && any(!is.na(sample_summary$aligner_input_reads))) {
  recommendations <- c(recommendations, "fastp JSON reports were not found. This is expected for Trimmomatic or other non-fastp trimming; use aligner_input_reads as the available read-input proxy.")
}
zero_peaks <- sample_summary$sample_id[!is.na(sample_summary$peak_count) & sample_summary$peak_count == 0 & !sample_summary$is_control]
if (length(zero_peaks) > 0) {
  recommendations <- c(recommendations, paste("No peaks detected for:", paste(zero_peaks, collapse = ", ")))
}
low_peaks <- sample_summary$sample_id[!is.na(sample_summary$peak_count) & sample_summary$peak_count > 0 & sample_summary$peak_count < 100 & !sample_summary$is_control]
if (length(low_peaks) > 0) {
  recommendations <- c(recommendations, paste("Very low peak counts (<100) detected:", paste(low_peaks, collapse = ", ")))
}
if (nrow(group_summary) > 0 && any(group_summary$ip_replicates < 2)) {
  low_rep <- paste(group_summary$condition[group_summary$ip_replicates < 2], group_summary$mark_or_factor[group_summary$ip_replicates < 2], sep = "/")
  recommendations <- c(recommendations, paste("Differential binding is underpowered for groups with <2 IP replicates:", paste(low_rep, collapse = ", ")))
}
if (nrow(diff_summary$overall) > 0 && diff_summary$overall$rows_with_padj[[1]] == 0) {
  recommendations <- c(recommendations, "Differential tables do not contain adjusted p-values. Check whether DESeq2 was available or whether fallback mode was used.")
}
if (nrow(diff_results) > 0 && !all(c("peak_set", "mark_or_factor") %in% names(diff_results))) {
  recommendations <- c(recommendations, "Differential results do not contain peak_set/mark_or_factor columns. Regenerate the differential step with the updated pipeline.")
}
if (length(recommendations) == 0) {
  recommendations <- "No automatic quality warnings were triggered."
}

sample_summary_file <- file.path(report_dir, paste0("chipseq_sample_qc_summary.tsv", table_suffix))
group_summary_file <- file.path(report_dir, paste0("chipseq_group_summary.tsv", table_suffix))
diff_summary_file <- file.path(report_dir, paste0("chipseq_differential_summary.tsv", table_suffix))
diff_peak_set_file <- file.path(report_dir, paste0("chipseq_differential_by_peak_set.tsv", table_suffix))
write_tsv_safe(sample_summary, sample_summary_file)
write_tsv_safe(group_summary, group_summary_file)
if (nrow(diff_summary$by_contrast) > 0) write_tsv_safe(diff_summary$by_contrast, diff_summary_file)
if (nrow(diff_summary$by_peak_set_contrast) > 0) write_tsv_safe(diff_summary$by_peak_set_contrast, diff_peak_set_file)

sample_display <- sample_summary[, c("sample_id", "condition", "mark_or_factor", "is_control", "raw_reads_fastp",
                                     "trimmed_reads_fastp", "trim_retained_pct", "aligner_input_reads", "aligner_overall_alignment_pct",
                                     "aligned_bam_reads", "aligned_bam_mapped_pct", "final_filtered_reads",
                                     "peak_type", "peak_count"), drop = FALSE]
sample_display$trim_retained_pct <- percent(sample_display$trim_retained_pct)
sample_display$aligner_overall_alignment_pct <- percent(sample_display$aligner_overall_alignment_pct)
sample_display$aligned_bam_mapped_pct <- percent(sample_display$aligned_bam_mapped_pct)

figures <- plot_report_figures(report_dir, sample_summary, annotation_totals, consensus_summary, diff_summary)
write_html_report(
  path = file.path(report_dir, "chipseq_report.html"),
  report_dir = report_dir,
  outdir = outdir,
  metadata = metadata,
  sample_display = sample_display,
  group_summary = group_summary,
  annotation_totals = annotation_totals,
  annotation_summary = annotation_summary,
  consensus_summary = consensus_summary,
  count_summary = count_summary,
  diff_summary = diff_summary,
  recommendations = recommendations,
  figures = figures,
  sample_summary_file = sample_summary_file,
  diff_summary_file = diff_summary_file,
  diff_peak_set_file = diff_peak_set_file
)

con <- file(report, open = "w", encoding = "UTF-8")
on.exit(close(con), add = TRUE)

writeLines(c(
  "# ChIP-seq final report",
  "",
  paste("Generated:", format(Sys.time(), "%Y-%m-%d %H:%M:%S")),
  paste("Work directory:", outdir),
  "",
  "## Run overview",
  "",
  paste("Total samples:", nrow(metadata)),
  paste("IP samples:", sum(!is_control)),
  paste("Control/input samples:", sum(is_control)),
  paste("Conditions:", paste(sort(unique(metadata$condition)), collapse = ", ")),
  paste("Marks/factors:", paste(sort(unique(metadata$mark_or_factor)), collapse = ", ")),
  "",
  "HTML report: `chipseq_report.html`",
  "Report figures: `figures/`",
  "",
  "## Important interpretation notes",
  "",
  "- `aligner_overall_alignment_pct` comes from the aligner log when available and is the preferred mapping-rate metric.",
  "- `aligned_bam_*` metrics come from the sorted BAM before MAPQ filtering, duplicate removal, and blacklist filtering when that file is available.",
  "- `final_mapped_pct` and `final_duplicate_pct` are calculated after filtering and duplicate removal; they describe the final BAM, not the original library complexity.",
  "- Differential binding counts below separate tested rows from statistically significant rows.",
  ""
), con)

writeLines("## Group summary\n", con)
markdown_table(group_summary, con, max_rows = 100)

writeLines(c("", "## Sample QC summary", ""), con)
markdown_table(sample_display, con, max_rows = 200)
writeLines(paste0("\nFull sample QC table: `", basename(sample_summary_file), "`"), con)

writeLines(c("", "## Peaks and consensus", ""), con)
writeLines(paste("Individual peak sets found:", sum(!is.na(sample_summary$peak_count))), con)
writeLines(paste("Total individual peaks:", fmt_num(sum(sample_summary$peak_count, na.rm = TRUE))), con)
if (nrow(consensus_summary) > 0) {
  writeLines(paste("Consensus peak sets:", nrow(consensus_summary)), con)
  markdown_table(consensus_summary[order(consensus_summary$consensus_peak_count, decreasing = TRUE), , drop = FALSE], con, max_rows = 30)
} else {
  writeLines("No consensus peak BED files were found.", con)
}
if (nrow(count_summary) > 0) {
  writeLines(c("", "Consensus count matrices:"), con)
  markdown_table(count_summary, con, max_rows = 50)
}

writeLines(c("", "## Peak annotation", ""), con)
if (nrow(annotation_totals) > 0) {
  markdown_table(annotation_totals[order(annotation_totals$n, decreasing = TRUE), , drop = FALSE], con)
  writeLines("", con)
}
if (nrow(annotation_summary) > 0) {
  writeLines("Annotation summary by peak set:", con)
  markdown_table(annotation_summary, con, max_rows = 80)
} else {
  writeLines("Peak annotation summary was not found.", con)
}

writeLines(c("", "## Differential binding", ""), con)
if (nrow(diff_summary$overall) > 0) {
  markdown_table(diff_summary$overall, con)
  if (nrow(diff_summary$by_method) > 0) {
    writeLines(c("", "Methods used:"), con)
    markdown_table(diff_summary$by_method, con)
  }
  if (nrow(diff_summary$by_mark) > 0) {
    writeLines(c("", "Differential summary by mark/factor:"), con)
    markdown_table(diff_summary$by_mark, con, max_rows = 50)
  }
  if (nrow(diff_summary$by_peak_set) > 0) {
    writeLines(c("", "Differential summary by peak set:"), con)
    markdown_table(diff_summary$by_peak_set, con, max_rows = 50)
  }
  if (nrow(diff_summary$by_contrast) > 0) {
    writeLines(c("", "Differential summary by contrast:"), con)
    markdown_table(diff_summary$by_contrast, con, max_rows = 50)
    writeLines(paste0("\nFull differential summary: `", basename(diff_summary_file), "`"), con)
  }
  if (nrow(diff_summary$by_peak_set_contrast) > 0) {
    writeLines(paste0("Full differential summary by peak set and contrast: `", basename(diff_peak_set_file), "`"), con)
  }
} else {
  writeLines("No differential binding results were generated.", con)
}

writeLines(c(
  "",
  "## Main output directories",
  "",
  "- `030-qc-fastq`: raw and post-trim FastQC/MultiQC",
  "- `040-trimming`: trimmed FASTQs and fastp reports",
  "- `050-alignment`: sorted BAMs and aligner logs",
  "- `060-filtering`: final filtered BAMs and BAM metrics",
  "- `070-qc-alignment`: alignment QC and MultiQC",
  "- `080-peak-calling`: MACS peak calls",
  "- `090-peak-annotation`: annotated peak tables",
  "- `100-tracks`: bigWig tracks",
  "- `110-consensus-peaks`: merged peaks and count matrices",
  "- `120-differential-binding`: differential enrichment tables and plots",
  "",
  "## Automatic recommendations",
  ""
), con)
writeLines(paste("-", recommendations), con)
