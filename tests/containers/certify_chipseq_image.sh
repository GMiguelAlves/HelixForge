#!/usr/bin/env bash

set -euo pipefail

role=${1:?container role is required}
image=${2:?container image is required}
case_root=${3:-$(mktemp -d "${TMPDIR:-/tmp}/helixforge-${role}.XXXXXX")}

mkdir -p "$case_root"

write_sam() {
    cat > "$case_root/reads.sam" <<'EOF'
@HD	VN:1.6	SO:coordinate
@SQ	SN:chr1	LN:80
read1	0	chr1	1	60	20M	*	0	0	ACGTTGCATGTCAGTACGAT	IIIIIIIIIIIIIIIIIIII
EOF
}

case "$role" in
    alignment)
        cat > "$case_root/reference.fa" <<'EOF'
>chr1
ACGTTGCATGTCAGTACGATCGATGCTAGCTAGGCTAACGTTAGCATCGATGCTAGCATGCTAACGATCGTAGCTA
EOF
        cat > "$case_root/reads.fastq" <<'EOF'
@read1
ACGTTGCATGTCAGTACGATCGATGCTAGC
+
IIIIIIIIIIIIIIIIIIIIIIIIIIIIII
EOF
        docker run --rm -v "$case_root:/case" "$image" bash -euo pipefail -c '
            bowtie2-build --threads 1 /case/reference.fa /case/genome > /case/bowtie2-build.log 2>&1
            bowtie2 -x /case/genome -U /case/reads.fastq -p 1 2> /case/bowtie2.log \
                | samtools sort -@ 1 -o /case/aligned.bam -
            samtools index /case/aligned.bam
            samtools quickcheck -v /case/aligned.bam
            test "$(samtools view -c -F 4 /case/aligned.bam)" -eq 1
            bowtie2 --version | sed -n "1p" > /case/versions.txt
            samtools --version | sed -n "1p" >> /case/versions.txt
        '
        ;;
    intervals)
        write_sam
        printf 'chr1\t0\t30\n' > "$case_root/peaks.bed"
        docker run --rm -v "$case_root:/case" "$image" bash -euo pipefail -c '
            samtools view -b /case/reads.sam > /case/reads.bam
            bedtools bamtobed -i /case/reads.bam > /case/reads.bed
            bedtools intersect -u -a /case/reads.bed -b /case/peaks.bed > /case/overlap.bed
            test "$(wc -l < /case/overlap.bed)" -eq 1
            python --version 2> /case/versions.txt
            samtools --version | sed -n "1p" >> /case/versions.txt
            bedtools --version >> /case/versions.txt
        '
        ;;
    counts)
        write_sam
        printf 'GeneID\tChr\tStart\tEnd\tStrand\npeak_1\tchr1\t1\t30\t.\n' > "$case_root/features.saf"
        docker run --rm -v "$case_root:/case" "$image" bash -euo pipefail -c '
            featureCounts -T 1 -F SAF -a /case/features.saf -o /case/counts.tsv /case/reads.sam \
                > /case/featurecounts.stdout.log 2> /case/featurecounts.stderr.log
            test -s /case/counts.tsv
            test -s /case/counts.tsv.summary
            awk "BEGIN{FS=OFS=\"\\t\"} !/^#/ && \$1==\"peak_1\" {found=(\$NF==1)} END{exit !found}" /case/counts.tsv
            python --version 2> /case/versions.txt
            featureCounts -v >> /case/versions.txt 2>&1
        '
        ;;
    tracks)
        write_sam
        docker run --rm -v "$case_root:/case" "$image" bash -euo pipefail -c '
            samtools view -b /case/reads.sam | samtools sort -o /case/reads.bam -
            samtools index /case/reads.bam
            bamCoverage -b /case/reads.bam -o /case/reads.bw -p 1 --binSize 10 --normalizeUsing None \
                > /case/bamCoverage.stdout.log 2> /case/bamCoverage.stderr.log
            test -s /case/reads.bw
            python -c "import pyBigWig; bw=pyBigWig.open(\"/case/reads.bw\"); assert bw.chroms()[\"chr1\"] == 80; bw.close()"
            python --version 2> /case/versions.txt
            bamCoverage --version >> /case/versions.txt
            samtools --version | sed -n "1p" >> /case/versions.txt
            python -c "import pyBigWig; print(\"pyBigWig \" + pyBigWig.__version__)" >> /case/versions.txt
        '
        ;;
    *)
        echo "unknown role: $role" >&2
        exit 2
        ;;
esac

docker image inspect \
    --format='{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}{{.Id}}{{end}}' \
    "$image" > "$case_root/image-digest.txt"
printf 'role\tresult\n%s\tPASS\n' "$role" > "$case_root/certification.tsv"
printf '[OK] %s image certification: %s\n' "$role" "$case_root"
