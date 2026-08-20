process CROSS_ASSAY_STATISTICS {
    tag "${meta.id}"
    label 'native_module'
    label 'integration_low'
    cpus 1
    memory 3.GB
    time 45.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0
    container params.interpretation_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/integration/interpretation/final", mode: 'copy', overwrite: true, pattern: 'interpretation'
    publishDir "${params.outdir}/pipeline_info/integration/interpretation/statistics", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(integration, stageAs: 'integrated_evidence'), path(classification, stageAs: 'regulatory_interpretation'), path(scoring, stageAs: 'candidate_scoring'), path(policy, stageAs: 'interpretation_policy.json'), path(mark_roles, stageAs: 'mark_roles.tsv'), path(context, stageAs: 'prioritization_context.tsv')

    output:
    tuple val(meta), path('interpretation'), emit: artifacts
    tuple val(meta), path('interpretation/interpretation_manifest.json'), emit: manifest
    tuple val(meta), path('cross_assay_statistics.log'), emit: reports
    tuple val(meta), path('cross_assay_statistics.versions.yml'), emit: versions
    tuple val(meta), path('cross_assay_statistics.done'), emit: status

    script:
    """
    calculate_cross_assay_statistics.py --integration-dir '${integration}' --classification-dir '${classification}' --scoring-dir '${scoring}' --policy '${policy}' --mark-roles '${mark_roles}' --context '${context}' --output-dir interpretation 2>&1 | tee cross_assay_statistics.log
    validate_interpretation.py interpretation/interpretation_manifest.json 2>&1 | tee -a cross_assay_statistics.log
    printf '"CROSS_ASSAY_STATISTICS":\n    python: "%s"\n    interpretation_model: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > cross_assay_statistics.versions.yml
    printf '{"id":"%s","process":"CROSS_ASSAY_STATISTICS","status":"complete"}\n' '${meta.id}' > cross_assay_statistics.done
    """

    stub:
    """
    mkdir -p interpretation
    printf 'classification_id\tcanonical_entity_id\n' > interpretation/regulatory_classes.tsv
    printf 'canonical_entity_id\tfinal_score\n' > interpretation/candidate_score.tsv
    printf 'rank\tcanonical_entity_id\n' > interpretation/candidate_ranking.tsv
    printf 'test_id\tpvalue\tpadj\n' > interpretation/fisher_tests.tsv
    printf 'analysis_id\tcorrelation\n' > interpretation/correlations.tsv
    printf 'mark\tcanonical_name\tregulatory_role\tcontext\tevidence_source\tnotes\n' > interpretation/mark_role_catalog.tsv
    printf '{"schema_version":"1.0","interpretation_model_version":"1.0","classification_version":"1.0","candidate_score_version":"1.0","type":"molecular_interpretation","id":"%s.interpretation","status":"stub","reference":{},"input_integration_manifest":{},"input_component_manifests":[],"policy_checksum":{},"candidate_score":{},"thresholds":{},"mark_role_catalog":{},"prioritization_context":{},"statistics_methods":{},"datasets":[],"record_counts":{},"provenance":{"provider":"stub"}}\n' '${meta.id}' > interpretation/interpretation_manifest.json
    printf '[STUB] Cross-Assay Statistics\n' > cross_assay_statistics.log
    printf '"CROSS_ASSAY_STATISTICS":\n    python: stub\n    interpretation_model: "1.0"\n' > cross_assay_statistics.versions.yml
    printf '{"id":"%s","process":"CROSS_ASSAY_STATISTICS","status":"stub"}\n' '${meta.id}' > cross_assay_statistics.done
    """
}
