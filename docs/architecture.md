# HelixForge implementation architecture

HelixForge is a compatibility-first Nextflow DSL2 platform. Native APIs exchange
typed channels and versioned manifests; unchanged pipeline coordinators remain
behind `LEGACY_STEP` only where migration or scientific validation is pending.
RNA-seq has crossed that boundary: its active DAG is fully native and the former
implementation is archived in `rnaseq-legacy-v1.0.0`.

## Top-level composition

```mermaid
flowchart TB
    MAIN["main.nf"] --> RNA["RNASEQ"]
    MAIN --> CHIP["CHIPSEQ"]
    MAIN --> INT["INTEGRATIVE"]
    MAIN --> ALL["ALL"]
    ALL --> RNA
    ALL --> CHIP
    RNA --> GATE["completion status barrier"]
    CHIP --> GATE
    GATE --> INT
```

`ALL` starts RNA-seq and ChIP-seq independently, waits for both completion
channels, then invokes Integrative. The current Integrative coordinator is a
legacy boundary and resolves its scientific inputs from the unchanged
integrative configuration. Completion status is therefore synchronization,
not an artifact API; semantic RNA+ChIP manifest coupling remains a final
validation item.

## RNA-seq native DAG

```mermaid
flowchart LR
    CTX["RNA context adapter"] --> META["RNASEQ_METADATA"]
    META --> REF["REFERENCE_BUNDLE"]
    META --> PLAN["Native QC plan"]
    PLAN --> RAW["FASTQC raw"]
    RAW --> TRIM["TRIM_GALORE"]
    TRIM --> POST["FASTQC trimmed"]
    POST --> MERGE["MERGE_FASTQ"]
    MERGE --> MQC["MULTIQC"]
    MQC --> FAN{"analysis mode"}
    FAN -->|alignment or both| SI["STAR_INDEX"]
    SI --> SA["STAR_ALIGN"]
    FAN -->|quantification or both| QI["SALMON_INDEX"]
    QI --> SQ["SALMON_QUANT"]
    SA --> IMP{"Import provider"}
    SQ --> IMP
    IMP -->|STAR| STARIMP["STAR_IMPORT"]
    IMP -->|Salmon| TX2["TX2GENE_BUILD"]
    TX2 --> TXI["TXIMPORT"]
    STARIMP --> DE["Differential Expression API"]
    TXI --> DE
    DE --> PRE["preflight"]
    PRE --> MODEL["DESEQ2_MODEL"]
    MODEL --> CONTRAST["DESEQ2_CONTRAST"]
    CONTRAST --> AGG["DE_AGGREGATE"]
    AGG --> RCTX["RNASEQ_REPORT_CONTEXT"]
    TXI --> RCTX
    STARIMP --> RCTX
    RCTX --> RPT["RNASEQ_GENE_REPORT"]
```

The default production path executes Salmon. `rnaseq_run_mode=alignment`
explicitly selects the experimental STAR stage; `quant`/`quantification`
executes only Salmon. `rnaseq_analysis_mode=both` fans the same merged reads to
independent providers. `config` retains legacy `QUANT_METHOD` compatibility but
is not the production default. Import and DE
never infer the provider from filenames: they consume provider manifests and
channels. Metadata validation and Reference Bundle construction are native;
the small context adapter only translates the existing shell configuration.
Data acquisition is outside the scientific DAG. `rnaseq_native_import=false` has no supported fallback
because the former tximport wrapper was intentionally removed.
The terminal report is optional in `full` and explicit in `report` mode. It
joins Import and DE artifacts through channels and manifest checksums; it does
not search published result directories or alter the DESeq2 inference path.

## ChIP-seq native DAG

```mermaid
flowchart LR
    CTX["Context adapter"] --> META["Metadata and controls"]
    META --> FQC["FASTQC"]
    FQC --> MQC["MULTIQC"]
    META --> IDX["BOWTIE2_INDEX keyed by reference"]
    IDX --> ALN["BOWTIE2_ALIGN"]
    ALN --> SEL["BAM_SELECT"]
    SEL --> DUP["BAM_DUPLICATES"]
    DUP --> BL["BAM_BLACKLIST"]
    BL --> FINAL["BAM_INDEX_QC"]
    FINAL --> PEAK["MACS3 Peak Calling API"]
    PEAK --> PQC["Peak QC API"]
    PQC --> CONS["Consensus or IDR context"]
    CONS --> DB["Differential Binding API"]
    PEAK -. manifest inventory .-> ANN["Peak Annotation API"]
    FINAL -. manifest inventory .-> TRACK["Track Generation API"]
    PQC -. component manifests .-> REPORT["ChIP-seq Report API"]
    CONS -. component manifests .-> REPORT
    DB -. component manifests .-> REPORT
    ANN -. component manifests .-> REPORT
    TRACK -. component manifests .-> REPORT
```

Records and Bowtie2 indices are paired by an explicit reference key, preventing
cross-reference Cartesian products. Each BAM transformation records the hash
of its upstream manifest, so the final BAM can be traced back to alignment.
Standalone `annotation`, `tracks`, and `report` modes require explicit inventory
manifests and do not search result directories.

Native staged modes are `qc`, `alignment`, `post_alignment`, `peaks`,
`peak_qc`, `consensus`, `idr`, `differential_binding`, `annotation`, `tracks`,
and `report`. ChIP-seq `full` composes those native APIs in one Nextflow session,
passing typed channels and manifests from QC through the final report. It has no
legacy fallback. IDR validates its request but honestly reports
`not_implemented`; it does not fabricate a result.

## Contracts and provenance

All new modules follow [module contracts](module_contracts.md). API manifests
use the common envelope in `schemas/manifest-v1.schema.json`:
`schema_version`, `type`, stable `id`, and honest `status`. Cross-API lineage is
recorded with upstream manifest checksums. Scientific outputs keep the legacy
names and locations where compatibility requires them.

Scientific parameters remain explicit in `nextflow.config` and are all exposed
by `nextflow_schema.json`. Scheduler queues, resources and environment engines
remain orchestration concerns; scientific defaults stay in the authoritative
pipeline configuration until their controlled migration.

## Deliberate legacy boundaries

- Optional exploratory Batch Effect Assessment API, tracked in the
  [scientific roadmap](roadmap.md). The current inferential DAG never consumes
  a batch-corrected matrix.
- ChIP-seq legacy per-stage compatibility execution outside native `full`.
- Integrative execution and its configured input discovery.
- RNA Pathway Enrichment API and any analysis not yet represented by a native
  provider, tracked in the [scientific roadmap](roadmap.md).

These boundaries are not described as scientifically validated native paths.
Their replacement requires the mandatory comparisons in
[final validation plan](final-validation-plan.md).
