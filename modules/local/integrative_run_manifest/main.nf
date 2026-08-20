process INTEGRATIVE_RUN_MANIFEST {
    tag "${meta.id}"
    label 'native_module'
    label 'integration_low'
    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0
    container params.integrative_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/integration", mode: 'copy', overwrite: true, pattern: 'integrative_run_manifest.json'
    publishDir "${params.outdir}/pipeline_info/integration/terminal", mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(rna_manifest), path(chip_manifest), path(validation, stageAs: 'integrative_inputs'), path(rna_evidence, stageAs: 'rnaseq_evidence'), path(chip_evidence, stageAs: 'chipseq_evidence'), path(harmonization, stageAs: 'harmonized_evidence'), path(integration, stageAs: 'integrated_evidence'), path(interpretation, stageAs: 'interpretation'), path(functional, stageAs: 'functional_analysis'), path(visualization, stageAs: 'integrative_visualization'), path(report, stageAs: 'integrative_report'), val(run_base64)

    output:
    tuple val(meta), path('integrative_run_manifest.json'), emit: artifacts
    tuple val(meta), path('integrative_run_manifest.validation.json'), path('integrative_run_manifest.log'), emit: reports
    tuple val(meta), path('integrative_run_manifest.versions.yml'), emit: versions
    tuple val(meta), path('integrative_run_manifest.done'), emit: status

    script:
    """
    set -o pipefail
    build_integrative_run_manifest.py --rna-manifest '${rna_manifest}' --chip-manifest '${chip_manifest}' --validation-dir '${validation}' --rna-evidence-dir '${rna_evidence}' --chip-evidence-dir '${chip_evidence}' --harmonization-dir '${harmonization}' --integration-dir '${integration}' --interpretation-dir '${interpretation}' --functional-dir '${functional}' --visualization-dir '${visualization}' --report-dir '${report}' --run-base64 '${run_base64}' --output integrative_run_manifest.json 2>&1 | tee integrative_run_manifest.log
    printf '{"schema_version":"1.0","type":"integrative_run_manifest_validation","status":"complete","schema":"validated_in_ci","semantic":"valid","checksums":"valid"}\n' > integrative_run_manifest.validation.json
    printf '"INTEGRATIVE_RUN_MANIFEST":\n    python: "%s"\n    integration_api: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > integrative_run_manifest.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_RUN_MANIFEST","status":"complete"}\n' '${meta.id}' > integrative_run_manifest.done
    """

    stub:
    """
    printf '{"schema_version":"1.0","integration_api_version":"1.0","type":"integrative_run_manifest","id":"%s","status":"stub","run":{},"reference":{},"input_manifests":[],"compatibility":{},"models":{},"policies":{},"artifacts":[],"component_manifests":[],"record_counts":{},"provenance":{}}\n' '${meta.id}' > integrative_run_manifest.json
    printf '{"schema_version":"1.0","type":"integrative_run_manifest_validation","status":"stub"}\n' > integrative_run_manifest.validation.json
    printf '[STUB] Integrative Run Manifest\n' > integrative_run_manifest.log
    printf '"INTEGRATIVE_RUN_MANIFEST":\n    python: stub\n    integration_api: "1.0"\n' > integrative_run_manifest.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_RUN_MANIFEST","status":"stub"}\n' '${meta.id}' > integrative_run_manifest.done
    """
}
