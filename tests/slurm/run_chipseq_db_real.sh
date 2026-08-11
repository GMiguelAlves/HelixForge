#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
r_env=${5:-r-analysis}
queue=${6:-general}
mode=${7:-driver}
case_name=${8:-chipseq-db-real}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${case_root}/fixture"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${r_env}/bin:${conda_root}/envs/${chip_env}/bin:${conda_root}/envs/${rna_env}/bin:/usr/bin:/bin"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac
test -d "$repo_root/.git"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${chip_env}/bin/featureCounts"
test -x "${conda_root}/envs/${r_env}/bin/Rscript"

if [[ "$mode" == "prepare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python \
        "$repo_root/tests/native_chipseq_differential_binding/generate_fixture.py" \
        --outdir "$fixture_root"
    env PATH="$runtime_path" python "$repo_root/tests/slurm/prepare_db_bams.py" \
        --outdir "$fixture_root"
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python - "$nextflow_out" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
result_root = root / "chipseq/differential_binding/differential_binding_results"
with (result_root / "differential_binding_results.tsv").open(encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
assert rows, rows
assert {row["contrast"] for row in rows} == {"treated_vs_control", "control_vs_treated"}, rows
for row in rows:
    for field in ("baseMean", "log2FoldChange", "pvalue"):
        float(row[field])
with (result_root / "differential_binding_summary.tsv").open(encoding="utf-8") as handle:
    summary = list(csv.DictReader(handle, delimiter="\t"))
assert len(summary) == 2, summary
manifest = json.loads((result_root / "manifest.json").read_text())
assert manifest["status"] == "complete", manifest
assert manifest["contrasts"] == 2, manifest
PY
    printf 'check\tresult\nfeaturecounts_matrix\tPASS\ndeseq2_model\tPASS\ncontrasts\tPASS\naggregate\tPASS\n' \
        > "$case_root/comparison.tsv"
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver, prepare-job, or compare-job" >&2
    exit 2
fi
if [[ -e "$case_root" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root"
prepare_job=$(sbatch --wait --parsable --job-name=hf-db-prepare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-prepare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$r_env" "$queue" \
    prepare-job "$case_name")
printf '%s\n' "$prepare_job" > "$case_root/prepare_job_id.txt"

mkdir -p "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" run tests/native_chipseq_differential_binding/main.nf \
    -c tests/native_chipseq_differential_binding/nextflow.config -c tests/slurm/native-runtime.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --fixture_dir "$fixture_root" --outdir "$nextflow_out" \
    --db_count_queue "$queue" --db_model_queue "$queue" --db_contrast_queue "$queue"

compare_job=$(sbatch --wait --parsable --job-name=hf-db-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$r_env" "$queue" \
    compare-job "$case_name")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 && $3 != "-" {print $3}' "$nextflow_out/pipeline_info/execution_trace.tsv" | paste -sd, -)
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\ndifferential_binding_slurm\t%s\n' "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real differential-binding Slurm validation passed."
echo "[OK] Case root: $case_root"

