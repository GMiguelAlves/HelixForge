process HOMER_ANNOTATION_ADAPTER {
    tag "${meta.id}"
    label 'native_module'
    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0
    container params.chipseq_peak_annotation_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/chipseq/peak_annotation", mode: 'copy', pattern: '*.peak_annotation'
    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_annotation/provider", mode: 'copy', pattern: '*.{json,yml,done}'

    input:
    tuple val(meta), path(peaks), path(request), path(raw_dir), path(support_dirs)
    path(providerProgram)

    output:
    tuple val(meta), path("${meta.id}.peak_annotation"), emit: artifacts
    tuple val(meta), path("${meta.id}.peak_annotation/provider_reports"), emit: reports
    tuple val(meta), path("${meta.id}.homer_adapter.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.homer_adapter.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.homer_adapter.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.homer_adapter.done"), emit: status

    script:
    def supportArgs = support_dirs.collect { item -> "--support-dir '${item}'" }.join(' ')
    """
    python3 '${providerProgram}' --request '${request}' --peaks '${peaks}' --raw-dir '${raw_dir}' ${supportArgs} \
        --output-dir '${meta.id}.peak_annotation' --manifest '${meta.id}.homer_adapter.manifest.json' \
        --execution '${meta.id}.homer_adapter.execution.json' --versions '${meta.id}.homer_adapter.versions.yml' \
        --cpus '${task.cpus}' --memory-bytes '${task.memory.toBytes()}' --task-time '${task.time}'
    printf '{"id":"%s","process":"HOMER_ANNOTATION_ADAPTER","status":"complete"}\n' '${meta.id}' > '${meta.id}.homer_adapter.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.peak_annotation/provider_reports'
    cp -r '${raw_dir}'/. '${meta.id}.peak_annotation/provider_reports/'
    printf 'peak_id\tchrom\tstart\tend\tcategory\tgene_ids\tgene_count\tdistance_to_tss\trecord_id\tsource_id\tincluded\tcalling_libraries\tcalling_samples\tcalling_library_count\ttotal_library_count\tlibrary_support_category\tgene_assignment_ambiguous\tgene_assignment_ambiguity_reason\tgene_assignment_ambiguity_scope\talternative_gene_ids\npeak_stub\tchrStub\t4\t12\tpromoter\tgene_stub\t1\t0\tstub_record\tstub.peaks\ttrue\tstub1,stub2\tstub1,stub2\t2\t2\tall_libraries\tnot_assessed\tstub\thomer_nearest_tss_distance_ties_v1\t[]\n' > '${meta.id}.peak_annotation/annotated_peaks.tsv'
    printf 'peak_id\tgene_id\tcategory\tdistance_to_tss\trecord_id\tsource_id\tcalling_libraries\tcalling_samples\tcalling_library_count\ttotal_library_count\tlibrary_support_category\tgene_assignment_ambiguous\tgene_assignment_ambiguity_reason\tgene_assignment_ambiguity_scope\talternative_gene_ids\npeak_stub\tgene_stub\tpromoter\t0\tstub_record\tstub.peaks\tstub1,stub2\tstub1,stub2\t2\t2\tall_libraries\tnot_assessed\tstub\thomer_nearest_tss_distance_ties_v1\t[]\n' > '${meta.id}.peak_annotation/peak_gene_associations.tsv'
    printf '{"schema_version":"1.0","type":"peak_annotation","id":"%s","source_id":"stub.peaks","provider":"homer_4_11","provider_version":"4.11","status":"stub"}\n' '${meta.id}' > '${meta.id}.homer_adapter.manifest.json'
    cp '${meta.id}.homer_adapter.manifest.json' '${meta.id}.peak_annotation/manifest.json'
    printf '{"status":"stub"}\n' > '${meta.id}.homer_adapter.execution.json'
    printf '"HOMER_ANNOTATION_ADAPTER":\n    python: stub\n    homer: stub\n' > '${meta.id}.homer_adapter.versions.yml'
    printf '{"id":"%s","process":"HOMER_ANNOTATION_ADAPTER","status":"stub"}\n' '${meta.id}' > '${meta.id}.homer_adapter.done'
    """
}
