nextflow.enable.dsl = 2

include { REGIONAL_CATALOG } from '../../modules/local/regional_catalog/main'
include { PEAK_ANNOTATION } from '../../subworkflows/local/chipseq/peak_annotation'
include { CHIPSEQ_FULL_REPORT_INPUT } from '../../modules/local/chipseq_full_report_input/main'
include { CHIPSEQ_REPORT } from '../../subworkflows/local/chipseq/report'

workflow {
    fixture = file(params.fixture_dir, checkIfExists: true)
    meta = [id: 'fixture.catalog', dataset: 'fixture', condition: 'fixture', target: 'H3K27me3', genome_id: 'fixture_v1']
    program = file("${projectDir}/../../modules/local/regional_catalog/resources/usr/bin/run_regional_catalog.py", checkIfExists: true)
    REGIONAL_CATALOG(channel.of(tuple(meta,
        [file("${fixture}/ip1.peak_calling", checkIfExists: true), file("${fixture}/ip2.peak_calling", checkIfExists: true)],
        file("${fixture}/request.json", checkIfExists: true), program)))

    specification = [provider: 'python_interval_v1', promoter_upstream: 0, promoter_downstream: 0, gene_assignment: 'all']
    encoded = groovy.json.JsonOutput.toJson(specification).bytes.encodeBase64().toString()
    annotation_inputs = REGIONAL_CATALOG.out.artifacts.map { source, directory -> tuple(source.id, source, directory) }
        .join(REGIONAL_CATALOG.out.manifest.map { source, manifest -> tuple(source.id, manifest) })
        .map { _id, source, directory, manifest ->
            tuple(source + [id: "${source.id}.annotation", source_id: source.id],
                file("${directory}/consolidated_peaks.bed", checkIfExists: true), manifest,
                file("${fixture}/reference.fa", checkIfExists: true), file("${fixture}/reference_manifest.json", checkIfExists: true),
                file("${fixture}/annotation.gtf", checkIfExists: true), encoded)
        }
    PEAK_ANNOTATION(annotation_inputs)

    sources = REGIONAL_CATALOG.out.manifest.map { _meta, manifest -> manifest }
        .mix(PEAK_ANNOTATION.out.manifests.map { _meta, manifest -> manifest })
        .mix(PEAK_ANNOTATION.out.manifest.map { _meta, manifest -> manifest })
    semantic = PEAK_ANNOTATION.out.artifacts.map { _meta, directory -> file("${directory}/statistics.tsv", checkIfExists: true) }
    materials = sources.toList().map { paths -> tuple('report', paths) }
        .join(semantic.toList().map { paths -> tuple('report', paths) })
    report_meta = [id: 'fixture.chipseq_report', project_id: 'fixture', dataset: 'fixture', genome_id: 'fixture_v1', build: 'fixture_v1',
        required_components: ['consensus_idr', 'annotation']]
    CHIPSEQ_FULL_REPORT_INPUT(materials.map { _key, manifests, artifacts -> tuple(report_meta, manifests, artifacts) })
    presentation = groovy.json.JsonOutput.toJson([provider: 'html_v1', title: 'Regional candidate fixture', language: 'en']).bytes.encodeBase64().toString()
    report_records = CHIPSEQ_FULL_REPORT_INPUT.out.artifacts.map { source, inventory -> tuple('report', source, inventory) }
        .join(materials).map { _key, source, inventory, manifests, artifacts -> tuple(source, inventory, manifests, artifacts, presentation) }
    CHIPSEQ_REPORT(report_records)
}
