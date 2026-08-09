process DE_PREFLIGHT {
    tag "${meta.id}"
    label 'native_module'
    label 'de_low'

    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0

    container params.de_adapter_container
    conda "${moduleDir}/environment.yml"

    publishDir "${params.outdir}/pipeline_info/native_de/preflight",
        mode: 'copy', overwrite: true, pattern: '*.{json,yml,tsv,done}'

    input:
    tuple val(meta), path(import_manifest), path(counts), path(sample_metadata), path(analysis_spec), path(annotation)

    output:
    tuple val(meta), path('model_specs'), path('contrast_specs'), path('validated_counts.tsv'),
        path('validated_samples.tsv'), path(annotation), emit: models
    tuple val(meta), path('skipped_models.tsv'), path(analysis_spec), emit: aggregate_context
    tuple val(meta), path('preflight_report.json'), emit: reports
    tuple val(meta), path('versions.yml'), emit: versions
    tuple val(meta), path('de_preflight.done'), emit: status

    script:
    """
    de_preflight.py \
        --manifest '${import_manifest}' \
        --counts '${counts}' \
        --samples '${sample_metadata}' \
        --spec '${analysis_spec}' \
        --output-dir . \
        > preflight_report.json
    printf '"%s":\n    python: "%s"\n' '${task.process}' \
        "\$(python3 --version 2>&1 | awk '{print \$2}')" > versions.yml
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > de_preflight.done
    """

    stub:
    """
    mkdir -p model_specs contrast_specs
    cp '${counts}' validated_counts.tsv
    cp '${sample_metadata}' validated_samples.tsv
    printf '%s\n' '{"schema_version":"1.0","model_id":"stub.condition","analysis_id":"stub","provider":"deseq2","test":"wald","variable":"condition","covariates":[],"formula":"~ condition","valid_levels":["control","treated"],"filter":{"method":"none"},"parameters":{"alpha":0.05,"lfc_threshold":1,"min_replicates":2,"non_integer_counts":"error"},"target_dir":"stub"}' > model_specs/stub.condition.json
    printf '%s\n' '{"model_id":"stub.condition","id":"condition__control_vs_treated","factor":"condition","numerator":"control","denominator":"treated","description":"control versus treated","direction":"control/treated","order":1}' > contrast_specs/stub.condition--condition__control_vs_treated.json
    printf 'analysis_id\tvariable\tstatus\tn_samples\tn_genes\n' > skipped_models.tsv
    printf '%s\n' '{"status":"stub","models":1,"contrasts":1}' > preflight_report.json
    printf '"DE_PREFLIGHT":\n    python: "stub"\n' > versions.yml
    printf '{"id":"%s","process":"DE_PREFLIGHT","status":"stub"}\n' '${meta.id}' > de_preflight.done
    """
}
