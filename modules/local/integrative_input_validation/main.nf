process INTEGRATIVE_INPUT_VALIDATION {
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
    publishDir "${params.outdir}/integration/010-input-validation", mode: 'copy', overwrite: true, pattern: 'integrative_inputs'
    publishDir "${params.outdir}/pipeline_info/integration/input-validation", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(rna_manifest, stageAs: 'rna_run_manifest.json'), path(rna_artifacts, stageAs: 'rna_integration_artifacts'), path(chip_manifest, stageAs: 'chipseq_run_manifest.json'), path(chip_artifacts, stageAs: 'chipseq_integration_artifacts')

    output:
    tuple val(meta), path('integrative_inputs'), emit: artifacts
    tuple val(meta), path('integrative_inputs/input_validation.json'), emit: manifest
    tuple val(meta), path('integrative_input_validation.log'), emit: reports
    tuple val(meta), path('integrative_input_validation.versions.yml'), emit: versions
    tuple val(meta), path('integrative_input_validation.done'), emit: status

    script:
    """
    set -o pipefail
    prepare_integrative_inputs.py --rna-manifest '${rna_manifest}' --rna-artifacts '${rna_artifacts}' --chip-manifest '${chip_manifest}' --chip-artifacts '${chip_artifacts}' --output-dir integrative_inputs 2>&1 | tee integrative_input_validation.log
    printf '"INTEGRATIVE_INPUT_VALIDATION":\n    python: "%s"\n    integration_api: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > integrative_input_validation.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_INPUT_VALIDATION","status":"complete"}\n' '${meta.id}' > integrative_input_validation.done
    """

    stub:
    """
    mkdir -p integrative_inputs/rnaseq_artifacts/stub integrative_inputs/chipseq_artifacts/stub
    printf 'stub\n' > integrative_inputs/rnaseq_artifacts/stub/artifact.tsv
    printf 'stub\n' > integrative_inputs/chipseq_artifacts/stub/artifact.tsv
    printf '{"schema_version":"1.0","type":"rnaseq_run_manifest","id":"stub.rna","status":"stub","run":{"run_id":"stub"},"reference":{"reference_id":"stub"},"artifacts":[]}\n' > integrative_inputs/rnaseq_run_manifest.json
    printf '{"schema_version":"1.0","type":"chipseq_run_manifest","id":"stub.chip","status":"stub","run":{"run_id":"stub"},"reference":{"reference_id":"stub"},"artifacts":[]}\n' > integrative_inputs/chipseq_run_manifest.json
    printf '{"bindings":[]}\n' > integrative_inputs/rnaseq_bindings.json
    printf '{"bindings":[]}\n' > integrative_inputs/chipseq_bindings.json
    printf '{"schema_version":"1.0","type":"integrative_input_validation","status":"stub","reference_compatibility":"compatible","inputs":[]}\n' > integrative_inputs/input_validation.json
    printf '[STUB] Integrative input validation\n' > integrative_input_validation.log
    printf '"INTEGRATIVE_INPUT_VALIDATION":\n    python: stub\n    integration_api: "1.0"\n' > integrative_input_validation.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_INPUT_VALIDATION","status":"stub"}\n' '${meta.id}' > integrative_input_validation.done
    """
}
