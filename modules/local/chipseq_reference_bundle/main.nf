process CHIPSEQ_REFERENCE_BUNDLE {
    tag "reference:${meta.id}"
    label 'native_module'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/reference",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(reference), path(annotation), path(blacklist, arity: '0..*')

    output:
    tuple val(meta), path(reference), path(annotation), path('reference_bundle.manifest.json'), emit: artifacts
    tuple val(meta), path('reference_bundle.validation.json'), path('reference_bundle.log'), emit: reports
    tuple val(meta), path('reference_bundle.versions.yml'), emit: versions
    tuple val(meta), path('reference_bundle.done'), emit: status

    script:
    def blacklistArg = blacklist ? "--blacklist '${blacklist[0]}'" : ''
    """
    python '${moduleDir}/build_chipseq_reference_bundle.py' \
        --reference-id '${meta.id}' \
        --genome-id '${meta.genome_id}' \
        --build '${meta.build}' \
        --organism '${meta.organism ?: ''}' \
        --reference '${reference}' \
        --annotation '${annotation}' \
        ${blacklistArg} \
        --manifest reference_bundle.manifest.json \
        --validation reference_bundle.validation.json \
        2>&1 | tee reference_bundle.log
    printf '"CHIPSEQ_REFERENCE_BUNDLE":\n    python: %s\n' "\$(python --version 2>&1 | awk '{print \$2}')" > reference_bundle.versions.yml
    printf '{"id":"%s","process":"CHIPSEQ_REFERENCE_BUNDLE","status":"complete"}\n' '${meta.id}' > reference_bundle.done
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"reference_bundle","id":"%s","genome_id":"%s","build":"%s","organism":"%s","artifacts":{},"status":"stub"}\n' \
        '${meta.id}' '${meta.genome_id}' '${meta.build}' '${meta.organism ?: ''}' > reference_bundle.manifest.json
    printf '{"schema_version":"1.0","status":"stub"}\n' > reference_bundle.validation.json
    printf '[STUB] ChIP-seq reference bundle\n' > reference_bundle.log
    printf '"CHIPSEQ_REFERENCE_BUNDLE":\n    python: stub\n' > reference_bundle.versions.yml
    printf '{"id":"%s","process":"CHIPSEQ_REFERENCE_BUNDLE","status":"stub"}\n' '${meta.id}' > reference_bundle.done
    """
}
