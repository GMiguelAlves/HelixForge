# RNASEQ_GENE_REPORT

Implements the `candidate_genes_v1` provider of the RNA-seq Report API. The
process invokes the module-owned `gene_set_report.R` analysis with explicit,
content-tracked inputs. Its initial native implementation is byte-identical to
the reviewed legacy source (SHA-256
`aaa456fae3558f11e3928797f69add3fc938e8d8c7be5a7c3b743d67755e1691`).
It preserves the `results/` hierarchy and adds API manifest, versions,
execution metadata, session information and log. The process replaces
`gene_report_job.sh` and performs no nested Slurm submission.
