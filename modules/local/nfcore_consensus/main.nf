process NFCORE_CONSENSUS {
    tag "${meta.id}"
    label 'native_module'
    label 'consensus'
    cpus 2
    memory 4.GB
    time 2.h
    cache 'deep'
    errorStrategy { task.exitStatus in [137, 143] ? 'retry' : 'terminate' }
    maxRetries 2
    container params.nfcore_consensus_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/chipseq/consensus/${meta.id}", mode: 'copy', pattern: '*.consensus_result'
    publishDir "${params.outdir}/pipeline_info/native_chipseq/consensus/providers", mode: 'copy', pattern: '*.{json,yml,done}'

    input:
    tuple val(meta), path(peak_dirs), path(request)
    path(providerProgram)
    path(upstreamHelper)

    output:
    tuple val(meta), path("${meta.id}.nfcore_2_1.consensus_result"), emit: artifacts
    tuple val(meta), path("${meta.id}.nfcore_2_1.consensus_result/provider_reports"), emit: reports
    tuple val(meta), path("${meta.id}.nfcore.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.nfcore.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.nfcore.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.nfcore.done"), emit: status

    script:
    def sources = peak_dirs.collect { item -> "--peak-dir '${item}'" }.join(' ')
    """
    export LC_ALL=C
    python3 '${providerProgram}' --request '${request}' ${sources} --helper '${upstreamHelper}' \
        --output-dir '${meta.id}.nfcore_2_1.consensus_result' \
        --manifest '${meta.id}.nfcore.manifest.json' --execution '${meta.id}.nfcore.execution.json' \
        --versions '${meta.id}.nfcore.versions.yml' --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' --task-time '${task.time}' --environment '${workflow.containerEngine ?: 'host'}'
    printf '{"id":"%s","process":"NFCORE_CONSENSUS","status":"complete"}\n' '${meta.id}' > '${meta.id}.nfcore.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.nfcore_2_1.consensus_result/provider_reports'
    printf 'chrStub\t4\t12\tInterval_1\n' > '${meta.id}.nfcore_2_1.consensus_result/consolidated_peaks.bed'
    printf 'peak_id\tchrom\tstart\tend\tsupport\tsupport_replicates\tcalling_libraries\tcalling_samples\tcalling_library_count\ttotal_library_count\tlibrary_support_category\nInterval_1\tchrStub\t4\t12\t2\t1,2\tstub1,stub2\tstub1,stub2\t2\t2\tall_libraries\n' > '${meta.id}.nfcore_2_1.consensus_result/consolidated_peaks.tsv'
    printf 'peak_id\tlibrary_id\tcovered_bp\tcovered_fraction\n' > '${meta.id}.nfcore_2_1.consensus_result/support_by_library.tsv'
    touch '${meta.id}.nfcore_2_1.consensus_result/support_core.bed'
    printf '{"schema_version":"1.0","type":"consensus","id":"%s","strategy":"nfcore_2_1","provider":"nfcore_chipseq_2.1.0","artifacts":{"consolidated_bed":{"available":true,"path":"consolidated_peaks.bed"}},"status":"stub"}\n' '${meta.id}' > '${meta.id}.nfcore.manifest.json'
    cp '${meta.id}.nfcore.manifest.json' '${meta.id}.nfcore_2_1.consensus_result/manifest.json'
    printf '{"status":"stub"}\n' > '${meta.id}.nfcore.execution.json'
    printf '"NFCORE_CONSENSUS":\n    bedtools: stub\n    nf_core_chipseq: stub\n' > '${meta.id}.nfcore.versions.yml'
    printf '[STUB]\n' > '${meta.id}.nfcore_2_1.consensus_result/provider_reports/commands.txt'
    printf '{"id":"%s","process":"NFCORE_CONSENSUS","status":"stub"}\n' '${meta.id}' > '${meta.id}.nfcore.done'
    """
}
