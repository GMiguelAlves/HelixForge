# Legacy script to Nextflow mapping

No scientific script was rewritten. `LEGACY_STEP` is included under a distinct
process alias for every coarse step below. Each alias calls the existing top
level orchestrator with one `--step` and forces local execution.

## RNA-seq

| Nextflow alias | Legacy coarse step | Scripts reached by the existing orchestrator |
|---|---|---|
| `RNASEQ_REFERENCE_STEP` | `reference` | `salmon_index.sh`, `star_index.sh`, `star_index_gtf.sh`, conditional on existing config flags |
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
| `RNASEQ_ALIGNMENT_STEP` | `salmon` | `run_alignment_project.sh` or `run_star_quant_project.sh`; their plan generators and array-task scripts execute sequentially in local mode |
| `RNASEQ_QUANTIFICATION_STEP` | `tximport` | `quantification_job.sh`, `run_quantification.sh`, `txtimport_quant.R` or `import_star_counts.py` |
| `RNASEQ_BATCH_STEP` | `batch` | `batch_correction_job.sh`, `run_batch_correction.sh`, `apply_batch_correction.py`; skipped when `RUN_BATCH_CORRECTION=0` |
| `RNASEQ_DEG_STEP` | `deg` | `run_deg_analysis_slurm.sh` in local mode, `generate_deg_plan.py`, `deseq2_plan_job.sh`, `deseq2_analysis.R` |
| `RNASEQ_REPORT_STEP` | `report` | `gene_report_job.sh`, `gene_set_report.R`; skipped when `RUN_GENE_REPORT=0` |

`validate_config.sh` is invoked by `rnaseq_pipeline.sh`. Rename helpers and
batch-assessment utilities remain available as manual legacy utilities because
the current top-level workflow does not invoke them in its standard graph.

## ChIP-seq

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
