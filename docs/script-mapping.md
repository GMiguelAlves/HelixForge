# Legacy script to Nextflow mapping

> **Historical migration reference.** This mapping explains provenance of the
> current modules; users do not need it to run HelixForge.

No scientific script was rewritten. `LEGACY_STEP` is included under a distinct
process alias for every coarse step below. Each alias calls the existing top
level orchestrator with one `--step` and forces local execution.

## RNA-seq

| Nextflow alias | Legacy coarse step | Scripts reached by the existing orchestrator |
|---|---|---|
| `RNASEQ_CONTEXT` | compatibility adapter | Reads the existing shell configuration once and materializes tracked settings; performs no acquisition or scientific work |
| `RNASEQ_METADATA` | native metadata module | Replaces the metadata wrapper and `RNASEQ_QC_PLAN`; validates a supplied samplesheet/local FASTQs and preserves established QC filenames |
| `REFERENCE_BUNDLE` | native reference module | Replaces `RNASEQ_REFERENCE_STEP`; validates supplied transcriptome/annotation/genome files and records SHA-256 checksums without downloading or indexing |
| Data acquisition | outside scientific DAG | No downloader is scheduled by `RNASEQ`; users provide validated local FASTQs |
| `FASTQC_RAW` | native per-FASTQ process | Replaces `fastqc_raw_plan.sh`; invokes the same FastQC command and writes to `fastqc_raw` |
| `TRIM_GALORE` | native per-run process | Executes the same `trim_galore --paired --quality --length --cores --output_dir` command previously in `trim_runs_plan.sh` |
| `FASTQC_TRIMMED` | native per-FASTQ process | Replaces `fastqc_trimmed_runs_plan.sh` and writes to `fastqc_trimmed_runs` |
| `MERGE_FASTQ` | native per-sample process | Replaces `merge_samples_plan.sh` / `merge_sample_from_plan.py`; concatenates ordered gzip members without recompression |
| `FASTQC_MERGED` | native per-FASTQ process | Replaces `fastqc_merged_plan.sh` and writes to `fastqc_merged` |
| `MULTIQC` | native reusable process | Replaces `multiqc_plan.sh`; consumes generic compatible artifacts and writes the same named report under `multiqc_030` |
| `RNASEQ_QC_STEP` | retired | No longer reachable; false native-QC flags fail explicitly |
| `RNASEQ_ALIGNMENT_PLAN` | compatibility adapter | Sources the transitional shell config and invokes its module-owned `generate_star_plan.py`; no scientific command is copied into Nextflow |
| `REFERENCE_INDEX` / `STAR_INDEX` | native index API/provider | Replaces STAR `genomeGenerate` in `star_index_gtf.sh` with the same parameters and resources |
| `ALIGNMENT` / `STAR_ALIGN` | native alignment API/provider | Replaces `run_star_quant_project.sh` / `star_quant_array_task.sh` with one task per sample and preserves every STAR filename |
| `RNASEQ_QUANTIFICATION_PLAN` | compatibility adapter | Sources the transitional shell config and invokes its module-owned `generate_salmon_plan.py`; emits generic Quantification API inputs |
| `TRANSCRIPTOME_INDEX` / `SALMON_INDEX` | native index API/provider | Replaces scientific execution in `salmon_index.sh` with the same transcriptome, k-mer, threads, resources, and filenames |
| `QUANTIFICATION` / `SALMON_QUANT` | native quantification API/provider | Replaces `run_alignment_project.sh` / `salmon_quant_plan.sh` with one task per sample and preserves the complete Salmon directory |
| Native provider guard | alignment/quantification boundary | The provider selected by `QUANT_METHOD` must emit a native manifest; legacy STAR/Salmon fallbacks are no longer scheduled in an Import API run |
| `RNASEQ_IMPORT_CONTEXT` | compatibility adapter | Receives native metadata and Reference Bundle annotation as tracked inputs; reads only remaining target/provider settings from the shell config |
| `IMPORT_SOURCE` | native manifest adapter | Validates provider, semantic role, sample identity, compatibility path, and SHA-256 before staging each upstream artifact |
| `IMPORT_SAMPLE_TABLE` | native metadata adapter | Replaces the inline legacy sample-table assembly with deterministic, manifest-backed sample mapping |
| `TX2GENE_BUILD` | native annotation module | Separates the unchanged GTF transcript/gene normalization previously embedded in `txtimport_quant.R` |
| `TXIMPORT` / `SALMON_IMPORT` | native Salmon import provider | Replaces `quantification_job.sh`, `run_quantification.sh`, and `txtimport_quant.R`; preserves all tximport scientific arguments and legacy filenames |
| `STAR_IMPORT` | native STAR import provider | Replaces `import_star_counts.py`; preserves count-column selection, gene normalization, outer join, integer counts, CPM, and legacy filenames |
| Batch correction | retired from the scientific DAG | Historical utilities are archived in `rnaseq-legacy-v1.0.0`; batch is represented in the explicit DESeq2 design |
| `RNASEQ_DEG_STEP` | retired | The native Differential Expression API is mandatory; tagged source remains available only for regression |
| `RNASEQ_REPORT_CONTEXT` | native Report API context | Replaces path/glob discovery with explicit Import/DE manifests, sample-aligned abundance, annotation and candidate-gene validation |
| `RNASEQ_GENE_REPORT` / `candidate_genes_v1` | native report provider | Replaces `gene_report_job.sh`; executes the module-owned, reviewed `gene_set_report.R` with tracked arguments, preserves `results/`, and adds manifest/provenance |
| `RNASEQ_REPORT_STEP` | retired | No longer reachable; `report` mode or `rnaseq_report_enabled=true` invokes the native API |

The former RNA-seq orchestrator and utilities are archived in
`rnaseq-legacy-v1.0.0` and are not part of the current source tree.

## ChIP-seq

Native foundation (`chipseq_run_mode=qc|alignment`):

| Nextflow process/API | Legacy evidence replaced or decomposed |
|---|---|
| `CHIPSEQ_CONTEXT` | Sources the unchanged config once and snapshots paths/parameters; no scheduler calls |
| `CHIPSEQ_METADATA` | Replaces rigid validation for the native path and adds dataset/reference/control/replicate consistency |
| reused `FASTQC` | Replaces raw per-FASTQ calls in `fastq_qc.sh` |
| reused `MULTIQC` | Replaces raw aggregation in `fastq_qc.sh` with the same `raw_fastq_multiqc.html` name |
| `REFERENCE_INDEX` / `BOWTIE2_INDEX` | Separates Bowtie2 indexing from monolithic `prepare_reference.sh` |
| `ALIGNMENT` / `BOWTIE2_ALIGN` | Replaces Bowtie2 + samtools sort/index/statistics in `align.sh`; raw reads are selected explicitly |
| `BAM_SELECT` | Decomposes MAPQ and explicit `-f`/`-F` selection from `filter.sh` |
| `BAM_DUPLICATES` | Decomposes `none|mark|remove`; measures duplicates before optional removal |
| `BAM_BLACKLIST` | Replaces optional alignment-level Bedtools filtering with explicit alignment/fragment SAMtools policies |
| `BAM_INDEX_QC` | Replaces final index, quickcheck, flagstat, idxstats and stats with reference validation and final manifest |
| `PEAK_CALLING_CONTEXT` | Replaces target-name inference and implicit control lookup with an explicit validated per-replicate request |
| `PEAK_CALLING` / `MACS3_CALLPEAK` | Replaces `call_peaks.sh` execution with pinned MACS3 3.0.4 and semantic provider inputs |
| `PEAK_CALLING_AGGREGATE` | Validates narrowPeak/broadPeak and normalizes peaks, signals, metrics and manifests |
| `PEAK_QC_CONTEXT` | New native contract; safely joins final BAM/BAI, peaks, manifests, reference, blacklist provenance and explicit QC policy |
| `FRIP` | New native implementation using SAMtools/BEDTools; no legacy FRiP command is treated as authoritative |
| `PEAK_STATISTICS` | Extends caller-neutral peak metrics with complete width distribution and chromosome counts |
| `PEAK_QC_AGGREGATE` | Produces one QC row per replicate without pooling, ranking, consensus or IDR |
| `CONSENSUS_CONTEXT` | Replaces metadata/glob grouping with manifest-ID joins and explicit replicate policy |
| `CONSENSUS_UNION` / `CONSENSUS_INTERSECTION` / `CONSENSUS_SUPPORT` | Decompose `consensus_peaks.sh` into explicit atomic-segment strategies; no count matrix is implied |
| `IDR_PROVIDER` | Native IDR 2.0.4.2 execution with explicit rank/threshold, deterministic seed, normalized peaks and provenance |
| `CONSENSUS_AGGREGATE` | Publishes provider-neutral group summaries and availability state |
| `DB_PREFLIGHT` | Replaces filename/order inference with manifest joins, an explicit comparison universe, design and contrasts |
| `PEAK_COUNTING_PROVIDER` / `FEATURECOUNTS_PEAK` | Replaces headerless `bedtools multicov` matrices with explicit sample columns and a raw-count manifest |
| `DESEQ2_DB_MODEL` | Replaces the monolithic model with one cached `~ condition` or `~ batch + condition` fit |
| `DESEQ2_DB_CONTRAST` | Replaces inferred/in-loop pairs with one task per named numerator/denominator contrast |
| `DB_AGGREGATE` | Replaces path-only tables with a semantic manifest for downstream APIs |
| `PEAK_ANNOTATION_CONTEXT` | Replaces directory globs/filename inference with manifest, checksum, build, coordinate, seqname and parameter validation |
| `PEAK_ANNOTATOR` | Replaces `annotate_peaks.R` with an explicit provider implementing the same conceptual priority and compatibility defaults |
| `PEAK_ANNOTATION_STATISTICS` | Separates metrics from provider execution and derives them only from semantic tables |
| `PEAK_ANNOTATION_AGGREGATE` | Publishes provider-neutral annotated peaks, peak-to-gene associations, statistics and provenance |
| `TRACK_CONTEXT` | Replaces BAM glob/path association and implicit grouping with final-BAM/reference manifests, stable identity, checksum/build validation, and explicit coverage policy |
| `TRACK_PROVIDER` / `DEEPTOOLS_BAMCOVERAGE` | Replaces native execution in `tracks.sh`; creates one BigWig per record and explicitly declared non-control aggregate groups without adding filters |
| `TRACK_STATISTICS` | Derives provider-neutral BigWig/source metrics as a separate cache boundary |
| `TRACK_AGGREGATE` | Joins provider and statistics artifacts by stable track ID and publishes `tracks.tsv` plus the Track Generation manifest |
| `REPORT_CONTEXT` | Replaces numbered-directory/glob discovery with explicit manifest roles, stable IDs, compatibility checks, and component status |
| `REPORT_AGGREGATE` | Replaces ad hoc parsing inside `render_report.R` with presentation-neutral scientific sections and checksum-declared inputs |
| `REPORT_GENERATOR` / `html_v1` | Replaces native presentation in `report.sh`/`render_report.R` with self-contained HTML, structured JSON, final manifest, versions, execution metadata, and provenance |

The native Alignment provider stops before MAPQ/flag selection. The
`post_alignment` mode applies those later policies through independent native
contracts.

All ChIP-seq stage modes now resolve exclusively to the native modules above.
The former aliases, coordinator and scripts were removed after the final
snapshot `chipseq-legacy-v1.0.0`. That tag remains the authoritative mapping for
historical regression. Destructive storage cleanup is intentionally absent from
the Nextflow graph because it can invalidate future cache and provenance work.

## Integrative

Historical mapping only. These aliases and scripts were removed from the
current tree after the Integrative migration gate. Inspect
`integrative-legacy-v1.0.0` to audit or reproduce this executable mapping; the
current workflow is documented in `docs/integrative-native-workflow.md`.

| Nextflow alias | Legacy step | Direct wrapper / engine command |
|---|---|---|
| `INTEGRATIVE_VALIDATE_STEP` | `validate` | `00_validate_inputs.sh` → `integrative_core.py validate` |
| `INTEGRATIVE_PREPARE_STEP` | `prepare` | `01_prepare_inputs.sh` → `prepare` |
| `INTEGRATIVE_HARMONIZE_STEP` | `harmonize` | `02_harmonize_ids.sh` → `harmonize` |
| `INTEGRATIVE_MAP_PEAKS_STEP` | `map-peaks` | `03_map_peaks.sh` → `map-peaks` |
| `INTEGRATIVE_SUMMARIZE_RNA_STEP` | `summarize-rna` | `04_summarize_rna.sh` → `summarize-rna` |
| `INTEGRATIVE_SUMMARIZE_CHIP_STEP` | `summarize-chip` | `05_summarize_chip.sh` → `summarize-chip` |
| `INTEGRATIVE_INTEGRATE_STEP` | `integrate` | `06_integrate.sh` → `integrate` |
| `INTEGRATIVE_SCORE_STEP` | `score` | `07_score_candidates.sh` → `score` |
| `INTEGRATIVE_VISUALIZE_STEP` | `visualize` | `08_visualize.sh` → `r/visualize_integrative.R` |
| `INTEGRATIVE_FUNCTIONAL_STEP` | `functional` | `09_functional_analysis.sh` → `functional` |
| `INTEGRATIVE_REPORT_STEP` | `report` | `10_render_report.sh` → `report` |

`server_inventory.sh` was a manual deployment utility, not a scientific stage.
