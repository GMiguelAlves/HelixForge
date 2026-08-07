process STAR_INDEX {
    tag "${meta.id}"
    label 'native_module'
    label 'alignment_index'

    cpus 16
    memory 180.GB
    time 8.h
    queue { params.star_index_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.star_apptainer_container : params.star_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_alignment/star_index",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done}'

    input:
    tuple val(meta), path(reference), path(annotation), val(index_params)

    output:
    tuple val(meta), path('star_index'), emit: artifacts
    tuple val(meta), path("${meta.id}.star_index_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.star_index.done"), emit: status

    script:
    def target_dir = meta.target_dir ?: ''
    def command_index_dir = target_dir ?: 'star_index'
    def sa_bases = index_params.genome_sa_index_nbases
    def limit_ram = index_params.limit_genome_generate_ram
    """
    start_epoch=\$(date +%s)
    mkdir -p star_index '${meta.id}.star_index_reports'
    reference_sha=\$(sha256sum '${reference}' | awk '{ print \$1 }')
    annotation_sha=\$(sha256sum '${annotation}' | awk '{ print \$1 }')

    printf '%s\n' \
        "STAR --runMode genomeGenerate --runThreadN ${task.cpus} --genomeDir ${command_index_dir} --genomeFastaFiles ${reference} --sjdbGTFfile ${annotation} --genomeSAindexNbases ${sa_bases} --limitGenomeGenerateRAM ${limit_ram}" \
        > '${meta.id}.star_index_reports/command.txt'

    if [[ -n '${target_dir}' && -d '${target_dir}' && -n "\$(find '${target_dir}' -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
        echo '[SKIP] STAR index ja existe: ${target_dir}' \
            | tee '${meta.id}.star_index_reports/star_index.log'
        cp -a '${target_dir}/.' star_index/
    else
        STAR --runMode genomeGenerate \
            --runThreadN ${task.cpus} \
            --genomeDir star_index \
            --genomeFastaFiles '${reference}' \
            --sjdbGTFfile '${annotation}' \
            --genomeSAindexNbases '${sa_bases}' \
            --limitGenomeGenerateRAM '${limit_ram}' \
            2>&1 | tee '${meta.id}.star_index_reports/star_index.log'

        [[ -s star_index/Genome && -s star_index/SA && -s star_index/SAindex ]]

        if [[ -n '${target_dir}' ]]; then
            target_tmp='${target_dir}.nextflow.tmp.${task.index}'
            mkdir -p "\$(dirname '${target_dir}')"
            mkdir "\$target_tmp"
            cp -a star_index/. "\$target_tmp/"
            if [[ -d '${target_dir}' ]]; then
                rmdir '${target_dir}'
            fi
            mv "\$target_tmp" '${target_dir}'
        fi
    fi

    index_sha=\$(find star_index -type f -print0 \
        | sort -z \
        | xargs -0 sha256sum \
        | sha256sum \
        | awk '{ print \$1 }')
    end_epoch=\$(date +%s)

    printf 'reference\tsha256\n%s\t%s\n%s\t%s\nindex\t%s\n' \
        '${reference}' "\$reference_sha" '${annotation}' "\$annotation_sha" "\$index_sha" \
        > '${meta.id}.star_index_reports/checksums.tsv'

    printf '"%s":\n    star: %s\n    samtools: %s\n    htslib: %s\n' \
        '${task.process}' \
        "\$(STAR --version | sed 's/^STAR_//')" \
        "\$(samtools --version | sed -n '1s/samtools //p')" \
        "\$(htsfile --version 2>&1 | awk 'NR==1 { print \$NF }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","reference":"%s","reference_sha256":"%s","annotation":"%s","annotation_sha256":"%s","target_index":"%s","index_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        '${reference}' "\$reference_sha" '${annotation}' "\$annotation_sha" '${target_dir}' "\$index_sha" \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${meta.id}.execution.json'

    printf '{"schema_version":"1.0","type":"alignment_index","id":"%s","aligner":"star","artifact":"star_index","sha256":"%s","reference_sha256":"%s","annotation_sha256":"%s"}\n' \
        '${meta.id}' "\$index_sha" "\$reference_sha" "\$annotation_sha" \
        > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.star_index.done'
    """

    stub:
    """
    mkdir -p star_index '${meta.id}.star_index_reports'
    for artifact in Genome SA SAindex chrLength.txt chrName.txt chrNameLength.txt chrStart.txt genomeParameters.txt; do
        printf 'stub\n' > "star_index/\$artifact"
    done
    printf '[STUB] STAR index %s\n' '${meta.id}' > '${meta.id}.star_index_reports/star_index.log'
    printf 'STAR --runMode genomeGenerate [stub]\n' > '${meta.id}.star_index_reports/command.txt'
    printf 'reference\tsha256\nindex\tstub\n' > '${meta.id}.star_index_reports/checksums.tsv'
    printf '"STAR_INDEX":\n    star: stub\n    samtools: stub\n    htslib: stub\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"STAR_INDEX","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"alignment_index","id":"%s","aligner":"star","sha256":"stub"}\n' '${meta.id}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"STAR_INDEX","status":"stub"}\n' '${meta.id}' > '${meta.id}.star_index.done'
    """
}
