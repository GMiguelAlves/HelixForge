#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-chipseq-tracks-real}
source_case=${8:-chipseq-peaks-real-02}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
source_dir="${validation_root}/results/${source_case}/fixture"
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
test -x "${conda_root}/envs/${chip_env}/bin/bamCoverage"
test -d "$source_dir"

if [[ "$mode" == "prepare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python "$repo_root/tests/slurm/prepare_tracks_input.py" \
        --source-dir "$source_dir" --outdir "$fixture_root"
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python - "$nextflow_out" <<'PY'
import csv
import json
import pathlib
import pyBigWig
import sys

root = pathlib.Path(sys.argv[1])
aggregate = root / "chipseq/tracks/track_aggregate"
with (aggregate / "tracks.tsv").open(encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
assert len(rows) == 4, rows
assert sum(row["track_role"] == "aggregate" for row in rows) == 1, rows
for row in rows:
    path = aggregate / row["track"]
    assert path.stat().st_size > 0, path
    with pyBigWig.open(str(path)) as handle:
        assert handle.chroms() == {"chrTest": 2000}, handle.chroms()
manifest = json.loads((aggregate / "manifest.json").read_text())
assert manifest["tracks"] == 4 and manifest["status"] == "complete", manifest
PY
    printf 'check\tresult\nindividual_tracks\tPASS\naggregate_track\tPASS\nbigwig_structure\tPASS\ncontigs\tPASS\n' \
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
prepare_job=$(sbatch --wait --parsable --job-name=hf-track-prepare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-prepare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    prepare-job "$case_name" "$source_case")
printf '%s\n' "$prepare_job" > "$case_root/prepare_job_id.txt"

mkdir -p "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" run tests/native_chipseq_tracks/main.nf \
    -c tests/native_chipseq_tracks/nextflow.config -c tests/slurm/native-runtime.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --fixture_dir "$fixture_root" --outdir "$nextflow_out"

compare_job=$(sbatch --wait --parsable --job-name=hf-track-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    compare-job "$case_name" "$source_case")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 && $3 != "-" {print $3}' "$nextflow_out/pipeline_info/execution_trace.tsv" | paste -sd, -)
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\ntrack_generation_slurm\t%s\n' "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real ChIP-seq track-generation Slurm validation passed."
echo "[OK] Case root: $case_root"

