include { INTEGRATION } from '../subworkflows/local/integrative/integration'

workflow INTEGRATIVE {
    take:
    seed

    main:
    config_file = file(params.integrative_config, checkIfExists: true)
    legacy_root = "${projectDir}/pipelines/integrative/legacy"
    INTEGRATION(config_file, legacy_root, seed)

    emit:
    completed = INTEGRATION.out.status
    logs      = INTEGRATION.out.logs
}

