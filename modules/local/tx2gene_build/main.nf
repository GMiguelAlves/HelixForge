process TX2GENE_BUILD {
    tag "${meta.id}"
    label 'native_module'
    label 'import_medium'

    cpus 2
    memory 32.GB
    time 6.h
    queue { params.tx2gene_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.tx2gene_apptainer_container : params.tx2gene_container}"
    conda "${moduleDir}/environment.yml"

    publishDir { meta.target_dir }, mode: 'copy', overwrite: true, pattern: 'tx2gene.tsv'
    publishDir "${params.outdir}/pipeline_info/native_import/tx2gene_build",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,txt,log,done}'

    input:
    tuple val(meta), path(annotation), val(tx2gene_params)

    output:
    tuple val(meta), path('tx2gene.tsv'), emit: artifacts
    tuple val(meta), path('tx2gene_build.log'), path('sessionInfo.txt'), emit: reports
    tuple val(meta), path('versions.yml'), emit: versions
    tuple val(meta), path('execution.json'), emit: execution_metadata
    tuple val(meta), path('tx2gene_manifest.json'), emit: manifest
    tuple val(meta), path('tx2gene_build.done'), emit: status

    script:
    """
    start_epoch=\$(date +%s)
    tx2gene_build.R \
        --annotation '${annotation}' \
        --output tx2gene.tsv \
        --strip-transcript-version '${tx2gene_params.strip_transcript_version}' \
        --strip-gene-version '${tx2gene_params.strip_gene_version}' \
        --strip-transcript-prefix '${tx2gene_params.strip_transcript_prefix}' \
        --strip-gene-prefix '${tx2gene_params.strip_gene_prefix}' \
        > tx2gene_build.log 2>&1
    Rscript -e 'sessionInfo()' > sessionInfo.txt

    annotation_sha=\$(sha256sum '${annotation}' | awk '{ print \$1 }')
    tx2gene_sha=\$(sha256sum tx2gene.tsv | awk '{ print \$1 }')
    end_epoch=\$(date +%s)
    r_version=\$(Rscript -e 'cat(as.character(getRversion()))')
    rtracklayer_version=\$(Rscript -e 'cat(as.character(packageVersion("rtracklayer")))')

    printf '"%s":\n    r: "%s"\n    bioconductor: "3.18"\n    rtracklayer: "%s"\n' \
        '${task.process}' "\$r_version" "\$rtracklayer_version" > versions.yml
    printf '{"id":"%s","process":"%s","parameters":{"strip_transcript_version":%s,"strip_gene_version":%s,"strip_transcript_prefix":%s,"strip_gene_prefix":%s},"cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","annotation_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${tx2gene_params.strip_transcript_version}' '${tx2gene_params.strip_gene_version}' '${tx2gene_params.strip_transcript_prefix}' '${tx2gene_params.strip_gene_prefix}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        '${params.tx2gene_container}' "\$annotation_sha" "\$start_epoch" "\$end_epoch" \
        "\$((end_epoch-start_epoch))" > execution.json
    printf '{"schema_version":"1.0","type":"tx2gene","id":"%s","annotation_sha256":"%s","artifacts":{"tx2gene":{"path":"tx2gene.tsv","sha256":"%s","available":true}}}\n' \
        '${meta.id}' "\$annotation_sha" "\$tx2gene_sha" > tx2gene_manifest.json
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > tx2gene_build.done
    """

    stub:
    """
    annotation_key=\$(sha256sum '${annotation}' | awk '{print substr(\$1,1,12)}')
    printf 'transcript_id\tgene_id\ntx_%s\tgene_%s\n' \
        "\$annotation_key" "\$annotation_key" > tx2gene.tsv
    printf '[STUB] tx2gene\n' > tx2gene_build.log
    printf 'stub\n' > sessionInfo.txt
    printf '"TX2GENE_BUILD":\n    r: "stub"\n    bioconductor: "stub"\n    rtracklayer: "stub"\n' > versions.yml
    printf '{"id":"%s","process":"TX2GENE_BUILD","status":"stub"}\n' '${meta.id}' > execution.json
    printf '{"schema_version":"1.0","type":"tx2gene","id":"%s"}\n' '${meta.id}' > tx2gene_manifest.json
    printf '{"id":"%s","process":"TX2GENE_BUILD","status":"stub"}\n' '${meta.id}' > tx2gene_build.done
    """
}
