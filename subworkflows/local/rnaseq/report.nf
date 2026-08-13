include { RNASEQ_REPORT_CONTEXT } from '../../../modules/local/rnaseq_report_context/main'
include { RNASEQ_GENE_REPORT }     from '../../../modules/local/rnaseq_gene_report/main'

workflow RNASEQ_REPORT {
    take:
    requests
    report_script

    main:
    RNASEQ_REPORT_CONTEXT(requests)
    RNASEQ_GENE_REPORT(RNASEQ_REPORT_CONTEXT.out.artifacts, report_script)

    emit:
    artifacts = RNASEQ_GENE_REPORT.out.artifacts
    html      = RNASEQ_GENE_REPORT.out.html
    tables    = RNASEQ_GENE_REPORT.out.tables
    plots     = RNASEQ_GENE_REPORT.out.plots
    manifest  = RNASEQ_GENE_REPORT.out.manifest
    reports   = RNASEQ_REPORT_CONTEXT.out.reports.mix(RNASEQ_GENE_REPORT.out.reports)
    versions  = RNASEQ_REPORT_CONTEXT.out.versions.mix(RNASEQ_GENE_REPORT.out.versions)
    status    = RNASEQ_GENE_REPORT.out.status
}
