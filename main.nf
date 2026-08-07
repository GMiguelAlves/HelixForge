nextflow.enable.dsl = 2

include { RNASEQ }     from './workflows/rnaseq'
include { CHIPSEQ }    from './workflows/chipseq'
include { INTEGRATIVE } from './workflows/integrative'
include { ALL }        from './workflows/all'

workflow {
    def selected = params.workflow.toString().toLowerCase()
    def seed = channel.value('omicsflow-start')

    if (selected == 'rnaseq') {
        RNASEQ(seed)
    } else if (selected == 'chipseq') {
        CHIPSEQ(seed)
    } else if (selected == 'integrative') {
        INTEGRATIVE(seed)
    } else if (selected == 'all') {
        ALL(seed)
    } else {
        error "Unknown workflow '${params.workflow}'. Use rnaseq, chipseq, integrative, or all."
    }
}
