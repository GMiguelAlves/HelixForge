# RNA-seq synthetic release validation

The official production path was revalidated on the institutional Slurm
cluster on 2026-08-13 at commit `967dfc4`:

```text
FASTQ -> QC -> Salmon -> Import/tximport -> DESeq2 -> Gene Report
```

The controlled run used Nextflow 25.10.7, the existing cluster environments,
four paired-end synthetic samples, two conditions, two batches, 30 genes and
an explicit DESeq2 design `~ batch + condition`. The executor was limited to
five concurrent tasks. Scientific commands ran on compute nodes; no nested
Slurm submission was used.

## Results

- 58 processes completed and zero failed; peak concurrency was five tasks.
- Salmon processed all four samples and the Import API emitted counts, TPM,
  lengths, metadata, `SummarizedExperiment` and its manifest.
- Every imported count vector had Pearson correlation effectively equal to
  1.0 with the generating fixture and a total-count ratio effectively equal to
  1.0.
- DESeq2 completed the configured `control` versus `treated` contrast with
  batch represented in the model formula.
- The native `candidate_genes_v1` provider preserved both requested genes and
  emitted a complete manifest, HTML report, 12 non-empty scientific PNGs and
  24 report files.
- Nextflow produced trace, timeline, execution report and DAG artifacts.

The result tree occupied 64 MB and the work directory 44 MB. The case is
`rnaseq-final-synthetic-20260813-02` under the isolated HelixForge validation
root. Its machine-readable `validation-baseline.json` records the sample-level
metrics and report inventory.

## Retirement decision

The supported RNA-seq production path is ready to retire its legacy execution
path. Salmon is the production quantifier; STAR remains optional and
experimental. Matrix batch correction is not part of inference: batch remains
in the DESeq2 formula, while a future Batch Effect Assessment API is tracked in
the roadmap. Pathway enrichment is also post-release roadmap work.

The reviewed biological RNA-seq benchmark remains required as a post-release
validation milestone, not as a claim inferred from this synthetic fixture.
The annotated tag `rnaseq-legacy-v1.0.0` preserves the final executable legacy
snapshot before its later removal from the default development path.

Task-cache persistence on the institutional NFS remains an external runtime
issue documented separately. It does not invalidate this successful complete
scientific execution.
