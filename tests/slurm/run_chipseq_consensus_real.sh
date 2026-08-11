#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-chipseq-consensus-real}
peaks_case=${8:-chipseq-peaks-real-02}
qc_case=${9:-chipseq-peak-qc-real-01}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
peaks_root="${validation_root}/results/${peaks_case}/nextflow/peaks"
qc_root="${validation_root}/results/${qc_case}/nextflow"
peak_plan="${validation_root}/results/${qc_case}/input/peak_plan.tsv"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${chip_env}/bin:${conda_root}/envs/${rna_env}/bin:/usr/bin:/bin"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac
test -d "$repo_root/.git"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${chip_env}/bin/bedtools"
test -d "$peaks_root"
test -s "$peak_plan"

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python - "$nextflow_out" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
summary = root / "chipseq/consensus/consolidation_summary.tsv"
with summary.open(encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
assert len(rows) == 1, rows
assert rows[0]["strategy"] == "union", rows[0]
assert rows[0]["consolidated_peaks_available"].lower() == "true", rows[0]
results = list((root / "chipseq/consensus").glob("*/*.union.consensus_result"))
assert len(results) == 1, results
result = results[0]
bed_rows = [line for line in (result / "consolidated_peaks.bed").read_text().splitlines() if line]
assert bed_rows, result
statistics = json.loads((result / "statistics.json").read_text())
assert statistics["consolidated_peaks"] == len(bed_rows), statistics
assert statistics["replicate_count"] == 2, statistics
PY
    printf 'check\tresult\nconsensus_group\tPASS\nunion_strategy\tPASS\nconsolidated_peaks\tPASS\nreplicate_count\tPASS\n' \
        > "$case_root/comparison.tsv"
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver or compare-job" >&2
    exit 2
fi
if [[ -e "$case_root" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root" "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" run tests/slurm/chipseq_consensus_real.nf \
    -c tests/native_chipseq_consensus/nextflow.config -c tests/slurm/native-runtime.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --peaks_dir "$peaks_root" --peak_qc_dir "$qc_root" --peak_plan "$peak_plan" \
    --outdir "$nextflow_out" --consensus_queue "$queue" \
    --chipseq_run_mode consensus --chipseq_consensus_method union --chipseq_min_replicates 2

compare_job=$(sbatch --wait --parsable --job-name=hf-cons-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    compare-job "$case_name" "$peaks_case" "$qc_case")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 && $3 != "-" {print $3}' "$nextflow_out/pipeline_info/execution_trace.tsv" | paste -sd, -)
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\nconsensus_union_slurm\t%s\n' "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real consensus-union Slurm validation passed."
echo "[OK] Case root: $case_root"

