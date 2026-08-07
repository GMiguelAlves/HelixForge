process IMPORT_SAMPLE_TABLE {
    tag "${meta.id}"
    label 'native_module'
    label 'import_low'

    cpus 1
    memory 1.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.import_source_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_import/sample_tables",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,done,tsv}'

    input:
    tuple val(meta), path(metadata), val(import_params)
    path sources

    output:
    tuple val(meta), path('import_samples.tsv'), val(import_params), emit: artifacts
    tuple val(meta), path('sample_table_plan.json'), emit: reports
    tuple val(meta), path('versions.yml'), emit: versions
    tuple val(meta), path('import_sample_table.done'), emit: status

    script:
    def sourceArgs = sources.collect { source -> "'${source}'" }.join(' ')
    def projectArg = import_params.project ? "--project '${import_params.project}'" : ''
    def missingArg = import_params.allow_missing ? '--allow-missing' : ''
    """
    import_build_sample_table.py \
        --metadata '${metadata}' \
        --provider '${meta.provider}' \
        --star-count-column '${import_params.star_count_column ?: 'unstranded'}' \
        ${projectArg} ${missingArg} \
        --output import_samples.tsv \
        ${sourceArgs} > sample_table_plan.json
    printf '"%s":\n    python: "%s"\n' '${task.process}' "\$(python3 --version 2>&1 | awk '{print \$2}')" > versions.yml
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > import_sample_table.done
    """

    stub:
    """
    if [[ '${meta.provider}' == star ]]; then
        printf 'dataset\tsample_id\timport_id\tquant_file\tquant_exists\tquant_method\texpression_unit\tstar_count_column\t__source_name\t__manifest_sha256\nSTUB\tstub_sample\tSTUB__stub_sample\tReadsPerGene.out.tab\tTrue\tstar\tCPM\tunstranded\tSTUB.stub_sample.import_source\tstub\n' > import_samples.tsv
    else
        printf 'dataset\tsample_id\timport_id\tquant_file\tquant_exists\t__source_name\t__manifest_sha256\nSTUB\tstub_sample\tSTUB__stub_sample\tquant.sf\tTRUE\tSTUB.stub_sample.import_source\tstub\n' > import_samples.tsv
    fi
    printf '{"provider":"%s","samples":1}\n' '${meta.provider}' > sample_table_plan.json
    printf '"IMPORT_SAMPLE_TABLE":\n    python: "stub"\n' > versions.yml
    printf '{"id":"%s","process":"IMPORT_SAMPLE_TABLE","status":"stub"}\n' '${meta.id}' > import_sample_table.done
    """
}
