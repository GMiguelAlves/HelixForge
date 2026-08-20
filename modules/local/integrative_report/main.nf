process INTEGRATIVE_REPORT {
    tag "${meta.id}"
    label 'native_module'
    label 'integration_low'
    cpus 1
    memory 3.GB
    time 45.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0
    container params.integrative_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/integration/100-report", mode: 'copy', overwrite: true, pattern: 'integrative_report'
    publishDir "${params.outdir}/pipeline_info/integration/report", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(inputs, stageAs: 'integrative_inputs'), path(rna_evidence, stageAs: 'rnaseq_evidence'), path(chip_evidence, stageAs: 'chipseq_evidence'), path(harmonization, stageAs: 'harmonized_evidence'), path(integration, stageAs: 'integrated_evidence'), path(interpretation, stageAs: 'interpretation'), path(functional, stageAs: 'functional_analysis'), path(visualization, stageAs: 'integrative_visualization'), val(title)

    output:
    tuple val(meta), path('integrative_report'), emit: artifacts
    tuple val(meta), path('integrative_report/report_manifest.json'), emit: manifest
    tuple val(meta), path('integrative_report/integrative_report.html'), emit: html
    tuple val(meta), path('integrative_report.log'), emit: reports
    tuple val(meta), path('integrative_report.versions.yml'), emit: versions
    tuple val(meta), path('integrative_report.done'), emit: status

    script:
    """
    set -o pipefail
    render_integrative_report.py --input-dir '${inputs}' --rna-evidence-dir '${rna_evidence}' --chip-evidence-dir '${chip_evidence}' --harmonization-dir '${harmonization}' --integration-dir '${integration}' --interpretation-dir '${interpretation}' --functional-dir '${functional}' --visualization-dir '${visualization}' --title '${title}' --output-dir integrative_report 2>&1 | tee integrative_report.log
    printf '"INTEGRATIVE_REPORT":\n    python: "%s"\n    report_model: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > integrative_report.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_REPORT","status":"complete"}\n' '${meta.id}' > integrative_report.done
    """

    stub:
    """
    mkdir -p integrative_report
    printf '# HelixForge Integrative Report\n' > integrative_report/integrative_report.md
    printf '<!doctype html><html><body><h1>HelixForge Integrative Report</h1><p>stub</p></body></html>\n' > integrative_report/integrative_report.html
    printf 'rank\tcanonical_entity_id\n' > integrative_report/candidate_explorer.tsv
    printf '{"schema_version":"1.0","report_model_version":"1.0","type":"integrative_report","id":"%s.report","status":"stub","science_recalculated":false,"sections":[],"datasets":[],"record_counts":{},"provenance":{"provider":"stub"}}\n' '${meta.id}' > integrative_report/report_manifest.json
    printf '[STUB] Integrative Report\n' > integrative_report.log
    printf '"INTEGRATIVE_REPORT":\n    python: stub\n    report_model: "1.0"\n' > integrative_report.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_REPORT","status":"stub"}\n' '${meta.id}' > integrative_report.done
    """
}
