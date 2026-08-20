process CHIPSEQ_EVIDENCE_PROVIDER {
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

    publishDir "${params.outdir}/integration/evidence/chipseq",
        mode: 'copy', overwrite: true, pattern: 'chipseq_evidence'
    publishDir "${params.outdir}/pipeline_info/evidence/chipseq",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta), path(run_manifest), path(bindings), path(declared_artifacts, stageAs: 'declared/??/*')

    output:
    tuple val(meta), path('chipseq_evidence'), emit: artifacts
    tuple val(meta), path('chipseq_evidence/evidence_manifest.json'), emit: manifest
    tuple val(meta), path('chipseq_evidence.validation.json'), path('chipseq_evidence.log'), emit: reports
    tuple val(meta), path('chipseq_evidence.versions.yml'), emit: versions
    tuple val(meta), path('chipseq_evidence.done'), emit: status

    script:
    def artifactArgs = declared_artifacts.collect { value -> "--declared-artifact '${value}'" }.join(' ')
    """
    set -o pipefail
    build_evidence.py \
        --manifest '${run_manifest}' \
        --bindings '${bindings}' \
        ${artifactArgs} \
        --output-dir chipseq_evidence \
        --validation-report chipseq_evidence.validation.json \
        2>&1 | tee chipseq_evidence.log
    printf '"CHIPSEQ_EVIDENCE_PROVIDER":\n    python: "%s"\n    evidence_model: "1.1"\n' \
        "\$(python --version 2>&1 | awk '{print \$2}')" > chipseq_evidence.versions.yml
    printf '{"id":"%s","process":"CHIPSEQ_EVIDENCE_PROVIDER","status":"complete"}\n' '${meta.id}' > chipseq_evidence.done
    """

    stub:
    """
    mkdir -p chipseq_evidence
    printf '{"schema_version":"1.0","evidence_model_version":"1.1","type":"evidence_manifest","id":"%s.evidence","assay":"chipseq","run_id":"stub","reference_id":"stub","reference":{"reference_id":"stub","genome_id":"stub","organism":"stub","assembly":"stub","annotation_id":"stub"},"source_run_manifest_id":"stub","status":"stub","contrasts":[],"datasets":[],"artifact_catalog":[],"provenance":{"provider":"chipseq_evidence_provider","provider_version":"1.1","source_run_manifest_id":"stub"}}\n' '${meta.id}' > chipseq_evidence/evidence_manifest.json
    printf '{"schema_version":"1.0","type":"evidence_validation","schema":"skipped_stub","semantic":"valid","filesystem":"tracked_inputs","status":"stub"}\n' > chipseq_evidence.validation.json
    printf '[STUB] ChIP Evidence Provider\n' > chipseq_evidence.log
    printf '"CHIPSEQ_EVIDENCE_PROVIDER":\n    python: stub\n    evidence_model: "1.1"\n' > chipseq_evidence.versions.yml
    printf '{"id":"%s","process":"CHIPSEQ_EVIDENCE_PROVIDER","status":"stub"}\n' '${meta.id}' > chipseq_evidence.done
    """
}
