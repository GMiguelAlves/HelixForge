process PEAK_ANNOTATION_STATISTICS {
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

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_annotation/statistics",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done,statistics_reports}'

    input:
    tuple val(meta), path(annotation_dir), path(annotation_manifest)

    output:
    tuple val(meta), path("${meta.id}.annotation_statistics.json"), path("${meta.id}.annotation_statistics.tsv"), emit: artifacts
    tuple val(meta), path("${meta.id}.annotation_statistics_reports"), emit: reports
    tuple val(meta), path("${meta.id}.annotation_statistics.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.annotation_statistics.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.annotation_statistics.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.annotation_statistics.done"), emit: status

    script:
    """
    peak_annotation_statistics.py \
        --annotation-dir '${annotation_dir}' \
        --annotation-manifest '${annotation_manifest}' \
        --output-json '${meta.id}.annotation_statistics.json' \
        --output-tsv '${meta.id}.annotation_statistics.tsv' \
        --reports '${meta.id}.annotation_statistics_reports' \
        --manifest '${meta.id}.annotation_statistics.manifest.json' \
        --execution '${meta.id}.annotation_statistics.execution.json' \
        --versions '${meta.id}.annotation_statistics.versions.yml' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}'
    printf '{"id":"%s","process":"PEAK_ANNOTATION_STATISTICS","status":"complete"}\n' '${meta.id}' > '${meta.id}.annotation_statistics.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.annotation_statistics_reports'
    printf 'category\tpeak_count\npromoter\t1\n' > '${meta.id}.annotation_statistics_reports/category_distribution.tsv'
    printf 'chromosome\tpeak_count\nchrStub\t1\n' > '${meta.id}.annotation_statistics_reports/peaks_by_chromosome.tsv'
    printf 'record_id\tpeak_count\tannotated_peaks\nstub_record\t1\t1\n' > '${meta.id}.annotation_statistics_reports/by_record.tsv'
    printf 'distance_to_tss\n' > '${meta.id}.annotation_statistics_reports/distance_to_tss.tsv'
    printf '{"schema_version":"1.0","id":"%s","total_peaks":1,"annotated_peaks":1,"unassociated_peaks":0,"unique_genes":1,"mean_genes_per_peak":1.0,"category_distribution":{"promoter":1},"distance_to_tss":{"available":false},"status":"stub"}\n' '${meta.id}' > '${meta.id}.annotation_statistics.json'
    printf 'metric\tvalue\ntotal_peaks\t1\nannotated_peaks\t1\nunassociated_peaks\t0\nunique_genes\t1\nmean_genes_per_peak\t1.0\n' > '${meta.id}.annotation_statistics.tsv'
    printf '{"schema_version":"1.0","type":"peak_annotation_statistics","id":"%s","status":"stub"}\n' '${meta.id}' > '${meta.id}.annotation_statistics.manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"PEAK_ANNOTATION_STATISTICS","status":"stub"}\n' '${meta.id}' > '${meta.id}.annotation_statistics.execution.json'
    printf '"PEAK_ANNOTATION_STATISTICS":\n    python: stub\n' > '${meta.id}.annotation_statistics.versions.yml'
    printf '{"id":"%s","process":"PEAK_ANNOTATION_STATISTICS","status":"stub"}\n' '${meta.id}' > '${meta.id}.annotation_statistics.done'
    """
}
