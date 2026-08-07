include { SALMON_QUANT } from '../../../modules/local/salmon_quant/main'

workflow QUANTIFICATION {
    take:
    quantification_inputs

    main:
    provider_inputs = quantification_inputs.map { meta, reads, transcriptome, transcriptome_index, quantification_params ->
        if (meta.quantifier != 'salmon') {
            error "Unsupported quantification provider: ${meta.quantifier}"
        }
        tuple(meta, reads, transcriptome, transcriptome_index, quantification_params)
    }

    SALMON_QUANT(provider_inputs)

    quantification_ch = SALMON_QUANT.out.artifacts.map { meta, quant_dir ->
        tuple(meta, quant_dir.resolve('quant.sf'))
    }
    command_info_ch = SALMON_QUANT.out.artifacts.map { meta, quant_dir ->
        tuple(meta, quant_dir.resolve('cmd_info.json'))
    }
    library_format_ch = SALMON_QUANT.out.artifacts.map { meta, quant_dir ->
        tuple(meta, quant_dir.resolve('lib_format_counts.json'))
    }
    auxiliary_ch = SALMON_QUANT.out.artifacts.map { meta, quant_dir ->
        tuple(meta, quant_dir.resolve('aux_info'))
    }
    logs_ch = SALMON_QUANT.out.reports.map { meta, logs, _statistics -> tuple(meta, logs) }
    statistics_ch = SALMON_QUANT.out.reports.map { meta, _logs, statistics -> tuple(meta, statistics) }

    emit:
    quantification     = quantification_ch
    command_info       = command_info_ch
    library_format     = library_format_ch
    auxiliary          = auxiliary_ch
    logs               = logs_ch
    statistics         = statistics_ch
    versions           = SALMON_QUANT.out.versions
    execution_metadata = SALMON_QUANT.out.execution_metadata
    manifest           = SALMON_QUANT.out.manifest
    status             = SALMON_QUANT.out.status
    artifacts          = SALMON_QUANT.out.artifacts
    reports            = SALMON_QUANT.out.reports
}
