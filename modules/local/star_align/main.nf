process STAR_ALIGN {
    tag "${meta.id}"
    label 'native_module'
    label 'alignment_high'

    cpus 8
    memory 64.GB
    time 24.h
    queue { params.star_align_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.star_apptainer_container : params.star_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_alignment/star_align",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,alignment_logs,alignment_statistics}'

    input:
    tuple val(meta), path(reads), path(reference), path(annotation), path(alignment_index), val(alignment_params)

    output:
    tuple val(meta), path('Aligned.sortedByCoord.out.bam'), path('Aligned.sortedByCoord.out.bam.bai'), emit: artifacts
    tuple val(meta), path("${meta.id}.alignment_logs"), path("${meta.id}.alignment_statistics"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.star_align.done"), emit: status

    script:
    def read_list = reads instanceof List ? reads : [reads]
    def read_r1 = read_list[0]
    def read_r2 = meta.single_end ? null : read_list[1]
    def read_args = meta.single_end ? "'${read_r1}'" : "'${read_r1}' '${read_r2}'"
    def read_files_command = alignment_params.read_files_command ?: ''
    def extra_args = alignment_params.extra_args ?: ''
    def target_dir = meta.target_dir ?: ''
    """
    start_epoch=\$(date +%s)
    bam='Aligned.sortedByCoord.out.bam'
    bai='Aligned.sortedByCoord.out.bam.bai'
    logs_dir='${meta.id}.alignment_logs'
    stats_dir='${meta.id}.alignment_statistics'
    mkdir -p "\$logs_dir" "\$stats_dir"

    if [[ '${extra_args}' =~ --(genomeDir|readFilesIn|runThreadN|outFileNamePrefix|outSAMtype|quantMode)([[:space:]]|$) ]]; then
        echo '[ERRO] STAR_EXTRA_ARGS tenta substituir um argumento controlado pela Alignment API.' >&2
        exit 2
    fi

    CMD=(
        STAR
        --genomeDir '${alignment_index}'
        --readFilesIn ${read_args}
        --runThreadN ${task.cpus}
        --outFileNamePrefix ./
        --outSAMtype BAM SortedByCoordinate
        --quantMode GeneCounts
    )
    if [[ -n '${read_files_command}' ]]; then
        CMD+=(--readFilesCommand '${read_files_command}')
    fi
    if [[ -n '${extra_args}' ]]; then
        EXTRA_ARGS=(${extra_args})
        CMD+=("\${EXTRA_ARGS[@]}")
    fi
    printf '%q ' "\${CMD[@]}" > "\$logs_dir/command.txt"
    printf '\n' >> "\$logs_dir/command.txt"

    echo '[INFO] STAR alignment: ${meta.id}' | tee "\$logs_dir/star_align.log"
    printf '+ %q ' "\${CMD[@]}" | tee -a "\$logs_dir/star_align.log"
    printf '\n' | tee -a "\$logs_dir/star_align.log"
    "\${CMD[@]}" 2>&1 | tee -a "\$logs_dir/star_align.log"

    [[ -s "\$bam" && -s ReadsPerGene.out.tab && -s Log.final.out ]]

    if [[ ! -s "\$bai" ]]; then
        samtools index -@ ${task.cpus} "\$bam"
    fi
    if [[ ! -s "\$bam.stats" ]]; then
        samtools stats --threads ${task.cpus} "\$bam" > "\$bam.stats"
    fi
    if [[ ! -s "\$bam.flagstat" ]]; then
        samtools flagstat --threads ${task.cpus} "\$bam" > "\$bam.flagstat"
    fi
    if [[ ! -s "\$bam.idxstats" ]]; then
        samtools idxstats "\$bam" > "\$bam.idxstats"
    fi

    awk -F'|' 'NF == 2 { key=\$1; value=\$2; sub(/^[[:space:]]+/, "", key); sub(/[[:space:]]+\$/, "", key); sub(/^[[:space:]]+/, "", value); sub(/[[:space:]]+\$/, "", value); print key "\t" value }' \
        Log.final.out > "\$stats_dir/mapping_summary.tsv"
    {
        printf 'mapq\talignments\n'
        samtools view "\$bam" | awk '{ count[\$5]++ } END { for (mapq in count) print mapq "\t" count[mapq] }' | sort -n
    } > "\$stats_dir/mapq_distribution.tsv"

    cp "\$bam.stats" "\$bam.flagstat" "\$bam.idxstats" "\$stats_dir/"
    cp ReadsPerGene.out.tab "\$stats_dir/"
    [[ ! -s SJ.out.tab ]] || cp SJ.out.tab "\$stats_dir/"
    for log_file in Log.out Log.progress.out Log.final.out; do
        [[ ! -s "\$log_file" ]] || cp "\$log_file" "\$logs_dir/"
    done

    if [[ -n '${target_dir}' ]]; then
        mkdir -p '${target_dir}'
        for artifact in \
            "\$bam" "\$bai" ReadsPerGene.out.tab SJ.out.tab \
            Log.out Log.progress.out Log.final.out \
            "\$bam.stats" "\$bam.flagstat" "\$bam.idxstats"; do
            if [[ -e "\$artifact" ]]; then
                cp "\$artifact" '${target_dir}/'"\${artifact}.nextflow.tmp"
                mv '${target_dir}/'"\${artifact}.nextflow.tmp" '${target_dir}/'"\${artifact}"
            fi
        done
    fi

    reference_sha=\$(sha256sum '${reference}' | awk '{ print \$1 }')
    annotation_sha=\$(sha256sum '${annotation}' | awk '{ print \$1 }')
    index_sha=\$(find '${alignment_index}' -type f -print0 \
        | sort -z | xargs -0 sha256sum | sha256sum | awk '{ print \$1 }')
    reads_sha=\$(sha256sum ${read_args} | awk '{ print \$1 }' | paste -sd, -)
    bam_sha=\$(sha256sum "\$bam" | awk '{ print \$1 }')
    bai_sha=\$(sha256sum "\$bai" | awk '{ print \$1 }')
    gene_counts_sha=\$(sha256sum ReadsPerGene.out.tab | awk '{ print \$1 }')
    end_epoch=\$(date +%s)
    command_base64=\$(base64 -w0 "\$logs_dir/command.txt")

    printf '"%s":\n    star: %s\n    samtools: %s\n    htslib: %s\n' \
        '${task.process}' \
        "\$(STAR --version | sed 's/^STAR_//')" \
        "\$(samtools --version | sed -n '1s/samtools //p')" \
        "\$(htsfile --version 2>&1 | awk 'NR==1 { print \$NF }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","command_base64":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","index":"%s","index_sha256":"%s","reference":"%s","reference_sha256":"%s","annotation_sha256":"%s","reads_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' "\$command_base64" '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        '${alignment_index}' "\$index_sha" '${reference}' "\$reference_sha" "\$annotation_sha" "\$reads_sha" \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${meta.id}.execution.json'

    printf '{"schema_version":"1.0","type":"alignment","id":"%s","status":"complete","aligner":"star","dataset":"%s","sample_id":"%s","artifacts":{"bam":{"path":"Aligned.sortedByCoord.out.bam","sha256":"%s"},"bai":{"path":"Aligned.sortedByCoord.out.bam.bai","sha256":"%s"},"gene_counts":{"path":"ReadsPerGene.out.tab","compatibility_path":"%s/ReadsPerGene.out.tab","sha256":"%s"}},"reference_sha256":"%s","index_sha256":"%s"}\n' \
        '${meta.id}' '${meta.dataset}' '${meta.sample_id}' "\$bam_sha" "\$bai_sha" '${target_dir}' "\$gene_counts_sha" "\$reference_sha" "\$index_sha" \
        > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.star_align.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.alignment_logs' '${meta.id}.alignment_statistics'
    touch Aligned.sortedByCoord.out.bam Aligned.sortedByCoord.out.bam.bai
    printf 'stub\n' > ReadsPerGene.out.tab
    printf 'stub\n' > Log.final.out
    printf 'STAR [stub]\n' > '${meta.id}.alignment_logs/command.txt'
    cp Log.final.out '${meta.id}.alignment_logs/'
    printf 'metric\tvalue\nstub\t1\n' > '${meta.id}.alignment_statistics/mapping_summary.tsv'
    printf 'mapq\talignments\n255\t1\n' > '${meta.id}.alignment_statistics/mapq_distribution.tsv'
    cp ReadsPerGene.out.tab '${meta.id}.alignment_statistics/'
    printf '"STAR_ALIGN":\n    star: stub\n    samtools: stub\n    htslib: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"STAR_ALIGN","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"alignment","id":"%s","status":"stub","aligner":"star"}\n' '${meta.id}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"STAR_ALIGN","status":"stub"}\n' '${meta.id}' > '${meta.id}.star_align.done'
    """
}
