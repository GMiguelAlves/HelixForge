#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-chipseq-report-real}
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

if [[ "$mode" == "prepare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python \
        "$repo_root/tests/native_chipseq_report/generate_fixture.py" --outdir "$fixture_root"
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    env PATH="$runtime_path" python - "$nextflow_out" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
report_root = root / "chipseq/report/report_result"
html = report_root / "chipseq_report.html"
text = html.read_text(encoding="utf-8")
assert html.stat().st_size > 1000, html
assert "Fixture ChIP-seq report" in text, text[:500]
assert "Differential" in text and "Annotation" in text and "Tracks" in text, text[:1000]
manifest = json.loads((report_root / "manifest.json").read_text())
assert manifest["status"] == "incomplete", manifest
assert manifest["component_status"]["consensus_idr"] == "incomplete", manifest
assert manifest["artifacts"]["report"]["path"] == "chipseq_report.html", manifest
PY
    printf 'check\tresult\nself_contained_html\tPASS\ncomponent_sections\tPASS\nincomplete_idr_disclosure\tPASS\nmanifest\tPASS\n' \
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
prepare_job=$(sbatch --wait --parsable --job-name=hf-report-prepare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-prepare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    prepare-job "$case_name")
printf '%s\n' "$prepare_job" > "$case_root/prepare_job_id.txt"

mkdir -p "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" run tests/native_chipseq_report/main.nf \
    -c tests/native_chipseq_report/nextflow.config -c tests/slurm/native-runtime.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --report_inventory "$fixture_root/report_input.json" --outdir "$nextflow_out"

compare_job=$(sbatch --wait --parsable --job-name=hf-report-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    compare-job "$case_name")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 && $3 != "-" {print $3}' "$nextflow_out/pipeline_info/execution_trace.tsv" | paste -sd, -)
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\nchipseq_report_slurm\t%s\n' "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real ChIP-seq report Slurm validation passed."
echo "[OK] Case root: $case_root"
