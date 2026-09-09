#!/usr/bin/env bash
set -euo pipefail

repo=${1:-/home/CLUSTER_USER/helixforge-integrative-sanitized}
root=${2:-/scratch/HELIXFORGE_WORKSPACE/helixforge-integrative-real}
mark=${3:?mark is required}
queue=${4:-general}
inventory=${5:?report inventory is required}
case "$mark" in
    H3K27ac) case_name=chipseq_h3k27ac; peak_type=narrow ;;
    H3K27me3) case_name=chipseq_h3k27me3; peak_type=broad ;;
    *) echo "unsupported mark: $mark" >&2; exit 2 ;;
esac
case_root="$root/cases/$case_name"
lower_mark=${mark,,}
analysis="gse133183_${lower_mark}.gse133183_${lower_mark}.${mark}.${mark}.GRCh38.p14_GENCODE_50.${peak_type}"
nextflow_jar=${HELIXFORGE_NEXTFLOW_JAR:-/home/CLUSTER_USER/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar}
java_runtime=${HELIXFORGE_JAVA_RUNTIME:-/scratch/HELIXFORGE_WORKSPACE/envs/rna-tools}
python_runtime=${HELIXFORGE_PYTHON_RUNTIME:-/scratch/HELIXFORGE_WORKSPACE/envs/python-runtime}
chip_runtime=${HELIXFORGE_CHIP_RUNTIME:-/home/CLUSTER_USER/miniconda3/envs/chipseq}
config="$repo/benchmark/integrative/configs/real_upstream_slurm.config"
entrypoint="$repo/benchmark/integrative/workflows/gse133183_chipseq_report_reentry.nf"
work=${HELIXFORGE_REPORT_REENTRY_WORK:-$case_root/report_reentry_work}
logs="$case_root/logs/report_reentry"
metadata="$case_root/results/pipeline_info/native_chipseq/metadata/validated_metadata.tsv"
reference_manifest="$case_root/results/pipeline_info/native_chipseq/reference/reference_bundle.manifest.json"
db_results="$case_root/results/120-differential-binding/differential_binding_results/contrasts/$analysis/GSK343_vs_DMSO/differential_binding_results.tsv"
contrast_spec="$case_root/db_spec.json"
annotation_results="$case_root/results/chipseq/peak_annotation/peak_annotation_aggregate/peak_gene_associations.tsv"
track_artifact="$case_root/results/chipseq/tracks/track_aggregate/tracks"
peak_qc_summary="$case_root/results/chipseq/peak_qc/peak_qc_summary.tsv"
consensus_id="gse133183_${lower_mark}.gse133183_${lower_mark}.${mark}.GSK343.${mark}.GRCh38.p14_GENCODE_50.${peak_type}"
consensus_artifact="$case_root/results/chipseq/consensus/$consensus_id/$consensus_id.union.consensus_result/consolidated_peaks.bed"

test -z "${SLURM_JOB_ID:-}"
for required in "$entrypoint" "$config" "$inventory" "$metadata" "$reference_manifest" \
    "$db_results" "$contrast_spec" "$annotation_results" "$track_artifact" \
    "$peak_qc_summary" "$consensus_artifact" "$nextflow_jar"; do
    test -e "$required"
done
test -x "$java_runtime/bin/java"
test -x "$python_runtime/bin/python3"
test ! -e "$work"
test ! -e "$case_root/results/chipseq/chipseq_run_manifest.json"
mkdir -p "$work" "$logs" "$case_root/report_reentry_nxf_home" "$case_root/report_reentry_nxf_cache"
runtime_path="$repo/modules/local/report_context/resources/usr/bin:$repo/modules/local/report_aggregate/resources/usr/bin:$repo/modules/local/report_generator/resources/usr/bin:$repo/bin:$chip_runtime/bin:$python_runtime/bin:/usr/bin:/bin"

cd "$repo"
env PATH="$runtime_path" NXF_HOME="$case_root/report_reentry_nxf_home" \
    NXF_CACHE_DIR="$case_root/report_reentry_nxf_cache" \
    "$java_runtime/bin/java" -Xms128m -Xmx1g -jar "$nextflow_jar" \
    -log "$logs/nextflow.log" run "$entrypoint" -c "$config" -ansi-log false \
    -work-dir "$work" -process.queue="$queue" \
    --helixforge_root "$repo" --outdir "$case_root/results" \
    --report_inventory "$inventory" --metadata "$metadata" \
    --reference_manifest "$reference_manifest" --contrast_spec "$contrast_spec" \
    --db_results "$db_results" --annotation_results "$annotation_results" \
    --track_artifact "$track_artifact" --peak_qc_summary "$peak_qc_summary" \
    --consensus_artifact "$consensus_artifact" --consensus_condition GSK343 \
    --mark "$mark" --peak_type "$peak_type" --contrast_id GSK343_vs_DMSO \
    --report_title "GSE133183 K562 $mark GSK343 versus DMSO" --report_language en \
    --chipseq_report_queue "$queue"

if grep -Eq 'Submitted process > .*:(FASTQC|BOWTIE2|BAM_|MACS3|PEAK_|CONSENSUS_|DESEQ2_DB_)' "$logs/driver.out"; then
    echo 'report re-entry unexpectedly submitted an upstream scientific process' >&2
    exit 3
fi
test -s "$case_root/results/chipseq/report/report_result/chipseq_report.html"
test -s "$case_root/results/chipseq/chipseq_run_manifest.json"
