#!/usr/bin/env bash
set -euo pipefail

rc_root=${1:?immutable RC checkout is required}
nextflow_jar=${2:?Nextflow jar is required}
java_bin=${3:?Java 21 executable is required}
rna_env=${4:?RNA tools environment is required}
python_env=${5:?Python environment is required}
r_env=${6:?R analysis environment is required}
case_root=${7:?prepared case root is required}
queue=${8:-general}

expected_sha=fc38ada8f592bb57a13467965a718ce0df7fb6ce
expected_tag=v1.0.0-rc.1
test -z "${SLURM_JOB_ID:-}"
git -C "$rc_root" rev-parse --is-inside-work-tree | grep -Fxq true
test -x "$java_bin"
test -s "$nextflow_jar"
test -x "$rna_env/bin/salmon"
test -x "$rna_env/bin/java"
test -x "$python_env/bin/python3"
test -x "$r_env/bin/Rscript"
test -s "$case_root/pipeline_config.sh"
test -s "$case_root/analysis_spec.json"
test ! -e "$case_root/results"
test ! -e "$case_root/work"

observed_sha=$(git -C "$rc_root" rev-parse HEAD)
observed_tag=$(git -C "$rc_root" describe --tags --exact-match HEAD)
[[ "$observed_sha" == "$expected_sha" ]]
[[ "$observed_tag" == "$expected_tag" ]]
"$java_bin" -version 2>&1 | grep -Fq 'version "21.'
"$java_bin" -jar "$nextflow_jar" -version 2>&1 | grep -Fq 'version 25.10.7'

mkdir -p "$case_root/logs" "$case_root/nxf-home" "$case_root/nxf-cache"
runtime_path="$r_env/bin:$python_env/bin:$rna_env/bin:$(dirname "$java_bin"):/usr/bin:/bin"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$rna_env/bin/java" -version > "$case_root/logs/fastqc_java_version.txt" 2>&1

cd "$rc_root"
env PATH="$runtime_path" \
    FONTCONFIG_PATH="$rna_env/etc/fonts" \
    FONTCONFIG_FILE="$rna_env/etc/fonts/fonts.conf" \
    XDG_DATA_DIRS="$rna_env/share:/usr/local/share:/usr/share" \
    NXF_HOME="$case_root/nxf-home" \
    NXF_CACHE_DIR="$case_root/nxf-cache" \
    "$java_bin" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$case_root/logs/nextflow.log" \
    run main.nf \
    -c tests/slurm/rnaseq-production.config \
    -ansi-log false \
    -work-dir "$case_root/work" \
    -process.queue="$queue" \
    --workflow rnaseq \
    --outdir "$case_root/results" \
    --rnaseq_config "$case_root/pipeline_config.sh" \
    --rnaseq_analysis_mode quantification \
    --rnaseq_run_mode full \
    --rnaseq_native_alignment false \
    --rnaseq_native_quantification true \
    --rnaseq_native_import true \
    --rnaseq_native_de true \
    --rnaseq_import_policy production_v1 \
    --rnaseq_de_spec "$case_root/analysis_spec.json" \
    --rnaseq_library_protocol full_length \
    --rnaseq_counts_from_abundance lengthScaledTPM \
    --rnaseq_report_enabled false \
    --salmon_validate_mappings true \
    --salmon_index_queue "$queue" \
    --salmon_quant_queue "$queue" \
    --tx2gene_queue "$queue" \
    --tximport_queue "$queue" \
    --deseq2_model_queue "$queue" \
    --deseq2_contrast_queue "$queue"

ended=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"status":"complete","rc_tag":"%s","rc_sha":"%s","nextflow":"25.10.7","java_major":21,"started_utc":"%s","ended_utc":"%s","queue":"%s","queue_size":5}\n' \
    "$expected_tag" "$expected_sha" "$started" "$ended" "$queue" \
    > "$case_root/execution_identity.json"
