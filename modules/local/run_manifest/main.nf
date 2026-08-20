process RUN_MANIFEST {
    tag "${meta.assay}:${meta.id}"
    label 'native_module'

    cpus 1
    memory 1.GB
    time 15.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.integration_manifest_container
    conda "${moduleDir}/environment.yml"

    publishDir { "${params.outdir}/${meta.assay}" },
        mode: 'copy', overwrite: true, pattern: "${meta.assay}_run_manifest.json"
    publishDir { "${params.outdir}/${meta.assay}" },
        mode: 'copy', overwrite: true, pattern: 'integration_artifacts'
    publishDir "${params.outdir}/pipeline_info/integration_api",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(metadata), path(reference_manifest), path(schema_dir),
        path(source_manifests, stageAs: 'source_manifests/??/*'),
        path(artifacts, stageAs: 'artifacts/??/*'),
        path(contrast_spec),
        val(run_base64), val(artifact_specs_base64)

    output:
    tuple val(meta), path("${meta.assay}_run_manifest.json"), emit: artifacts
    tuple val(meta), path("${meta.assay}_run_manifest.json"), path('integration_artifacts'), emit: bundle
    tuple val(meta), path('run_manifest.validation.json'), path('run_manifest.log'), emit: reports
    tuple val(meta), path('run_manifest.versions.yml'), emit: versions
    tuple val(meta), path('run_manifest.done'), emit: status

    script:
    def sourceArgs = source_manifests.collect { value -> "--source-manifest '${value}'" }.join(' ')
    def artifactArgs = artifacts.collect { value -> "--artifact '${value}'" }.join(' ')
    def contrastArg = contrast_spec ? "--contrast-spec '${contrast_spec}'" : ''
    """
    set -o pipefail
    build_run_manifest.py \
        --assay '${meta.assay}' \
        --run-base64 '${run_base64}' \
        --metadata '${metadata}' \
        --reference-manifest '${reference_manifest}' \
        --schema-root '${schema_dir}' \
        ${sourceArgs} \
        ${artifactArgs} \
        --artifact-specs-base64 '${artifact_specs_base64}' \
        --portable-integration-dir integration_artifacts \
        ${contrastArg} \
        --output '${meta.assay}_run_manifest.json' \
        --validation-report run_manifest.validation.json \
        2>&1 | tee run_manifest.log
    printf '"RUN_MANIFEST":\n    python: "%s"\n    integration_api: "1.0"\n' \
        "\$(python --version 2>&1 | awk '{print \$2}')" > run_manifest.versions.yml
    printf '{"id":"%s","process":"RUN_MANIFEST","status":"complete"}\n' '${meta.id}' > run_manifest.done
    """

    stub:
    def sourceArgsStub = source_manifests.collect { value -> "--source-manifest '${value}'" }.join(' ')
    def artifactArgsStub = artifacts.collect { value -> "--artifact '${value}'" }.join(' ')
    def contrastArgStub = contrast_spec ? "--contrast-spec '${contrast_spec}'" : ''
    """
    build_run_manifest.py \
        --assay '${meta.assay}' \
        --run-base64 '${run_base64}' \
        --metadata '${metadata}' \
        --reference-manifest '${reference_manifest}' \
        --schema-root '${schema_dir}' \
        ${sourceArgsStub} \
        ${artifactArgsStub} \
        --artifact-specs-base64 '${artifact_specs_base64}' \
        --portable-integration-dir integration_artifacts \
        ${contrastArgStub} \
        --status stub \
        --skip-json-schema \
        --output '${meta.assay}_run_manifest.json' \
        --validation-report run_manifest.validation.json \
        > run_manifest.log 2>&1
    printf '"RUN_MANIFEST":\n    python: stub\n    integration_api: "1.0"\n' > run_manifest.versions.yml
    printf '{"id":"%s","process":"RUN_MANIFEST","status":"stub"}\n' '${meta.id}' > run_manifest.done
    """
}
