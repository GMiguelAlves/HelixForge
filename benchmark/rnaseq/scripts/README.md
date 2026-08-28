# RNA-seq benchmark scripts

These scripts reproduce the frozen Polyester and GSE52778 benchmark cases.
They fail closed, preserve machine-readable provenance and keep scientific
processing on Slurm compute nodes. Head-node drivers only validate identity,
prepare submission metadata and launch Nextflow or `sbatch`.

## Layout

| Directory | Responsibility |
|---|---|
| `common/` | runtime checks, reference preparation and cross-run comparisons |
| `synthetic/` | Polyester generation, HelixForge execution, truth evaluation and figures |
| `gse52778/` | metadata/download validation, full biological execution, comparison and figures |
| `tests/` | lightweight syntax and contract checks |

## Shared scripts

- `slurm_runtime_preflight.sh` records the scheduler and certified runtime.
- `slurm_create_environment.sh` creates exact benchmark-specific environments.
- `slurm_download_reference.sh` downloads registered reference sources on a
  compute node.
- `slurm_restore_temurin21.sh` restores the checksum-pinned Temurin 21 runtime
  when it is unavailable, without modifying shared environments.
- `prepare_gencode_reference.py` creates the version-preserving GENCODE 49
  transcriptome and `tx2gene` contract.
- `compare_independent.py`, `compare_reference_repeats.py`,
  `compare_helixforge_repeats.py` and `compare_gse52778_independent.py` perform
  explicit ID-aware numeric and semantic comparisons.

## Polyester scripts

- `prepare_synthetic_reference.py`, `build_synthetic_truth.R` and
  `fasta_to_fastq.py` construct the deterministic reference, truth and paired
  FASTQs declared in `configs/synthetic_design.json`.
- `slurm_generate_polyester.sh` and `slurm_convert_polyester_sample.sh` keep
  simulation and conversion on compute nodes.
- `build_helixforge_inputs.py` produces the frozen case inputs.
- `run_helixforge_synthetic.sh` launches the immutable RC with a five-task
  queue ceiling.
- `run_independent_reference.sh` and `independent_tximport_deseq2.R` implement
  the independent Salmon 1.10.3, tximport 1.30.0 and DESeq2 1.42.0 reference.
- `validate_synthetic_dataset.py`, `validate_helixforge_run.py`,
  `evaluate_synthetic.py`, `compare_independent.py` and
  `summarize_performance.py` validate inputs, contracts, truth recovery,
  reproducibility and descriptive resource use.
- `prepare_polyester_figures.py`, `plot_polyester_benchmark.R`,
  `finalize_polyester_figures.py` and `render_polyester_figures.sh` regenerate
  the six public synthetic figures and their checksum manifest.
- `verify_audit_archive.py` verifies the checksum and required contents of the
  frozen private audit archive. Historical archive member names are retained
  inside that verifier because the archive is immutable.

## GSE52778 scripts

- `slurm_prepare_gse52778_metadata.sh` and
  `validate_gse52778_metadata.py` retrieve and freeze official ENA, NCBI and
  GEO metadata.
- `download_gse52778.sh`, `validate_gse52778_fastq.py` and
  `finalize_gse52778_download.py` perform resumable paired FASTQ download,
  official MD5 verification, local SHA-256 recording, gzip/pair validation and
  aggregate manifest creation. The download array uses `%2` concurrency.
- `slurm_prepare_gencode_reference.sh` and the shared reference builder produce
  the exact versioned GENCODE 49 reference contract.
- `build_gse52778_inputs.py` joins validated manifests into the eight-library
  paired-donor case.
- `run_helixforge_gse52778.sh` launches or resumes the full RC analysis with
  the biological Slurm resource configuration and at most five tasks.
- `independent_gse52778_tximport_deseq2.R` implements the independent
  `~ batch + condition` analysis and dexamethasone-versus-untreated contrast.
- `validate_gse52778_run.py`, `compare_gse52778_independent.py`,
  `summarize_gse52778_comparison.py`, `measure_gse52778_concordance.py` and
  `evaluate_gse52778_biology.py` validate the terminal contract, controlled
  reference concordance and nine preregistered biological expectations.
- `summarize_gse52778_qc.py` and `summarize_gse52778_performance.py` create the
  versioned QC and descriptive Slurm summaries.
- `plot_gse52778_benchmark.R` and `slurm_finalize_gse52778.sh` regenerate the
  compact public figures and redacted performance evidence on a compute node.

## Contract tests

`tests/test_benchmark_scripts.sh` checks Python and R syntax, shell syntax and
small deterministic contracts without downloading data or running a scientific
workflow. Complete benchmark execution additionally requires the frozen Slurm
runtime and external payloads represented by manifests/checksums.

Raw reads, complete references, environments and Nextflow work directories are
not version controlled.
