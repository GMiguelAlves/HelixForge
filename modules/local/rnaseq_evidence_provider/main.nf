process RNASEQ_EVIDENCE_PROVIDER {
    tag "${meta.id}"
    label 'native_module'
    label 'evidence_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.evidence_provider_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/integration/evidence/rnaseq",
        mode: 'copy', overwrite: true, pattern: 'rnaseq_evidence'
    publishDir "${params.outdir}/pipeline_info/evidence/rnaseq",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(run_manifest), path(bindings), path(declared_artifacts, stageAs: 'declared/??/*')

    output:
    tuple val(meta), path('rnaseq_evidence'), emit: artifacts
    tuple val(meta), path('rnaseq_evidence/evidence_manifest.json'), emit: manifest
    tuple val(meta), path('rnaseq_evidence.validation.json'), path('rnaseq_evidence.log'), emit: reports
    tuple val(meta), path('rnaseq_evidence.versions.yml'), emit: versions
    tuple val(meta), path('rnaseq_evidence.done'), emit: status

    script:
    def artifactArgs = declared_artifacts.collect { value -> "--declared-artifact '${value}'" }.join(' ')
    """
    set -o pipefail
    build_evidence.py \
        --manifest '${run_manifest}' \
        --bindings '${bindings}' \
        ${artifactArgs} \
        --output-dir rnaseq_evidence \
        --validation-report rnaseq_evidence.validation.json \
        2>&1 | tee rnaseq_evidence.log
    printf '"RNASEQ_EVIDENCE_PROVIDER":\n    python: "%s"\n    evidence_model: "1.0"\n' \
        "\$(python --version 2>&1 | awk '{print \$2}')" > rnaseq_evidence.versions.yml
    printf '{"id":"%s","process":"RNASEQ_EVIDENCE_PROVIDER","status":"complete"}\n' '${meta.id}' > rnaseq_evidence.done
    """

    stub:
    """
    mkdir -p rnaseq_evidence
    printf '{"schema_version":"1.0","evidence_model_version":"1.0","type":"evidence_manifest","id":"%s.evidence","assay":"rnaseq","run_id":"stub","reference_id":"stub","source_run_manifest_id":"stub","status":"stub","contrasts":[],"datasets":[],"artifact_catalog":[],"provenance":{"provider":"rnaseq_evidence_provider","provider_version":"1.0","source_run_manifest_id":"stub"}}\n' '${meta.id}' > rnaseq_evidence/evidence_manifest.json
    printf '{"schema_version":"1.0","type":"evidence_validation","schema":"skipped_stub","semantic":"valid","filesystem":"tracked_inputs","status":"stub"}\n' > rnaseq_evidence.validation.json
    printf '[STUB] RNA Evidence Provider\n' > rnaseq_evidence.log
    printf '"RNASEQ_EVIDENCE_PROVIDER":\n    python: stub\n    evidence_model: "1.0"\n' > rnaseq_evidence.versions.yml
    printf '{"id":"%s","process":"RNASEQ_EVIDENCE_PROVIDER","status":"stub"}\n' '${meta.id}' > rnaseq_evidence.done
    """
}
