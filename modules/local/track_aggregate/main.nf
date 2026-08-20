process TRACK_AGGREGATE {
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

    publishDir "${params.outdir}/pipeline_info/native_chipseq/tracks/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done}'
    publishDir "${params.outdir}/chipseq/tracks",
        mode: 'copy', overwrite: true, pattern: 'track_aggregate'

    input:
    tuple val(meta), path(track_dirs), path(track_manifests), path(statistics_json), path(statistics_manifests)

    output:
    tuple val(meta), path('track_aggregate'), emit: artifacts
    tuple val(meta), path('track_aggregate/tracks.tsv'), emit: reports
    tuple val(meta), path('track_aggregate.versions.yml'), emit: versions
    tuple val(meta), path('track_aggregate.execution.json'), emit: execution_metadata
    tuple val(meta), path('track_aggregate.manifest.json'), emit: manifest
    tuple val(meta), path('track_aggregate.done'), emit: status

    script:
    def dirArgs = track_dirs.collect { value -> "--track-dir '${value}'" }.join(' ')
    def manifestArgs = track_manifests.collect { value -> "--track-manifest '${value}'" }.join(' ')
    def statisticsArgs = statistics_json.collect { value -> "--statistics-json '${value}'" }.join(' ')
    def statisticsManifestArgs = statistics_manifests.collect { value -> "--statistics-manifest '${value}'" }.join(' ')
    """
    track_aggregate.py \
        ${dirArgs} \
        ${manifestArgs} \
        ${statisticsArgs} \
        ${statisticsManifestArgs} \
        --output-dir track_aggregate \
        --manifest track_aggregate.manifest.json \
        --execution track_aggregate.execution.json \
        --versions track_aggregate.versions.yml \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}'
    printf '{"id":"%s","process":"TRACK_AGGREGATE","status":"complete"}\n' '${meta.id}' > track_aggregate.done
    """

    stub:
    """
    mkdir -p track_aggregate/tracks
    : > track_aggregate/tracks/stub.track.bw
    printf 'track_id\ttrack_role\trecord_id\trecord_ids\tsample_ids\tdataset\tcondition\ttarget\tgenome_id\tbuild\tnormalization\tbin_size\ttrack\ttrack_sha256\tsource_reads\tmapped_reads\tbases_covered\tnumber_of_bins\tstatus\nstub.track\tindividual\tstub_record\tstub_record\tstub_sample\tstub\ttreated\tH3K27ac\tstub_v1\tstub_v1\tCPM\t10\ttracks/stub.track.bw\t\t1\t1\t10\t1\tstub\n' > track_aggregate/tracks.tsv
    printf '{"schema_version":"1.0","type":"track_aggregate","id":"chipseq.tracks.aggregate","tracks":1,"status":"stub"}\n' > track_aggregate/manifest.json
    cp track_aggregate/manifest.json track_aggregate.manifest.json
    printf '{"schema_version":"1.0","id":"chipseq.tracks.aggregate","process":"TRACK_AGGREGATE","status":"stub"}\n' > track_aggregate.execution.json
    printf '"TRACK_AGGREGATE":\n    python: stub\n' > track_aggregate.versions.yml
    printf '{"id":"chipseq.tracks.aggregate","process":"TRACK_AGGREGATE","status":"stub"}\n' > track_aggregate.done
    """
}
