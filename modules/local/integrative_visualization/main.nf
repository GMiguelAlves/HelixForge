process INTEGRATIVE_VISUALIZATION {
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
    publishDir "${params.outdir}/integration/090-visualization", mode: 'copy', overwrite: true, pattern: 'integrative_visualization'
    publishDir "${params.outdir}/pipeline_info/integration/visualization", mode: 'copy', overwrite: true, pattern: '*.{yml,done,log}'

    input:
    tuple val(meta), path(interpretation, stageAs: 'interpretation'), path(functional, stageAs: 'functional_analysis'), val(panel_count)

    output:
    tuple val(meta), path('integrative_visualization'), emit: artifacts
    tuple val(meta), path('integrative_visualization/visualization_manifest.json'), emit: manifest
    tuple val(meta), path('integrative_visualization.log'), emit: reports
    tuple val(meta), path('integrative_visualization.versions.yml'), emit: versions
    tuple val(meta), path('integrative_visualization.done'), emit: status

    script:
    """
    set -o pipefail
    render_integrative_visualizations.py --interpretation-dir '${interpretation}' --functional-dir '${functional}' --panel-count '${panel_count}' --output-dir integrative_visualization 2>&1 | tee integrative_visualization.log
    printf '"INTEGRATIVE_VISUALIZATION":\n    python: "%s"\n    renderer: "helixforge_svg_v1"\n' "\$(python --version 2>&1 | awk '{print \$2}')" > integrative_visualization.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_VISUALIZATION","status":"complete"}\n' '${meta.id}' > integrative_visualization.done
    """

    stub:
    """
    mkdir -p integrative_visualization
    printf 'figure_id\tpath\tformat\ttitle\tsource_datasets\tstatus\n' > integrative_visualization/visualization_manifest.tsv
    printf 'canonical_entity_id\trank\tfinal_score\tlegacy_evidence_class\tregulatory_patterns\tfigure\n' > integrative_visualization/candidate_panel_index.tsv
    printf '{"schema_version":"1.0","visualization_model_version":"1.0","type":"integrative_visualization","id":"%s.visualization","status":"stub","renderer":{},"datasets":[],"record_counts":{},"provenance":{"provider":"stub"}}\n' '${meta.id}' > integrative_visualization/visualization_manifest.json
    printf '[STUB] Integrative Visualization\n' > integrative_visualization.log
    printf '"INTEGRATIVE_VISUALIZATION":\n    python: stub\n    renderer: "helixforge_svg_v1"\n' > integrative_visualization.versions.yml
    printf '{"id":"%s","process":"INTEGRATIVE_VISUALIZATION","status":"stub"}\n' '${meta.id}' > integrative_visualization.done
    """
}
