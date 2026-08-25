# Stage 9B.1 protocol/implementation audit

Audit date: 2026-08-25

| ID | Classification | Observation | Resolution before execution |
|---|---|---|---|
| 9B1-D01 | `BENCHMARK_FINDING` | The Stage 9B.1 request still names `benchmarks/rnaseq/`, but the repository's pre-existing canonical directory is singular `benchmark/`. | All benchmark-only implementation and evidence use `benchmark/rnaseq/`. No second top-level directory is created. |
| 9B1-D02 | `BENCHMARK_FINDING` | Stage 9A described downloading the complete GENCODE GTF/genome bundle, while Stage 9B.1 requires a tightly controlled synthetic reference and warns against using GENCODE if it weakens ground truth. | Use only the registered GENCODE v49 all-transcript FASTA as sequence source. Deterministically select 1,200 genes/2,400 real isoforms, then generate a closed pseudo-genome, GTF and tx2gene containing only those records. This preserves real within-gene sequence ambiguity and exact gene↔transcript truth. |
| 9B1-D03 | `BENCHMARK_FINDING` | The 9A JSON defined condition count but did not enumerate sample IDs and condition membership. | `synthetic_design.json` now freezes all six samples and replicates explicitly. |
| 9B1-D04 | `BENCHMARK_FINDING` | The 9A JSON froze the number and size of DE effects but left the assignment order implicit. | The contract now hashes gene IDs with the fixed selection seed and assigns fixed consecutive up/down effect blocks. |
| 9B1-D05 | `BENCHMARK_FINDING` | The 9A truth contract did not state how transcript/gene TPM is derived from the exact Polyester fragment counts. | The JSON now freezes length-normalized transcript TPM and gene aggregation formulas. |
| 9B1-D06 | `BENCHMARK_FINDING` | The RC `full` workflow only runs the candidate-gene Report API when `rnaseq_report_enabled=true`, while the frozen 9A synthetic run matrix deliberately disables it to prevent truth-derived gene selection. | The synthetic benchmark validates the standard QC/MultiQC and terminal reporting/provenance outputs but classifies the optional candidate-gene report as `NOT_APPLICABLE`. The public-data stage will exercise it with a predeclared list. |

## Confirmed RC implementation

The audited RC path is:

```text
RNASEQ_CONTEXT -> RNASEQ_METADATA -> REFERENCE_BUNDLE
  -> FASTQC(raw) -> TRIM_GALORE -> FASTQC(trimmed)
  -> MERGE_FASTQ -> FASTQC(merged) -> MULTIQC
  -> SALMON_INDEX -> SALMON_QUANT
  -> TX2GENE_BUILD -> TXIMPORT
  -> DE_PREFLIGHT -> DESEQ2_MODEL -> DESEQ2_CONTRAST -> DE_AGGREGATE
  -> RUN_MANIFEST
```

The benchmark uses `rnaseq_run_mode=full`,
`rnaseq_analysis_mode=quantification`, `rnaseq_native_alignment=false`,
`production_v1`, `full_length`, `lengthScaledTPM`, and the frozen
`~ condition` contrast. STAR and automatic batch correction are absent.

No discrepancy above modifies HelixForge scientific code, module parameters,
schemas or statistical thresholds.
