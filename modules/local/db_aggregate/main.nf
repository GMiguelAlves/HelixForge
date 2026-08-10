process DB_AGGREGATE {
    tag "${meta.id}"
    label 'native_module'
    label 'db_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.db_adapter_container
    conda "${moduleDir}/environment.yml"

    publishDir { params.chipseq_db_target_dir ?: "${params.outdir}/chipseq/differential_binding" },
        mode: 'copy', overwrite: true, pattern: 'differential_binding_results'
    publishDir "${params.outdir}/pipeline_info/native_chipseq/differential_binding/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done}'

    input:
    tuple val(meta), path(counts), path(models), path(contrasts), path(db_spec)

    output:
    tuple val(meta), path('differential_binding_results'), emit: artifacts
    tuple val(meta), path('differential_binding_results/differential_binding_results.tsv'), emit: results
    tuple val(meta), path('differential_binding_results/differential_binding_summary.tsv'), emit: reports
    tuple val(meta), path('db_aggregate.versions.yml'), emit: versions
    tuple val(meta), path('db_aggregate.execution.json'), emit: execution_metadata
    tuple val(meta), path('db_manifest.json'), emit: manifest
    tuple val(meta), path('db_aggregate.done'), emit: status

    script:
    def countArgs = counts.collect { directory -> "--counts '${directory}'" }.join(' ')
    def modelArgs = models.collect { directory -> "--model '${directory}'" }.join(' ')
    def contrastArgs = contrasts.collect { directory -> "--contrast '${directory}'" }.join(' ')
    def gitCommit = workflow.commitId ?: 'unknown'
    def profile = workflow.profile ?: ''
    """
    start_epoch=\$(date +%s)
    db_aggregate.py \
        ${countArgs} \
        ${modelArgs} \
        ${contrastArgs} \
        --spec '${db_spec}' \
        --output-dir differential_binding_results \
        --manifest db_manifest.json
    end_epoch=\$(date +%s)
    printf '"DB_AGGREGATE":\n    python: "%s"\n' "\$(python3 --version | awk '{print \$2}')" > db_aggregate.versions.yml
    printf '{"schema_version":"1.0","id":"%s","process":"DB_AGGREGATE","cpus":%s,"memory_bytes":%s,"time":"%s","nextflow_version":"%s","profile":"%s","git_commit":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' '${workflow.nextflow.version}' '${profile}' '${gitCommit}' \
        "\$start_epoch" "\$end_epoch" "\$((end_epoch-start_epoch))" > db_aggregate.execution.json
    cp db_aggregate.execution.json differential_binding_results/execution.json
    cp db_aggregate.versions.yml differential_binding_results/versions.yml
    cp db_manifest.json differential_binding_results/manifest.json
    printf '{"id":"%s","process":"DB_AGGREGATE","status":"complete"}\n' '${meta.id}' > db_aggregate.done
    cp db_aggregate.done differential_binding_results/status.json
    """

    stub:
    """
    mkdir -p differential_binding_results/counts differential_binding_results/models differential_binding_results/contrasts
    printf 'analysis_id\tpeak_id\tchrom\tstart\tend\tbaseMean\tlog2FoldChange\tlfcSE\tstat\tpvalue\tpadj\tcontrast\tnumerator\tdenominator\tdesign\tsignificant\nstub.condition\tpeak_000001\tchrStub\t4\t12\t15\t1\t0.5\t2\t0.05\t0.1\ttreated_vs_control\ttreated\tcontrol\t~ condition\tfalse\n' > differential_binding_results/differential_binding_results.tsv
    printf 'analysis_id\tcontrast\tsamples\tpeaks\tsignificant\tstatus\nstub.condition\ttreated_vs_control\t4\t1\t0\tstub\n' > differential_binding_results/differential_binding_summary.tsv
    printf '"DB_AGGREGATE":\n    python: stub\n' > db_aggregate.versions.yml
    printf '{"id":"%s","process":"DB_AGGREGATE","status":"stub"}\n' '${meta.id}' > db_aggregate.execution.json
    printf '{"schema_version":"1.0","type":"differential_binding","id":"%s","analyses":1,"contrasts":1,"status":"stub"}\n' '${meta.id}' > db_manifest.json
    cp db_aggregate.versions.yml differential_binding_results/versions.yml
    cp db_aggregate.execution.json differential_binding_results/execution.json
    cp db_manifest.json differential_binding_results/manifest.json
    printf '{"id":"%s","process":"DB_AGGREGATE","status":"stub"}\n' '${meta.id}' > db_aggregate.done
    cp db_aggregate.done differential_binding_results/status.json
    """
}
