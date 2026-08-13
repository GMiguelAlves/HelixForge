process RNASEQ_REPORT_CONTEXT {
    tag "${meta.id}"
    label 'native_module'
    label 'report_low'

    cpus 1
    memory 1.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.rnaseq_report_context_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_rnaseq/report/context",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,log}'

    input:
    tuple val(meta),
        path(import_manifest, stageAs: 'upstream/import_manifest.json'),
        path(abundance, stageAs: 'inputs/abundance.tsv'),
        path(samples, stageAs: 'inputs/quant_samples.tsv'),
        path(annotation, stageAs: 'inputs/annotation.gtf'),
        path(de_results, stageAs: 'inputs/DEGs_all_results.tsv'),
        path(de_manifest, stageAs: 'upstream/de_manifest.json'),
        path(genes, stageAs: 'inputs/genes.txt'),
        val(report_params)

    output:
    tuple val(meta), path('report_context.json'), path('report.env'),
        path('upstream/import_manifest.json'), path('inputs/abundance.tsv'),
        path('inputs/quant_samples.tsv'), path('inputs/annotation.gtf'),
        path('inputs/DEGs_all_results.tsv'), path('upstream/de_manifest.json'),
        path('inputs/genes.txt'), emit: artifacts
    tuple val(meta), path('rnaseq_report_context.log'), emit: reports
    tuple val(meta), path('rnaseq_report_context.versions.yml'), emit: versions
    tuple val(meta), path('rnaseq_report_context.done'), emit: status

    script:
    """
    validate_rnaseq_report_context.py \
        --id '${meta.id}' \
        --provider '${meta.provider}' \
        --import-manifest '${import_manifest}' \
        --abundance '${abundance}' \
        --samples '${samples}' \
        --annotation '${annotation}' \
        --de-results '${de_results}' \
        --de-manifest '${de_manifest}' \
        --genes '${genes}' \
        --parameters-base64 '${report_params}' \
        --output report_context.json \
        --environment report.env \
        > rnaseq_report_context.log 2>&1
    printf '"%s":\n    python: "%s"\n' '${task.process}' "\$(python3 --version | awk '{print \$2}')" \
        > rnaseq_report_context.versions.yml
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > rnaseq_report_context.done
    """

    stub:
    """
    printf '{"schema_version":"1.0","type":"rnaseq_report_context","id":"%s","provider":"candidate_genes_v1","status":"stub","sample_count":1,"gene_count":1,"query_count":1}\n' \
        '${meta.id}' > report_context.json
    printf 'export REPORT_TITLE=%s\nexport EXPRESSION_UNIT=TPM\nexport LIFE_STAGE_LEVELS=unknown\nexport STAGE_SYNONYM_MAP=%s\nexport ORGANISM_SPECIFIC_REPORTS=0\n' \
        "'Candidate gene report'" "''" > report.env
    printf '[STUB] RNA-seq report context\n' > rnaseq_report_context.log
    printf '"RNASEQ_REPORT_CONTEXT":\n    python: stub\n' > rnaseq_report_context.versions.yml
    printf '{"id":"%s","process":"RNASEQ_REPORT_CONTEXT","status":"stub"}\n' \
        '${meta.id}' > rnaseq_report_context.done
    """
}
