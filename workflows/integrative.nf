include { NATIVE_INTEGRATION } from '../subworkflows/local/integrative/native_integration'

workflow INTEGRATIVE {
    take:
    rna_bundle
    chip_bundle

    main:
    NATIVE_INTEGRATION(rna_bundle, chip_bundle)

    emit:
    completed = NATIVE_INTEGRATION.out.status
    terminal_manifest = NATIVE_INTEGRATION.out.terminal_manifest
    report = NATIVE_INTEGRATION.out.report
    master_evidence = NATIVE_INTEGRATION.out.master_evidence
    interpretation = NATIVE_INTEGRATION.out.interpretation
    functional = NATIVE_INTEGRATION.out.functional
    visualization = NATIVE_INTEGRATION.out.visualization
    logs = NATIVE_INTEGRATION.out.logs
}
