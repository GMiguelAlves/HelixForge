#!/usr/bin/env bash

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
nextflow_bin=${NEXTFLOW_BIN:-nextflow}
nextflow_jar=${NEXTFLOW_JAR:-}
image=${STAR_CONTAINER:-community.wave.seqera.io/library/htslib_samtools_star_gawk:ae438e9a604351a4}
case_root="${project_root}/results/test/native-alignment-regression"
fixture_root="${project_root}/tests/fixtures/native_alignment"
input_dir="${case_root}/input"
legacy_dir="${case_root}/legacy"
native_dir="${case_root}/native"
nextflow_out="${case_root}/nextflow"

case "$case_root" in
    "${project_root}"/results/test/*) ;;
    *) echo "Unsafe test path: $case_root" >&2; exit 2 ;;
esac
rm -rf "$case_root"

run_nextflow() {
    if [[ -n "$nextflow_jar" ]]; then
        java -jar "$nextflow_jar" "$@"
    else
        "$nextflow_bin" "$@"
    fi
}

mkdir -p "$input_dir" "$legacy_dir/index" "$legacy_dir/output" "$native_dir" "$nextflow_out"
gzip -n -c "${fixture_root}/reads_R1.fastq" > "${input_dir}/reads_R1.fastq.gz"
gzip -n -c "${fixture_root}/reads_R2.fastq" > "${input_dir}/reads_R2.fastq.gz"

start_legacy=$(date +%s%N)
docker run --rm \
    -v "${case_root}:/data" \
    -v "${fixture_root}:/fixtures:ro" \
    "$image" \
    STAR --runMode genomeGenerate \
        --runThreadN 1 \
        --genomeDir /data/legacy/index \
        --genomeFastaFiles /fixtures/reference.fa \
        --sjdbGTFfile /fixtures/annotation.gtf \
        --genomeSAindexNbases 2 \
        --limitGenomeGenerateRAM 100000000

docker run --rm \
    -v "${case_root}:/data" \
    "$image" \
    STAR \
        --genomeDir /data/legacy/index \
        --readFilesIn /data/input/reads_R1.fastq.gz /data/input/reads_R2.fastq.gz \
        --runThreadN 1 \
        --outFileNamePrefix /data/legacy/output/ \
        --outSAMtype BAM SortedByCoordinate \
        --quantMode GeneCounts \
        --readFilesCommand zcat \
        --outTmpDir /tmp/omicsflow_star_tmp

docker run --rm -v "${case_root}:/data" "$image" \
    samtools index -@ 1 /data/legacy/output/Aligned.sortedByCoord.out.bam
docker run --rm -v "${case_root}:/data" "$image" \
    samtools stats --threads 1 /data/legacy/output/Aligned.sortedByCoord.out.bam \
    > "${legacy_dir}/output/Aligned.sortedByCoord.out.bam.stats"
docker run --rm -v "${case_root}:/data" "$image" \
    samtools flagstat --threads 1 /data/legacy/output/Aligned.sortedByCoord.out.bam \
    > "${legacy_dir}/output/Aligned.sortedByCoord.out.bam.flagstat"
docker run --rm -v "${case_root}:/data" "$image" \
    samtools idxstats /data/legacy/output/Aligned.sortedByCoord.out.bam \
    > "${legacy_dir}/output/Aligned.sortedByCoord.out.bam.idxstats"
end_legacy=$(date +%s%N)

start_native=$(date +%s%N)
run_nextflow run "${project_root}/tests/native_alignment/main.nf" \
    -c "${project_root}/tests/native_alignment/nextflow.config" \
    -profile docker \
    -ansi-log false \
    --reference "${fixture_root}/reference.fa" \
    --annotation "${fixture_root}/annotation.gtf" \
    --read1 "${input_dir}/reads_R1.fastq.gz" \
    --read2 "${input_dir}/reads_R2.fastq.gz" \
    --target_root "$native_dir" \
    --docker_bind_root "$case_root" \
    --extra_args '--outTmpDir /tmp/omicsflow_star_tmp' \
    --outdir "$nextflow_out"
end_native=$(date +%s%N)

legacy_output="${legacy_dir}/output"
native_output="${native_dir}/star_output"
samtools quickcheck -v "${legacy_output}/Aligned.sortedByCoord.out.bam"
samtools quickcheck -v "${native_output}/Aligned.sortedByCoord.out.bam"

comparison="${case_root}/comparison.tsv"
printf 'artifact\tcomparison\tresult\n' > "$comparison"
compare_exact() {
    local name=$1 legacy_file=$2 native_file=$3
    if cmp -s "$legacy_file" "$native_file"; then
        printf '%s\tbyte\tPASS\n' "$name" >> "$comparison"
    else
        printf '%s\tbyte\tFAIL\n' "$name" >> "$comparison"
        return 1
    fi
}

compare_exact ReadsPerGene.out.tab \
    "${legacy_output}/ReadsPerGene.out.tab" "${native_output}/ReadsPerGene.out.tab"
compare_exact flagstat \
    "${legacy_output}/Aligned.sortedByCoord.out.bam.flagstat" \
    "${native_output}/Aligned.sortedByCoord.out.bam.flagstat"
compare_exact BAI_idxstats \
    "${legacy_output}/Aligned.sortedByCoord.out.bam.idxstats" \
    "${native_output}/Aligned.sortedByCoord.out.bam.idxstats"

samtools view "${legacy_output}/Aligned.sortedByCoord.out.bam" | sort \
    > "${case_root}/legacy.alignments.sam"
samtools view "${native_output}/Aligned.sortedByCoord.out.bam" | sort \
    > "${case_root}/native.alignments.sam"
compare_exact bam_records "${case_root}/legacy.alignments.sam" "${case_root}/native.alignments.sam"

samtools view "${legacy_output}/Aligned.sortedByCoord.out.bam" \
    | awk '{ count[$5]++ } END { for (mapq in count) print mapq "\t" count[mapq] }' \
    | sort -n > "${case_root}/legacy.mapq.tsv"
samtools view "${native_output}/Aligned.sortedByCoord.out.bam" \
    | awk '{ count[$5]++ } END { for (mapq in count) print mapq "\t" count[mapq] }' \
    | sort -n > "${case_root}/native.mapq.tsv"
compare_exact MAPQ_distribution "${case_root}/legacy.mapq.tsv" "${case_root}/native.mapq.tsv"

awk -F'|' 'NF == 2 { key=$1; value=$2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", key); gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); if (key !~ /Started job|Started mapping|Finished on|Mapping speed/) print key "\t" value }' \
    "${legacy_output}/Log.final.out" > "${case_root}/legacy.log_final.tsv"
awk -F'|' 'NF == 2 { key=$1; value=$2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", key); gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); if (key !~ /Started job|Started mapping|Finished on|Mapping speed/) print key "\t" value }' \
    "${native_output}/Log.final.out" > "${case_root}/native.log_final.tsv"
compare_exact Log.final.out "${case_root}/legacy.log_final.tsv" "${case_root}/native.log_final.tsv"

for star_log in Log.out Log.progress.out; do
    [[ -s "${legacy_output}/${star_log}" && -s "${native_output}/${star_log}" ]]
    printf '%s\tsemantic-presence\tPASS\n' "$star_log" >> "$comparison"
done

legacy_ms=$(((end_legacy - start_legacy) / 1000000))
native_ms=$(((end_native - start_native) / 1000000))
printf 'implementation\telapsed_ms\nlegacy_command\t%s\nnextflow_native\t%s\n' \
    "$legacy_ms" "$native_ms" > "${case_root}/benchmark.tsv"

echo "[OK] STAR legacy and native outputs are semantically equivalent."
echo "[OK] Comparison: ${comparison}"
echo "[OK] Benchmark: ${case_root}/benchmark.tsv"
