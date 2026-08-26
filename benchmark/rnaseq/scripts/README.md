# Stage 9B script contracts

Stage 9A defined contracts; Stage 9B.1 implements the synthetic subset here.
Scripts must
be deterministic, fail closed, emit a machine-readable manifest and run as Slurm
jobs through Nextflow or `sbatch`; none may perform scientific processing on the
head node.

| Planned script | Required inputs | Required outputs | Failure conditions |
|---|---|---|---|
| `collect_environment.py` | RC SHA/tag, Nextflow, Java, scheduler and runtime commands | `environment.json`, `versions.yml` | missing identity or runtime version |
| `download_and_verify.py` | dataset/reference registry row | payload, `download_manifest.json` | URL failure, size or MD5 mismatch |
| `prepare_gencode_reference.py` | registered GTF and transcript FASTA | filtered transcriptome, tx2gene, checksums, manifest | duplicate/absent IDs or inconsistent version policy |
| `build_synthetic_truth.R` | `synthetic_design.json`, prepared reference | truth tables and paired FASTA | unresolved seed/version or count mismatch |
| `fasta_to_fastq.py` | paired simulated FASTA | paired gzip FASTQ, checksums | pair/order mismatch |
| `subsample_pairs.py` | paired FASTQ, explicit target and seed | paired gzip FASTQ, selected-read digest and manifest | insufficient pairs or mate mismatch |
| `build_helixforge_inputs.py` | frozen registry/design | samplesheet, metadata, shell configuration and DE specification | contract/schema failure |
| `run_independent_reference.sh` | post-trim merged reads, reference, sample table and exact locks | Salmon/tximport/DESeq2 artifacts plus command/version manifest | any import of HelixForge implementation or version drift |
| `evaluate_quantification.py` | truth/reference outputs and HelixForge outputs | transcript/gene metric tables | unmatched sample/feature universe |
| `evaluate_de.py` | DE truth/public expectations and DE results | DE metric tables and set comparisons | contrast/design mismatch |
| `compare_runs.py` | two complete run manifests | numeric and semantic comparison tables | incompatible protocol/RC identity |
| `collect_performance.py` | Nextflow trace/report and `sacct` export | task/run resource tables | missing task-to-job mapping |
| `render_report.R` | all validated metric tables/manifests | HTML/PDF summary | missing provenance or gate classification |

Implemented for the Stage 9B.1 preparation boundary:

- `slurm_runtime_preflight.sh`;
- `test_benchmark_scripts.sh`;
- `slurm_create_environment.sh`;
- `slurm_download_reference.sh`;
- `prepare_synthetic_reference.py`;
- `build_synthetic_truth.R`;
- `fasta_to_fastq.py`;
- `validate_synthetic_dataset.py`;
- `build_helixforge_inputs.py`.
- `run_independent_reference.sh` and `independent_tximport_deseq2.R`.
- `slurm_generate_polyester.sh` and `slurm_convert_polyester_sample.sh`.
- `run_helixforge_synthetic.sh`.
- `evaluate_synthetic.py`.
- `compare_independent.py`.
- `validate_helixforge_run.py`.

`run_independent_reference.sh` must invoke Salmon 1.10.3, tximport 1.30.0 and
DESeq2 1.42.0 directly from a separately pinned environment. It must consume the
same post-trim merged FASTQs and reference artifacts as HelixForge, but it must
not source, include or copy any HelixForge process/module script.

`run_helixforge_synthetic.sh` is a head-node driver only. It verifies the
immutable RC identity and starts Nextflow 25.10.7; every scientific process is
submitted by Nextflow to Slurm with a five-task queue ceiling.

Implemented for the Stage 9B.2 metadata and download boundary:

- `slurm_prepare_gse52778_metadata.sh` fetches official ENA, NCBI and GEO
  metadata inside a Slurm allocation;
- `validate_gse52778_metadata.py` verifies the frozen eight-run selection and
  writes the exact transfer/space plan;
- `download_gse52778.sh` downloads one run per array task using resumable ENA
  paired FASTQs and excludes orphan exports;
- `validate_gse52778_fastq.py` checks official MD5, local SHA-256, gzip
  structure, mate IDs, lengths and paired-record counts;
- `finalize_gse52778_download.py` emits the aggregate manifest, checksum file
  and `DOWNLOAD_READY.json` only after all eight run checkpoints pass.
- `slurm_prepare_gencode_reference.sh` downloads the three frozen GENCODE 49
  inputs with resume support and validates the official release MD5 values;
- `prepare_gencode_reference.py` derives the exact versioned primary-assembly
  transcriptome and `tx2gene.tsv`, decompresses the matching annotation/genome,
  and emits a self-validating `REFERENCE_READY` manifest.
- `build_gse52778_inputs.py` joins the frozen registry, validated download and
  reference manifests into the exact eight-library donor-paired RC case;
- `run_helixforge_gse52778.sh` verifies the immutable RC/Nextflow/Java identity
  and launches the full biological path with at most five Slurm tasks.
- `slurm_restore_temurin21.sh` restores only the exact Temurin 21.0.12+8
  runtime certified in Stage 9B.1 when the portable binary is no longer present;
  the official Adoptium archive is pinned by SHA-256 and extracted on a node.

The download array is submitted with a conservative `%2` concurrency limit.
Heavy payloads remain in the dedicated scratch root and are never committed.
