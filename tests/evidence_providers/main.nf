nextflow.enable.dsl = 2

include { RNASEQ_EVIDENCE_PROVIDER } from '../../modules/local/rnaseq_evidence_provider/main'
include { CHIPSEQ_EVIDENCE_PROVIDER } from '../../modules/local/chipseq_evidence_provider/main'

params.assay = params.assay ?: 'rnaseq'

workflow {
    legacy = file("${projectDir}/../integrative_legacy_characterization/fixture/inputs")
    fixture = file("${projectDir}/fixture")
    if (params.assay == 'rnaseq') {
        input_ch = channel.of(tuple(
            [id: 'fixture.rnaseq'],
            file("${fixture}/rnaseq_run_manifest.json"),
            file("${fixture}/rna_bindings.json"),
            [file("${legacy}/tpm_matrix.tsv"), file("${legacy}/deg_results.tsv")]
        ))
        RNASEQ_EVIDENCE_PROVIDER(input_ch)
    } else if (params.assay == 'chipseq') {
        input_ch = channel.of(tuple(
            [id: 'fixture.chipseq'],
            file("${fixture}/chipseq_run_manifest.json"),
            file("${fixture}/chip_bindings.json"),
            [file("${legacy}/annotated_peaks_fixture.tsv"), file("${legacy}/differential_binding.tsv")]
        ))
        CHIPSEQ_EVIDENCE_PROVIDER(input_ch)
    } else {
        error "Use --assay rnaseq or chipseq"
    }
}
