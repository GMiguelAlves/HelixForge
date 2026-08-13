# RNASEQ_GENE_REPORT

Implements the `candidate_genes_v1` provider of the RNA-seq Report API. The
process invokes the module-owned `gene_set_report.R` analysis with explicit,
content-tracked inputs. Its initial native implementation is text-identical to
the reviewed legacy source after canonical LF normalization (SHA-256
`36e084d6a36ec16d125ad94f5cd3e9890de265ffa63d80d01ab8e6b98ed03930`).
It preserves the `results/` hierarchy and adds API manifest, versions,
execution metadata, session information and log. The process replaces
`gene_report_job.sh` and performs no nested Slurm submission.
