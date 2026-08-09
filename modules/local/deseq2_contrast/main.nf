process DESEQ2_CONTRAST {
    tag "${meta.id}"
    label 'native_module'
    label 'de_medium'

    cpus 2
    memory 16.GB
    time 4.h
    queue { params.deseq2_contrast_queue ?: null }
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.deseq2_apptainer_container : params.deseq2_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_de/contrasts",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,txt,log,done}'

    input:
    tuple val(meta), path(model), path(model_spec), path(contrast_spec), path(annotation)

    output:
    tuple val(meta), path("${meta.id}.contrast"), emit: artifacts
    tuple val(meta), path("${meta.id}.contrast/DEG_*.tsv"), emit: results
    tuple val(meta), path("${meta.id}.contrast/common_results.tsv"), emit: common_results
    tuple val(meta), path("${meta.id}.contrast/contrast.log"), path("${meta.id}.contrast/contrast_statistics.json"), emit: reports
    tuple val(meta), path("${meta.id}.contrast/versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.contrast/execution.json"), path("${meta.id}.contrast/sessionInfo.txt"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.contrast/contrast_manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.contrast/deseq2_contrast.done"), emit: status

    script:
    def outputDir = "${meta.id}.contrast"
    def gitCommit = workflow.commitId ?: 'unknown'
    def profile = workflow.profile ?: ''
    """
    mkdir -p '${outputDir}'
    start_epoch=\$(date +%s)
    deseq2_contrast.R \
        --model-dir '${model}' \
        --model-spec '${model_spec}' \
        --contrast-spec '${contrast_spec}' \
        --annotation '${annotation}' \
        --output-dir '${outputDir}' \
        > '${outputDir}/contrast.log' 2>&1
    cp '${model_spec}' '${outputDir}/model_spec.json'
    cp '${contrast_spec}' '${outputDir}/contrast_spec.json'
    Rscript -e 'sessionInfo()' > '${outputDir}/sessionInfo.txt'

    model_sha=\$(sha256sum '${model}'/dds_*.rds | awk '{print \$1}')
    contrast_sha=\$(sha256sum '${contrast_spec}' | awk '{print \$1}')
    result_file=\$(find '${outputDir}' -maxdepth 1 -name 'DEG_*.tsv' -print -quit)
    result_sha=\$(sha256sum "\$result_file" | awk '{print \$1}')
    common_sha=\$(sha256sum '${outputDir}/common_results.tsv' | awk '{print \$1}')
    end_epoch=\$(date +%s)
    r_version=\$(Rscript -e 'cat(as.character(getRversion()))')
    deseq2_version=\$(Rscript -e 'cat(as.character(packageVersion("DESeq2")))')
    printf '"%s":\n    r: "%s"\n    bioconductor: "3.18"\n    deseq2: "%s"\n' \
        '${task.process}' "\$r_version" "\$deseq2_version" > '${outputDir}/versions.yml'
    printf '{"id":"%s","process":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","git_commit":"%s","profile":"%s","model_sha256":"%s","contrast_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        '${params.deseq2_container}' '${gitCommit}' '${profile}' "\$model_sha" "\$contrast_sha" \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > '${outputDir}/execution.json'
    printf '{"schema_version":"1.0","type":"differential_expression_contrast","id":"%s","provider":"deseq2","test":"wald","inputs":{"model_sha256":"%s","contrast_sha256":"%s"},"artifacts":{"results":{"path":"%s","sha256":"%s","available":true},"common_results":{"path":"common_results.tsv","sha256":"%s","available":true}}}\n' \
        '${meta.id}' "\$model_sha" "\$contrast_sha" "\$(basename "\$result_file")" "\$result_sha" "\$common_sha" \
        > '${outputDir}/contrast_manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${outputDir}/deseq2_contrast.done'
    """

    stub:
    def outputDir = "${meta.id}.contrast"
    """
    mkdir -p '${outputDir}'
    printf 'analysis_id\tvariable\tcontrast\tlevel_a\tlevel_b\tgene_id\tbaseMean\tlog2FoldChange\tlfcSE\tstat\tpvalue\tpadj\tgene_name\tbiotype\nstub\tcondition\tcondition__control_vs_treated\tcontrol\ttreated\tgene_stub\t1\t0\t1\t0\t1\t1\tgene_stub\tUnknown\n' > '${outputDir}/DEG_stub.tsv'
    printf 'gene_id\tbaseMean\tlog2FoldChange\tlfcSE\tstatistic\tpvalue\tpadj\tcontrast\tdesign\ngene_stub\t1\t0\t1\t0\t1\t1\tcondition__control_vs_treated\t~ condition\n' > '${outputDir}/common_results.tsv'
    printf '[STUB] DESeq2 contrast\n' > '${outputDir}/contrast.log'
    printf '{"samples":2,"genes":1,"significant":0}\n' > '${outputDir}/contrast_statistics.json'
    printf 'stub\n' > '${outputDir}/volcano_stub.png'
    printf 'stub\n' > '${outputDir}/sessionInfo.txt'
    printf '"DESEQ2_CONTRAST":\n    r: "stub"\n    bioconductor: "stub"\n    deseq2: "stub"\n' > '${outputDir}/versions.yml'
    printf '{"id":"%s","process":"DESEQ2_CONTRAST","status":"stub"}\n' '${meta.id}' > '${outputDir}/execution.json'
    printf '{"schema_version":"1.0","type":"differential_expression_contrast","id":"%s","provider":"deseq2","test":"wald"}\n' '${meta.id}' > '${outputDir}/contrast_manifest.json'
    printf '{"id":"%s","process":"DESEQ2_CONTRAST","status":"stub"}\n' '${meta.id}' > '${outputDir}/deseq2_contrast.done'
    """
}
