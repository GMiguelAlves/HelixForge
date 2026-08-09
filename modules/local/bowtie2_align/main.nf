process BOWTIE2_ALIGN {
    tag "${meta.id}"
    label 'native_module'
    label 'alignment_high'

    cpus 8
    memory 32.GB
    time 12.h
    queue { params.bowtie2_align_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.bowtie2_apptainer_container : params.bowtie2_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_alignment/bowtie2_align",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,alignment_logs,alignment_statistics}'
    publishDir { meta.target_dir ?: "${params.outdir}/alignment/${meta.id}" },
        mode: 'copy', overwrite: true,
        pattern: '*.sorted.bam*'

    input:
    tuple val(meta), path(reads), path(reference), path(annotation), path(alignment_index), val(alignment_params)

    output:
    tuple val(meta), path("${meta.id}.sorted.bam"), path("${meta.id}.sorted.bam.bai"), emit: artifacts
    tuple val(meta), path("${meta.id}.alignment_logs"), path("${meta.id}.alignment_statistics"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.bowtie2_align.done"), emit: status

    script:
    def read_list = reads instanceof List ? reads : [reads]
    def read_r1 = read_list[0]
    def read_r2 = meta.single_end ? null : read_list[1]
    def read_args = meta.single_end ? "-U '${read_r1}'" : "-1 '${read_r1}' -2 '${read_r2}'"
    def extra_args = alignment_params.extra_args ?: ''
    def basename = alignment_params.index_basename ?: 'genome'
    """
    set -o pipefail
    start_epoch=\$(date +%s)
    bam='${meta.id}.sorted.bam'
    bai='${meta.id}.sorted.bam.bai'
    logs_dir='${meta.id}.alignment_logs'
    stats_dir='${meta.id}.alignment_statistics'
    mkdir -p "\$logs_dir" "\$stats_dir"

    if [[ '${extra_args}' =~ (^|[[:space:]])(-x|-1|-2|-U|-S|-p|--threads)([[:space:]]|=|\$) ]]; then
        echo '[ERROR] Bowtie2 options override an argument controlled by the Alignment API.' >&2
        exit 2
    fi
    index_prefix='${alignment_index}/${basename}'
    ls "\${index_prefix}".*.bt2* >/dev/null 2>&1 || { echo "[ERROR] Bowtie2 index missing: \$index_prefix"; exit 3; }

    printf "bowtie2 -x %q -p %q %s %s | samtools view -@ %q -bS - | samtools sort -@ %q -o %q -\n" \
        "\$index_prefix" '${task.cpus}' "${read_args}" '${extra_args}' '${task.cpus}' '${task.cpus}' "\$bam" \
        > "\$logs_dir/command.txt"
    bowtie2 -x "\$index_prefix" -p ${task.cpus} ${read_args} ${extra_args} \
        2> "\$logs_dir/bowtie2.log" \
        | samtools view -@ ${task.cpus} -bS - \
        | samtools sort -@ ${task.cpus} -o "\$bam" -

    [[ -s "\$bam" ]]
    samtools index -@ ${task.cpus} "\$bam" "\$bai"
    samtools quickcheck "\$bam"
    samtools flagstat --threads ${task.cpus} "\$bam" > "\$stats_dir/${meta.id}.flagstat.txt"
    samtools idxstats "\$bam" > "\$stats_dir/${meta.id}.idxstats.txt"
    samtools stats --threads ${task.cpus} "\$bam" > "\$stats_dir/${meta.id}.stats.txt"
    {
        printf 'mapq\talignments\n'
        samtools view "\$bam" | awk '{count[\$5]++} END {for (mapq in count) print mapq "\t" count[mapq]}' | sort -n
    } > "\$stats_dir/mapq_distribution.tsv"

    reference_sha=\$(sha256sum '${reference}' | awk '{print \$1}')
    index_sha=\$(find '${alignment_index}' -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print \$1}')
    reads_sha=\$(sha256sum '${read_r1}' ${meta.single_end ? '' : "'${read_r2}'"} | awk '{print \$1}' | paste -sd, -)
    bam_sha=\$(sha256sum "\$bam" | awk '{print \$1}')
    bai_sha=\$(sha256sum "\$bai" | awk '{print \$1}')
    command_base64=\$(base64 -w0 "\$logs_dir/command.txt")
    end_epoch=\$(date +%s)

    printf '"%s":\n    bowtie2: %s\n    samtools: %s\n' '${task.process}' \
        "\$(bowtie2 --version | sed -n '1s/.*version //p')" \
        "\$(samtools --version | sed -n '1s/samtools //p')" > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","command_base64":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","reference_sha256":"%s","index_sha256":"%s","reads_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' "\$command_base64" '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        "\$reference_sha" "\$index_sha" "\$reads_sha" "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${meta.id}.execution.json'
    printf '{"schema_version":"1.1","type":"alignment","id":"%s","aligner":"bowtie2","dataset":"%s","sample_id":"%s","record_id":"%s","artifacts":{"bam":{"path":"%s","sha256":"%s"},"bai":{"path":"%s","sha256":"%s"}},"reference_sha256":"%s","index_sha256":"%s"}\n' \
        '${meta.id}' '${meta.dataset}' '${meta.sample_id}' '${meta.id}' "\$bam" "\$bam_sha" "\$bai" "\$bai_sha" "\$reference_sha" "\$index_sha" \
        > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' \
        > '${meta.id}.bowtie2_align.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.alignment_logs' '${meta.id}.alignment_statistics'
    touch '${meta.id}.sorted.bam' '${meta.id}.sorted.bam.bai'
    printf 'bowtie2 [stub]\n' > '${meta.id}.alignment_logs/command.txt'
    printf '[STUB] Bowtie2 alignment\n' > '${meta.id}.alignment_logs/bowtie2.log'
    printf 'stub\n' > '${meta.id}.alignment_statistics/${meta.id}.flagstat.txt'
    printf 'stub\n' > '${meta.id}.alignment_statistics/${meta.id}.idxstats.txt'
    printf 'stub\n' > '${meta.id}.alignment_statistics/${meta.id}.stats.txt'
    printf 'mapq\talignments\n42\t1\n' > '${meta.id}.alignment_statistics/mapq_distribution.tsv'
    printf '"BOWTIE2_ALIGN":\n    bowtie2: stub\n    samtools: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"BOWTIE2_ALIGN","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"1.1","type":"alignment","id":"%s","aligner":"bowtie2"}\n' '${meta.id}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"BOWTIE2_ALIGN","status":"stub"}\n' '${meta.id}' > '${meta.id}.bowtie2_align.done'
    """
}
