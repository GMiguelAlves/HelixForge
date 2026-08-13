process BAM_INDEX_QC {
    tag "${meta.id}"
    label 'native_module'
    label 'bam_processing'

    cpus 8
    memory 32.GB
    time 12.h
    queue { params.bam_index_qc_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.bam_samtools_apptainer_container : params.bam_samtools_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/bam_final",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,bam_index_qc_reports}'
    publishDir { meta.final_target_dir ?: "${params.outdir}/bam_final/${meta.id}" },
        mode: 'copy', overwrite: true,
        pattern: '*.filtered.bam*'

    input:
    tuple val(meta), path(bam), path(reference), val(qc_params), path(upstream_manifest)

    output:
    tuple val(meta), path("${meta.id}.filtered.bam"), path("${meta.id}.filtered.bam.bai"), emit: artifacts
    tuple val(meta), path("${meta.id}.bam_index_qc_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.bam_final.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.bam_index_qc.done"), emit: status

    script:
    def sort_if_needed = qc_params.sort_if_needed == true
    """
    set -o pipefail
    start_epoch=\$(date +%s)
    output='${meta.id}.filtered.bam'
    bai='${meta.id}.filtered.bam.bai'
    reports='${meta.id}.bam_index_qc_reports'
    mkdir -p "\$reports"
    [[ -s '${bam}' && -s '${reference}' ]] || { echo '[ERROR] BAM and reference must be non-empty' >&2; exit 3; }
    samtools quickcheck -v '${bam}' 2> "\$reports/input.quickcheck.log" || { cat "\$reports/input.quickcheck.log" >&2; exit 3; }

    samtools view -H '${bam}' > "\$reports/header.sam"
    sort_order=\$(awk -F '\t' '\$1=="@HD" {for(i=2;i<=NF;i++) if(\$i ~ /^SO:/) {print substr(\$i,4); exit}}' "\$reports/header.sam")
    if [[ "\$sort_order" == 'coordinate' ]]; then
        printf 'cp %q %q\n' '${bam}' "\$output" > "\$reports/command.txt"
        cp '${bam}' "\$output"
        sorted_by_module=false
    elif [[ '${sort_if_needed}' == 'true' ]]; then
        printf 'samtools sort -@ %s -o %q %q\n' '${task.cpus}' "\$output" '${bam}' > "\$reports/command.txt"
        samtools sort -@ ${task.cpus} -o "\$output" '${bam}' 2> "\$reports/sort.log"
        sorted_by_module=true
    else
        echo "[ERROR] final BAM sort order is '\${sort_order:-missing}'; set sort_if_needed=true to sort explicitly" >&2
        exit 4
    fi

    samtools faidx '${reference}'
    samtools view -H "\$output" | awk -F '\t' '
        \$1 == "@SQ" {
            sn=""; ln=""
            for (i=2; i<=NF; i++) {
                if (\$i ~ /^SN:/) sn=substr(\$i,4)
                if (\$i ~ /^LN:/) ln=substr(\$i,4)
            }
            if (sn != "" && ln != "") print sn "\t" ln
        }
    ' > "\$reports/bam_contigs.tsv"
    cut -f1,2 '${reference}.fai' > "\$reports/reference_contigs.tsv"
    if ! diff -u "\$reports/reference_contigs.tsv" "\$reports/bam_contigs.tsv" > "\$reports/reference_compatibility.diff"; then
        echo '[ERROR] final BAM and reference contigs/lengths are incompatible' >&2
        cat "\$reports/reference_compatibility.diff" >&2
        exit 4
    fi

    samtools index -@ ${task.cpus} "\$output" "\$bai"
    samtools quickcheck -v "\$output" 2> "\$reports/final.quickcheck.log"
    samtools flagstat --threads ${task.cpus} "\$output" > "\$reports/${meta.id}.flagstat.txt"
    samtools idxstats "\$output" > "\$reports/${meta.id}.idxstats.txt"
    samtools stats --threads ${task.cpus} "\$output" > "\$reports/${meta.id}.stats.txt"
    total=\$(samtools view -c "\$output")
    mapped=\$(samtools view -c -F 4 "\$output")
    proper=\$(samtools view -c -f 2 "\$output")
    duplicates=\$(samtools view -c -f 1024 "\$output")
    printf 'metric\tvalue\ntotal_reads\t%s\nmapped_reads\t%s\nproperly_paired\t%s\nduplicate_flagged\t%s\nsort_order\tcoordinate\nsorted_by_module\t%s\n' \
        "\$total" "\$mapped" "\$proper" "\$duplicates" "\$sorted_by_module" > "\$reports/final_metrics.tsv"
    {
        printf 'mapq\talignments\n'
        samtools view "\$output" | awk '{count[\$5]++} END {for (mapq in count) print mapq "\t" count[mapq]}' | sort -n
    } > "\$reports/mapq_distribution.tsv"

    reference_sha=\$(sha256sum '${reference}' | awk '{print \$1}')
    input_sha=\$(sha256sum '${bam}' | awk '{print \$1}')
    output_sha=\$(sha256sum "\$output" | awk '{print \$1}')
    bai_sha=\$(sha256sum "\$bai" | awk '{print \$1}')
    upstream_sha=\$(sha256sum '${upstream_manifest}' | awk '{print \$1}')
    command_base64=\$(base64 -w0 "\$reports/command.txt")
    end_epoch=\$(date +%s)
    printf '"%s":\n    samtools: %s\n' '${task.process}' "\$(samtools --version | sed -n '1s/samtools //p')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","command_base64":"%s","sort_if_needed":${sort_if_needed},"sorted_by_module":%s,"input_sha256":"%s","reference_sha256":"%s","output_sha256":"%s","bai_sha256":"%s","total_reads":%s,"mapped_reads":%s,"properly_paired":%s,"duplicates":%s,"cpus":%s,"memory_bytes":%s,"time":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' "\$command_base64" "\$sorted_by_module" "\$input_sha" "\$reference_sha" "\$output_sha" "\$bai_sha" \
        "\$total" "\$mapped" "\$proper" "\$duplicates" '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"bam_final","id":"%s","status":"complete","record_id":"%s","dataset":"%s","sample_id":"%s","condition":"%s","target":"%s","genome_id":"%s","artifact":"%s","sha256":"%s","index":"%s","index_sha256":"%s","reference_sha256":"%s","duplicate_policy":"%s","selection":{"min_mapq":%s,"include_flags":%s,"exclude_flags":%s},"blacklist_policy":"%s","metrics":{"total_reads":%s,"mapped_reads":%s,"properly_paired":%s,"duplicates":%s},"upstream_manifests":[{"sha256":"%s"}]}\n' \
        '${meta.id}' '${meta.id}' '${meta.dataset}' '${meta.sample_id}' '${meta.condition ?: ''}' '${meta.target ?: ''}' '${meta.genome_id ?: ''}' "\$output" "\$output_sha" "\$bai" "\$bai_sha" "\$reference_sha" \
        '${meta.bam_duplicate_policy ?: 'unknown'}' '${meta.bam_min_mapq ?: 0}' '${meta.bam_include_flags ?: 0}' '${meta.bam_exclude_flags ?: 0}' '${meta.bam_blacklist_policy ?: 'unknown'}' \
        "\$total" "\$mapped" "\$proper" "\$duplicates" "\$upstream_sha" > '${meta.id}.bam_final.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > '${meta.id}.bam_index_qc.done'
    """

    stub:
    """
    touch '${meta.id}.filtered.bam' '${meta.id}.filtered.bam.bai'
    mkdir -p '${meta.id}.bam_index_qc_reports'
    printf '@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:chrStub\tLN:16\n' > '${meta.id}.bam_index_qc_reports/header.sam'
    printf 'chrStub\t16\n' > '${meta.id}.bam_index_qc_reports/bam_contigs.tsv'
    cp '${meta.id}.bam_index_qc_reports/bam_contigs.tsv' '${meta.id}.bam_index_qc_reports/reference_contigs.tsv'
    : > '${meta.id}.bam_index_qc_reports/reference_compatibility.diff'
    : > '${meta.id}.bam_index_qc_reports/input.quickcheck.log'
    : > '${meta.id}.bam_index_qc_reports/final.quickcheck.log'
    printf 'cp [stub]\n' > '${meta.id}.bam_index_qc_reports/command.txt'
    printf 'stub\n' > '${meta.id}.bam_index_qc_reports/${meta.id}.flagstat.txt'
    printf 'stub\n' > '${meta.id}.bam_index_qc_reports/${meta.id}.idxstats.txt'
    printf 'stub\n' > '${meta.id}.bam_index_qc_reports/${meta.id}.stats.txt'
    printf 'metric\tvalue\ntotal_reads\t1\nmapped_reads\t1\nproperly_paired\t1\nduplicate_flagged\t0\nsort_order\tcoordinate\nsorted_by_module\tfalse\n' > '${meta.id}.bam_index_qc_reports/final_metrics.tsv'
    printf 'mapq\talignments\n42\t1\n' > '${meta.id}.bam_index_qc_reports/mapq_distribution.tsv'
    printf '"BAM_INDEX_QC":\n    samtools: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"BAM_INDEX_QC","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    upstream_sha=\$(sha256sum '${upstream_manifest}' | awk '{print \$1}')
    printf '{"schema_version":"1.0","type":"bam_final","id":"%s","status":"stub","record_id":"%s","duplicate_policy":"%s","selection":{"min_mapq":%s,"include_flags":%s,"exclude_flags":%s},"blacklist_policy":"%s","upstream_manifests":[{"sha256":"%s"}]}\n' \
        '${meta.id}' '${meta.id}' '${meta.bam_duplicate_policy ?: 'unknown'}' '${meta.bam_min_mapq ?: 0}' '${meta.bam_include_flags ?: 0}' '${meta.bam_exclude_flags ?: 0}' '${meta.bam_blacklist_policy ?: 'unknown'}' "\$upstream_sha" > '${meta.id}.bam_final.manifest.json'
    printf '{"id":"%s","process":"BAM_INDEX_QC","status":"stub"}\n' '${meta.id}' > '${meta.id}.bam_index_qc.done'
    """
}
