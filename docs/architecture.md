# Implementation architecture

```mermaid
flowchart TB
    MAIN["main.nf"] --> RNA["workflow rnaseq"]
    MAIN --> CHIP["workflow chipseq"]
    MAIN --> INT["workflow integrative"]
    MAIN --> ALL["workflow all"]

    RNA --> RSW["RNA subworkflows"]
    CHIP --> CSW["ChIP subworkflows"]
    INT --> ISW["Integration subworkflow"]

    RSW --> QC["Native RNA QC subworkflow"]
    RSW --> WRAP["LEGACY_STEP module"]
    CSW --> WRAP
    ISW --> WRAP

    WRAP --> RB["rnaseq_pipeline.sh --local"]
    WRAP --> CB["chipseq_pipeline.sh --local"]
    WRAP --> IB["integrative_pipeline.sh --mode local"]
    QC --> FASTQC["FastQC raw / trimmed / merged"]
    QC --> TRIM["Trim Galore"]
    QC --> MERGE["FASTQ merge"]
    QC --> MULTIQC["MultiQC"]
    TRIM --> TRIMMED["Legacy-compatible run FASTQs"]
    MERGE --> MERGED["Legacy-compatible sample FASTQs"]
```

Native modules emit primary artifacts, reports, versions, and status tuples.
Scientific outputs remain in the directories defined by each unchanged
`pipeline_config.sh`.

The RNA-seq QC subworkflow reads its scientific parameters from that same
configuration, fans out one FastQC task per FASTQ and one Trim Galore task per
technical run, groups trimmed runs by biological sample for byte-concatenation,
and runs a reusable MultiQC process. The legacy QC coordinator is used only
when native QC is explicitly disabled.
