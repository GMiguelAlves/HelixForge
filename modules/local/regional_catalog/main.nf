process REGIONAL_CATALOG {
    tag "${meta.id}:regional_catalog_v1"
    label 'native_module'
    label 'consensus'
    cpus 2
    memory 4.GB
    time 2.h
    queue { params.consensus_queue ?: null }
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0
    container { workflow.containerEngine in ['singularity', 'apptainer'] ? params.consensus_apptainer_container : params.consensus_container }
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/consensus/providers",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,consensus_reports}'
    publishDir { "${params.outdir}/chipseq/consensus/${meta.id}" },
        mode: 'copy', overwrite: true, pattern: '*.consensus_result'

    input:
    tuple val(meta), path(peak_dirs), path(request), path(program)

    output:
    tuple val(meta), path("${meta.id}.regional_catalog.consensus_result"), emit: artifacts
    tuple val(meta), path("${meta.id}.regional_catalog.consensus_reports"), emit: reports
    tuple val(meta), path("${meta.id}.regional_catalog.versions.yml"), emit: versions
    tuple val(meta), path("${meta.id}.regional_catalog.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.id}.regional_catalog.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.id}.regional_catalog.done"), emit: status

    script:
    def peakArgs = peak_dirs.collect { directory -> "--peak-dir '${directory}'" }.join(' ')
    """
    python3 '${program}' --request '${request}' ${peakArgs} \
        --output-dir '${meta.id}.regional_catalog.consensus_result' \
        --reports '${meta.id}.regional_catalog.consensus_reports' \
        --manifest '${meta.id}.regional_catalog.manifest.json' \
        --execution '${meta.id}.regional_catalog.execution.json' \
        --versions '${meta.id}.regional_catalog.versions.yml' \
        --cpus '${task.cpus}' --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' --nextflow-version '${workflow.nextflow.version}' \
        --environment '${workflow.containerEngine ?: 'host'}'
    printf '{"status":"complete","provider":"regional_catalog_v1"}\n' > '${meta.id}.regional_catalog.done'
    """

    stub:
    """
    mkdir -p '${meta.id}.regional_catalog.consensus_result' '${meta.id}.regional_catalog.consensus_reports'
    printf 'chrStub\t0\t400\tregion1\n' > '${meta.id}.regional_catalog.consensus_result/consolidated_peaks.bed'
    cp '${meta.id}.regional_catalog.consensus_result/consolidated_peaks.bed' '${meta.id}.regional_catalog.consensus_result/supported_regions.bed'
    printf 'chrStub\t199\t200\tcore1\n' > '${meta.id}.regional_catalog.consensus_result/core_supported.bed'
    printf 'peak_id\tchrom\tstart\tend\tsupport\tsupport_replicates\tcore_bp\tcore_fraction\tbelow_threshold_bp\tclassification\toccupancy_status\nregion1\tchrStub\t0\t400\t2\t1,2\t1\t0.0025\t399\tspatially_supported_candidate\tnot_assessed\n' > '${meta.id}.regional_catalog.consensus_result/consolidated_peaks.tsv'
    printf 'peak_id\treplicate_id\tcalled_bp\tcalled_fraction\thas_call\nregion1\t1\t200\t0.5\ttrue\nregion1\t2\t201\t0.5025\ttrue\n' > '${meta.id}.regional_catalog.consensus_result/regional_support.tsv'
    printf 'replicate_id\tpeak_id\tchrom\tstart\tend\n1\tp1\tchrStub\t0\t200\n2\tp2\tchrStub\t199\t400\n' > '${meta.id}.regional_catalog.consensus_result/replicate_evidence.tsv'
    printf '{"status":"stub","reproducible_occupancy_assessed":false}\n' > '${meta.id}.regional_catalog.consensus_result/statistics.json'
    printf '{"schema_version":"1.0","type":"consensus","id":"%s","strategy":"regional_catalog","provider":"regional_catalog_v1","provider_version":"1.0.0","status":"stub","semantics":{"reproducible_occupancy":"not_assessed"},"artifacts":{"consolidated_bed":{"available":true,"path":"consolidated_peaks.bed"}}}\n' '${meta.id}' > '${meta.id}.regional_catalog.manifest.json'
    cp '${meta.id}.regional_catalog.manifest.json' '${meta.id}.regional_catalog.consensus_result/manifest.json'
    printf '{"status":"stub"}\n' > '${meta.id}.regional_catalog.execution.json'
    printf '"REGIONAL_CATALOG":\n    provider: "1.0.0"\n    bedtools: stub\n    python: stub\n' > '${meta.id}.regional_catalog.versions.yml'
    printf '{"status":"stub"}\n' > '${meta.id}.regional_catalog.done'
    printf '[STUB]\n' > '${meta.id}.regional_catalog.consensus_reports/commands.txt'
    """
}
