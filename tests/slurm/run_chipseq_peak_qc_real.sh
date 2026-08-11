#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-chipseq-peak-qc-real}
peaks_case=${8:-chipseq-peaks-real-02}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
peaks_case_root="${validation_root}/results/${peaks_case}"
bam_fixture="${peaks_case_root}/fixture"
peaks_root="${peaks_case_root}/nextflow/peaks"
input_dir="${case_root}/input"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${chip_env}/bin:${conda_root}/envs/${rna_env}/bin:/usr/bin:/bin"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac
test -d "$repo_root/.git"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${chip_env}/bin/samtools"
test -x "${conda_root}/envs/${chip_env}/bin/bedtools"
test -d "$peaks_root"

if [[ "$mode" == "prepare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python "$repo_root/tests/slurm/prepare_peak_qc_input.py" \
        --source-plan "$bam_fixture/chipseq_plan.tsv" --outdir "$input_dir"
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
summary = root / "chipseq/peak_qc/peak_qc_summary.tsv"
with summary.open(encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
assert len(rows) == 2, rows
for row in rows:
    frip = float(row["frip"])
    assert 0.0 < frip <= 1.0, row
    assert int(row["peak_count"]) > 0, row
    assert int(row["total_units"]) >= int(row["units_in_peaks"]) > 0, row
manifests = sorted((root / "pipeline_info/native_chipseq/peak_qc/frip").glob("*.frip.manifest.json"))
assert len(manifests) == 2, manifests
for path in manifests:
    document = json.loads(path.read_text())
    assert document["metrics"]["frip"] > 0, document
PY
    printf 'check\tresult\nreplicates\tPASS\nfrip_range\tPASS\npeak_statistics\tPASS\naggregate\tPASS\n' \
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
prepare_job=$(sbatch --wait --parsable --job-name=hf-frip-prepare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-prepare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    prepare-job "$case_name" "$peaks_case")
printf '%s\n' "$prepare_job" > "$case_root/prepare_job_id.txt"

mkdir -p "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" run tests/slurm/chipseq_peak_qc_real.nf \
    -c tests/native_chipseq_peak_qc/nextflow.config -c tests/slurm/native-runtime.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --bam_fixture_dir "$bam_fixture" --peaks_dir "$peaks_root" \
    --peak_plan "$input_dir/peak_plan.tsv" --outdir "$nextflow_out" \
    --peak_qc_queue "$queue"

compare_job=$(sbatch --wait --parsable --job-name=hf-frip-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    compare-job "$case_name" "$peaks_case")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 && $3 != "-" {print $3}' "$nextflow_out/pipeline_info/execution_trace.tsv" | paste -sd, -)
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\npeak_qc_slurm\t%s\n' "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real FRiP and peak-statistics Slurm validation passed."
echo "[OK] Case root: $case_root"

