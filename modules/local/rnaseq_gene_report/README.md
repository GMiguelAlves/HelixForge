# RNASEQ_GENE_REPORT

Implements the `candidate_genes_v1` provider of the RNA-seq Report API. The
process invokes the module-owned `gene_set_report.R` analysis with explicit,
content-tracked inputs. The implementation preserves the reviewed scientific
calculations while providing a native report presentation optimized for large
candidate panels: overview-first navigation, explicit found/missing status,
deferred image loading, collapsible gene/group sections, informative-metadata
selection and one figure set per unique gene. It preserves the `results/`
hierarchy and adds API manifest, versions,
execution metadata, session information and log. The process replaces
`gene_report_job.sh` and performs no nested Slurm submission.
