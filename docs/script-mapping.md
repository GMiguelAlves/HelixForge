# Legacy script to Nextflow mapping

No scientific script was rewritten. `LEGACY_STEP` is included under a distinct
process alias for every coarse step below. Each alias calls the existing top
level orchestrator with one `--step` and forces local execution.

## RNA-seq

| Nextflow alias | Legacy coarse step | Scripts reached by the existing orchestrator |
|---|---|---|
| `RNASEQ_REFERENCE_STEP` | `reference` | Prepares unchanged FASTA/GTF/transcriptome inputs. Native STAR and Salmon compatibility flags stop the scripts before index construction |
| `RNASEQ_DOWNLOAD_STEP` | `download` | `download_final.sh` per project |
| `RNASEQ_METADATA_STEP` | `metadata` | `run_metaqc.sh`, `run_parse.sh`, `run_merge.sh` |
| `RNASEQ_QC_PLAN` | compatibility adapter | Calls unchanged `generate_qc_plan.py` and annotates its Nextflow-owned copy with `TRIM_QUALITY`/`TRIM_LENGTH` from the legacy config |
| `FASTQC_RAW` | native per-FASTQ process | Replaces `fastqc_raw_plan.sh`; invokes the same FastQC command and writes to `fastqc_raw` |
| `TRIM_GALORE` | native per-run process | Executes the same `trim_galore --paired --quality --length --cores --output_dir` command previously in `trim_runs_plan.sh` |
| `FASTQC_TRIMMED` | native per-FASTQ process | Replaces `fastqc_trimmed_runs_plan.sh` and writes to `fastqc_trimmed_runs` |
| `MERGE_FASTQ` | native per-sample process | Replaces `merge_samples_plan.sh` / `merge_sample_from_plan.py`; concatenates ordered gzip members without recompression |
| `FASTQC_MERGED` | native per-FASTQ process | Replaces `fastqc_merged_plan.sh` and writes to `fastqc_merged` |
| `MULTIQC` | native reusable process | Replaces `multiqc_plan.sh`; consumes generic compatible artifacts and writes the same named report under `multiqc_030` |
| `RNASEQ_QC_STEP` | legacy fallback only | Runs the unchanged complete `qc` step when `rnaseq_native_qc=false` |
| `RNASEQ_ALIGNMENT_PLAN` | compatibility adapter | Sources the legacy config and invokes unchanged `generate_star_plan.py`; no scientific command is copied into Nextflow |
| `REFERENCE_INDEX` / `STAR_INDEX` | native index API/provider | Replaces STAR `genomeGenerate` in `star_index_gtf.sh` with the same parameters and resources |
| `ALIGNMENT` / `STAR_ALIGN` | native alignment API/provider | Replaces `run_star_quant_project.sh` / `star_quant_array_task.sh` with one task per sample and preserves every STAR filename |
| `RNASEQ_QUANTIFICATION_PLAN` | compatibility adapter | Sources the legacy config and invokes unchanged `generate_salmon_plan.py`; emits generic Quantification API inputs |
| `TRANSCRIPTOME_INDEX` / `SALMON_INDEX` | native index API/provider | Replaces scientific execution in `salmon_index.sh` with the same transcriptome, k-mer, threads, resources, and filenames |
| `QUANTIFICATION` / `SALMON_QUANT` | native quantification API/provider | Replaces `run_alignment_project.sh` / `salmon_quant_plan.sh` with one task per sample and preserves the complete Salmon directory |
| Native provider guard | alignment/quantification boundary | The provider selected by `QUANT_METHOD` must emit a native manifest; legacy STAR/Salmon fallbacks are no longer scheduled in an Import API run |
| `RNASEQ_IMPORT_CONTEXT` | compatibility adapter | Reads metadata, GTF, target directory, provider, and STAR count-column settings from the unchanged config; it performs no scientific import |
| `IMPORT_SOURCE` | native manifest adapter | Validates provider, semantic role, sample identity, compatibility path, and SHA-256 before staging each upstream artifact |
| `IMPORT_SAMPLE_TABLE` | native metadata adapter | Replaces the inline legacy sample-table assembly with deterministic, manifest-backed sample mapping |
| `TX2GENE_BUILD` | native annotation module | Separates the unchanged GTF transcript/gene normalization previously embedded in `txtimport_quant.R` |
| `TXIMPORT` / `SALMON_IMPORT` | native Salmon import provider | Replaces `quantification_job.sh`, `run_quantification.sh`, and `txtimport_quant.R`; preserves all tximport scientific arguments and legacy filenames |
| `STAR_IMPORT` | native STAR import provider | Replaces `import_star_counts.py`; preserves count-column selection, gene normalization, outer join, integer counts, CPM, and legacy filenames |
| `RNASEQ_BATCH_STEP` | `batch` | `batch_correction_job.sh`, `run_batch_correction.sh`, `apply_batch_correction.py`; skipped when `RUN_BATCH_CORRECTION=0` |
| `RNASEQ_DEG_STEP` | `deg` | `run_deg_analysis_slurm.sh` in local mode, `generate_deg_plan.py`, `deseq2_plan_job.sh`, `deseq2_analysis.R` |
| `RNASEQ_REPORT_STEP` | `report` | `gene_report_job.sh`, `gene_set_report.R`; skipped when `RUN_GENE_REPORT=0` |

`validate_config.sh` is invoked by `rnaseq_pipeline.sh`. Rename helpers and
batch-assessment utilities remain available as manual legacy utilities because
the current top-level workflow does not invoke them in its standard graph.

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

The native Alignment provider stops before MAPQ/flag selection. The
`post_alignment` mode applies those later policies through independent native
contracts.

Legacy fallback (`chipseq_run_mode=full`, `chipseq_native_foundation=false`, or
`chipseq_native_peak_calling=false` for the `peaks` step):

| Nextflow alias | Legacy step | Direct legacy script |
|---|---|---|
| `CHIPSEQ_REFERENCE_STEP` | `reference` | `prepare_reference.sh`, which calls `create_annotation_beds.py` |
| `CHIPSEQ_QC_STEP` | `qc` | `fastq_qc.sh` for samples and MultiQC targets |
| `CHIPSEQ_TRIM_STEP` | `trim` | `trim.sh` |
| `CHIPSEQ_ALIGNMENT_STEP` | `align` | `align.sh` |
| `CHIPSEQ_FILTER_STEP` | `filter` | `filter.sh` |
| `CHIPSEQ_BAM_QC_STEP` | `bam_qc` | `bam_qc.sh` for samples, fingerprint, and MultiQC |
| `CHIPSEQ_PEAK_CALLING_STEP` | `peaks` | `call_peaks.sh` for IP samples |
| `CHIPSEQ_CONSENSUS_STEP` | `consensus` | `consensus_peaks.sh` |
| `CHIPSEQ_DIFFERENTIAL_BINDING_STEP` | `differential` | `differential_binding.sh` and `r/differential_binding.R` |
| `CHIPSEQ_ANNOTATION_STEP` | `annotate` | `annotate_peaks.sh` and `r/annotate_peaks.R` |
| `CHIPSEQ_TRACKS_STEP` | `tracks` | `tracks.sh` for samples and aggregate tracks |
| `CHIPSEQ_REPORT_STEP` | `report` | `report.sh` and `r/render_report.R` |

`chipseq_pipeline.sh` invokes config and metadata validators before the selected
step. `cleanup_storage.sh` is intentionally not part of the Nextflow graph
because deleting intermediates can invalidate future cache/provenance work.

## Integrative

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

`server_inventory.sh` remains a manual deployment utility and is not a
scientific workflow stage.
