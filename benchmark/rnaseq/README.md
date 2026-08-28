# HelixForge RNA-seq benchmark

This directory freezes the RNA-seq benchmark baseline for HelixForge
`v1.0.0-rc.1`. The workflow was evaluated under controlled configurations with
a synthetic ground-truth experiment and a public biological dataset. The
combined classification is **`PASS_WITH_LIMITATIONS`**; it is not a claim of
universal validation across organisms, library protocols or executors.

## Evaluated subject

| Item | Frozen value |
|---|---|
| HelixForge release | `v1.0.0-rc.1` |
| Scientific commit | `fc38ada8f592bb57a13467965a718ce0df7fb6ce` |
| Nextflow / Java | `25.10.7` / `21` |
| Production path | QC → Salmon → tximport → DESeq2 → reports |
| Import policy | `production_v1`, `lengthScaledTPM` |
| Transcript IDs | versions preserved; bar/version stripping disabled |
| Statistical provider | DESeq2 Wald |

STAR was excluded because it remains an experimental provider. Downloading is
outside the scientific workflow. No pipeline algorithm, scientific parameter
or statistical threshold was changed while producing the benchmark evidence.

## Benchmark cases

### Polyester synthetic ground truth

Six paired-end libraries (three control and three treatment replicates) were
generated from a deterministic 1,200-gene/2,400-transcript design. HelixForge
was compared with the known abundance and differential-expression truth and
with an independently implemented Salmon + tximport + DESeq2 harness.

**Classification: `PASS_WITH_LIMITATIONS`.**

| Endpoint | Result |
|---|---:|
| Gene TPM Spearman | 0.9889–0.9905 |
| Transcript TPM Spearman | 0.9865–0.9873 |
| DE precision | 0.9147 |
| AUPRC / prevalence baseline | 0.7703 / 0.2000 |
| Direction concordance among true DE genes | 0.954 |
| Significant genes stable across repetitions | 129 |

The complete interpretation and figures are in the
[Polyester benchmark report](reports/polyester_benchmark.md).

### GSE52778 biological benchmark

The complete eight-library paired-donor airway dataset was processed without
subsampling. HelixForge used `~ batch + condition` and was compared with a
separately launched but methodologically matched Salmon + tximport + DESeq2
analysis. Nine response/reference genes were declared before evaluation.

**Classification: `PASS_WITH_LIMITATIONS`.**

| Endpoint | Result |
|---|---:|
| Complete libraries | 8 |
| Post-trim pair retention | 98.16–99.09% |
| Salmon mapping | 94.38–95.61% |
| log2FC Pearson correlation | 0.999878 |
| Shared DEGs | 3,507 |
| DEG-set Jaccard | 0.99546 |
| Predeclared biological controls recovered | 9/9 |

The complete interpretation and figures are in the
[GSE52778 benchmark report](reports/gse52778_full_benchmark.md).

## Accepted limitations

- Salmon 1.10.3 showed small numerical differences between controlled
  invocations. Strict numeric tolerance failed, while feature identities,
  rankings, effect directions and scientific conclusions remained stable.
- The synthetic MultiQC report aggregated FastQC but did not include terminal
  Salmon/Trim Galore sections and collapsed duplicate labels.
- GSE52778 required a controlled report-only recovery after correcting
  versioned Ensembl ID handling; the scientific matrices and DE model were not
  recomputed.
- Performance measurements are descriptive for one shared Slurm cluster and
  are not cross-platform speed or cost claims.

## Documentation and evidence

- [Benchmark protocol](protocol/benchmark_protocol.md)
- [Metric definitions](protocol/metrics.md)
- [Interpretation criteria](protocol/interpretation_criteria.md)
- [Risks and limitations](protocol/risks_and_limitations.md)
- [Dataset registry](datasets/dataset_registry.md)
- [Frozen run matrix](configs/run_matrix.tsv)
- [Synthetic design](configs/synthetic_design.json)
- [Reproducibility scripts](scripts/README.md)
- [Versioned result summaries](results/README.md)
- [Provenance contract](provenance/README.md)
- [Administrative file audit](provenance/baseline_file_audit.tsv)

Raw FASTQs, full references, Salmon indexes, software environments and
Nextflow work directories are deliberately excluded from Git. Their identities
are represented by frozen manifests/checksums, and compact audit archives are
retained separately from the repository.

## Future extensions

The following are classified as **`FUTURE_EXTENSION`** and do not block this
baseline:

- deterministic coverage robustness at 5 M, 2.5 M, 1.25 M and 500 k read
  pairs per sample;
- comparison with nf-core/rnaseq as a comparison between pipelines;
- additional real biological datasets;
- cross-platform performance comparison.

The independent Salmon + tximport + DESeq2 harness remains the primary
external reference because it isolates implementation agreement without adding
unrelated pipeline-level methodological choices.
