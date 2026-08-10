process DESEQ2_DB_MODEL {
    tag "${meta.id}"
    label 'native_module'
    label 'db_high'

    cpus 4
    memory 64.GB
    time 24.h
    queue { params.db_model_queue ?: null }
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.deseq2_apptainer_container : params.deseq2_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/differential_binding/models",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,txt,log,done}'

    input:
    tuple val(meta), path(counts_dir), path(count_spec), path(sample_table), path(model_spec), path(peak_bed), path(count_manifest)

    output:
    tuple val(meta), path("${meta.id}.db_model"), path(model_spec), path(peak_bed), emit: artifacts
    tuple val(meta), path("${meta.id}.db_model/model.log"), path("${meta.id}.db_model/model_statistics.json"), emit: reports
    tuple val(meta), path("${meta.id}.db_model/versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.db_model/execution.json"), path("${meta.id}.db_model/sessionInfo.txt"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.db_model/model_manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.db_model/db_model.done"), emit: status

    script:
    def modelDir = "${meta.id}.db_model"
    def gitCommit = workflow.commitId ?: 'unknown'
    def profile = workflow.profile ?: ''
    """
    mkdir -p '${modelDir}'
    start_epoch=\$(date +%s)
    deseq2_db_model.R \
        --counts '${counts_dir}/raw_peak_counts.tsv' \
        --samples '${sample_table}' \
        --spec '${model_spec}' \
        --peak-bed '${peak_bed}' \
        --output-dir '${modelDir}' \
        > '${modelDir}/model.log' 2>&1
    cp '${model_spec}' '${modelDir}/model_spec.json'
    cp '${count_spec}' '${modelDir}/count_spec.json'
    Rscript -e 'sessionInfo()' > '${modelDir}/sessionInfo.txt'
    counts_sha=\$(sha256sum '${counts_dir}/raw_peak_counts.tsv' | awk '{print \$1}')
    samples_sha=\$(sha256sum '${sample_table}' | awk '{print \$1}')
    model_spec_sha=\$(sha256sum '${model_spec}' | awk '{print \$1}')
    count_manifest_sha=\$(sha256sum '${count_manifest}' | awk '{print \$1}')
    dds_sha=\$(sha256sum '${modelDir}/dds.rds' | awk '{print \$1}')
    normalized_sha=\$(sha256sum '${modelDir}/normalized_peak_counts.tsv' | awk '{print \$1}')
    end_epoch=\$(date +%s)
    r_version=\$(Rscript -e 'cat(as.character(getRversion()))')
    deseq2_version=\$(Rscript -e 'cat(as.character(packageVersion("DESeq2")))')
    bioc_version=\$(Rscript -e 'cat(as.character(packageVersion("BiocVersion")))')
    printf '"DESEQ2_DB_MODEL":\n    r: "%s"\n    bioconductor: "%s"\n    deseq2: "%s"\n' "\$r_version" "\$bioc_version" "\$deseq2_version" > '${modelDir}/versions.yml'
    printf '{"schema_version":"1.0","id":"%s","process":"DESEQ2_DB_MODEL","cpus":%s,"memory_bytes":%s,"time":"%s","nextflow_version":"%s","profile":"%s","git_commit":"%s","counts_sha256":"%s","samples_sha256":"%s","model_spec_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' '${workflow.nextflow.version}' '${profile}' '${gitCommit}' \
        "\$counts_sha" "\$samples_sha" "\$model_spec_sha" "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > '${modelDir}/execution.json'
    printf '{"schema_version":"1.0","type":"differential_binding_model","id":"%s","provider":"deseq2","test":"wald","inputs":{"count_manifest_sha256":"%s","model_spec_sha256":"%s"},"artifacts":{"model":{"path":"dds.rds","sha256":"%s","available":true},"normalized_counts":{"path":"normalized_peak_counts.tsv","sha256":"%s","available":true}},"status":"complete"}\n' \
        '${meta.id}' "\$count_manifest_sha" "\$model_spec_sha" "\$dds_sha" "\$normalized_sha" > '${modelDir}/model_manifest.json'
    printf '{"id":"%s","process":"DESEQ2_DB_MODEL","status":"complete"}\n' '${meta.id}' > '${modelDir}/db_model.done'
    """

    stub:
    def modelDir = "${meta.id}.db_model"
    """
    mkdir -p '${modelDir}'
    printf 'stub-rds\n' > '${modelDir}/dds.rds'
    printf 'peak_id\tchrom\tstart\tend\tS1\tS2\npeak_000001\tchrStub\t4\t12\t10\t20\n' > '${modelDir}/normalized_peak_counts.tsv'
    printf 'peak_id\tdispersion\npeak_000001\t0.1\n' > '${modelDir}/dispersions.tsv'
    printf 'peak_id\tIntercept\npeak_000001\t1\n' > '${modelDir}/coefficients.tsv'
    cp '${model_spec}' '${modelDir}/model_spec.json'
    cp '${count_spec}' '${modelDir}/count_spec.json'
    printf '[STUB] DESeq2 differential-binding model\n' > '${modelDir}/model.log'
    printf '{"samples":4,"peaks_before_filter":1,"peaks_after_filter":1,"status":"stub"}\n' > '${modelDir}/model_statistics.json'
    printf 'stub\n' > '${modelDir}/sessionInfo.txt'
    printf '"DESEQ2_DB_MODEL":\n    r: stub\n    bioconductor: stub\n    deseq2: stub\n' > '${modelDir}/versions.yml'
    printf '{"id":"%s","process":"DESEQ2_DB_MODEL","status":"stub"}\n' '${meta.id}' > '${modelDir}/execution.json'
    printf '{"schema_version":"1.0","type":"differential_binding_model","id":"%s","provider":"deseq2","test":"wald","status":"stub"}\n' '${meta.id}' > '${modelDir}/model_manifest.json'
    printf '{"id":"%s","process":"DESEQ2_DB_MODEL","status":"stub"}\n' '${meta.id}' > '${modelDir}/db_model.done'
    """
}
