#!/usr/bin/env bash
set -euo pipefail

r_env=${1:?R environment prefix is required}
output_json=${2:?output JSON path is required}

test -n "${SLURM_JOB_ID:-}"
test -x "$r_env/bin/Rscript"

mkdir -p "$(dirname "$output_json")"

"$r_env/bin/Rscript" --vanilla - "$output_json" <<'RSCRIPT'
args <- commandArgs(trailingOnly = TRUE)
output_json <- args[[1]]
packages <- c("readr", "dplyr", "tidyr", "stringr", "ggplot2", "pheatmap")

loaded <- vapply(
  packages,
  function(package) requireNamespace(package, quietly = TRUE),
  logical(1)
)
if (!all(loaded)) {
  stop(sprintf("missing R packages: %s", paste(packages[!loaded], collapse = ", ")))
}

escape_json <- function(value) {
  value <- gsub("\\\\", "\\\\\\\\", value)
  gsub('"', '\\\\"', value)
}

versions <- vapply(packages, function(package) as.character(packageVersion(package)), character(1))
package_json <- paste(
  sprintf('"%s":"%s"', escape_json(names(versions)), escape_json(versions)),
  collapse = ","
)
payload <- sprintf(
  paste0(
    '{"status":"complete","provider":"rnaseq_report_r",',
    '"r_version":"%s","packages":{%s},',
    '"slurm_job_id":"%s","host":"%s","validated_utc":"%s"}\n'
  ),
  escape_json(as.character(getRversion())),
  package_json,
  escape_json(Sys.getenv("SLURM_JOB_ID")),
  escape_json(Sys.info()[["nodename"]]),
  format(Sys.time(), tz = "UTC", format = "%Y-%m-%dT%H:%M:%SZ")
)
writeLines(payload, output_json, useBytes = TRUE)
RSCRIPT

test -s "$output_json"
