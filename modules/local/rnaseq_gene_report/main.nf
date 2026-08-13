process RNASEQ_GENE_REPORT {
    tag "${meta.id}"
    label 'native_module'
    label 'report_medium'

    cpus 2
    memory 32.GB
    time 4.h
    queue { params.rnaseq_report_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.rnaseq_report_apptainer_container : params.rnaseq_report_container}"
    conda "${moduleDir}/environment.yml"

    publishDir { meta.target_dir }, mode: 'copy', overwrite: true, pattern: 'results'
    publishDir "${params.outdir}/pipeline_info/native_rnaseq/report/provider",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,txt,done,log}'

    input:
    tuple val(meta), path(context), path(report_environment),
        path(import_manifest), path(abundance), path(samples), path(annotation),
        path(de_results), path(de_manifest), path(genes)

    output:
    tuple val(meta), path('results'), emit: artifacts
    tuple val(meta), path('results/gene_set_report.html'), emit: html
    tuple val(meta), path('results/tables'), emit: tables
    tuple val(meta), path('results/plots'), emit: plots
    tuple val(meta), path('rnaseq_gene_report.execution.json'), path('rnaseq_gene_report.log'), emit: reports
    tuple val(meta), path('rnaseq_gene_report.versions.yml'), emit: versions
    tuple val(meta), path('results/manifest.json'), emit: manifest
    tuple val(meta), path('rnaseq_gene_report.done'), emit: status

    script:
    def gitCommit = workflow.commitId ?: 'unknown'
    def profile = workflow.profile ?: ''
    """
    set -o pipefail
    source '${report_environment}'
    mkdir -p de_inputs results
    cp '${de_results}' de_inputs/DEGs_all_results.tsv
    start_epoch=\$(date +%s)
    gene_set_report.R \
        --genes '${genes}' \
        --tpm '${abundance}' \
        --expression-unit "\$EXPRESSION_UNIT" \
        --samples '${samples}' \
        --metadata '${samples}' \
        --deg-root de_inputs \
        --gff '${annotation}' \
        --output-dir results \
        --title "\$REPORT_TITLE" \
        > rnaseq_gene_report.log 2>&1
    end_epoch=\$(date +%s)
    Rscript -e 'sessionInfo()' > rnaseq_gene_report.sessionInfo.txt
    finalize_rnaseq_report.py \
        --id '${meta.id}' \
        --provider '${meta.provider}' \
        --context '${context}' \
        --results results \
        --execution rnaseq_gene_report.execution.json \
        --versions rnaseq_gene_report.versions.yml \
        --session-info rnaseq_gene_report.sessionInfo.txt \
        --container '${params.rnaseq_report_container}' \
        --git-commit '${gitCommit}' \
        --profile '${profile}' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --started-epoch "\$start_epoch" \
        --ended-epoch "\$end_epoch"
    cp rnaseq_gene_report.execution.json results/execution.json
    cp rnaseq_gene_report.versions.yml results/versions.yml
    cp rnaseq_gene_report.sessionInfo.txt results/sessionInfo.txt
    cp rnaseq_gene_report.log results/report.log
    cp '${context}' results/context.json
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > rnaseq_gene_report.done
    """

    stub:
    """
    mkdir -p results/tables results/plots results/genes results/groups
    printf '<!doctype html><html><head><title>Candidate gene report</title></head><body><h1>Candidate gene report</h1></body></html>\n' > results/gene_set_report.html
    printf 'group\tquery\tgene_id\nCandidates\tgene_stub\tgene_stub\n' > results/tables/gene_catalog.tsv
    printf 'stub\n' > results/plots/expression_heatmap.png
    printf '{"schema_version":"1.0","type":"rnaseq_report","id":"%s","provider":"candidate_genes_v1","status":"stub","artifacts":{"html":{"path":"gene_set_report.html"},"tables":{"path":"tables"},"plots":{"path":"plots"}}}\n' \
        '${meta.id}' > results/manifest.json
    printf '{"id":"%s","process":"RNASEQ_GENE_REPORT","status":"stub"}\n' '${meta.id}' > rnaseq_gene_report.execution.json
    printf '"RNASEQ_GENE_REPORT":\n    r: stub\n    provider: candidate_genes_v1\n' > rnaseq_gene_report.versions.yml
    printf 'stub\n' > rnaseq_gene_report.sessionInfo.txt
    printf '[STUB] RNA-seq gene report\n' > rnaseq_gene_report.log
    cp rnaseq_gene_report.execution.json results/execution.json
    cp rnaseq_gene_report.versions.yml results/versions.yml
    cp rnaseq_gene_report.sessionInfo.txt results/sessionInfo.txt
    cp rnaseq_gene_report.log results/report.log
    cp '${context}' results/context.json
    printf '{"id":"%s","process":"RNASEQ_GENE_REPORT","status":"stub"}\n' '${meta.id}' > rnaseq_gene_report.done
    """
}
