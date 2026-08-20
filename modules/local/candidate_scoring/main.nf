process CANDIDATE_SCORING {
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
    publishDir "${params.outdir}/integration/interpretation/scoring", mode: 'copy', overwrite: true, pattern: 'candidate_scoring'
    publishDir "${params.outdir}/pipeline_info/integration/interpretation/scoring", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(integration, stageAs: 'integrated_evidence'), path(classification, stageAs: 'regulatory_interpretation'), path(policy, stageAs: 'interpretation_policy.json'), path(context, stageAs: 'prioritization_context.tsv')

    output:
    tuple val(meta), path('candidate_scoring'), emit: artifacts
    tuple val(meta), path('candidate_scoring/candidate_scoring_manifest.json'), emit: manifest
    tuple val(meta), path('candidate_scoring.log'), emit: reports
    tuple val(meta), path('candidate_scoring.versions.yml'), emit: versions
    tuple val(meta), path('candidate_scoring.done'), emit: status

    script:
    """
    score_candidates.py --integration-dir '${integration}' --classification-dir '${classification}' --policy '${policy}' --context '${context}' --output-dir candidate_scoring 2>&1 | tee candidate_scoring.log
    printf '"CANDIDATE_SCORING":\n    python: "%s"\n    candidate_score: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > candidate_scoring.versions.yml
    printf '{"id":"%s","process":"CANDIDATE_SCORING","status":"complete"}\n' '${meta.id}' > candidate_scoring.done
    """

    stub:
    """
    mkdir -p candidate_scoring
    printf 'canonical_entity_id\tfinal_score\n' > candidate_scoring/candidate_score.tsv
    printf 'rank\tcanonical_entity_id\n' > candidate_scoring/candidate_ranking.tsv
    printf '{"schema_version":"1.0","type":"candidate_scoring_component","id":"%s.scoring","status":"stub"}\n' '${meta.id}' > candidate_scoring/candidate_scoring_manifest.json
    printf '[STUB] Candidate Scoring\n' > candidate_scoring.log
    printf '"CANDIDATE_SCORING":\n    python: stub\n    candidate_score: "1.0"\n' > candidate_scoring.versions.yml
    printf '{"id":"%s","process":"CANDIDATE_SCORING","status":"stub"}\n' '${meta.id}' > candidate_scoring.done
    """
}
