process TXIMPORT {
    tag "${meta.id}"
    label 'native_module'
    label 'import_medium'

    cpus 2
    memory 32.GB
    time 6.h
    queue { params.tximport_queue ?: null }
    cache 'deep'
    errorStrategy { task.exitStatus in 130..145 ? 'retry' : 'terminate' }
    maxRetries 2

    container "${workflow.containerEngine in ['singularity', 'apptainer'] ? params.tximport_apptainer_container : params.tximport_container}"
    conda "${moduleDir}/environment.yml"

    publishDir { meta.target_dir }, mode: 'copy', overwrite: true,
        pattern: '{counts_matrix.tsv,tpm_matrix.tsv,length_matrix.tsv,summarized_experiment.rds,quant_samples.tsv}'
    publishDir "${params.outdir}/pipeline_info/native_import/tximport",
        mode: 'copy', overwrite: true,
        pattern: '*.{json,yml,txt,log,tsv,done}'

    input:
    tuple val(meta), path(sample_table), val(import_params)
    tuple val(tx2gene_meta), path(tx2gene)
    path sources

    output:
    tuple val(meta), path('counts_matrix.tsv'), emit: counts
    tuple val(meta), path('tpm_matrix.tsv'), emit: abundance
    tuple val(meta), path('length_matrix.tsv'), emit: lengths
    tuple val(meta), path('summarized_experiment.rds'), emit: experiment
    tuple val(meta), path('quant_samples.tsv'), emit: metadata
    tuple val(meta), path('import.log'), path('import_statistics.tsv'), emit: reports
    tuple val(meta), path('versions.yml'), emit: versions
    tuple val(meta), path('execution.json'), path('sessionInfo.txt'), emit: execution_metadata
    tuple val(meta), path('import_manifest.json'), emit: manifest
    tuple val(meta), path('tximport.done'), emit: status
    tuple val(meta), path('counts_matrix.tsv'), path('tpm_matrix.tsv'), path('length_matrix.tsv'),
        path('summarized_experiment.rds'), path('quant_samples.tsv'), emit: artifacts

    script:
    def sourceArgs = sources.collect { source -> "'${source}'" }.join(' ')
    """
    start_epoch=\$(date +%s)
    tximport_quant.R \
        --sample-table '${sample_table}' \
        --tx2gene '${tx2gene}' \
        --counts-from-abundance '${import_params.countsFromAbundance}' \
        --ignore-tx-version '${import_params.ignoreTxVersion}' \
        --ignore-after-bar '${import_params.ignoreAfterBar}' \
        --unmapped-transcripts '${import_params.unmappedTranscripts}' \
        --counts-name counts_matrix.tsv \
        --abundance-name tpm_matrix.tsv \
        --length-name length_matrix.tsv \
        --experiment-name summarized_experiment.rds \
        --metadata-name quant_samples.tsv \
        > import.log 2>&1
    Rscript -e 'sessionInfo()' > sessionInfo.txt

    counts_sha=\$(sha256sum counts_matrix.tsv | awk '{print \$1}')
    abundance_sha=\$(sha256sum tpm_matrix.tsv | awk '{print \$1}')
    length_sha=\$(sha256sum length_matrix.tsv | awk '{print \$1}')
    experiment_sha=\$(sha256sum summarized_experiment.rds | awk '{print \$1}')
    metadata_sha=\$(sha256sum quant_samples.tsv | awk '{print \$1}')
    tx2gene_sha=\$(sha256sum '${tx2gene}' | awk '{print \$1}')
    sources_sha=\$(find ${sourceArgs} -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print \$1}')
    sample_count=\$(awk 'END {print NR-1}' quant_samples.tsv)
    end_epoch=\$(date +%s)
    r_version=\$(Rscript -e 'cat(as.character(getRversion()))')
    tximport_version=\$(Rscript -e 'cat(as.character(packageVersion("tximport")))')
    summarized_experiment_version=\$(Rscript -e 'cat(as.character(packageVersion("SummarizedExperiment")))')
    readr_version=\$(Rscript -e 'cat(as.character(packageVersion("readr")))')
    data_table_version=\$(Rscript -e 'cat(as.character(packageVersion("data.table")))')

    printf '"%s":\n    r: "%s"\n    bioconductor: "3.18"\n    tximport: "%s"\n    SummarizedExperiment: "%s"\n    readr: "%s"\n    data.table: "%s"\n' \
        '${task.process}' "\$r_version" "\$tximport_version" "\$summarized_experiment_version" \
        "\$readr_version" "\$data_table_version" > versions.yml
    printf '{"id":"%s","process":"%s","parameters":{"type":"salmon","countsFromAbundance":"%s","libraryProtocol":"%s","ignoreTxVersion":%s,"ignoreAfterBar":%s,"unmappedTranscripts":"%s"},"cpus":%s,"memory_bytes":%s,"time":"%s","container":"%s","sources_sha256":"%s","tx2gene_sha256":"%s","started_epoch":%s,"ended_epoch":%s,"elapsed_seconds":%s}\n' \
        '${meta.id}' '${task.process}' '${import_params.countsFromAbundance}' '${import_params.libraryProtocol}' '${import_params.ignoreTxVersion}' '${import_params.ignoreAfterBar}' '${import_params.unmappedTranscripts}' '${task.cpus}' '${task.memory.toBytes()}' '${task.time}' \
        '${params.tximport_container}' "\$sources_sha" "\$tx2gene_sha" "\$start_epoch" "\$end_epoch" \
        "\$((end_epoch-start_epoch))" > execution.json
    printf '{"schema_version":"1.0","type":"import","id":"%s","status":"complete","provider":"salmon","sample_count":%s,"parameters":{"countsFromAbundance":"%s","libraryProtocol":"%s","ignoreTxVersion":%s,"ignoreAfterBar":%s,"unmappedTranscripts":"%s"},"artifacts":{"counts":{"path":"counts_matrix.tsv","sha256":"%s","available":true},"abundance":{"path":"tpm_matrix.tsv","sha256":"%s","available":true},"lengths":{"path":"length_matrix.tsv","sha256":"%s","available":true},"experiment":{"path":"summarized_experiment.rds","sha256":"%s","available":true},"metadata":{"path":"quant_samples.tsv","sha256":"%s","available":true}},"tx2gene_sha256":"%s"}\n' \
        '${meta.id}' "\$sample_count" '${import_params.countsFromAbundance}' '${import_params.libraryProtocol}' '${import_params.ignoreTxVersion}' '${import_params.ignoreAfterBar}' '${import_params.unmappedTranscripts}' "\$counts_sha" "\$abundance_sha" "\$length_sha" \
        "\$experiment_sha" "\$metadata_sha" "\$tx2gene_sha" > import_manifest.json
    printf '{"id":"%s","process":"%s","status":"complete"}\n' \
        '${meta.id}' '${task.process}' > tximport.done
    """

    stub:
    """
    printf 'gene_id\tSTUB__stub_sample\ngene_stub\t1\n' > counts_matrix.tsv
    printf 'gene_id\tSTUB__stub_sample\ngene_stub\t1000000\n' > tpm_matrix.tsv
    printf 'gene_id\tSTUB__stub_sample\ngene_stub\t80\n' > length_matrix.tsv
    printf 'stub-rds\n' > summarized_experiment.rds
    awk -F '\t' 'BEGIN{OFS="\t"} NR==1{for(i=1;i<=NF;i++) if(\$i !~ /^__/) keep[i]=1} {out=""; for(i=1;i<=NF;i++) if(keep[i]) out=out (out?OFS:"") \$i; print out}' '${sample_table}' > quant_samples.tsv
    printf '[STUB] tximport\n' > import.log
    printf 'metric\tvalue\nsamples\t1\ngenes\t1\nsum_counts\t1\nsum_abundance\t1000000\n' > import_statistics.tsv
    printf 'stub\n' > sessionInfo.txt
    printf '"TXIMPORT":\n    r: "stub"\n    bioconductor: "stub"\n    tximport: "stub"\n    SummarizedExperiment: "stub"\n    readr: "stub"\n    data.table: "stub"\n' > versions.yml
    printf '{"id":"%s","process":"TXIMPORT","status":"stub"}\n' '${meta.id}' > execution.json
    printf '{"schema_version":"1.0","type":"import","id":"%s","status":"stub","provider":"salmon"}\n' '${meta.id}' > import_manifest.json
    printf '{"id":"%s","process":"TXIMPORT","status":"stub"}\n' '${meta.id}' > tximport.done
    """
}
