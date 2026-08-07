include { LEGACY_STEP as RNASEQ_ALIGNMENT_STEP }      from '../../../modules/local/legacy_step/main'
include { LEGACY_STEP as RNASEQ_QUANTIFICATION_STEP } from '../../../modules/local/legacy_step/main'
include { RNASEQ_ALIGNMENT_PLAN }                     from '../../../modules/local/rnaseq_alignment_plan/main'
include { REFERENCE_INDEX }                           from '../alignment/reference_index'
include { ALIGNMENT }                                 from '../alignment/alignment'

workflow RNASEQ_ALIGNMENT_QUANTIFICATION {
    take:
    config_file
    legacy_root
    reference_status
    qc_status
    qc_plans

    main:
    no_dep = channel.value('none')
    native_alignment_enabled = params.rnaseq_native_alignment instanceof Boolean \
        ? params.rnaseq_native_alignment \
        : params.rnaseq_native_alignment.toString().toBoolean()

    if (native_alignment_enabled) {
        RNASEQ_ALIGNMENT_PLAN(
            config_file,
            legacy_root,
            qc_plans,
            reference_status,
            qc_status
        )

        settings_rows = RNASEQ_ALIGNMENT_PLAN.out.settings
            .splitCsv(header: true, sep: '\t')

        star_settings = settings_rows
            .filter { row -> row.method == 'star' }

        index_inputs = star_settings
            .map { row ->
                def safe_reference = file(row.reference).baseName.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def meta = [
                    id        : "star.${safe_reference}.index",
                    aligner   : 'star',
                    target_dir: row.index_dir,
                    project   : row.project
                ]
                def index_params = [
                    genome_sa_index_nbases   : row.genome_sa_index_nbases,
                    limit_genome_generate_ram: row.limit_genome_generate_ram
                ]
                tuple(
                    meta,
                    file(row.reference, checkIfExists: true),
                    file(row.annotation, checkIfExists: true),
                    index_params
                )
            }
            .unique { item -> item[0].target_dir }

        REFERENCE_INDEX(index_inputs)

        settings_by_project = star_settings.map { row -> tuple(row.project, row) }
        samples_by_project = RNASEQ_ALIGNMENT_PLAN.out.plans
            .splitCsv(header: true)
            .map { row -> tuple(row.dataset, row) }

        sample_specs = samples_by_project
            .join(settings_by_project)
            .map { project, sample, settings ->
                def safe_dataset = project.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def safe_sample = sample.sample_id.replaceAll(/[^A-Za-z0-9_.-]/, '_')
                def meta = [
                    id        : "${safe_dataset}.${safe_sample}.alignment",
                    aligner   : 'star',
                    dataset   : project,
                    sample_id : sample.sample_id,
                    single_end: false,
                    target_dir: sample.star_dir
                ]
                def reads = [
                    file(sample.merged_sample_r1, checkIfExists: true),
                    file(sample.merged_sample_r2, checkIfExists: true)
                ]
                def alignment_params = [
                    read_files_command: settings.read_files_command,
                    extra_args        : settings.extra_args
                ]
                tuple(
                    meta,
                    reads,
                    file(settings.reference, checkIfExists: true),
                    file(settings.annotation, checkIfExists: true),
                    alignment_params
                )
            }

        samples_by_index_key = sample_specs.map { meta, reads, reference, annotation, alignment_params ->
            tuple(meta.dataset, meta, reads, reference, annotation, alignment_params)
        }
        indexes_by_project = REFERENCE_INDEX.out.artifacts.map { index_meta, index ->
            tuple(index_meta.project, index)
        }

        alignment_inputs = samples_by_index_key
            .join(indexes_by_project)
            .map { _project, meta, reads, reference, annotation, alignment_params, index ->
                tuple(meta, reads, reference, annotation, index, alignment_params)
            }

        ALIGNMENT(alignment_inputs)

        salmon_gate = settings_rows
            .filter { row -> row.method == 'salmon' }
            .map { _row -> 'salmon' }
            .first()

        RNASEQ_ALIGNMENT_STEP(
            'rnaseq', 'salmon', 'high_cpu', config_file, legacy_root,
            reference_status, qc_status, salmon_gate
        )

        alignment_status = ALIGNMENT.out.status
            .mix(RNASEQ_ALIGNMENT_STEP.out.status)
            .collect()
        alignment_logs = RNASEQ_ALIGNMENT_PLAN.out.log
            .mix(REFERENCE_INDEX.out.reports)
            .mix(ALIGNMENT.out.logs)
            .mix(RNASEQ_ALIGNMENT_STEP.out.log)
    } else {
        RNASEQ_ALIGNMENT_STEP(
            'rnaseq', 'salmon', 'high_cpu', config_file, legacy_root,
            reference_status, qc_status, no_dep
        )
        alignment_status = RNASEQ_ALIGNMENT_STEP.out.status
        alignment_logs = RNASEQ_ALIGNMENT_STEP.out.log
    }

    RNASEQ_QUANTIFICATION_STEP(
        'rnaseq', 'tximport', 'medium', config_file, legacy_root,
        alignment_status, no_dep, no_dep
    )

    emit:
    status = RNASEQ_QUANTIFICATION_STEP.out.status
    logs   = alignment_logs.mix(RNASEQ_QUANTIFICATION_STEP.out.log)
}
