#!/usr/bin/env bash
#SBATCH --job-name=hf-int-real-inputs
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901/logs/%x.%j.out
#SBATCH --error=/scratch/Schisto-epigenetics/gustavo/helixforge-integrative-real-20260901/logs/%x.%j.err
set -euo pipefail

repo=${1:?repository checkout is required}
root=${2:?benchmark root is required}
repo_commit=${3:?repository commit captured on the head node is required}
attempt=${4:-initial}
state="$root/benchmark_state.json"
cases="$root/cases"
rna_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/rna-tools-rc
python_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/python-runtime-rc
r_runtime=/scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs/r-analysis-rc
chip_runtime=/home/ra236875@bio.ib.unicamp.br/miniconda3/envs/chipseq

update() {
    HF_STATE_TIME_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
        python3 "$repo/benchmark/integrative/scripts/real/update_real_benchmark_state.py" \
        --state "$state" --phase "$1" --status "$2" --job-id "$SLURM_JOB_ID" \
        --job-kind upstream_input_preparation --repo-commit "$repo_commit" \
        --workdir "$cases" --expected-output cases/cases_manifest.json
}
if [[ "$attempt" == retry ]]; then
    submitted_phase=UPSTREAM_INPUTS_RETRY_SUBMITTED
    failed_phase=UPSTREAM_INPUTS_RETRY_FAILED
    complete_phase=UPSTREAM_INPUTS_RETRY_COMPLETE
else
    submitted_phase=UPSTREAM_INPUTS_SUBMITTED
    failed_phase=UPSTREAM_INPUTS_FAILED
    complete_phase=UPSTREAM_INPUTS_COMPLETE
fi
trap 'update "$failed_phase" FAILED' ERR
update "$submitted_phase" RUNNING

test -x "$rna_runtime/bin/salmon"
test -x "$rna_runtime/bin/trim_galore"
test -x "$python_runtime/bin/python3"
test -x "$r_runtime/bin/Rscript"
test -x "$chip_runtime/bin/bowtie2"
test -x "$chip_runtime/bin/samtools"
test -x "$chip_runtime/bin/macs3"
test -x "$chip_runtime/bin/bedtools"
test -x "$chip_runtime/bin/featureCounts"
test -x "$chip_runtime/bin/Rscript"
test -x "$chip_runtime/bin/bamCoverage"
test -s /home/ra236875@bio.ib.unicamp.br/.nextflow/framework/25.10.7/nextflow-25.10.7-one.jar

mkdir -p "$root/provenance/upstream_inputs"
{
    "$rna_runtime/bin/salmon" --version
    "$chip_runtime/bin/bowtie2" --version | head -1
    "$chip_runtime/bin/samtools" --version | head -1
    "$chip_runtime/bin/macs3" --version
    "$chip_runtime/bin/bedtools" --version
    "$chip_runtime/bin/featureCounts" -v 2>&1
    "$chip_runtime/bin/Rscript" --version
    "$chip_runtime/bin/bamCoverage" --version
} > "$root/provenance/upstream_inputs/tool_versions.txt"

"$python_runtime/bin/python3" "$repo/benchmark/integrative/scripts/real/prepare_gse133183_upstream_inputs.py" \
    --metadata "$root/metadata/dataset_metadata.tsv" \
    --fastq-inventory "$root/download_validation/fastq_inventory.tsv" \
    --reference-manifest "$root/reference/reference_manifest.json" \
    --repo "$repo" --output-root "$cases" \
    --conda-base /scratch/Schisto-epigenetics/gustavo/helixforge-rnaseq-benchmark-20260825/envs

update "$complete_phase" COMPLETE
trap - ERR
