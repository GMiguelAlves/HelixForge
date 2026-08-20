process FUNCTIONAL_ANALYSIS {
    tag "${meta.id}"
    label 'native_module'
    label 'integration_low'
    cpus 1
    memory 2.GB
    time 30.m
    cache 'deep'
    errorStrategy 'terminate'
    maxRetries 0
    container params.integrative_container
    conda "${moduleDir}/environment.yml"
    publishDir "${params.outdir}/integration/080-functional-analysis", mode: 'copy', overwrite: true, pattern: 'functional_analysis'
    publishDir "${params.outdir}/pipeline_info/integration/functional", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(interpretation, stageAs: 'interpretation'), path(annotation, stageAs: 'functional_annotation.tsv'), val(top_n)

    output:
    tuple val(meta), path('functional_analysis'), emit: artifacts
    tuple val(meta), path('functional_analysis/functional_manifest.json'), emit: manifest
    tuple val(meta), path('functional_analysis.log'), emit: reports
    tuple val(meta), path('functional_analysis.versions.yml'), emit: versions
    tuple val(meta), path('functional_analysis.done'), emit: status

    script:
    """
    set -o pipefail
    run_functional_analysis.py --interpretation-dir '${interpretation}' --annotation '${annotation}' --top-n '${top_n}' --output-dir functional_analysis 2>&1 | tee functional_analysis.log
    printf '"FUNCTIONAL_ANALYSIS":\n    python: "%s"\n    functional_model: "1.0"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > functional_analysis.versions.yml
    printf '{"id":"%s","process":"FUNCTIONAL_ANALYSIS","status":"complete"}\n' '${meta.id}' > functional_analysis.done
    """

    stub:
    """
    mkdir -p functional_analysis
    printf 'gene_set_id\tcanonical_entity_id\tmembership\trank\n' > functional_analysis/gene_sets.tsv
    printf '{"schema_version":"1.0","functional_model_version":"1.0","type":"functional_analysis","id":"%s.functional","status":"stub","reference":{},"selection":{},"methods":{},"datasets":[],"record_counts":{},"provenance":{"provider":"stub"}}\n' '${meta.id}' > functional_analysis/functional_manifest.json
    printf '[STUB] Functional Analysis\n' > functional_analysis.log
    printf '"FUNCTIONAL_ANALYSIS":\n    python: stub\n    functional_model: "1.0"\n' > functional_analysis.versions.yml
    printf '{"id":"%s","process":"FUNCTIONAL_ANALYSIS","status":"stub"}\n' '${meta.id}' > functional_analysis.done
    """
}
