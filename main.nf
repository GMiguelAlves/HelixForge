nextflow.enable.dsl = 2

include { RNASEQ }     from './workflows/rnaseq'
include { CHIPSEQ }    from './workflows/chipseq'
include { INTEGRATIVE } from './workflows/integrative'
include { ALL }        from './workflows/all'

workflow {
    def selected = params.workflow.toString().toLowerCase()
    def seed = Channel.value('omicsflow-start')

    switch (selected) {
        case 'rnaseq':
            RNASEQ(seed)
            break
        case 'chipseq':
            CHIPSEQ(seed)
            break
        case 'integrative':
            INTEGRATIVE(seed)
            break
        case 'all':
            ALL(seed)
            break
        default:
            error "Unknown workflow '${params.workflow}'. Use rnaseq, chipseq, integrative, or all."
    }
}

