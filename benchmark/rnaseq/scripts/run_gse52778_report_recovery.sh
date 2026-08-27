#!/usr/bin/env bash
set -euo pipefail

repo_root=${1:?benchmark checkout is required}
nextflow_jar=${2:?Nextflow jar is required}
java_bin=${3:?Java 21 executable is required}
rna_env=${4:?RNA tools prefix is required}
python_env=${5:?Python provider prefix is required}
r_env=${6:?R analysis prefix is required}
case_root=${7:?prepared case root is required}
source_work=${8:?successful report-context work directory is required}
queue=${9:-general}

test -z "${SLURM_JOB_ID:-}"
test -x "$java_bin"
test -s "$nextflow_jar"
test -x "$python_env/bin/python3"
test -x "$r_env/bin/Rscript"
test -s "$source_work/report_context.json"
test -s "$source_work/inputs/genes.txt"
test ! -e "$case_root/pipeline/090-search-gene/results"
git -C "$repo_root" diff --quiet v1.0.0-rc.1 -- \
    modules/local/rnaseq_report_context \
    modules/local/rnaseq_gene_report \
    subworkflows/local/rnaseq/report.nf

recovery="$case_root/report-recovery"
mkdir -p "$recovery/logs" "$recovery/nxf-home" "$recovery/nxf-cache"
runtime_path="$python_env/bin:$r_env/bin:$rna_env/bin:$(dirname "$java_bin"):/usr/bin:/bin"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cd "$repo_root"
env PATH="$runtime_path" \
    FONTCONFIG_PATH="$rna_env/etc/fonts" \
    FONTCONFIG_FILE="$rna_env/etc/fonts/fonts.conf" \
    XDG_DATA_DIRS="$rna_env/share:/usr/local/share:/usr/share" \
    NXF_HOME="$recovery/nxf-home" \
    NXF_CACHE_DIR="$recovery/nxf-cache" \
    "$java_bin" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$recovery/logs/nextflow.log" \
    run benchmark/rnaseq/workflows/gse52778_report_recovery.nf \
    -c benchmark/rnaseq/configs/slurm-biological.config \
    -ansi-log false \
    -work-dir "$recovery/work" \
    -process.queue="$queue" \
    --outdir "$case_root/results" \
    --report_target "$case_root/pipeline/090-search-gene" \
    --report_title 'GSE52778 dexamethasone versus untreated' \
    --import_manifest "$source_work/upstream/import_manifest.json" \
    --abundance "$source_work/inputs/abundance.tsv" \
    --samples "$source_work/inputs/quant_samples.tsv" \
    --annotation "$source_work/inputs/annotation.gtf" \
    --de_results "$source_work/inputs/DEGs_all_results.tsv" \
    --de_manifest "$source_work/upstream/de_manifest.json" \
    --genes "$case_root/report_genes.txt" \
    --rnaseq_report_queue "$queue"

ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
benchmark_sha=$(git -C "$repo_root" rev-parse HEAD)
printf '{"status":"complete","type":"report_recovery","rc_tag":"v1.0.0-rc.1","report_modules_equal_rc":true,"benchmark_sha":"%s","nextflow":"25.10.7","java_major":21,"started_utc":"%s","ended_utc":"%s","queue":"%s"}\n' \
    "$benchmark_sha" "$started" "$ended" "$queue" > "$recovery/recovery_identity.json"
