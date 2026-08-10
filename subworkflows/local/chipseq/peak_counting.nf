include { FEATURECOUNTS_PEAK } from '../../../modules/local/featurecounts_peak/main'

workflow PEAK_COUNTING_PROVIDER {
    take:
    requests

    main:
    provider = params.chipseq_db_count_provider.toString().toLowerCase()
    if (provider == 'featurecounts') {
        FEATURECOUNTS_PEAK(requests)
        artifacts_ch = FEATURECOUNTS_PEAK.out.artifacts
        reports_ch = FEATURECOUNTS_PEAK.out.reports
        versions_ch = FEATURECOUNTS_PEAK.out.versions
        execution_ch = FEATURECOUNTS_PEAK.out.execution_metadata
        manifest_ch = FEATURECOUNTS_PEAK.out.manifest
        status_ch = FEATURECOUNTS_PEAK.out.status
    } else {
        error "Unsupported PEAK_COUNTING_PROVIDER '${provider}'"
    }

    emit:
    artifacts          = artifacts_ch
    reports            = reports_ch
    versions           = versions_ch
    execution_metadata = execution_ch
    manifest           = manifest_ch
    status             = status_ch
}
