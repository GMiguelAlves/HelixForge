process SALMON_INDEX_VALIDATE {
    tag "${meta.id}"
    label 'native_module'

    cpus 1
    memory 2.GB
    time 1.h
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.salmon_index_validation_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_quantification/salmon_index_validation",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,log,done}'

    input:
    tuple val(meta), path(transcriptome), path(transcriptome_index), path(index_manifest), val(index_params)

    output:
    tuple val(meta), path(transcriptome_index), emit: artifacts
    tuple val(meta), path("${meta.id}.validation.json"), path("${meta.id}.validation.log"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.salmon_index_validate.done"), emit: status

    script:
    """
    python '${moduleDir}/validate_salmon_index.py' \
        --index '${transcriptome_index}' \
        --transcriptome '${transcriptome}' \
        --manifest '${index_manifest}' \
        --expected-kmer-size '${index_params.kmer_size}' \
        --id '${meta.id}' \
        --validation-json '${meta.id}.validation.json' \
        --validation-log '${meta.id}.validation.log' \
        --versions-yml '${meta.id}.versions.yml' \
        --execution-json '${meta.id}.execution.json' \
        --output-manifest '${meta.id}.manifest.json' \
        --status-json '${meta.id}.salmon_index_validate.done'
    """

    stub:
    """
    printf '{"id":"%s","status":"stub"}\n' '${meta.id}' > '${meta.id}.validation.json'
    printf '[STUB] Salmon external index validation\n' > '${meta.id}.validation.log'
    printf '"SALMON_INDEX_VALIDATE":\n    python: "stub"\n    salmon_index: "stub"\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"SALMON_INDEX_VALIDATE","status":"stub"}\n' '${meta.id}' > '${meta.id}.execution.json'
    printf '{"schema_version":"1.0","type":"transcriptome_index","id":"%s","status":"stub","source":"prebuilt"}\n' '${meta.id}' > '${meta.id}.manifest.json'
    printf '{"id":"%s","process":"SALMON_INDEX_VALIDATE","status":"stub"}\n' '${meta.id}' > '${meta.id}.salmon_index_validate.done'
    """
}
