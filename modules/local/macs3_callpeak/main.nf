process MACS3_CALLPEAK {
    tag "${meta.peak_id}"
    label 'native_module'
    label 'peak_calling'

    cpus 2
    memory 8.GB
    time 4.h
    queue { params.macs3_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.macs3_apptainer_container : params.macs3_container}"
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_chipseq/peak_calling/providers",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,macs3_reports}'

    input:
    tuple val(meta), path(treatment_bam), path(treatment_bai), path(control_bam), path(control_bai), val(request_base64)

    output:
    tuple val(meta), path("${meta.peak_id}.provider.peaks"), path('macs3_output'), val(request_base64), emit: artifacts
    tuple val(meta), path("${meta.peak_id}.macs3_reports"), emit: reports
    tuple val(meta), path("${meta.peak_id}.versions.yml"), emit: versions
    tuple val(meta), path("${meta.peak_id}.execution.json"), emit: execution_metadata
    tuple val(meta), path("${meta.peak_id}.provider.manifest.json"), emit: manifest
    tuple val(meta), path("${meta.peak_id}.macs3.done"), emit: status

    script:
    def control = control_bam ? control_bam[0] : ''
    def environment = workflow.containerEngine ? "${workflow.containerEngine}:${task.container}" : "conda:${task.conda ?: 'host'}"
    """
    run_macs3_callpeak.py \
        --request-base64 '${request_base64}' \
        --treatment '${treatment_bam}' \
        --control '${control}' \
        --output-dir macs3_output \
        --provider-peak '${meta.peak_id}.provider.peaks' \
        --reports '${meta.peak_id}.macs3_reports' \
        --manifest '${meta.peak_id}.provider.manifest.json' \
        --execution '${meta.peak_id}.execution.json' \
        --cpus '${task.cpus}' \
        --memory-bytes '${task.memory.toBytes()}' \
        --task-time '${task.time}' \
        --environment '${environment}'
    printf '"%s":\n    macs3: %s\n' '${task.process}' "\$(macs3 --version 2>&1 | awk '{print \$2}')" > '${meta.peak_id}.versions.yml'
    printf '{"id":"%s","process":"%s","status":"complete"}\n' '${meta.peak_id}' '${task.process}' > '${meta.peak_id}.macs3.done'
    """

    stub:
    """
    mkdir -p macs3_output '${meta.peak_id}.macs3_reports'
    printf 'chrStub\t2\t10\t${meta.peak_id}_1\t100\t.\t5\t10\t8\t4\n' > '${meta.peak_id}.provider.peaks'
    cp '${meta.peak_id}.provider.peaks' 'macs3_output/${meta.peak_id}_peaks.narrowPeak'
    printf 'chrStub\t6\t7\t${meta.peak_id}_1\t100\n' > 'macs3_output/${meta.peak_id}_summits.bed'
    printf 'chrStub\t0\t16\t1\n' > 'macs3_output/${meta.peak_id}_treat_pileup.bdg'
    printf '[STUB] macs3 callpeak\n' > '${meta.peak_id}.macs3_reports/macs3.stderr.log'
    printf '[]\n' > '${meta.peak_id}.macs3_reports/command.json'
    printf 'macs3 callpeak [stub]\n' > '${meta.peak_id}.macs3_reports/command.txt'
    printf '{"schema_version":"1.0","id":"%s","process":"MACS3_CALLPEAK","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.execution.json'
    printf '{"schema_version":"1.0","type":"peak_calling_provider","id":"%s","caller":"macs3","caller_version":"3.0.4"}\n' '${meta.peak_id}' > '${meta.peak_id}.provider.manifest.json'
    printf '"MACS3_CALLPEAK":\n    macs3: stub\n' > '${meta.peak_id}.versions.yml'
    printf '{"id":"%s","process":"MACS3_CALLPEAK","status":"stub"}\n' '${meta.peak_id}' > '${meta.peak_id}.macs3.done'
    """
}
