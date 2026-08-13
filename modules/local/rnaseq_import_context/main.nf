process RNASEQ_IMPORT_CONTEXT {
    tag "rnaseq:import:${import_method}"
    label 'compatibility_adapter'

    cpus 1
    memory 1.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    publishDir "${params.outdir}/pipeline_info/native_import/context",
        mode: 'copy', overwrite: true, pattern: '*.{log,tsv}'

    input:
    path config_file
    val pipeline_root
    val import_method
    val native_alignment_enabled
    val native_quantification_enabled
    path metadata_table
    path reference_annotation

    output:
    path 'import_context.tsv', emit: settings
    path 'metadata_input.csv', emit: metadata
    path 'annotation_input.gtf', emit: annotation
    path 'rnaseq.import_context.log', emit: log

    script:
    """
    export PROJECT_DIR='${pipeline_root}'
    export PIPELINE_CONFIG="\$PWD/${config_file}"
    source "\$PIPELINE_CONFIG"

    if [[ '${import_method}' == star && '${native_alignment_enabled}' != true ]]; then
        echo '[ERRO] Import API provider star requires rnaseq_native_alignment=true.' >&2
        exit 2
    fi
    if [[ '${import_method}' == salmon && '${native_quantification_enabled}' != true ]]; then
        echo '[ERRO] Import API provider salmon requires rnaseq_native_quantification=true.' >&2
        exit 2
    fi

    [[ -s '${metadata_table}' ]] || { echo '[ERRO] Metadata nativo ausente.'; exit 1; }
    [[ -s '${reference_annotation}' ]] || { echo '[ERRO] Anotacao do Reference Bundle ausente.'; exit 1; }
    cp '${metadata_table}' metadata_input.csv
    cp '${reference_annotation}' annotation_input.gtf
    printf 'provider\ttarget_dir\tstar_count_column\n%s\t%s\t%s\n' \
        '${import_method}' "\$QUANTIFICATION_DIR" "\$STAR_GENECOUNT_COLUMN" > import_context.tsv
    printf '[OK] provider=%s metadata=%s annotation=%s target=%s\n' \
        '${import_method}' '${metadata_table}' '${reference_annotation}' "\$QUANTIFICATION_DIR" > rnaseq.import_context.log
    """

    stub:
    """
    printf 'dataset,sample_id\nSTUB,stub_sample\n' > metadata_input.csv
    printf 'chrStub\tstub\ttranscript\t1\t100\t.\t+\t.\tgene_id "gene_stub"; transcript_id "tx_stub";\n' > annotation_input.gtf
    printf 'provider\ttarget_dir\tstar_count_column\n%s\t%s\tunstranded\n' \
        '${import_method}' '${params.outdir}/stub/050-quantification' > import_context.tsv
    printf '[STUB] RNA-seq import context\n' > rnaseq.import_context.log
    """
}
