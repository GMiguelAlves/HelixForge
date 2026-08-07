process IMPORT_SOURCE {
    tag "${meta.id}:${role}"
    label 'native_module'
    label 'import_low'

    cpus 1
    memory 1.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.import_source_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_import/sources",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done}'

    input:
    tuple val(meta), path(provider_manifest), path(provider_artifact), val(role)

    output:
    tuple val(meta), path("${meta.id}.import_source"), emit: artifacts
    tuple val(meta), path("${meta.id}.source_validation.json"), emit: reports
    tuple val(meta), path("${meta.id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.import_source.done"), emit: status

    script:
    def provider = meta.provider
    def targetRoot = meta.target_dir ?: ''
    """
    python '${moduleDir}/bin/validate_source.py' \
        --manifest '${provider_manifest}' \
        --artifact '${provider_artifact}' \
        --role '${role}' \
        --provider '${provider}' \
        --source-name '${meta.id}.import_source' \
        --target-root '${targetRoot}' \
        --output '${meta.id}.import_source' \
        > '${meta.id}.source_validation.json'
    printf '"%s":\n    python: "%s"\n' '${task.process}' "\$(python --version 2>&1 | awk '{print \$2}')" \
        > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${meta.id}.import_source.done'
    """

    stub:
    """
    mkdir '${meta.id}.import_source'
    cp '${provider_artifact}' '${meta.id}.import_source/artifact'
    cp '${provider_manifest}' '${meta.id}.import_source/manifest.json'
    printf '{"schema_version":"1.0","type":"import_source","source_name":"%s.import_source","provider":"%s","role":"%s","dataset":"%s","sample_id":"%s","compatibility_path":"%s"}\n' \
        '${meta.id}' '${meta.provider}' '${role}' '${meta.dataset}' '${meta.sample_id}' '${meta.target_dir ?: ''}' \
        > '${meta.id}.import_source/source.json'
    cp '${meta.id}.import_source/source.json' '${meta.id}.source_validation.json'
    printf '"IMPORT_SOURCE":\n    python: "stub"\n' > '${meta.id}.versions.yml'
    printf '{"id":"%s","process":"IMPORT_SOURCE","status":"stub"}\n' \
        '${meta.id}' > '${meta.id}.import_source.done'
    """
}
