include { RNASEQ as ALL_RNASEQ }         from './rnaseq'
include { CHIPSEQ as ALL_CHIPSEQ }       from './chipseq'
include { INTEGRATIVE as ALL_INTEGRATIVE } from './integrative'

workflow ALL {
    take:
    seed

    main:
    ALL_RNASEQ(seed)
    ALL_CHIPSEQ(seed)

    ALL_INTEGRATIVE(ALL_RNASEQ.out.terminal_bundle, ALL_CHIPSEQ.out.terminal_bundle)

    emit:
    completed = ALL_INTEGRATIVE.out.completed
    terminal_manifests = ALL_RNASEQ.out.terminal_manifest
        .mix(ALL_CHIPSEQ.out.terminal_manifest)
        .mix(ALL_INTEGRATIVE.out.terminal_manifest)
    logs      = ALL_RNASEQ.out.logs
        .mix(ALL_CHIPSEQ.out.logs)
        .mix(ALL_INTEGRATIVE.out.logs)
}
