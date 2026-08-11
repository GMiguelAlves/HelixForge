#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-bowtie2-real}
compat_bin=${8:-}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${repo_root}/tests/fixtures/native_alignment"
legacy_dir="${case_root}/legacy"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${chip_env}/bin:${conda_root}/envs/${rna_env}/bin:/usr/bin:/bin"
if [[ -n "$compat_bin" ]]; then
    case "$compat_bin" in
        "$validation_root"/*) ;;
        *) echo "Refusing compatibility binaries outside validation root: $compat_bin" >&2; exit 2 ;;
    esac
    test -x "$compat_bin/bowtie2"
    test -x "$compat_bin/bowtie2-build"
    runtime_path="${compat_bin}:${runtime_path}"
fi
native_id='SYNTHETIC.synthetic_sample.bowtie2.alignment'

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac

test -d "$repo_root/.git"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${chip_env}/bin/bowtie2"
test -x "${conda_root}/envs/${chip_env}/bin/samtools"
test -s "$validation_root/nextflow.jar"

if [[ "$mode" == "legacy-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    mkdir -p "$legacy_dir/index" "$legacy_dir/output"
    cd "$case_root"
    env PATH="$runtime_path" bowtie2-build --threads 1 \
        "$fixture_root/reference.fa" "$legacy_dir/index/genome" \
        > "$legacy_dir/bowtie2-build.log" 2>&1
    env PATH="$runtime_path" bowtie2 \
        -x "$legacy_dir/index/genome" \
        -p 1 \
        -1 "$fixture_root/reads_R1.fastq" \
        -2 "$fixture_root/reads_R2.fastq" \
        2> "$legacy_dir/output/bowtie2.log" \
        | env PATH="$runtime_path" samtools view -@ 1 -bS - \
        | env PATH="$runtime_path" samtools sort -@ 1 \
            -o "$legacy_dir/output/${native_id}.sorted.bam" -
    env PATH="$runtime_path" samtools index -@ 1 \
        "$legacy_dir/output/${native_id}.sorted.bam"
    env PATH="$runtime_path" samtools flagstat --threads 1 \
        "$legacy_dir/output/${native_id}.sorted.bam" \
        > "$legacy_dir/output/${native_id}.flagstat.txt"
    env PATH="$runtime_path" samtools idxstats \
        "$legacy_dir/output/${native_id}.sorted.bam" \
        > "$legacy_dir/output/${native_id}.idxstats.txt"
    exit 0
fi

if [[ "$mode" == "compare-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    legacy_bam="$legacy_dir/output/${native_id}.sorted.bam"
    native_bam="$native_dir/bowtie2_output/${native_id}.sorted.bam"
    env PATH="$runtime_path" samtools quickcheck -v "$legacy_bam" "$native_bam"
    env PATH="$runtime_path" samtools view "$legacy_bam" | sort \
        > "$case_root/legacy.alignments.sam"
    env PATH="$runtime_path" samtools view "$native_bam" | sort \
        > "$case_root/native.alignments.sam"
    cmp "$case_root/legacy.alignments.sam" "$case_root/native.alignments.sam"
    env PATH="$runtime_path" samtools flagstat --threads 1 "$native_bam" \
        > "$case_root/native.flagstat.txt"
    env PATH="$runtime_path" samtools idxstats "$native_bam" \
        > "$case_root/native.idxstats.txt"
    cmp "$legacy_dir/output/${native_id}.flagstat.txt" "$case_root/native.flagstat.txt"
    cmp "$legacy_dir/output/${native_id}.idxstats.txt" "$case_root/native.idxstats.txt"
    printf 'artifact\tcomparison\tresult\nbam_records\tsemantic\tPASS\nflagstat\tbyte\tPASS\nidxstats\tbyte\tPASS\n' \
        > "$case_root/comparison.tsv"
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver, legacy-job, or compare-job" >&2
    exit 2
fi
if [[ -e "$legacy_dir" || -e "$native_dir" || -e "$nextflow_out" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root"
legacy_job=$(sbatch --wait --parsable \
    --job-name=hf-bowtie-legacy --partition="$queue" \
    --cpus-per-task=1 --mem=2G --time=00:10:00 \
    --output="$case_root/slurm-legacy-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    legacy-job "$case_name" "$compat_bin")
printf '%s\n' "$legacy_job" > "$case_root/legacy_job_id.txt"

mkdir -p "$native_dir" "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" \
    -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" \
    run tests/native_alignment/main.nf \
    -c tests/native_alignment/nextflow.config \
    -ansi-log false -process.executor=slurm -process.queue="$queue" \
    -executor.queueSize=1 -work-dir "$validation_root/work/$case_name" \
    --aligner bowtie2 \
    --reference "$fixture_root/reference.fa" \
    --annotation "$fixture_root/annotation.gtf" \
    --read1 "$fixture_root/reads_R1.fastq" \
    --read2 "$fixture_root/reads_R2.fastq" \
    --target_root "$native_dir" --outdir "$nextflow_out" \
    --bowtie2_index_queue "$queue" --bowtie2_align_queue "$queue"

compare_job=$(sbatch --wait --parsable \
    --job-name=hf-bowtie-compare --partition="$queue" \
    --cpus-per-task=1 --mem=1G --time=00:05:00 \
    --output="$case_root/slurm-compare-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    compare-job "$case_name" "$compat_bin")
printf '%s\n' "$compare_job" > "$case_root/compare_job_id.txt"

native_jobs=$(awk 'NR > 1 {print $3}' "$nextflow_out/execution_trace.tsv" | paste -sd, -)
legacy_seconds=$(sacct -j "$legacy_job" -X -n -o ElapsedRaw | awk 'NF {print $1; exit}')
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw | awk 'NF {sum += $1} END {print sum + 0}')
printf 'implementation\telapsed_ms\tthreads\nlegacy_bowtie2_slurm\t%s\t1\nnextflow_alignment_tasks\t%s\t1\n' \
    "$((legacy_seconds * 1000))" "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real Bowtie2 legacy/native Slurm comparison passed."
echo "[OK] Case root: $case_root"
