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
    rnaseq_de_context.py \
        --analysis-id all_projects_raw \
        --scope all_projects \
        --correction raw \
        --target-dir "\$DEG_DIR/all_projects/raw" \
        --test-variables "\$DEG_TEST_VARIABLES" \
        --design-covariates "\$DEG_DESIGN_COVARIATES" \
        --output analysis_spec.json
    printf '[OK] analysis=all_projects_raw target=%s variables=%s covariates=%s\n' \
        "\$DEG_DIR/all_projects/raw" "\$DEG_TEST_VARIABLES" "\$DEG_DESIGN_COVARIATES" \
        > rnaseq.de_context.log
    """

    stub:
    """
    printf '%s\n' '{"schema_version":"1.0","analysis_id":"all_projects_raw","scope":"all_projects","correction":"raw","provider":"deseq2","test":"wald","target_dir":"${params.outdir}/stub/060-deg-analysis/all_projects/raw","test_variables":["condition"],"design_covariates":[],"contrasts":[],"parameters":{"alpha":0.05,"lfc_threshold":1,"min_replicates":2,"min_total_count":10}}' > analysis_spec.json
    : > annotation_input.gff
    printf '[STUB] RNA-seq DE context\n' > rnaseq.de_context.log
    """
}
