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

    RSW --> TRIM["Native Trim Galore"]
    RSW --> WRAP["LEGACY_STEP module"]
    CSW --> WRAP
    ISW --> WRAP

    WRAP --> RB["rnaseq_pipeline.sh --local"]
    WRAP --> CB["chipseq_pipeline.sh --local"]
    WRAP --> IB["integrative_pipeline.sh --mode local"]
    TRIM --> TRIMMED["Legacy-compatible trimmed FASTQs"]
```

The module emits a small status JSON and a log. Scientific outputs remain in
the directories defined by each unchanged `pipeline_config.sh`.

The RNA-seq QC subworkflow reads its scientific parameters from that same
configuration, fans out one native Trim Galore task per technical run, and then
calls the legacy QC coordinator. Its trimming script sees the completed files
and skips, while FastQC, merge, and MultiQC retain their original behavior.
