process PEAK_ANNOTATION_AGGREGATE {
    tag "${meta.id}"
    label 'native_module'
    label 'peak_annotation_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_peak_annotation_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_annotation/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done}'
    publishDir "${params.outdir}/chipseq/peak_annotation",
        mode: 'copy', overwrite: true, pattern: 'peak_annotation_aggregate'

    input:
    tuple val(meta), path(annotation_dirs), path(annotation_manifests), path(statistics_json), path(statistics_manifests)

    output:
    tuple val(meta), path('peak_annotation_aggregate'), emit: artifacts
    tuple val(meta), path('peak_annotation_aggregate/statistics.tsv'), emit: reports
    tuple val(meta), path('peak_annotation_aggregate.versions.yml'), emit: versions
    tuple val(meta), path('peak_annotation_aggregate.execution.json'), emit: execution_metadata
    tuple val(meta), path('peak_annotation_aggregate.manifest.json'), emit: manifest
    tuple val(meta), path('peak_annotation_aggregate.done'), emit: status

    script:
    def dirArgs = annotation_dirs.collect { value -> "--annotation-dir '${value}'" }.join(' ')
    def manifestArgs = annotation_manifests.collect { value -> "--annotation-manifest '${value}'" }.join(' ')
    def statisticsArgs = statistics_json.collect { value -> "--statistics-json '${value}'" }.join(' ')
    def statisticsManifestArgs = statistics_manifests.collect { value -> "--statistics-manifest '${value}'" }.join(' ')
    """
    peak_annotation_aggregate.py \
        ${dirArgs} \
        ${manifestArgs} \
        ${statisticsArgs} \
        ${statisticsManifestArgs} \
        --output-dir peak_annotation_aggregate \
        --manifest peak_annotation_aggregate.manifest.json \
        --execution peak_annotation_aggregate.execution.json \
        --versions peak_annotation_aggregate.versions.yml \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}'
    printf '{"id":"%s","process":"PEAK_ANNOTATION_AGGREGATE","status":"complete"}\n' '${meta.id}' > peak_annotation_aggregate.done
    """

    stub:
    """
    mkdir -p peak_annotation_aggregate
    printf 'annotation_id\tpeak_id\tchrom\tstart\tend\tcategory\tgene_ids\tgene_count\tdistance_to_tss\trecord_id\tsource_id\tincluded\nstub.annotation\tpeak_stub\tchrStub\t1\t9\tpromoter\tgene_stub\t1\t\tstub_record\tstub.peaks\ttrue\n' > peak_annotation_aggregate/annotated_peaks.tsv
    printf 'annotation_id\tpeak_id\tgene_id\tcategory\tdistance_to_tss\trecord_id\tsource_id\nstub.annotation\tpeak_stub\tgene_stub\tpromoter\t\tstub_record\tstub.peaks\n' > peak_annotation_aggregate/peak_gene_associations.tsv
    printf 'annotation_id\tsource_id\trecord_id\ttotal_peaks\tannotated_peaks\tunassociated_peaks\tunique_genes\tmean_genes_per_peak\tstatus\nstub.annotation\tstub.peaks\tstub_record\t1\t1\t0\t1\t1.0\tstub\n' > peak_annotation_aggregate/statistics.tsv
    printf '{"schema_version":"1.0","type":"peak_annotation_aggregate","records":1,"status":"stub"}\n' > peak_annotation_aggregate/manifest.json
    cp peak_annotation_aggregate/manifest.json peak_annotation_aggregate.manifest.json
    printf '{"schema_version":"1.0","id":"chipseq.peak_annotation.aggregate","process":"PEAK_ANNOTATION_AGGREGATE","status":"stub"}\n' > peak_annotation_aggregate.execution.json
    printf '"PEAK_ANNOTATION_AGGREGATE":\n    python: stub\n' > peak_annotation_aggregate.versions.yml
    printf '{"id":"chipseq.peak_annotation.aggregate","process":"PEAK_ANNOTATION_AGGREGATE","status":"stub"}\n' > peak_annotation_aggregate.done
    """
}
