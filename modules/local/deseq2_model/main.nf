process DESEQ2_MODEL {
    tag "${meta.id}"
    label 'native_module'
    label 'de_high'

    cpus 4
    memory 64.GB
    time 24.h
    queue { params.deseq2_model_queue ?: null }
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.deseq2_apptainer_container : params.deseq2_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_de/models",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,txt,log,done}'

    input:
    tuple val(meta), path(counts), path(sample_metadata), path(model_spec), path(annotation)

    output:
    tuple val(meta), path("${meta.id}.model"), path(model_spec), path(annotation), emit: artifacts
    tuple val(meta), path("${meta.id}.model/model.log"), path("${meta.id}.model/model_statistics.json"), emit: reports
    tuple val(meta), path("${meta.id}.model/versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.model/execution.json"), path("${meta.id}.model/sessionInfo.txt"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.model/model_manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.model/deseq2_model.done"), emit: status

    script:
    def modelDir = "${meta.id}.model"
    def gitCommit = workflow.commitId ?: 'unknown'
    def profile = workflow.profile ?: ''
    """
    mkdir -p '${modelDir}'
    start_epoch=\$(date +%s)
    deseq2_model.R \
        --counts '${counts}' \
        --samples '${sample_metadata}' \
        --spec '${model_spec}' \
        --output-dir '${modelDir}' \
        > '${modelDir}/model.log' 2>&1
    cp '${model_spec}' '${modelDir}/model_spec.json'
    Rscript -e 'sessionInfo()' > '${modelDir}/sessionInfo.txt'

    counts_sha=\$(sha256sum '${counts}' | awk '{print \$1}')
    samples_sha=\$(sha256sum '${sample_metadata}' | awk '{print \$1}')
    spec_sha=\$(sha256sum '${model_spec}' | awk '{print \$1}')
    dds_sha=\$(sha256sum '${modelDir}'/dds_*.rds | awk '{print \$1}')
    normalized_sha=\$(sha256sum '${modelDir}'/normalized_counts_*.tsv | awk '{print \$1}')
    dispersions_sha=\$(sha256sum '${modelDir}'/dispersions_*.tsv | awk '{print \$1}')
    coefficients_sha=\$(sha256sum '${modelDir}'/coefficients_*.tsv | awk '{print \$1}')
    end_epoch=\$(date +%s)

    r_version=\$(Rscript -e 'cat(as.character(getRversion()))')
    deseq2_version=\$(Rscript -e 'cat(as.character(packageVersion("DESeq2")))')
    bioc_version=\$(Rscript -e 'cat(as.character(packageVersion("BiocVersion")))')
    printf '"%s":\n    r: "%s"\n    bioconductor: "%s"\n    deseq2: "%s"\n' \
        '${task.process}' "\$r_version" "\$bioc_version" "\$deseq2_version" \
        > '${modelDir}/versions.yml'
    printf '{"id":"%s","process":"%s","cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","git_commit":"%s","profile":"%s","counts_sha256":"%s","sample_metadata_sha256":"%s","design_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        '${params.deseq2_container}' '${gitCommit}' '${profile}' "\$counts_sha" "\$samples_sha" \
        "\$spec_sha" "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" \
        > '${modelDir}/execution.json'
    dds_name=\$(basename \$(find '${modelDir}' -maxdepth 1 -name 'dds_*.rds' -print -quit))
    normalized_name=\$(basename \$(find '${modelDir}' -maxdepth 1 -name 'normalized_counts_*.tsv' -print -quit))
    printf '{"schema_version":"1.0","type":"differential_expression_model","id":"%s","status":"complete","provider":"deseq2","test":"wald","inputs":{"counts_sha256":"%s","sample_metadata_sha256":"%s","design_sha256":"%s"},"artifacts":{"model":{"path":"%s","sha256":"%s","available":true},"normalized_counts":{"path":"%s","sha256":"%s","available":true},"dispersions":{"sha256":"%s","available":true},"coefficients":{"sha256":"%s","available":true}}}\n' \
        '${meta.id}' "\$counts_sha" "\$samples_sha" "\$spec_sha" "\$dds_name" "\$dds_sha" \
        "\$normalized_name" "\$normalized_sha" "\$dispersions_sha" "\$coefficients_sha" \
        > '${modelDir}/model_manifest.json'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > '${modelDir}/deseq2_model.done'
    """

    stub:
    def modelDir = "${meta.id}.model"
    """
    mkdir -p '${modelDir}/plots'
    printf 'stub-rds\n' > '${modelDir}/dds_stub.rds'
    printf '\tS1\ngene_stub\t1\n' > '${modelDir}/normalized_counts_stub.tsv'
    printf 'gene_id\tdispersion\ngene_stub\t0.1\n' > '${modelDir}/dispersions_stub.tsv'
    printf 'gene_id\tIntercept\ngene_stub\t1\n' > '${modelDir}/coefficients_stub.tsv'
    printf 'stub\n' > '${modelDir}/plots/PCA_stub.png'
    printf 'stub\n' > '${modelDir}/plots/heatmap_top100_stub.png'
    printf '[STUB] DESeq2 model\n' > '${modelDir}/model.log'
    printf '{"samples":2,"genes_before_filter":1,"genes_after_filter":1}\n' > '${modelDir}/model_statistics.json'
    printf 'stub\n' > '${modelDir}/sessionInfo.txt'
    printf '"DESEQ2_MODEL":\n    r: "stub"\n    bioconductor: "stub"\n    deseq2: "stub"\n' > '${modelDir}/versions.yml'
    printf '{"id":"%s","process":"DESEQ2_MODEL","status":"stub"}\n' '${meta.id}' > '${modelDir}/execution.json'
    printf '{"schema_version":"1.0","type":"differential_expression_model","id":"%s","status":"stub","provider":"deseq2","test":"wald"}\n' '${meta.id}' > '${modelDir}/model_manifest.json'
    printf '{"id":"%s","process":"DESEQ2_MODEL","status":"stub"}\n' '${meta.id}' > '${modelDir}/deseq2_model.done'
    """
}
