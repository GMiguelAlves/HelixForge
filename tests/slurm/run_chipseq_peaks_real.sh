#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-chipseq-peaks-real}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${case_root}/fixture"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${chip_env}/bin:${conda_root}/envs/${rna_env}/bin:/usr/bin:/bin"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac
test -d "$repo_root/.git"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${chip_env}/bin/macs3"
test -s "$validation_root/nextflow.jar"

if [[ "$mode" == "prepare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python \
        "$repo_root/tests/native_chipseq_peaks/generate_fixture.py" \
        --outdir "$fixture_root"
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python - "$nextflow_out" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1]) / "peaks"
manifests = sorted(root.glob("**/*.peak_calling/manifest.json"))
assert len(manifests) == 2, manifests
record_ids = set()
for path in manifests:
    document = json.loads(path.read_text())
    assert document["metrics"]["total_peaks"] > 0, document
    assert document["peak_type"] == "narrow", document
    assert document["control_record_id"] == "input_rep1", document
    peak = path.parent / "peaks.narrowPeak"
    for line in peak.read_text().splitlines():
        columns = line.split("\t")
        assert len(columns) == 10, columns
        assert int(columns[1]) >= 0 and int(columns[2]) > int(columns[1]), columns
    record_ids.add(document["record_id"])
assert record_ids == {"chip_rep1", "chip_rep2"}, record_ids
PY
    printf 'check\tresult\nreplicate_manifests\tPASS\npeak_count\tPASS\nnarrowpeak_format\tPASS\ncontrol_identity\tPASS\n' \
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
prepare_job=$(sbatch --wait --parsable \
    --job-name=hf-peaks-prepare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 \
    --output="$case_root/slurm-prepare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    prepare-job "$case_name")
printf '%s\n' "$prepare_job" > "$case_root/prepare_job_id.txt"

mkdir -p "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" run tests/native_chipseq_peaks/main.nf \
    -c tests/native_chipseq_peaks/nextflow.config \
    -c tests/slurm/native-runtime.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --fixture_dir "$fixture_root" --outdir "$nextflow_out" \
    --macs3_queue "$queue"

compare_job=$(sbatch --wait --parsable \
    --job-name=hf-peaks-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 \
    --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    compare-job "$case_name")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 && $3 != "-" {print $3}' "$nextflow_out/pipeline_info/execution_trace.tsv" | paste -sd, -)
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\nmacs3_peak_calling_slurm\t%s\n' \
    "$((native_seconds * 1000))" > "$case_root/benchmark.tsv"

echo "[OK] Real MACS3 peak-calling Slurm validation passed."
echo "[OK] Case root: $case_root"
