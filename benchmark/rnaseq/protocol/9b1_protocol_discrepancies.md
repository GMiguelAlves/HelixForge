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
| 9B1-D07 | `ENVIRONMENTAL_FAILURE` | The reusable cluster `rna-tools` environment contains Java 23.0.2 and MultiQC 1.30; `r-analysis` contains DESeq2 1.42.1. These differ from the RC locks Java 21, MultiQC 1.17 and DESeq2 1.42.0. | Reuse the already certified Temurin 21 runtime, but create benchmark-specific exact Conda prefixes for the scientific tools. Existing shared environments remain untouched. |
| 9B1-D08 | `BENCHMARK_FINDING` | The initial runtime preflight invoked FastQC by absolute path without putting Java on `PATH`; FastQC therefore printed a missing-Java message although the preflight job completed. | Export the combined explicit runtime PATH before version probes and repeat the preflight. Job `15165` is retained as superseded provenance, not scientific evidence. |
| 9B1-D09 | `ENVIRONMENTAL_FAILURE` | The mutable validation path `nextflow.jar` contained Nextflow 26.04.6 when the primary run was attempted. | The fail-closed driver stopped before submission. Use the existing immutable framework artifact `nextflow-25.10.7-one.jar`; record the exact path/version and retain the blocked attempt in the audit trail. |
| 9B1-D10 | `ENVIRONMENTAL_FAILURE` | The portable Temurin 21 runtime used by the Nextflow driver could not discover the Conda fontconfig stack when FastQC rendered its report (`Fontconfig head is null`). | Keep Nextflow on Java 21. Run FastQC with the JVM and fonts resolved inside the exact `rna-tools-rc` environment, expose its fontconfig paths to Slurm tasks, and record this tool JVM separately. Probe `15202` produced complete HTML/ZIP; the failed workflow attempt remains preserved. |
| 9B1-D11 | `ENVIRONMENTAL_FAILURE` | The shared `python-list` prefix lacks `jsonschema`, so the completed scientific path could not emit the terminal `RUN_MANIFEST`. | Preserve the failed attempt; create a clean benchmark prefix with Python 3.12.4 and jsonschema 4.23.0 exactly as declared by the module. Do not modify the shared prefix or the RC. Repeat the primary run from a clean case root after a fail-closed preflight. |

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
