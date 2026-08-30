#!/usr/bin/env bash

set -euo pipefail

benchmark_root=${1:?benchmark root is required}
output_root=${2:?independent output root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}
idr_prefix=${4:?IDR runtime prefix is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Independent scientific processing must run under Slurm." >&2
    exit 2
}
expected_root=/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830
[[ "$(realpath -m "$benchmark_root")" == "$expected_root" ]] || {
    echo "Refusing unexpected benchmark root: $benchmark_root" >&2
    exit 2
}
[[ "$(realpath -m "$output_root")" == "$expected_root/independent" ]] || {
    echo "Refusing unexpected independent output: $output_root" >&2
    exit 2
}
[[ ! -e "$output_root" ]] || {
    echo "Refusing to overwrite independent output: $output_root" >&2
    exit 2
}

export PATH="$runtime_prefix/bin:$idr_prefix/bin:/usr/bin:/bin"
threads=${SLURM_CPUS_PER_TASK:-8}
reference="$benchmark_root/reference/genome.fa"
blacklist="$benchmark_root/reference/blacklist.bed"
index_prefix="$output_root/reference/bowtie2/genome"
samples=(ENCFF000BWK ENCFF000BWM ENCFF000BWR)
mkdir -p "$output_root"/{commands,input,fastqc,reference/bowtie2,bam,peaks,idr,qc,provenance}

record_command() {
    local name=$1
    shift
    printf '%q ' "$@" > "$output_root/commands/${name}.sh"
    printf '\n' >> "$output_root/commands/${name}.sh"
}

for sample in "${samples[@]}"; do
    source_fastq="$benchmark_root/downloads/fastq/${sample}.fastq.gz"
    [[ -s "$source_fastq" ]]
    ln -s "$source_fastq" "$output_root/input/${sample}.fastq.gz"
done

record_command bowtie2-build bowtie2-build --threads "$threads" "$reference" "$index_prefix"
bowtie2-build --threads "$threads" "$reference" "$index_prefix" \
    > "$output_root/reference/bowtie2/build.stdout.log" \
    2> "$output_root/reference/bowtie2/build.stderr.log"

for sample in "${samples[@]}"; do
    fastq="$output_root/input/${sample}.fastq.gz"
    record_command "fastqc_${sample}" fastqc --threads "$threads" --outdir "$output_root/fastqc" "$fastq"
    fastqc --threads "$threads" --outdir "$output_root/fastqc" "$fastq" \
        > "$output_root/fastqc/${sample}.stdout.log" \
        2> "$output_root/fastqc/${sample}.stderr.log"

    record_command "bowtie2_${sample}" bowtie2 --very-sensitive -x "$index_prefix" -U "$fastq" --threads "$threads"
    bowtie2 --very-sensitive -x "$index_prefix" -U "$fastq" --threads "$threads" \
        2> "$output_root/bam/${sample}.bowtie2.log" \
        | samtools view -@ "$threads" -bS - \
        | samtools sort -@ "$threads" -o "$output_root/bam/${sample}.raw.sorted.bam" -

    record_command "select_${sample}" samtools view -@ "$threads" -b -q 30 -F 2308 \
        -o "$output_root/bam/${sample}.selected.bam" "$output_root/bam/${sample}.raw.sorted.bam"
    samtools view -@ "$threads" -b -q 30 -F 2308 \
        -o "$output_root/bam/${sample}.selected.bam" "$output_root/bam/${sample}.raw.sorted.bam"

    record_command "blacklist_${sample}" samtools view -@ "$threads" -L "$blacklist" \
        "$output_root/bam/${sample}.selected.bam"
    samtools view -@ "$threads" -L "$blacklist" "$output_root/bam/${sample}.selected.bam" \
        | cut -f1 | LC_ALL=C sort -u > "$output_root/bam/${sample}.blacklisted_qnames.txt"
    if [[ -s "$output_root/bam/${sample}.blacklisted_qnames.txt" ]]; then
        samtools view -h "$output_root/bam/${sample}.selected.bam" \
            | awk 'NR==FNR {remove[$1]=1; next} /^@/ {print; next} !($1 in remove)' \
                "$output_root/bam/${sample}.blacklisted_qnames.txt" - \
            | samtools view -@ "$threads" -b -o "$output_root/bam/${sample}.final.bam" -
    else
        cp "$output_root/bam/${sample}.selected.bam" "$output_root/bam/${sample}.final.bam"
    fi
    samtools quickcheck -v "$output_root/bam/${sample}.final.bam"
    samtools index -@ "$threads" "$output_root/bam/${sample}.final.bam"
    samtools flagstat -@ "$threads" "$output_root/bam/${sample}.final.bam" > "$output_root/qc/${sample}.flagstat.txt"
    samtools stats -@ "$threads" "$output_root/bam/${sample}.final.bam" > "$output_root/qc/${sample}.stats.txt"
    samtools idxstats "$output_root/bam/${sample}.final.bam" > "$output_root/qc/${sample}.idxstats.txt"
done

for sample in ENCFF000BWM ENCFF000BWR; do
    peak_dir="$output_root/peaks/$sample"
    mkdir -p "$peak_dir"
    record_command "macs3_${sample}" macs3 callpeak \
        -t "$output_root/bam/${sample}.final.bam" \
        -c "$output_root/bam/ENCFF000BWK.final.bam" \
        -f BAM -g 2913022398 -n "$sample" --outdir "$peak_dir" --keep-dup all -B -q 0.01
    macs3 callpeak \
        -t "$output_root/bam/${sample}.final.bam" \
        -c "$output_root/bam/ENCFF000BWK.final.bam" \
        -f BAM -g 2913022398 -n "$sample" --outdir "$peak_dir" \
        --keep-dup all -B -q 0.01 \
        > "$peak_dir/macs3.stdout.log" 2> "$peak_dir/macs3.stderr.log"
    [[ -s "$peak_dir/${sample}_peaks.narrowPeak" ]]
done

record_command idr idr \
    --samples "$output_root/peaks/ENCFF000BWM/ENCFF000BWM_peaks.narrowPeak" \
              "$output_root/peaks/ENCFF000BWR/ENCFF000BWR_peaks.narrowPeak" \
    --input-file-type narrowPeak --output-file-type narrowPeak --rank signal.value \
    --idr-threshold 0.05 --soft-idr-threshold 0.05 --random-seed 0 --plot \
    --output-file "$output_root/idr/idr_output.narrowPeak" \
    --log-output-file "$output_root/idr/idr.log"
idr \
    --samples "$output_root/peaks/ENCFF000BWM/ENCFF000BWM_peaks.narrowPeak" \
              "$output_root/peaks/ENCFF000BWR/ENCFF000BWR_peaks.narrowPeak" \
    --input-file-type narrowPeak --output-file-type narrowPeak --rank signal.value \
    --idr-threshold 0.05 --soft-idr-threshold 0.05 --random-seed 0 --plot \
    --output-file "$output_root/idr/idr_output.narrowPeak" \
    --log-output-file "$output_root/idr/idr.log" \
    > "$output_root/idr/idr.stdout.log" 2> "$output_root/idr/idr.stderr.log"
[[ -s "$output_root/idr/idr_output.narrowPeak" ]]

{
    printf 'tool\tversion\n'
    printf 'bowtie2\t%s\n' "$(bowtie2 --version | head -n1)"
    printf 'samtools\t%s\n' "$(samtools --version | head -n1)"
    printf 'macs3\t%s\n' "$(macs3 --version)"
    printf 'idr\t%s\n' "$(idr --version 2>&1 | head -n1)"
    printf 'fastqc\t%s\n' "$(fastqc --version 2>&1 | head -n1)"
} > "$output_root/provenance/versions.tsv"

find "$output_root/commands" "$output_root/peaks" "$output_root/idr" "$output_root/qc" \
    -type f -print0 | sort -z | xargs -0 sha256sum > "$output_root/provenance/checksums.sha256"
sha256sum "$output_root"/bam/*.final.bam "$output_root"/bam/*.final.bam.bai \
    > "$output_root/provenance/final_bam_checksums.sha256"
printf '{"schema_version":"1.0","type":"independent_real_narrow","slurm_job_id":"%s","status":"complete"}\n' \
    "$SLURM_JOB_ID" > "$output_root/provenance/manifest.json"
