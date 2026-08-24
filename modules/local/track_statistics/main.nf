process TRACK_STATISTICS {
    tag "${meta.id}"
    label 'native_module'
    label 'track_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.chipseq_track_apptainer_container : params.chipseq_track_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/tracks/statistics",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done,track_statistics_reports}'

    input:
    tuple val(meta), path(track_dir), path(track_manifest)

    output:
    tuple val(meta), path("${meta.id}.track_statistics.json"), path("${meta.id}.track_statistics.tsv"), emit: artifacts
    tuple val(meta), path("${meta.id}.track_statistics_reports"), emit: reports
    tuple val(meta), path("${meta.id}.track_statistics.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.track_statistics.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.track_statistics.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.track_statistics.done"), emit: status

    script:
    """
    track_statistics.py \
        --track-dir '${track_dir}' \
        --track-manifest '${track_manifest}' \
        --output-json '${meta.id}.track_statistics.json' \
        --output-tsv '${meta.id}.track_statistics.tsv' \
        --reports '${meta.id}.track_statistics_reports' \
        --manifest '${meta.id}.track_statistics.manifest.json' \
        --execution '${meta.id}.track_statistics.execution.json' \
        --versions '${meta.id}.track_statistics.versions.yml' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}'
    printf '{"id":"%s","process":"TRACK_STATISTICS","status":"complete"}\n' '${meta.id}' > '${meta.id}.track_statistics.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.track_statistics_reports'
    printf 'contig\tlength\tintervals\tbases_covered\nchrStub\t16\t1\t10\n' > '${meta.id}.track_statistics_reports/contigs.tsv'
    printf '{"schema_version":"1.0","id":"%s","track_role":"%s","source_reads":1,"mapped_reads":1,"contigs":1,"bases_covered":10,"depth":{"available":true,"min":1.0,"max":1.0,"mean":1.0},"number_of_bins":1,"track_bytes":0,"normalization":"CPM","scale_factor":1.0,"status":"stub"}\n' '${meta.id}' '${meta.track_role}' > '${meta.id}.track_statistics.json'
    printf 'metric\tvalue\nsource_reads\t1\nmapped_reads\t1\ncontigs\t1\nbases_covered\t10\nnumber_of_bins\t1\ntrack_bytes\t0\n' > '${meta.id}.track_statistics.tsv'
    printf '{"schema_version":"1.0","type":"track_statistics","id":"%s","status":"stub"}\n' '${meta.id}' > '${meta.id}.track_statistics.manifest.json'
    printf '{"schema_version":"1.0","id":"%s","process":"TRACK_STATISTICS","status":"stub"}\n' '${meta.id}' > '${meta.id}.track_statistics.execution.json'
    printf '"TRACK_STATISTICS":\n    python: stub\n    pyBigWig: stub\n' > '${meta.id}.track_statistics.versions.yml'
    printf '{"id":"%s","process":"TRACK_STATISTICS","status":"stub"}\n' '${meta.id}' > '${meta.id}.track_statistics.done'
    """
}
