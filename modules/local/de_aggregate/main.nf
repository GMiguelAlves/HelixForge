process DE_AGGREGATE {
    tag "${meta.id}"
    label 'native_module'
    label 'de_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.de_adapter_container
    conda "${moduleDir}/environment.yml"

    publishDir { meta.target_dir }, mode: 'copy', overwrite: true,
        pattern: '{DEGs_*.tsv,differential_expression_results.tsv,deg_summary.tsv,analysis_summary.txt,versions.yml,execution.json,de_manifest.json,differential_expression.done,contrasts,plots,dds_*.rds,normalized_counts_*.tsv,dispersions_*.tsv,coefficients_*.tsv}'
    publishDir "${params.outdir}/pipeline_info/native_de/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,txt,log,tsv,done}'

    input:
    tuple val(meta), path(skipped), path(analysis_spec)
    path models
    path contrasts

    output:
    tuple val(meta), path('DEGs_all_results.tsv'), path('DEGs_significant.tsv'),
        path('differential_expression_results.tsv'), path('deg_summary.tsv'),
        path('analysis_summary.txt'), path('contrasts'), path('plots'), emit: artifacts
    tuple val(meta), path('DEGs_all_results.tsv'), emit: results
    tuple val(meta), path('DEGs_significant.tsv'), emit: significant
    tuple val(meta), path('differential_expression_results.tsv'), emit: common_results
    tuple val(meta), path('deg_summary.tsv'), path('analysis_summary.txt'), emit: reports
    tuple val(meta), path('dds_*.rds'), emit: models, optional: true
    tuple val(meta), path('normalized_counts_*.tsv'), emit: normalized_counts, optional: true
    tuple val(meta), path('dispersions_*.tsv'), path('coefficients_*.tsv'), emit: model_statistics, optional: true
    tuple val(meta), path('versions.yml'), emit: versions
    tuple val(meta), path('execution.json'), emit: execution_metadata
    tuple val(meta), path('de_manifest.json'), emit: manifest
    tuple val(meta), path('differential_expression.done'), emit: status

    script:
    def outputDir = '.'
    def modelArgs = models.collect { model -> "'${model}'" }.join(' ')
    def contrastArgs = contrasts.collect { contrast -> "'${contrast}'" }.join(' ')
    def gitCommit = workflow.commitId ?: 'unknown'
    def profile = workflow.profile ?: ''
    """
    start_epoch=\$(date +%s)
    de_aggregate.py \
        --spec '${analysis_spec}' \
        --skipped '${skipped}' \
        --output-dir '${outputDir}' \
        --models ${modelArgs} \
        --contrasts ${contrastArgs}
    end_epoch=\$(date +%s)
    printf '{"id":"%s","process":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","git_commit":"%s","profile":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        '${params.de_adapter_container}' '${gitCommit}' '${profile}' "\$start_epoch" "\$end_epoch" \
        "\$((end_epoch-start_epoch))" > execution.json
    """

    stub:
    """
    mkdir -p contrasts plots
    printf 'analysis_id\tvariable\tcontrast\tlevel_a\tlevel_b\tgene_id\tbaseMean\tlog2FoldChange\tlfcSE\tstat\tpvalue\tpadj\tgene_name\tbiotype\nstub\tcondition\tcondition__control_vs_treated\tcontrol\ttreated\tgene_stub\t1\t0\t1\t0\t1\t1\tgene_stub\tUnknown\n' > DEGs_all_results.tsv
    cp DEGs_all_results.tsv DEGs_significant.tsv
    printf 'gene_id\tbaseMean\tlog2FoldChange\tlfcSE\tstatistic\tpvalue\tpadj\tcontrast\tdesign\ngene_stub\t1\t0\t1\t0\t1\t1\tcondition__control_vs_treated\t~ condition\n' > differential_expression_results.tsv
    printf 'analysis_id\tvariable\tcontrast\tstatus\tn_samples\tn_genes\tn_significant\nstub\tcondition\tcondition__control_vs_treated\tok\t2\t1\t0\n' > deg_summary.tsv
    printf 'Analise DEG - stub\n' > analysis_summary.txt
    printf '"DE_AGGREGATE":\n    python: "stub"\n' > versions.yml
    printf '{"id":"%s","process":"DE_AGGREGATE","status":"stub"}\n' '${meta.id}' > execution.json
    printf '{"schema_version":"1.0","type":"differential_expression","id":"%s","status":"stub","provider":"deseq2","test":"wald"}\n' '${meta.analysis_id ?: meta.id}' > de_manifest.json
    printf '{"id":"%s","process":"DE_AGGREGATE","status":"stub"}\n' '${meta.id}' > differential_expression.done
    """
}
