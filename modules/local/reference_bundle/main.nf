process REFERENCE_BUNDLE {
    tag { "reference:${meta.id}" }
    label 'native_module'

    cpus 1
    memory 2.GB
    time 1.h
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.reference_bundle_container
    conda "${moduleDir}/environment.yml"

    publishDir { "${params.outdir}/references/${meta.id}" },
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(transcriptome), path(annotation), path(genome)

    output:
    tuple val(meta), path(transcriptome), path(annotation), path('reference_bundle.manifest.json'), emit: artifacts
    tuple val(meta), path('reference_bundle.validation.json'), path('reference_bundle.log'), emit: reports
    tuple val(meta), path('reference_bundle.versions.yml'), emit: versions
    tuple val(meta), path('reference_bundle.done'), emit: status

    script:
    def genomeArg = genome ? "--genome '${genome}'" : ''
    """
    python '${moduleDir}/validate_reference_bundle.py' \
        --reference-id '${meta.id}' \
        --organism '${meta.organism ?: ''}' \
        --transcriptome '${transcriptome}' \
        --annotation '${annotation}' \
        ${genomeArg} \
        --run-mode '${params.rnaseq_run_mode}' \
        --manifest reference_bundle.manifest.json \
        --report reference_bundle.validation.json \
        2>&1 | tee reference_bundle.log

    printf '"%s":\n    python: %s\n' '${task.process}' "\$(python --version 2>&1 | awk '{print \$2}')" \
        > reference_bundle.versions.yml
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > reference_bundle.done
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"reference_bundle","id":"%s","organism":"%s","artifacts":[],"status":"stub"}\n' \
        '${meta.id}' '${meta.organism ?: 'unknown'}' > reference_bundle.manifest.json
    printf '{"schema_version":"1.0","status":"stub"}\n' > reference_bundle.validation.json
    printf '[STUB] Reference Bundle\n' > reference_bundle.log
    printf '"REFERENCE_BUNDLE":\n    python: stub\n' > reference_bundle.versions.yml
    printf '{"id":"%s","process":"REFERENCE_BUNDLE","status":"stub"}\n' '${meta.id}' > reference_bundle.done
    """
}
