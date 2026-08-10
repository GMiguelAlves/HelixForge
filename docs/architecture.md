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
    RSW --> RNAALIGN["Generic Alignment API"]
    RSW --> RNAQUANT["Generic Quantification API"]
    RSW --> RNAIMPORT["Generic Import API"]
    RSW --> RNADE["Generic Differential Expression API"]
    RSW --> WRAP["LEGACY_STEP module"]
    CSW --> WRAP
    CSW --> CHIPNATIVE["Native ChIP foundation"]
    ISW --> WRAP

    WRAP --> RB["rnaseq_pipeline.sh --local"]
    WRAP --> CB["chipseq_pipeline.sh --local"]
    WRAP --> IB["integrative_pipeline.sh --mode local"]
    QC --> FASTQC["FastQC raw / trimmed / merged"]
    QC --> TRIM["Trim Galore"]
    QC --> MERGE["FASTQ merge"]
    QC --> MULTIQC["MultiQC"]
    RNAALIGN --> REFINDEX["REFERENCE_INDEX"]
    REFINDEX --> STARINDEX["STAR_INDEX"]
    REFINDEX --> BOWTIEINDEX["BOWTIE2_INDEX"]
    RNAALIGN --> ALIGN["ALIGNMENT"]
    ALIGN --> STARALIGN["STAR_ALIGN"]
    ALIGN --> BOWTIEALIGN["BOWTIE2_ALIGN"]
    STARINDEX --> STARALIGN
    BOWTIEINDEX --> BOWTIEALIGN
    STARALIGN --> STAROUT["Legacy-compatible BAM, counts, logs"]
    RNAQUANT --> TRANSCRIPTINDEX["TRANSCRIPTOME_INDEX"]
    TRANSCRIPTINDEX --> SALMONINDEX["SALMON_INDEX"]
    RNAQUANT --> QUANTIFY["QUANTIFICATION"]
    QUANTIFY --> SALMONQUANT["SALMON_QUANT"]
    SALMONINDEX --> SALMONQUANT
    SALMONQUANT --> SALMONOUT["Legacy-compatible quant.sf, JSON, aux_info, logs"]
    STAROUT --> RNAIMPORT
    SALMONOUT --> RNAIMPORT
    RNAIMPORT --> SOURCE["IMPORT_SOURCE manifest validation"]
    SOURCE --> PROVIDER{"Provider"}
    PROVIDER -->|Salmon| TX2GENE["TX2GENE_BUILD"]
    TX2GENE --> TXIMPORT["TXIMPORT"]
    PROVIDER -->|STAR| STARIMPORT["STAR_IMPORT"]
    TXIMPORT --> COMMON["Counts + abundance + metadata + provenance"]
    STARIMPORT --> COMMON
    COMMON --> RNADE
    RNADE --> PREFLIGHT["Design and contrast preflight"]
    PREFLIGHT --> MODEL["DESEQ2_MODEL"]
    MODEL --> CONTRAST["DESEQ2_CONTRAST per comparison"]
    CONTRAST --> DEOUT["Common + legacy DEG outputs"]
    DEOUT --> WRAP
    TRIM --> TRIMMED["Legacy-compatible run FASTQs"]
    MERGE --> MERGED["Legacy-compatible sample FASTQs"]
    CHIPNATIVE --> CHIPMETA["ChIP metadata/control validation"]
    CHIPMETA --> FASTQC
    CHIPMETA --> BOWTIEALIGN
    BOWTIEALIGN --> CHIPBAM["Sorted BAM + BAI + statistics"]
    CHIPBAM --> BAMSELECT["BAM_SELECT"]
    BAMSELECT --> BAMDUP["BAM_DUPLICATES"]
    BAMDUP --> BAMBLACK["BAM_BLACKLIST"]
    BAMBLACK --> BAMFINAL["BAM_INDEX_QC + final BAM"]
    CHIPMETA --> PEAKCTX["PEAK_CALLING_CONTEXT"]
    BAMFINAL --> MACS3["PEAK_CALLING / MACS3 3.0.4"]
    PEAKCTX --> MACS3
    MACS3 --> PEAKOUT["Semantic peaks + metrics + manifest"]
```

Native modules emit primary artifacts, reports, versions, and status tuples.
Scientific outputs remain in the directories defined by each unchanged
`pipeline_config.sh`.

The RNA-seq QC subworkflow reads its scientific parameters from that same
configuration, fans out one FastQC task per FASTQ and one Trim Galore task per
technical run, groups trimmed runs by biological sample for byte-concatenation,
and runs a reusable MultiQC process. The legacy QC coordinator is used only
when native QC is explicitly disabled.

The alignment adapter converts the unchanged STAR plan into Alignment API
tuples. The quantification adapter converts the unchanged Salmon plan into
Quantification API tuples. Each API owns an independent content-tracked index
and per-sample provider. `rnaseq_analysis_mode=both` fans merged FASTQs into
both branches; no STAR output is an input to Salmon.

The Import API consumes only the provider selected by authoritative
`QUANT_METHOD`. It validates upstream manifests, builds a sample table, then
normalizes Salmon through `TX2GENE_BUILD` + `TXIMPORT` or STAR gene counts
through `STAR_IMPORT`. The Differential Expression API consumes only the
common matrix, metadata, manifest, and a user-supplied DE specification. The
native path models batch only as an explicit design covariate and does not run
matrix correction before DESeq2. The legacy batch wrapper remains available
only with the legacy DE fallback; final reporting remains a compatibility
wrapper.

For ChIP-seq, `qc`, `alignment`, `post_alignment`, `peaks`, `peak_qc`,
`consensus`, `idr`, and `differential_binding` use the native foundation. The workflow
reuses generic FastQC/MultiQC and the generic Alignment API with Bowtie2.
MAPQ/flag selection, duplicate handling, optional blacklist exclusion and final
BAM integrity/QC, per-replicate peak calling, Peak QC and interval consensus
are native independent boundaries. IDR currently validates a provider request
without producing statistical peaks. Differential Binding has native preflight,
featureCounts, DESeq2 model/contrast and manifest boundaries, while its legacy
step remains selectable. Annotation, tracks and reporting remain legacy.
See `docs/chipseq-architecture.md` for the staged graph.
