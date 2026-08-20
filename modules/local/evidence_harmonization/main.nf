process EVIDENCE_HARMONIZATION {
    tag "${meta.id}"
    label 'native_module'
    label 'integration_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.molecular_integration_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/integration/harmonization", mode: 'copy', overwrite: true, pattern: 'harmonized_evidence'
    publishDir "${params.outdir}/pipeline_info/integration/harmonization", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(rna_evidence, stageAs: 'rna_evidence'), path(chip_evidence, stageAs: 'chipseq_evidence'), path(policy, stageAs: 'harmonization_policy.json')

    output:
    tuple val(meta), path('harmonized_evidence'), emit: artifacts
    tuple val(meta), path('harmonized_evidence/harmonization_manifest.json'), emit: manifest
    tuple val(meta), path('evidence_harmonization.log'), emit: reports
    tuple val(meta), path('evidence_harmonization.versions.yml'), emit: versions
    tuple val(meta), path('evidence_harmonization.done'), emit: status

    script:
    """
    set -o pipefail
    harmonize_evidence.py \
        --rna-evidence-dir '${rna_evidence}' \
        --chip-evidence-dir '${chip_evidence}' \
        --policy '${policy}' \
        --output-dir harmonized_evidence \
        2>&1 | tee evidence_harmonization.log
    validate_molecular_integration.py harmonized_evidence/harmonization_manifest.json
    printf '"EVIDENCE_HARMONIZATION":\n    python: "%s"\n    harmonization_model: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > evidence_harmonization.versions.yml
    printf '{"id":"%s","process":"EVIDENCE_HARMONIZATION","status":"complete"}\n' '${meta.id}' > evidence_harmonization.done
    """

    stub:
    """
    mkdir -p harmonized_evidence
    printf 'source_assay\tsource_entity_id\tcanonical_entity_id\tentity_type\treference_id\tsymbol\taliases\tnormalization_rule\trule_class\n' > harmonized_evidence/entity_map.tsv
    printf 'canonical_contrast_id\tfactor\tnumerator\tdenominator\trna_contrast_ids\tchip_contrast_ids\tmapping_status\tnormalization_rule\n' > harmonized_evidence/contrast_map.tsv
    printf 'source_mark\tcanonical_mark\tnormalization_rule\trule_class\n' > harmonized_evidence/mark_map.tsv
    printf '{"schema_version":"1.0","harmonization_model_version":"1.0","type":"cross_assay_harmonization","id":"%s.harmonization","status":"stub","reference":{"reference_id":"stub"},"input_evidence_manifests":[{"id":"rna","assay":"rnaseq"},{"id":"chip","assay":"chipseq"}],"policy":{},"datasets":[],"provenance":{"provider":"stub"}}\n' '${meta.id}' > harmonized_evidence/harmonization_manifest.json
    printf '[STUB] Cross-Assay Harmonization\n' > evidence_harmonization.log
    printf '"EVIDENCE_HARMONIZATION":\n    python: stub\n    harmonization_model: "1.0"\n' > evidence_harmonization.versions.yml
    printf '{"id":"%s","process":"EVIDENCE_HARMONIZATION","status":"stub"}\n' '${meta.id}' > evidence_harmonization.done
    """
}
