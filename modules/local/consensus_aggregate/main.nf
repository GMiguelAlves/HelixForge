process CONSENSUS_AGGREGATE {
    tag "${meta.id}"
    label 'native_module'
    label 'consensus_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.chipseq_metadata_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/consensus/aggregate",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done}'
    publishDir "${params.outdir}/chipseq/consensus",
        mode: 'copy', overwrite: true, pattern: 'consolidation_summary.{json,tsv}'

    input:
    tuple val(meta), path(provider_manifests)

    output:
    tuple val(meta), path('consolidation_summary.json'), path('consolidation_summary.tsv'), emit: artifacts
    tuple val(meta), path('consolidation_summary.tsv'), emit: reports
    tuple val(meta), path('consensus_aggregate.versions.yml'), emit: versions
    tuple val(meta), path('consensus_aggregate.execution.json'), emit: execution_metadata
    tuple val(meta), path('consensus_manifest.json'), emit: manifest
    tuple val(meta), path('consensus_aggregate.done'), emit: status

    script:
    def manifestArgs = provider_manifests.collect { manifest -> "--provider-manifest '${manifest}'" }.join(' ')
    """
    consensus_aggregate.py \
        ${manifestArgs} \
        --summary-json consolidation_summary.json \
        --summary-tsv consolidation_summary.tsv \
        --manifest consensus_manifest.json \
        --execution consensus_aggregate.execution.json \
        --versions consensus_aggregate.versions.yml \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --nextflow-version '${workflow.nextflow.version}'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.id}' '${task.process}' > consensus_aggregate.done
    """

    stub:
    """
    printf 'group_id\tdataset\texperiment_id\tcondition\ttarget\tgenome_id\tpeak_type\tstrategy\tstatus\treplicate_count\tconsolidated_peaks_available\nfixture.treated.H3K27ac.fixture_v1.narrow\tfixture\tfixture.H3K27ac\ttreated\tH3K27ac\tfixture_v1\tnarrow\t%s\t%s\t2\t%s\n' \
        '${meta.strategy}' 'stub' 'true' > consolidation_summary.tsv
    printf '{"schema_version":"1.0","type":"consensus_idr_summary","groups":1,"strategy":"%s","status":"stub"}\n' '${meta.strategy}' > consolidation_summary.json
    printf '{"schema_version":"1.0","type":"consensus_idr","id":"chipseq.consensus.aggregate","groups":1,"strategy":"%s","status":"stub"}\n' '${meta.strategy}' > consensus_manifest.json
    printf '{"schema_version":"1.0","id":"chipseq.consensus.aggregate","process":"CONSENSUS_AGGREGATE","status":"stub"}\n' > consensus_aggregate.execution.json
    printf '"CONSENSUS_AGGREGATE":\n    python: stub\n' > consensus_aggregate.versions.yml
    printf '{"id":"chipseq.consensus.aggregate","process":"CONSENSUS_AGGREGATE","status":"stub"}\n' > consensus_aggregate.done
    """
}
