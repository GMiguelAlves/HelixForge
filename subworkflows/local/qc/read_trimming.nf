include { READ_TRIMMING_AUDIT as TRIMMING_PREFLIGHT } from '../../../modules/local/read_trimming_audit/main'
include { READ_TRIMMING_AUDIT as TRIMMING_OUTPUT_AUDIT } from '../../../modules/local/read_trimming_audit/main'
include { TRIM_GALORE } from '../../../modules/local/trim_galore/main'
include { TRIM_GALORE_SINGLE } from '../../../modules/local/trim_galore_single/main'

workflow READ_TRIMMING {
    take:
    trimming_inputs // tuple(meta, ordered reads, explicit policy)

    main:
    requests = trimming_inputs.map { meta, reads, policy ->
        def ordered = reads instanceof List ? reads : [reads]
        if (!(meta.single_end instanceof Boolean) || ordered.size() != (meta.single_end ? 1 : 2)) {
            error 'Read-trimming layout and FASTQ cardinality disagree'
        }
        if (!meta.id.toString().matches(/[A-Za-z0-9_][A-Za-z0-9_.-]*/)) {
            error 'Read trimming requires a safe record ID'
        }
        tuple(meta, ordered, policy, [], [])
    }
    TRIMMING_PREFLIGHT(requests)
    policies = trimming_inputs.map { meta, _reads, policy -> tuple(meta.id, policy) }
    checked = TRIMMING_PREFLIGHT.out.artifacts
        .map { meta, reads, manifest -> tuple(meta.id, meta, reads, manifest) }
        .join(policies)
        .map { _id, meta, reads, manifest, policy ->
            def trim_meta = meta + [
                source_meta: meta, trim_policy: policy, trim_quality: policy.quality, trim_length: policy.minimum_length,
                trim_adapter: policy.adapter, trim_adapter2: policy.adapter2,
                trim_force_gzip: true, trim_legacy_publish: false, trim_native_publish: true,
                trimmed_dir: "${params.outdir}/trimmed_reads/${meta.id}",
                trimmed_r1_name: "${meta.id}.trimmed_R1.fq.gz",
                trimmed_r2_name: "${meta.id}.trimmed_R2.fq.gz"
            ]
            tuple(trim_meta, reads, manifest)
        }
    paired = checked.filter { meta, _reads, _manifest -> !meta.single_end }
        .map { meta, reads, _manifest -> tuple(meta, reads[0], reads[1]) }
    single = checked.filter { meta, _reads, _manifest -> meta.single_end }
        .map { meta, reads, _manifest -> tuple(meta, reads instanceof List ? reads[0] : reads) }
    TRIM_GALORE(paired)
    TRIM_GALORE_SINGLE(single)
    trimmed = TRIM_GALORE.out.artifacts.map { meta, r1, r2 -> tuple(meta.id, meta, [r1, r2]) }
        .mix(TRIM_GALORE_SINGLE.out.artifacts.map { meta, r1 -> tuple(meta.id, meta, [r1]) })
    versions = TRIM_GALORE.out.versions.mix(TRIM_GALORE_SINGLE.out.versions)
        .map { meta, version -> tuple(meta.id, version) }
    prior = TRIMMING_PREFLIGHT.out.manifest.map { meta, manifest -> tuple(meta.id, manifest) }
    audit_inputs = trimmed.join(versions).join(prior)
        .map { _id, meta, reads, version, manifest ->
            tuple(meta.source_meta + [read_processing: 'trimmed'], reads, meta.trim_policy, [manifest], [version])
        }
    TRIMMING_OUTPUT_AUDIT(audit_inputs)

    emit:
    artifacts = TRIMMING_OUTPUT_AUDIT.out.artifacts.map { meta, reads, _manifest -> tuple(meta, reads instanceof List ? reads : [reads]) }
    manifest = TRIMMING_OUTPUT_AUDIT.out.manifest
    reports = TRIM_GALORE.out.reports.mix(TRIM_GALORE_SINGLE.out.reports)
    logs = TRIMMING_PREFLIGHT.out.reports.mix(TRIMMING_OUTPUT_AUDIT.out.reports)
    versions = TRIM_GALORE.out.versions.mix(TRIM_GALORE_SINGLE.out.versions)
    status = TRIMMING_OUTPUT_AUDIT.out.status
}
