process SALMON_INDEX {
    tag "${meta.id}"
    label 'native_module'
    label 'quantification_index'

    cpus 16
    memory 64.GB
    time 12.h
    queue { params.salmon_index_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.salmon_apptainer_container : params.salmon_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_quantification/salmon_index",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,salmon_index_reports}'
    publishDir { meta.target_dir ?: "${params.outdir}/quantification_index/${meta.id}" },
        mode: 'copy', overwrite: true,
        pattern: '{complete_ref_lens.bin,ctable.bin,ctg_offsets.bin,duplicate_clusters.tsv,info.json,mphf.bin,pos.bin,pre_indexing.log,rank.bin,refAccumLengths.bin,ref_indexing.log,reflengths.bin,refseq.bin,seq.bin,versionInfo.json}'

    input:
    tuple val(meta), path(transcriptome), val(index_params)

    output:
    tuple val(meta), path('salmon_index'), emit: artifacts
    tuple val(meta), path('{complete_ref_lens.bin,ctable.bin,ctg_offsets.bin,duplicate_clusters.tsv,info.json,mphf.bin,pos.bin,pre_indexing.log,rank.bin,refAccumLengths.bin,ref_indexing.log,reflengths.bin,refseq.bin,seq.bin,versionInfo.json}'), emit: compatibility_files
    tuple val(meta), path("${meta.id}.salmon_index_reports"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.salmon_index.done"), emit: status

    script:
    def kmer_size = index_params.kmer_size
    """
    start_epoch=\$(date +%s)
    reports_dir='${meta.id}.salmon_index_reports'
    mkdir -p "\$reports_dir"

    printf '%s\n' \
        "salmon index -t ${transcriptome} -i salmon_index -p ${task.cpus} -k ${kmer_size}" \
        > "\$reports_dir/command.txt"

    salmon index \
        -t '${transcriptome}' \
        -i salmon_index \
        -p ${task.cpus} \
        -k '${kmer_size}' \
        2>&1 | tee "\$reports_dir/salmon_index.log"

    [[ -s salmon_index/versionInfo.json && -s salmon_index/info.json ]]
    for index_file in salmon_index/*; do
        ln -s "\$index_file" "\$(basename "\$index_file")"
    done

    transcriptome_sha=\$(sha256sum '${transcriptome}' | awk '{ print \$1 }')
    index_sha=\$(find salmon_index -type f -print0 \
        | sort -z \
        | xargs -0 sha256sum \
        | sha256sum \
        | awk '{ print \$1 }')
    end_epoch=\$(date +%s)

    printf 'artifact\tsha256\ntranscriptome\t%s\nindex\t%s\n' \
        "\$transcriptome_sha" "\$index_sha" \
        > "\$reports_dir/checksums.tsv"

    printf '"%s":\n    salmon: "%s"\n' \
        '${task.process}' \
        "\$(salmon --version | awk '{ print \$NF }')" \
        > '${meta.id}.versions.yml'

    printf '{"id":"%s","process":"%s","command":"salmon index -t %s -i salmon_index -p %s -k %s","cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","transcriptome":"%s","transcriptome_sha256":"%s","target_index":"%s","index_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${transcriptome}' '${task.cpus}' '${kmer_size}' \
        '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' '${params.salmon_container}' \
        '${transcriptome}' "\$transcriptome_sha" '${meta.target_dir ?: ''}' "\$index_sha" \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${meta.id}.execution.json'

    printf '{"schema_version":"1.0","type":"transcriptome_index","id":"%s","quantifier":"salmon","artifact":"salmon_index","sha256":"%s","transcriptome_sha256":"%s","parameters":{"kmer_size":%s}}\n' \
        '${meta.id}' "\$index_sha" "\$transcriptome_sha" '${kmer_size}' \
        > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.salmon_index.done'
    """

    stub:
    """
    mkdir -p salmon_index '${meta.id}.salmon_index_reports'
    for artifact in \
        complete_ref_lens.bin ctable.bin ctg_offsets.bin duplicate_clusters.tsv \
        info.json mphf.bin pos.bin pre_indexing.log rank.bin refAccumLengths.bin \
        ref_indexing.log reflengths.bin refseq.bin seq.bin versionInfo.json; do
        printf 'stub\n' > "salmon_index/\$artifact"
    done
    for index_file in salmon_index/*; do
        ln -s "\$index_file" "\$(basename "\$index_file")"
    done
    printf 'salmon index [stub]\n' > '${meta.id}.salmon_index_reports/command.txt'
    printf '[STUB] Salmon index %s\n' '${meta.id}' > '${meta.id}.salmon_index_reports/salmon_index.log'
    printf 'artifact\tsha256\ntranscriptome\tstub\nindex\tstub\n' > '${meta.id}.salmon_index_reports/checksums.tsv'
    printf '"SALMON_INDEX":\n    salmon: "stub"\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"SALMON_INDEX","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"transcriptome_index","id":"%s","quantifier":"salmon","sha256":"stub"}\n' '${meta.id}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"SALMON_INDEX","status":"stub"}\n' '${meta.id}' > '${meta.id}.salmon_index.done'
    """
}
