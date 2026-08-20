include { INTEGRATIVE_INPUT_VALIDATION } from '../../../modules/local/integrative_input_validation/main'
include { RNASEQ_EVIDENCE_PROVIDER } from '../../../modules/local/rnaseq_evidence_provider/main'
include { CHIPSEQ_EVIDENCE_PROVIDER } from '../../../modules/local/chipseq_evidence_provider/main'
include { EVIDENCE_HARMONIZATION } from '../../../modules/local/evidence_harmonization/main'
include { MOLECULAR_EVIDENCE_INTEGRATION } from '../../../modules/local/molecular_evidence_integration/main'
include { REGULATORY_INTERPRETATION } from '../../../modules/local/regulatory_interpretation/main'
include { CANDIDATE_SCORING } from '../../../modules/local/candidate_scoring/main'
include { CROSS_ASSAY_STATISTICS } from '../../../modules/local/cross_assay_statistics/main'
include { FUNCTIONAL_ANALYSIS } from '../../../modules/local/functional_analysis/main'
include { INTEGRATIVE_VISUALIZATION } from '../../../modules/local/integrative_visualization/main'
include { INTEGRATIVE_REPORT } from '../../../modules/local/integrative_report/main'
include { INTEGRATIVE_RUN_MANIFEST } from '../../../modules/local/integrative_run_manifest/main'

workflow NATIVE_INTEGRATION {
    take:
    rna_bundle
    chip_bundle

    main:
    harmonization_policy = file(params.integrative_harmonization_policy, checkIfExists: true)
    interpretation_policy = file(params.integrative_interpretation_policy, checkIfExists: true)
    mark_roles = file(params.integrative_mark_roles, checkIfExists: true)
    context = file(params.integrative_prioritization_context, checkIfExists: true)
    functional_annotation = file(params.integrative_functional_annotation, checkIfExists: true)

    paired_inputs = rna_bundle.combine(chip_bundle).map { rna_meta, rna_manifest, rna_artifacts, chip_meta, chip_manifest, chip_artifacts ->
        def pair_id = "${rna_meta.id}.${chip_meta.id}.integrative".replaceAll(/[^A-Za-z0-9._-]+/, '_')
        tuple([id: pair_id, assay: 'integrative', rna_manifest_id: rna_meta.id, chip_manifest_id: chip_meta.id], rna_manifest, rna_artifacts, chip_manifest, chip_artifacts)
    }
    INTEGRATIVE_INPUT_VALIDATION(paired_inputs)

    rna_provider_inputs = INTEGRATIVE_INPUT_VALIDATION.out.artifacts.map { meta, bundle ->
        tuple(meta, file("${bundle}/rnaseq_run_manifest.json", checkIfExists: true), file("${bundle}/rnaseq_bindings.json", checkIfExists: true), file("${bundle}/rnaseq_artifacts/*/*", checkIfExists: true))
    }
    chip_provider_inputs = INTEGRATIVE_INPUT_VALIDATION.out.artifacts.map { meta, bundle ->
        tuple(meta, file("${bundle}/chipseq_run_manifest.json", checkIfExists: true), file("${bundle}/chipseq_bindings.json", checkIfExists: true), file("${bundle}/chipseq_artifacts/*/*", checkIfExists: true))
    }
    RNASEQ_EVIDENCE_PROVIDER(rna_provider_inputs)
    CHIPSEQ_EVIDENCE_PROVIDER(chip_provider_inputs)

    evidence_pair = RNASEQ_EVIDENCE_PROVIDER.out.artifacts.join(CHIPSEQ_EVIDENCE_PROVIDER.out.artifacts)
    harmonization_inputs = evidence_pair.map { meta, rna_evidence, chip_evidence -> tuple(meta, rna_evidence, chip_evidence, harmonization_policy) }
    EVIDENCE_HARMONIZATION(harmonization_inputs)

    integration_inputs = evidence_pair.join(EVIDENCE_HARMONIZATION.out.artifacts).map { meta, rna_evidence, chip_evidence, harmonization -> tuple(meta, rna_evidence, chip_evidence, harmonization) }
    MOLECULAR_EVIDENCE_INTEGRATION(integration_inputs)

    regulatory_inputs = MOLECULAR_EVIDENCE_INTEGRATION.out.artifacts.map { meta, integration -> tuple(meta, integration, interpretation_policy, mark_roles) }
    REGULATORY_INTERPRETATION(regulatory_inputs)

    integration_and_classes = MOLECULAR_EVIDENCE_INTEGRATION.out.artifacts.join(REGULATORY_INTERPRETATION.out.artifacts)
    scoring_inputs = integration_and_classes.map { meta, integration, classification -> tuple(meta, integration, classification, interpretation_policy, context) }
    CANDIDATE_SCORING(scoring_inputs)

    statistics_inputs = integration_and_classes.join(CANDIDATE_SCORING.out.artifacts).map { meta, integration, classification, scoring -> tuple(meta, integration, classification, scoring, interpretation_policy, mark_roles, context) }
    CROSS_ASSAY_STATISTICS(statistics_inputs)

    functional_inputs = CROSS_ASSAY_STATISTICS.out.artifacts.map { meta, interpretation -> tuple(meta, interpretation, functional_annotation, params.integrative_top_candidates as Integer) }
    FUNCTIONAL_ANALYSIS(functional_inputs)

    visualization_inputs = CROSS_ASSAY_STATISTICS.out.artifacts.join(FUNCTIONAL_ANALYSIS.out.artifacts).map { meta, interpretation, functional -> tuple(meta, interpretation, functional, params.integrative_candidate_panels as Integer) }
    INTEGRATIVE_VISUALIZATION(visualization_inputs)

    report_inputs = INTEGRATIVE_INPUT_VALIDATION.out.artifacts
        .join(evidence_pair)
        .join(EVIDENCE_HARMONIZATION.out.artifacts)
        .join(MOLECULAR_EVIDENCE_INTEGRATION.out.artifacts)
        .join(CROSS_ASSAY_STATISTICS.out.artifacts)
        .join(FUNCTIONAL_ANALYSIS.out.artifacts)
        .join(INTEGRATIVE_VISUALIZATION.out.artifacts)
        .map { meta, inputs, rna_evidence, chip_evidence, harmonization, integration, interpretation, functional, visualization ->
            tuple(meta, inputs, rna_evidence, chip_evidence, harmonization, integration, interpretation, functional, visualization, params.integrative_report_title)
        }
    INTEGRATIVE_REPORT(report_inputs)

    terminal_inputs = INTEGRATIVE_INPUT_VALIDATION.out.artifacts
        .join(evidence_pair)
        .join(EVIDENCE_HARMONIZATION.out.artifacts)
        .join(MOLECULAR_EVIDENCE_INTEGRATION.out.artifacts)
        .join(CROSS_ASSAY_STATISTICS.out.artifacts)
        .join(FUNCTIONAL_ANALYSIS.out.artifacts)
        .join(INTEGRATIVE_VISUALIZATION.out.artifacts)
        .join(INTEGRATIVE_REPORT.out.artifacts)
        .map { meta, inputs, rna_evidence, chip_evidence, harmonization, integration, interpretation, functional, visualization, report ->
            def logical_run = [id: "${meta.id}.run", workflow: 'integrative', run_id: meta.id, run_name: meta.id,
                helixforge_version: workflow.manifest.version ?: 'unknown', git_commit: workflow.commitId ?: 'unknown',
                nextflow_version: workflow.nextflow.version.toString(), profile: workflow.profile ?: '',
                parameters: [top_candidates: params.integrative_top_candidates, candidate_panels: params.integrative_candidate_panels],
                source: [type: 'helixforge', name: 'HelixForge', version: workflow.manifest.version ?: 'unknown']]
            def run_base64 = groovy.json.JsonOutput.toJson(logical_run).bytes.encodeBase64().toString()
            tuple(meta, file("${inputs}/rnaseq_run_manifest.json", checkIfExists: true), file("${inputs}/chipseq_run_manifest.json", checkIfExists: true), inputs, rna_evidence, chip_evidence, harmonization, integration, interpretation, functional, visualization, report, run_base64)
        }
    INTEGRATIVE_RUN_MANIFEST(terminal_inputs)

    emit:
    terminal_manifest = INTEGRATIVE_RUN_MANIFEST.out.artifacts
    report = INTEGRATIVE_REPORT.out.html
    master_evidence = MOLECULAR_EVIDENCE_INTEGRATION.out.artifacts
    interpretation = CROSS_ASSAY_STATISTICS.out.artifacts
    functional = FUNCTIONAL_ANALYSIS.out.artifacts
    visualization = INTEGRATIVE_VISUALIZATION.out.artifacts
    status = INTEGRATIVE_RUN_MANIFEST.out.status
    logs = INTEGRATIVE_INPUT_VALIDATION.out.reports
        .mix(RNASEQ_EVIDENCE_PROVIDER.out.reports)
        .mix(CHIPSEQ_EVIDENCE_PROVIDER.out.reports)
        .mix(EVIDENCE_HARMONIZATION.out.reports)
        .mix(MOLECULAR_EVIDENCE_INTEGRATION.out.reports)
        .mix(REGULATORY_INTERPRETATION.out.reports)
        .mix(CANDIDATE_SCORING.out.reports)
        .mix(CROSS_ASSAY_STATISTICS.out.reports)
        .mix(FUNCTIONAL_ANALYSIS.out.reports)
        .mix(INTEGRATIVE_VISUALIZATION.out.reports)
        .mix(INTEGRATIVE_REPORT.out.reports)
        .mix(INTEGRATIVE_RUN_MANIFEST.out.reports)
}
