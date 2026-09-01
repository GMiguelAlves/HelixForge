#!/usr/bin/env bash

set -euo pipefail

dataset_root=${1:?dataset root is required}
output_root=${2:?output root is required}
runtime_prefix=${3:?frozen ChIP runtime prefix is required}
consensus_script=${4:?independent broad consensus script is required}

[[ -n "${SLURM_JOB_ID:-}" ]] || {
    echo "Independent scientific processing must run under Slurm." >&2
    exit 2
}
[[ ! -e "$output_root" ]] || {
    echo "Refusing to overwrite independent output: $output_root" >&2
    exit 2
}
[[ -f "$consensus_script" ]]

export PATH="$runtime_prefix/bin:/usr/bin:/bin"
threads=${SLURM_CPUS_PER_TASK:-8}
reference="$dataset_root/reference/synthetic_chip_v1.fa"
index_prefix="$output_root/reference/bowtie2/genome"
mkdir -p "$output_root"/{commands,fastqc,reference/bowtie2,bam,peaks,consensus,qc,provenance}

record_command() {
    local name=$1
    shift
    printf '%q ' "$@" > "$output_root/commands/${name}.sh"
    printf '\n' >> "$output_root/commands/${name}.sh"
}

record_command bowtie2-build bowtie2-build --threads "$threads" "$reference" "$index_prefix"
bowtie2-build --threads "$threads" "$reference" "$index_prefix" > "$output_root/reference/bowtie2/build.stdout.log" 2> "$output_root/reference/bowtie2/build.stderr.log"

for sample in chip_rep1 chip_rep2 input; do
    r1="$dataset_root/fastq/${sample}_1.fastq"
    r2="$dataset_root/fastq/${sample}_2.fastq"
    record_command "fastqc_${sample}" fastqc --threads "$threads" --outdir "$output_root/fastqc" "$r1" "$r2"
    fastqc --threads "$threads" --outdir "$output_root/fastqc" "$r1" "$r2" > "$output_root/fastqc/${sample}.stdout.log" 2> "$output_root/fastqc/${sample}.stderr.log"

    record_command "bowtie2_${sample}" bowtie2 --very-sensitive -x "$index_prefix" -1 "$r1" -2 "$r2" --threads "$threads"
    bowtie2 --very-sensitive -x "$index_prefix" -1 "$r1" -2 "$r2" --threads "$threads" 2> "$output_root/bam/${sample}.bowtie2.log" \
        | samtools view -@ "$threads" -bS - \
        | samtools sort -@ "$threads" -o "$output_root/bam/${sample}.raw.sorted.bam" -
    record_command "filter_${sample}" samtools view -@ "$threads" -b -q 30 -F 2308 -o "$output_root/bam/${sample}.final.bam" "$output_root/bam/${sample}.raw.sorted.bam"
    samtools view -@ "$threads" -b -q 30 -F 2308 -o "$output_root/bam/${sample}.final.bam" "$output_root/bam/${sample}.raw.sorted.bam"
    samtools index -@ "$threads" "$output_root/bam/${sample}.final.bam"
    samtools quickcheck -v "$output_root/bam/${sample}.final.bam"
    samtools flagstat -@ "$threads" "$output_root/bam/${sample}.final.bam" > "$output_root/qc/${sample}.flagstat.txt"
    samtools stats -@ "$threads" "$output_root/bam/${sample}.final.bam" > "$output_root/qc/${sample}.stats.txt"
    samtools idxstats "$output_root/bam/${sample}.final.bam" > "$output_root/qc/${sample}.idxstats.txt"
done

for sample in chip_rep1 chip_rep2; do
    peak_dir="$output_root/peaks/$sample"
    mkdir -p "$peak_dir"
    record_command "macs3_${sample}" macs3 callpeak -t "$output_root/bam/${sample}.final.bam" -c "$output_root/bam/input.final.bam" -f BAMPE -g 54000000 -n "$sample" --outdir "$peak_dir" --keep-dup all -B -q 0.01 --broad
    macs3 callpeak \
        -t "$output_root/bam/${sample}.final.bam" \
        -c "$output_root/bam/input.final.bam" \
        -f BAMPE -g 54000000 -n "$sample" --outdir "$peak_dir" \
        --keep-dup all -B -q 0.01 --broad \
        > "$peak_dir/macs3.stdout.log" 2> "$peak_dir/macs3.stderr.log"
    [[ -s "$peak_dir/${sample}_peaks.broadPeak" ]]
done

record_command consensus python3 "$consensus_script" \
    --peak "$output_root/peaks/chip_rep1/chip_rep1_peaks.broadPeak" \
    --peak "$output_root/peaks/chip_rep2/chip_rep2_peaks.broadPeak" \
    --output "$output_root/consensus/consolidated_peaks.bed"
python3 "$consensus_script" \
    --peak "$output_root/peaks/chip_rep1/chip_rep1_peaks.broadPeak" \
    --peak "$output_root/peaks/chip_rep2/chip_rep2_peaks.broadPeak" \
    --output "$output_root/consensus/consolidated_peaks.bed" \
    --statistics "$output_root/consensus/statistics.json"
[[ -s "$output_root/consensus/consolidated_peaks.bed" ]]

{
    printf 'tool\tversion\n'
    printf 'bowtie2\t%s\n' "$(bowtie2 --version | head -n1)"
    printf 'samtools\t%s\n' "$(samtools --version | head -n1)"
    printf 'macs3\t%s\n' "$(macs3 --version)"
    printf 'bedtools\t%s\n' "$(bedtools --version | head -n1)"
    printf 'fastqc\t%s\n' "$(fastqc --version 2>&1 | head -n1)"
} > "$output_root/provenance/versions.tsv"
find "$output_root/commands" "$output_root/peaks" "$output_root/consensus" "$output_root/qc" -type f -print0 \
    | sort -z | xargs -0 sha256sum > "$output_root/provenance/checksums.sha256"
printf '{"schema_version":"1.0","type":"independent_synthetic_broad","slurm_job_id":"%s","status":"complete"}\n' \
    "$SLURM_JOB_ID" > "$output_root/provenance/manifest.json"
