process MOLECULAR_EVIDENCE_INTEGRATION {
    tag "${meta.id}"
    label 'native_module'
    label 'integration_low'

    cpus 1
    memory 3.GB
    time 45.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.molecular_integration_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/integration/master", mode: 'copy', overwrite: true, pattern: 'integrated_evidence'
    publishDir "${params.outdir}/pipeline_info/integration/master", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(rna_evidence, stageAs: 'rna_evidence'), path(chip_evidence, stageAs: 'chipseq_evidence'), path(harmonization, stageAs: 'harmonized_evidence')

    output:
    tuple val(meta), path('integrated_evidence'), emit: artifacts
    tuple val(meta), path('integrated_evidence/integration_manifest.json'), emit: manifest
    tuple val(meta), path('molecular_integration.log'), emit: reports
    tuple val(meta), path('molecular_integration.versions.yml'), emit: versions
    tuple val(meta), path('molecular_integration.done'), emit: status

    script:
    """
    set -o pipefail
    integrate_evidence.py \
        --rna-evidence-dir '${rna_evidence}' \
        --chip-evidence-dir '${chip_evidence}' \
        --harmonization-dir '${harmonization}' \
        --output-dir integrated_evidence \
        2>&1 | tee molecular_integration.log
    validate_molecular_integration.py integrated_evidence/integration_manifest.json
    printf '"MOLECULAR_EVIDENCE_INTEGRATION":\n    python: "%s"\n    integration_model: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > molecular_integration.versions.yml
    printf '{"id":"%s","process":"MOLECULAR_EVIDENCE_INTEGRATION","status":"complete"}\n' '${meta.id}' > molecular_integration.done
    """

    stub:
    """
    mkdir -p integrated_evidence
    printf 'observation_id\tcanonical_entity_id\tentity_type\treference_id\tsource_assay\tevidence_type\tsource_evidence_id\tsource_entity_id\tsource_artifact_id\tcontext_type\tsource_context\tcanonical_context\tsource_contrast_id\tcanonical_contrast_id\tsource_mark\tcanonical_mark\tmeasurement\tunit\teffect\tdirection\tpvalue\tpadj\tpeak_id\tpeak_relationship\tdistance_to_tss\tposition\tmeasurement_state\n' > integrated_evidence/master_evidence_long.tsv
    printf 'canonical_entity_id\treference_id\trna_evidence_state\tchip_evidence_state\texpression_observations\tdifferential_expression_observations\tpeak_associations\tdifferential_binding_observations\tmarks_or_factors\tcontexts\tcanonical_contrasts\trna_evidence_ids\tchip_evidence_ids\n' > integrated_evidence/master_evidence.tsv
    printf 'canonical_entity_id\tcanonical_mark\tcanonical_context\ttotal_associated_peaks\tpromoter_peaks\tgene_body_peaks\tdistal_peaks\tpeak_ids\tsource_evidence_ids\n' > integrated_evidence/peak_aggregation.tsv
    printf '{"schema_version":"1.0","integration_model_version":"1.0","type":"molecular_evidence_integration","id":"%s.integration","status":"stub","reference":{"reference_id":"stub"},"input_evidence_manifests":[{"id":"rna","assay":"rnaseq"},{"id":"chip","assay":"chipseq"}],"harmonization_manifest_id":"stub","harmonization_manifest_checksum":{"algorithm":"sha256","value":"0000000000000000000000000000000000000000000000000000000000000000"},"datasets":[],"record_counts":{"canonical_genes":0,"long_observations":0,"peak_groups":0},"provenance":{"provider":"stub"}}\n' '${meta.id}' > integrated_evidence/integration_manifest.json
    printf '[STUB] Molecular Evidence Integration\n' > molecular_integration.log
    printf '"MOLECULAR_EVIDENCE_INTEGRATION":\n    python: stub\n    integration_model: "1.0"\n' > molecular_integration.versions.yml
    printf '{"id":"%s","process":"MOLECULAR_EVIDENCE_INTEGRATION","status":"stub"}\n' '${meta.id}' > molecular_integration.done
    """
}
