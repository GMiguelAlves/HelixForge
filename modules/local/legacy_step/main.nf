process LEGACY_STEP {
    tag "${pipeline}:${step}"
    label 'legacy_orchestrator'

    cpus {
        resource_class == 'high_memory' ? 16 :
        resource_class == 'high_cpu'    ? 8  :
        resource_class == 'medium'      ? 4  : 2
    }
    memory {
        resource_class == 'high_memory' ? 180.GB :
        resource_class == 'high_cpu'    ? 64.GB  :
        resource_class == 'medium'      ? 32.GB  : 8.GB
    }
    time {
        resource_class == 'high_memory' ? 24.h :
        resource_class == 'high_cpu'    ? 12.h :
        resource_class == 'medium'      ? 8.h  : 2.h
    }

    publishDir "${params.outdir}/pipeline_info/legacy_steps", mode: 'copy', overwrite: true

    input:
    val pipeline
    val step
    val resource_class
    path config_file
    val legacy_root
    val prerequisite_one
    val prerequisite_two
    val prerequisite_three

    output:
    tuple val(pipeline), val(step), path("${pipeline}.${step}.done"), emit: status
    tuple val(pipeline), val(step), path("${pipeline}.${step}.log"), emit: log

    script:
    def done_name = "${pipeline}.${step}.done"
    def log_name  = "${pipeline}.${step}.log"
    """
    export OMICSFLOW_NATIVE_STAR_ALIGNMENT='${params.rnaseq_native_alignment}'
    export OMICSFLOW_NATIVE_SALMON_QUANTIFICATION='${params.rnaseq_native_quantification}'
    export OMICSFLOW_RNASEQ_ANALYSIS_MODE='${params.rnaseq_analysis_mode}'
    bash "${projectDir}/bin/run_legacy_step.sh" \
        "${pipeline}" \
        "${step}" \
        "${legacy_root}" \
        "\$PWD/${config_file}" \
        "${log_name}" \
        "${done_name}" \
        "${params.legacy_dry_run}"
    """

    stub:
    """
    printf '[STUB] %s/%s; script root=%s; config=%s\n' \
        '${pipeline}' '${step}' '${legacy_root}' '${config_file}' > '${pipeline}.${step}.log'
    printf '{"pipeline":"%s","step":"%s","status":"stub"}\n' \
        '${pipeline}' '${step}' > '${pipeline}.${step}.done'
    """
}
