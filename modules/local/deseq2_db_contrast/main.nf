process DESEQ2_DB_CONTRAST {
    tag "${meta.id}"
    label 'native_module'
    label 'db_medium'

    cpus 2
    memory 16.GB
    time 4.h
    queue { params.db_contrast_queue ?: null }
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.deseq2_apptainer_container : params.deseq2_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/differential_binding/contrasts",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,txt,log,done}'

    input:
    tuple val(meta), path(model_dir), path(model_spec), path(contrast_spec), path(peak_bed)

    output:
    tuple val(meta), path("${meta.id}.db_contrast"), emit: artifacts
    tuple val(meta), path("${meta.id}.db_contrast/differential_binding_results.tsv"), emit: results
    tuple val(meta), path("${meta.id}.db_contrast/ma_plot_data.tsv"), emit: ma_data
    tuple val(meta), path("${meta.id}.db_contrast/contrast.log"), path("${meta.id}.db_contrast/contrast_statistics.json"), emit: reports
    tuple val(meta), path("${meta.id}.db_contrast/versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.db_contrast/execution.json"), path("${meta.id}.db_contrast/sessionInfo.txt"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.db_contrast/contrast_manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.db_contrast/db_contrast.done"), emit: status

    script:
    def outputDir = "${meta.id}.db_contrast"
    def gitCommit = workflow.commitId ?: 'unknown'
    def profile = workflow.profile ?: ''
    """
    mkdir -p '${outputDir}'
    start_epoch=\$(date +%s)
    deseq2_db_contrast.R \
        --model-dir '${model_dir}' \
        --model-spec '${model_spec}' \
        --contrast-spec '${contrast_spec}' \
        --peak-bed '${peak_bed}' \
        --output-dir '${outputDir}' \
        > '${outputDir}/contrast.log' 2>&1
    cp '${model_spec}' '${outputDir}/model_spec.json'
    cp '${contrast_spec}' '${outputDir}/contrast_spec.json'
    Rscript -e 'sessionInfo()' > '${outputDir}/sessionInfo.txt'
    model_sha=\$(sha256sum '${model_dir}/dds.rds' | awk '{print \$1}')
    contrast_sha=\$(sha256sum '${contrast_spec}' | awk '{print \$1}')
    result_sha=\$(sha256sum '${outputDir}/differential_binding_results.tsv' | awk '{print \$1}')
    ma_sha=\$(sha256sum '${outputDir}/ma_plot_data.tsv' | awk '{print \$1}')
    end_epoch=\$(date +%s)
    r_version=\$(Rscript -e 'cat(as.character(getRversion()))')
    deseq2_version=\$(Rscript -e 'cat(as.character(packageVersion("DESeq2")))')
    bioc_version=\$(Rscript -e 'cat(as.character(packageVersion("BiocVersion")))')
    printf '"DESEQ2_DB_CONTRAST":\n    r: "%s"\n    bioconductor: "%s"\n    deseq2: "%s"\n' "\$r_version" "\$bioc_version" "\$deseq2_version" > '${outputDir}/versions.yml'
    printf '{"schema_version":"1.0","id":"%s","process":"DESEQ2_DB_CONTRAST","cpus":%s,"memory_bytes":%s,"time":"%s","nextflow_version":"%s","profile":"%s","git_commit":"%s","model_sha256":"%s","contrast_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' '${workflow.nextflow.version}' '${profile}' '${gitCommit}' \
        "\$model_sha" "\$contrast_sha" "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > '${outputDir}/execution.json'
    printf '{"schema_version":"1.0","type":"differential_binding_contrast","id":"%s","provider":"deseq2","test":"wald","inputs":{"model_sha256":"%s","contrast_sha256":"%s"},"artifacts":{"results":{"path":"differential_binding_results.tsv","sha256":"%s","available":true},"ma_data":{"path":"ma_plot_data.tsv","sha256":"%s","available":true}},"status":"complete"}\n' \
        '${meta.id}' "\$model_sha" "\$contrast_sha" "\$result_sha" "\$ma_sha" > '${outputDir}/contrast_manifest.json'
    printf '{"id":"%s","process":"DESEQ2_DB_CONTRAST","status":"complete"}\n' '${meta.id}' > '${outputDir}/db_contrast.done'
    """

    stub:
    def outputDir = "${meta.id}.db_contrast"
    """
    mkdir -p '${outputDir}'
    printf 'peak_id\tchrom\tstart\tend\tbaseMean\tlog2FoldChange\tlfcSE\tstat\tpvalue\tpadj\tcontrast\tnumerator\tdenominator\tdesign\tsignificant\npeak_000001\tchrStub\t4\t12\t15\t1\t0.5\t2\t0.05\t0.1\t%s\ttreated\tcontrol\t~ condition\tfalse\n' '${meta.contrast_id}' > '${outputDir}/differential_binding_results.tsv'
    cp '${outputDir}/differential_binding_results.tsv' '${outputDir}/ma_plot_data.tsv'
    cp '${model_spec}' '${outputDir}/model_spec.json'
    cp '${contrast_spec}' '${outputDir}/contrast_spec.json'
    printf '[STUB] DESeq2 differential-binding contrast\n' > '${outputDir}/contrast.log'
    printf '{"samples":4,"peaks":1,"significant":0,"status":"stub"}\n' > '${outputDir}/contrast_statistics.json'
    printf 'stub\n' > '${outputDir}/sessionInfo.txt'
    printf '"DESEQ2_DB_CONTRAST":\n    r: stub\n    bioconductor: stub\n    deseq2: stub\n' > '${outputDir}/versions.yml'
    printf '{"id":"%s","process":"DESEQ2_DB_CONTRAST","status":"stub"}\n' '${meta.id}' > '${outputDir}/execution.json'
    printf '{"schema_version":"1.0","type":"differential_binding_contrast","id":"%s","provider":"deseq2","test":"wald","status":"stub"}\n' '${meta.id}' > '${outputDir}/contrast_manifest.json'
    printf '{"id":"%s","process":"DESEQ2_DB_CONTRAST","status":"stub"}\n' '${meta.id}' > '${outputDir}/db_contrast.done'
    """
}
