#!/usr/bin/env bash

set -euo pipefail

validation_root=${1:?validation root is required}
conda_bin=${2:?conda executable is required}
rna_env=${3:-rna-tools}
chip_env=${4:-chipseq}
queue=${5:-general}
mode=${6:-driver}
case_name=${7:-star-real}
star_command_dir=${8:-}
repo_root="${validation_root}/repo"
case_root="${validation_root}/results/${case_name}"
fixture_root="${repo_root}/tests/fixtures/native_alignment"
input_dir="${case_root}/input"
legacy_dir="${case_root}/legacy"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"
conda_root=$(cd "$(dirname "$conda_bin")/.." && pwd)
runtime_path="${conda_root}/envs/${rna_env}/bin:${conda_root}/envs/${chip_env}/bin:/usr/bin:/bin"

case "$validation_root" in
    /*/helixforge-validation-*) ;;
    *) echo "Refusing unexpected validation root: $validation_root" >&2; exit 2 ;;
esac

test -d "$repo_root/.git"
test -x "$conda_bin"
test -x "${conda_root}/envs/${rna_env}/bin/java"
test -x "${conda_root}/envs/${rna_env}/bin/STAR"
test -x "${conda_root}/envs/${chip_env}/bin/samtools"
test -s "$validation_root/nextflow.jar"
if [[ -n "$star_command_dir" ]]; then
    case "$star_command_dir" in
        "$validation_root"/*) ;;
        *) echo "Refusing unexpected STAR command path: $star_command_dir" >&2; exit 2 ;;
    esac
    test -x "$star_command_dir/STAR"
    runtime_path="$star_command_dir:$runtime_path"
fi

if [[ "$mode" == "legacy-job" ]]; then
    test -n "${SLURM_JOB_ID:-}"
    mkdir -p "$input_dir" "$legacy_dir/index" "$legacy_dir/output"
    cd "$case_root"
    gzip -n -c "$fixture_root/reads_R1.fastq" \
        > "$input_dir/reads_R1.fastq.gz"
    gzip -n -c "$fixture_root/reads_R2.fastq" \
        > "$input_dir/reads_R2.fastq.gz"

    env PATH="$runtime_path" STAR --runMode genomeGenerate \
        --runThreadN 1 \
        --genomeDir "$legacy_dir/index" \
        --genomeFastaFiles "$fixture_root/reference.fa" \
        --sjdbGTFfile "$fixture_root/annotation.gtf" \
        --genomeSAindexNbases 2 \
        --limitGenomeGenerateRAM 100000000

    env PATH="$runtime_path" STAR \
        --genomeDir "$legacy_dir/index" \
        --readFilesIn "$input_dir/reads_R1.fastq.gz" "$input_dir/reads_R2.fastq.gz" \
        --runThreadN 1 \
        --outFileNamePrefix "$legacy_dir/output/" \
        --outSAMtype BAM SortedByCoordinate \
        --quantMode GeneCounts \
        --readFilesCommand zcat \
        --outTmpDir /tmp/helixforge_star_tmp

    env PATH="$runtime_path" samtools index -@ 1 \
        "$legacy_dir/output/Aligned.sortedByCoord.out.bam"
    env PATH="$runtime_path" samtools stats --threads 1 \
        "$legacy_dir/output/Aligned.sortedByCoord.out.bam" \
        > "$legacy_dir/output/Aligned.sortedByCoord.out.bam.stats"
    env PATH="$runtime_path" samtools flagstat --threads 1 \
        "$legacy_dir/output/Aligned.sortedByCoord.out.bam" \
        > "$legacy_dir/output/Aligned.sortedByCoord.out.bam.flagstat"
    env PATH="$runtime_path" samtools idxstats \
        "$legacy_dir/output/Aligned.sortedByCoord.out.bam" \
        > "$legacy_dir/output/Aligned.sortedByCoord.out.bam.idxstats"
    exit 0
fi

if [[ "$mode" != "driver" ]]; then
    echo "mode must be driver or legacy-job" >&2
    exit 2
fi
if [[ -e "$legacy_dir" || -e "$native_dir" || -e "$nextflow_out" ]]; then
    echo "Refusing to overwrite an existing validation case: $case_root" >&2
    exit 2
fi

mkdir -p "$case_root"
legacy_job=$(sbatch --wait --parsable \
    --job-name=hf-star-legacy \
    --partition="$queue" \
    --cpus-per-task=1 \
    --mem=2G \
    --time=00:10:00 \
    --output="$case_root/slurm-legacy-%j.out" \
    "$0" "$validation_root" "$conda_bin" "$rna_env" "$chip_env" "$queue" \
    legacy-job "$case_name" "$star_command_dir")
printf '%s\n' "$legacy_job" > "$case_root/legacy_job_id.txt"

mkdir -p "$native_dir" "$nextflow_out"
cd "$repo_root"
env PATH="$runtime_path" \
    NXF_HOME="$validation_root/.nextflow-home" \
    "${conda_root}/envs/${rna_env}/bin/java" \
    -jar "$validation_root/nextflow.jar" \
    -log "$case_root/nextflow.log" \
    run tests/native_alignment/main.nf \
    -c tests/native_alignment/nextflow.config \
    -ansi-log false \
    -process.executor=slurm \
    -process.queue="$queue" \
    -work-dir "$validation_root/work/$case_name" \
    --reference "$fixture_root/reference.fa" \
    --annotation "$fixture_root/annotation.gtf" \
    --read1 "$input_dir/reads_R1.fastq.gz" \
    --read2 "$input_dir/reads_R2.fastq.gz" \
    --target_root "$native_dir" \
    --extra_args '--outTmpDir /tmp/helixforge_star_tmp' \
    --outdir "$nextflow_out" \
    --star_index_queue "$queue" \
    --star_align_queue "$queue"

legacy_output="$legacy_dir/output"
native_output="$native_dir/star_output"
env PATH="$runtime_path" samtools quickcheck -v \
    "$legacy_output/Aligned.sortedByCoord.out.bam" \
    "$native_output/Aligned.sortedByCoord.out.bam"

comparison="$case_root/comparison.tsv"
printf 'artifact\tcomparison\tresult\n' > "$comparison"
compare_exact() {
    local name=$1 legacy_file=$2 native_file=$3
    cmp -s "$legacy_file" "$native_file"
    printf '%s\tbyte\tPASS\n' "$name" >> "$comparison"
}

compare_exact ReadsPerGene.out.tab \
    "$legacy_output/ReadsPerGene.out.tab" "$native_output/ReadsPerGene.out.tab"
compare_exact flagstat \
    "$legacy_output/Aligned.sortedByCoord.out.bam.flagstat" \
    "$native_output/Aligned.sortedByCoord.out.bam.flagstat"
compare_exact BAI_idxstats \
    "$legacy_output/Aligned.sortedByCoord.out.bam.idxstats" \
    "$native_output/Aligned.sortedByCoord.out.bam.idxstats"

env PATH="$runtime_path" samtools view "$legacy_output/Aligned.sortedByCoord.out.bam" \
    | sort > "$case_root/legacy.alignments.sam"
env PATH="$runtime_path" samtools view "$native_output/Aligned.sortedByCoord.out.bam" \
    | sort > "$case_root/native.alignments.sam"
compare_exact bam_records "$case_root/legacy.alignments.sam" \
    "$case_root/native.alignments.sam"

for output in legacy native; do
    source_dir="$legacy_output"
    [[ "$output" == native ]] && source_dir="$native_output"
    awk -F'|' 'NF == 2 { key=$1; value=$2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", key); gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); if (key !~ /Started job|Started mapping|Finished on|Mapping speed/) print key "\t" value }' \
        "$source_dir/Log.final.out" > "$case_root/$output.log_final.tsv"
done
compare_exact Log.final.out "$case_root/legacy.log_final.tsv" \
    "$case_root/native.log_final.tsv"

native_jobs=$(awk 'NR > 1 { print $3 }' "$nextflow_out/execution_trace.tsv" \
    | paste -sd, -)
legacy_seconds=$(sacct -j "$legacy_job" -X -n -o ElapsedRaw \
    | awk 'NF { print $1; exit }')
native_seconds=$(sacct -j "$native_jobs" -X -n -o ElapsedRaw \
    | awk 'NF { total += $1 } END { print total + 0 }')
printf 'implementation\telapsed_ms\ttest_threads\nlegacy_slurm\t%s\t1\nnextflow_native_slurm_tasks\t%s\t1\n' \
    "$((legacy_seconds * 1000))" "$((native_seconds * 1000))" \
    > "$case_root/benchmark.tsv"

echo "[OK] Real STAR legacy/native Slurm comparison passed."
echo "[OK] Case root: $case_root"
