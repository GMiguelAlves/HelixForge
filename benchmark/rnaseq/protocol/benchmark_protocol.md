# RNA-seq benchmark protocol

Protocol version: `1.0.0-rc.1-design.1`

## 1. Questions

The benchmark estimates technical correctness, agreement with known truth or
a controlled reference, differential-expression recovery, reproducibility,
coverage robustness and computational cost. It does not rank HelixForge
against all RNA-seq pipelines and makes no biological superiority claim.

## 2. Audited production DAG

The RC code executes:

```text
RNASEQ_CONTEXT
  -> RNASEQ_METADATA
  -> REFERENCE_BUNDLE
  -> FASTQC(raw)
  -> TRIM_GALORE
  -> FASTQC(trimmed)
  -> MERGE_FASTQ
  -> FASTQC(merged)
  -> MULTIQC
  -> SALMON_INDEX
  -> SALMON_QUANT
  -> TX2GENE_BUILD
  -> TXIMPORT
  -> DE_PREFLIGHT
  -> DESEQ2_MODEL
  -> DESEQ2_CONTRAST
  -> DE_AGGREGATE
  -> optional RNASEQ_GENE_REPORT
  -> rnaseq_run_manifest.json
```

The benchmark invokes `--workflow rnaseq --rnaseq_run_mode full
--rnaseq_analysis_mode quantification`. STAR is experimental and excluded.
Download is outside the scientific DAG. Metadata and Reference Bundle are
native; the context adapter translates the shell configuration.

The frozen case list is `configs/run_matrix.tsv`. The public cases set
`--rnaseq_report_enabled true` and use the predeclared
`configs/airway_report_genes.txt`; the synthetic case disables candidate-gene
reporting so no truth-derived gene selection enters the workflow. All other
top-level production stages are exercised in both primary cases.

The public candidate-gene request contains two explicit report groups and nine
queries: five glucocorticoid-response genes and four reference controls. The
grouped syntax is part of the Report API input contract and does not affect the
differential-expression model.

Scientific settings frozen from the RC are Trim Galore 0.6.10 with quality 20
and minimum length 20, Salmon 1.10.3 with k=31, library type `A` and validated
mappings, tximport 1.30.0 with `production_v1`, full-length libraries,
`lengthScaledTPM`, `ignoreTxVersion=false`, `ignoreAfterBar=false`, and DESeq2
1.42.0 using Wald tests. The DE matrix interface rounds the explicitly
length-scaled count matrix as declared by the DE specification.

## 3. Immutable benchmark identity

Before every run, `collect_environment.py` must fail unless all of the
following match:

```text
tag                         v1.0.0-rc.1
commit                      fc38ada8f592bb57a13467965a718ce0df7fb6ce
HelixForge manifest.version 1.0.0-rc.1
Nextflow                    25.10.7
Java major                  21
```

It records OS, kernel, CPU model, allocated CPUs/memory, Slurm partition,
filesystem types, container/environment identity, reference checksums and
versions emitted by every provider. Institutional hostnames, account names and
private paths are redacted only in the public summary; unredacted evidence is
kept in the user's audit archive.

No code under `modules/`, `subworkflows/`, `workflows/`, `schemas/` or the RC
configuration may change during measurement. A discovered defect is recorded,
the affected run is stopped, and any fix occurs on a separate branch. The
benchmark is then repeated from the first affected boundary.

## 4. Reference preparation

Both benchmark cases use GENCODE Human Release 49, GRCh38.p14. Reference
preparation downloads and checksums:

- comprehensive primary-assembly GTF;
- all-transcript FASTA;
- GRCh38 primary-assembly genome FASTA.

`prepare_gencode_reference.py` selects transcript IDs present in the primary
GTF and rewrites each retained FASTA header to the exact versioned
`transcript_id` (the token before the first `|`). It rejects duplicate or
unmapped IDs. This derived transcriptome is required because production policy
preserves versions and does not strip bar-delimited metadata. The script emits
the input and output SHA-256 values, record counts and exact command in
`reference_manifest.json`.

The complete derived reference is used for the public dataset and independent
reference run. The synthetic builder selects a deterministic, documented
subset from it; the truth files never enter HelixForge.

## 5. Level A — synthetic ground truth

### 5.1 Simulator decision

Polyester is selected because it produces raw reads from supplied transcript
sequences, supports paired-end fragments, explicit per-transcript counts,
replicates, negative-binomial variability, controlled differential signal,
fragment-length distributions and sequencing error. RSEM simulation would
require fitting a model from real data and has no built-in DE experiment
design; ART models quality well but requires a separate expression/replicate
generator; BEERS2 is more comprehensive but materially heavier for the first
release benchmark.

Polyester writes FASTA rather than FASTQ quality strings. The benchmark will
convert mates deterministically to FASTQ with constant Phred 40 after sequence
errors have already been introduced by Polyester. Consequently, Level A tests
quantification and DE truth, not realistic quality-score trimming. Level B is
the source of real QC/trimming evidence.

### 5.2 Design

The exact machine-readable design is in `configs/synthetic_design.json`:

- 1,200 genes and exactly 2,400 transcripts: 400 genes with one, 400 with two
  and 400 with three retained transcripts of length 500–5,000 bp;
- within each transcript-count stratum, genes are ordered by
  `SHA-256(seed + gene_id)` and the first 400 are retained;
- two conditions (`control`, `treatment`), three replicates each;
- 75 bp paired-end reads; normal fragment length 250 bp, SD 25 bp;
- 0.005 uniform sequence error;
- 2,000,000 fragments per sample after deterministic largest-remainder
  count-matrix rescaling, with `transcript_id` as the tie-breaker;
- 240 DE genes and 960 non-DE genes;
- balanced up/down effects at absolute log2FC 0.5, 1.0 and 2.0;
- every transcript of a DE gene receives the same gene-level multiplier, so
  gene truth is unambiguous; transcript proportions vary across genes but not
  systematically between conditions;
- seed `20260825` is primary; `20260826` and `20260827` are confirmatory seeds
  if the primary pass completes within the allocated budget.

The builder writes truth before generating reads:

```text
truth/transcript_truth.tsv
truth/gene_truth.tsv
truth/gene_de_truth.tsv
truth/sample_table.tsv
truth/simulation_manifest.json
truth/versions.yml
```

`simulation_manifest.json` contains selection rules, seeds, count-distribution
parameters, fragment/error parameters, reference checksums and truth-file
checksums. HelixForge receives only FASTQ, metadata and the derived reference.

## 6. Level B — public biological dataset

The selected study is `GSE52778` / `SRP033351` / `PRJNA229998`: primary human
airway smooth-muscle cell lines from four donors, untreated or exposed to 1 µM
dexamethasone for 18 hours. The study describes 75 bp paired-end sequencing;
the deposited ENA exports contain 63+63 bp application reads, which are the
actual benchmark inputs. Only the eight untreated/DEX runs in
`datasets/airway_samples.tsv` are used; albuterol arms and ENA orphan/unpaired
exports are excluded.

The original paired FASTQs were downloaded from ENA to scratch and checked
against ENA MD5 values. The completed biological benchmark used every paired
read from all eight selected libraries without subsampling. Pair identity,
exact pair count, gzip integrity and SHA-256 passed before execution.

Metadata maps donor to `batch`, treatment to `condition`, and uses the paired
design `~ batch + condition`. The contrast is
`condition__dexamethasone_vs_untreated`. The primary call definition for
comparison is `padj < 0.05`; `padj < 0.05 && abs(log2FC) >= 1` is reported as a
separate effect-filtered set.

Published expectations are classified, not treated as exact truth:

- `BIOLOGICAL_EXPECTATION`: CRISPLD2 is induced by dexamethasone; DUSP1,
  KLF15, PER1 and TSC22D3 are glucocorticoid-responsive;
- `BIOLOGICAL_EXPECTATION`: B2M, GABARAP, GAPDH and RPL19 remain highly
  expressed without strong treatment effects;
- `SET_OVERLAP`: compare to the published 316 adjusted-P-value DE genes and
  the GEO Cuffdiff table;
- never `EXACT` or `NUMERIC`, because the publication used hg19, a fixed
  12-base crop and Cufflinks/Cuffdiff rather than the RC methodology.

## 7. Controlled external reference

The primary external reference is an independent command-line harness that
does not import HelixForge code. It consumes the same post-trim, merged FASTQs
and executes the pinned Salmon 1.10.3 image, tximport 1.30.0 and DESeq2 1.42.0
with the same reference, tx2gene, sample order, `production_v1` policy, design,
contrast, filtering and thresholds. Using HelixForge post-trim reads isolates
the Salmon/Import/DE semantics; QC/trimming correctness is evaluated from its
own outputs and reproducibility checks.

The harness must reproduce explicit commands rather than call HelixForge
resources. It emits its own environment and command manifest. The comparison
is semantic for JSON/TSV and ignores paths/timestamps only where listed.

An nf-core/rnaseq comparison is a future, non-gating comparison between
pipelines. It is not required to validate this baseline because its additional
methodological choices would make it less controlled than the independent
same-method harness used here.

## 8. Future coverage robustness

Coverage subsampling is a `FUTURE_EXTENSION`, not part of this baseline. The
frozen plan defines 5,000,000, 2,500,000, 1,250,000 and 500,000 pairs per
sample with seeds in `configs/subsampling_plan.tsv`.

When implemented, paired subsampling must apply the same deterministic
selection to both mates, record parent/output checksums and compare each depth
with truth where available and with the full-depth public result. This work is
robustness characterization and does not block the frozen RNA-seq baseline.

## 9. Replicability

The primary synthetic analysis ran twice from separate clean output/work
directories with identical inputs. The GSE52778 case was compared with an
independently launched same-method analysis. FASTQ/reference inputs use byte
comparison; numeric matrices and statistical tables use the tolerances in
`metrics.md`; manifests ignore only declared volatile paths, run IDs and
timestamps. Cache behavior is an operational concern and does not replace
scientific evaluation.

## 10. Performance and storage

For every Nextflow process, preserve the trace fields for duration, realtime,
CPU, peak RSS/VMEM, I/O and workdir. Record workflow wall time, task count,
failed/retried tasks, input pairs, published-result size and work-directory
size. Use `sacct` for requested/allocated resources and maximum RSS where
available. Do not optimize or change code during measurement.

Sizes are measured with one filesystem-consistent method after tasks finish.
Temporary container caches and the immutable source FASTQs are reported
separately from scientific work/results.

## 11. Slurm operational policy

Before every batch, capture `date`, `sinfo`, the user's `squeue`, a compact
global `squeue`, and `scontrol show node` for each node. Start with
`queueSize/maxForks=5`. Raising the ceiling to ten requires one node in a fully
idle state and no visible queue pressure. Revert to five if jobs begin pending
for resources or other users' demand rises.

All processing uses Slurm allocations. The head node may run only the Nextflow
driver, Git, checksum verification of small manifests and scheduler inspection.
No module submits nested jobs. Scratch data live below a benchmark-specific
directory and are removed only after compact audit evidence is archived under
the user's home directory.

Runtime preflight is mandatory. If the compute nodes cannot execute a
site-supported environment matching the RC versions, execution stops and marks
the runtime blocked; it must not silently mix OCI, Conda or host results.

## 12. Reproduction sequence

1. Capture a read-only Slurm/runtime preflight.
2. Verify the RC commit, Nextflow 25.10.7, Java 21 and scientific runtimes.
3. Download and checksum registered inputs; build the exact-ID reference.
4. Generate and validate the deterministic Polyester truth and paired FASTQs.
5. Run the synthetic HelixForge case, independent reference and clean repeat.
6. Download and validate the eight complete ENA paired libraries.
7. Run the full GSE52778 HelixForge case and independent same-method reference.
8. Calculate metrics, evaluate preregistered biological expectations and
   render reports/figures.
9. Archive compact manifests, logs, metrics, traces and reports; remove only
   owned disposable scratch data after checksum verification.

Every boundary fails closed. A failed result is preserved and is never
silently overwritten or reinterpreted.

## 13. Resolved protocol decisions

- The canonical repository path is the existing singular `benchmark/rnaseq/`.
- The synthetic case uses a deterministic closed pseudo-reference derived from
  real GENCODE v49 transcripts, preserving exact gene/transcript truth.
- Sample membership, differential-effect assignment, TPM formulas, seeds and
  ID normalization are explicit machine-readable contracts.
- The optional candidate-gene report is disabled for Polyester to avoid
  truth-derived selection and is exercised by GSE52778 with a predeclared list.
- Salmon duplicate removal defines an estimable universe of 2,376 transcripts
  and 1,195 genes; metrics distinguish it from the 2,400/1,200 input universe.
- Differential tables are compared by unique gene identity rather than display
  order; quantification and Import matrices retain strict ID/order checks.
- The biological benchmark uses deposited 63+63 bp ENA pairs, excludes orphan
  exports and processes full data. The study-level 75 bp description is retained
  as provenance.
- Strict numeric discrepancies from Salmon index/quantification parallelism are
  retained as accepted limitations; tolerances were not silently widened.
- MultiQC aggregation limitations and the controlled GSE52778 report recovery
  remain visible in the final reports.

## 14. Command contract

`build_helixforge_inputs.py` creates a case-specific `pipeline_config.sh`,
samplesheet/metadata files and a resolved parameter manifest. It must not
change values frozen above. From the immutable RC checkout, every HelixForge
case uses this command shape on the Slurm head node (the driver only):

```bash
nextflow-25.10.7 run main.nf \
  -profile slurm -c <reviewed-site-config> \
  -work-dir <case-work> \
  --workflow rnaseq \
  --outdir <case-results> \
  --rnaseq_config <case>/pipeline_config.sh \
  --rnaseq_analysis_mode quantification \
  --rnaseq_run_mode full \
  --rnaseq_native_alignment false \
  --rnaseq_de_spec <frozen-de-spec> \
  --rnaseq_library_protocol full_length \
  --rnaseq_counts_from_abundance lengthScaledTPM \
  --rnaseq_report_enabled <frozen-run-matrix-value> \
  --rnaseq_report_genes <public-report-list-when-enabled> \
  --salmon_validate_mappings true
```

The reviewed site config may set only executor, queue/account/QoS, scratch,
runtime plumbing and resource overrides. A generated `resolved_parameters.json`
is compared with the frozen protocol before submission; any scientific
parameter difference stops the case. The run matrix defines clean repetitions
and whether the independent harness is required.
