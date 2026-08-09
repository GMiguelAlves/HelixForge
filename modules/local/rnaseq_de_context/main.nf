process RNASEQ_DE_CONTEXT {
    tag 'rnaseq:de:context'
    label 'compatibility_adapter'

    cpus 1
    memory 1.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.de_adapter_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_de/context",
        mode: 'copy', overwrite: true, pattern: '*.{json,gff,log}'

    input:
    path config_file
    val legacy_root
    path analysis_spec_input, stageAs: 'requested_de_spec.json'

    output:
    path 'analysis_spec.json', emit: analysis_spec
    path 'annotation_input.gff', emit: annotation
    path 'rnaseq.de_context.log', emit: log

    script:
    """
    export PROJECT_DIR='${legacy_root}'
    export PIPELINE_CONFIG="\$PWD/${config_file}"
    source "\$PIPELINE_CONFIG"
    if [[ -n "\${REF_GFF3:-}" && -s "\$REF_GFF3" ]]; then
        cp "\$REF_GFF3" annotation_input.gff
    else
        : > annotation_input.gff
    fi
    cp '${analysis_spec_input}' analysis_spec.json
    python3 -m json.tool analysis_spec.json > /dev/null
    printf '[OK] explicit DE specification=%s\n' '${analysis_spec_input}' > rnaseq.de_context.log
    """

    stub:
    """
    cp '${analysis_spec_input}' analysis_spec.json
    : > annotation_input.gff
    printf '[STUB] RNA-seq DE context\n' > rnaseq.de_context.log
    """
}
