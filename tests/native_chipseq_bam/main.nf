nextflow.enable.dsl = 2

include { CHIPSEQ_BAM_PROCESSING } from '../../subworkflows/local/chipseq/bam_processing'

workflow {
    bam = file(params.bam, checkIfExists: true)
    bai = file(params.bai, checkIfExists: true)
    reference = file(params.reference, checkIfExists: true)
    blacklist = params.blacklist ? file(params.blacklist, checkIfExists: true) : []
    upstream_manifest = file(params.upstream_manifest, checkIfExists: true)

    with_blacklist = tuple(
        [
            id              : 'rep_blacklist',
            sample_id       : 'rep_blacklist',
            dataset         : 'BAM_TEST',
            single_end      : false,
            final_target_dir: "${params.target_root}/rep_blacklist"
        ],
        bam,
        bai,
        reference,
        blacklist,
        [min_mapq: 30, include_flags: 0, exclude_flags: 2308, region: ''],
        [mode: 'remove'],
        [overlap_mode: 'fragment'],
        [sort_if_needed: false],
        upstream_manifest
    )
    without_blacklist = tuple(
        [
            id              : 'rep_no_blacklist',
            sample_id       : 'rep_no_blacklist',
            dataset         : 'BAM_TEST',
            single_end      : false,
            final_target_dir: "${params.target_root}/rep_no_blacklist"
        ],
        bam,
        bai,
        reference,
        [],
        [min_mapq: 30, include_flags: 0, exclude_flags: 2308, region: ''],
        [mode: 'none'],
        [overlap_mode: 'fragment'],
        [sort_if_needed: false],
        upstream_manifest
    )

    CHIPSEQ_BAM_PROCESSING(channel.of(with_blacklist, without_blacklist))
}
