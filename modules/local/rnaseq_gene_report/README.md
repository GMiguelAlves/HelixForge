# RNASEQ_GENE_REPORT

Implements the `candidate_genes_v1` provider of the RNA-seq Report API. The
process invokes the existing `gene_set_report.R` analysis unchanged with
explicit, content-tracked inputs. It preserves the `results/` hierarchy and
adds API manifest, versions, execution metadata, session information and log.

The R script remains in the legacy source tree during this transition; the
Nextflow process replaces `gene_report_job.sh` and performs no nested Slurm
submission.
