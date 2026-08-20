process REGULATORY_INTERPRETATION {
    tag "${meta.id}"
    label 'native_module'
    label 'integration_low'
    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0
    container params.interpretation_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/integration/interpretation/regulatory", mode: 'copy', overwrite: true, pattern: 'regulatory_interpretation'
    publishDir "${params.outdir}/pipeline_info/integration/interpretation/regulatory", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(integration, stageAs: 'integrated_evidence'), path(policy, stageAs: 'interpretation_policy.json'), path(mark_roles, stageAs: 'mark_roles.tsv')

    output:
    tuple val(meta), path('regulatory_interpretation'), emit: artifacts
    tuple val(meta), path('regulatory_interpretation/regulatory_interpretation_manifest.json'), emit: manifest
    tuple val(meta), path('regulatory_interpretation.log'), emit: reports
    tuple val(meta), path('regulatory_interpretation.versions.yml'), emit: versions
    tuple val(meta), path('regulatory_interpretation.done'), emit: status

    script:
    """
    classify_regulatory_evidence.py --integration-dir '${integration}' --policy '${policy}' --mark-roles '${mark_roles}' --output-dir regulatory_interpretation 2>&1 | tee regulatory_interpretation.log
    printf '"REGULATORY_INTERPRETATION":\n    python: "%s"\n    classification_model: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > regulatory_interpretation.versions.yml
    printf '{"id":"%s","process":"REGULATORY_INTERPRETATION","status":"complete"}\n' '${meta.id}' > regulatory_interpretation.done
    """

    stub:
    """
    mkdir -p regulatory_interpretation
    printf 'classification_id\tcanonical_entity_id\n' > regulatory_interpretation/regulatory_classes.tsv
    printf '{"schema_version":"1.0","type":"regulatory_interpretation_component","id":"%s.regulatory","status":"stub"}\n' '${meta.id}' > regulatory_interpretation/regulatory_interpretation_manifest.json
    printf '[STUB] Regulatory Interpretation\n' > regulatory_interpretation.log
    printf '"REGULATORY_INTERPRETATION":\n    python: stub\n    classification_model: "1.0"\n' > regulatory_interpretation.versions.yml
    printf '{"id":"%s","process":"REGULATORY_INTERPRETATION","status":"stub"}\n' '${meta.id}' > regulatory_interpretation.done
    """
}
