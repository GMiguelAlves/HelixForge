#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/CLUSTER_USER/helixforge-integrative-sanitized}
root=${2:-/scratch/HELIXFORGE_WORKSPACE/helixforge-integrative-real}
queue=${3:-general}
case_root="$root/cases/chipseq_h3k27me3"
nextflow_jar=${HELIXFORGE_NEXTFLOW_JAR:-/home/CLUSTER_USER/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar}
java_runtime=${HELIXFORGE_JAVA_RUNTIME:-/scratch/HELIXFORGE_WORKSPACE/envs/rna-tools}
python_runtime=${HELIXFORGE_PYTHON_RUNTIME:-/scratch/HELIXFORGE_WORKSPACE/envs/python-runtime}
chip_runtime=${HELIXFORGE_CHIP_RUNTIME:-/home/CLUSTER_USER/miniconda3/envs/chipseq}
config="$repo/benchmark/integrative/configs/real_upstream_slurm.config"
entrypoint="$repo/benchmark/integrative/workflows/gse133183_h3k27me3_completion_reentry.nf"
work=${HELIXFORGE_H3K27ME3_COMPLETION_WORK:-$case_root/completion_reentry_work}
logs="$case_root/logs/completion_reentry"

test -z "${SLURM_JOB_ID:-}"
test -s "$entrypoint"
test -s "$config"
test -s "$nextflow_jar"
test -x "$java_runtime/bin/java"
test -x "$python_runtime/bin/python3"
test ! -e "$work"
test ! -e "$case_root/results/chipseq/chipseq_run_manifest.json"
test ! -e "$case_root/results/chipseq/peak_annotation/peak_annotation_aggregate"
test ! -e "$case_root/results/chipseq/tracks/track_aggregate"
mkdir -p "$work" "$logs" "$case_root/completion_reentry_nxf_home" "$case_root/completion_reentry_nxf_cache"

runtime_path="$repo/modules/local/peak_annotation_context/resources/usr/bin:$repo/modules/local/peak_annotator/resources/usr/bin:$repo/modules/local/peak_annotation_statistics/resources/usr/bin:$repo/modules/local/peak_annotation_aggregate/resources/usr/bin:$repo/modules/local/track_aggregate/resources/usr/bin:$chip_runtime/bin:$python_runtime/bin:/usr/bin:/bin"

cd "$repo"
env PATH="$runtime_path" NXF_HOME="$case_root/completion_reentry_nxf_home" \
    NXF_CACHE_DIR="$case_root/completion_reentry_nxf_cache" \
    "$java_runtime/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$logs/nextflow.log" run "$entrypoint" -c "$config" -ansi-log false \
    -work-dir "$work" -process.queue="$queue" \
    --outdir "$case_root/results" --case_root "$case_root" --benchmark_root "$root"

if grep -Eq 'Submitted process > .*:(FASTQC|BOWTIE2|BAM_|MACS3|PEAK_QC|CONSENSUS_|DESEQ2_DB_)' "$logs/driver.out"; then
    echo 'H3K27me3 completion re-entry unexpectedly submitted an upstream scientific process' >&2
    exit 3
fi
test -s "$case_root/results/chipseq/peak_annotation/peak_annotation_aggregate/peak_gene_associations.tsv"
test -s "$case_root/results/chipseq/tracks/track_aggregate/tracks.tsv"
test -s "$case_root/results/pipeline_info/native_chipseq/full/chipseq_full_report_input.json"
