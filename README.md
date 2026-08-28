# HelixForge

HelixForge is a reproducible Nextflow DSL2 framework for RNA-seq, ChIP-seq,
and cross-assay molecular evidence integration. It preserves explicit
scientific contracts, provenance, and deterministic outputs while remaining
ready for future assay providers.

## What it runs

| Workflow | Production path | Terminal contract |
|---|---|---|
| RNA-seq | QC -> Salmon -> tximport -> DESeq2 -> reports | `rnaseq_run_manifest.json` |
| ChIP-seq | QC -> Bowtie2 -> BAM processing -> MACS3 -> peak QC/consensus or IDR -> differential binding -> annotation/tracks -> report | `chipseq_run_manifest.json` |
| Integrative | RNA and ChIP manifests -> evidence normalization -> linkage -> ranking -> functional interpretation -> report | `integrative_run_manifest.json` |
| All | Independent RNA-seq and ChIP-seq DAGs followed by Integrative | all three manifests |

Salmon is the certified RNA-seq production provider. STAR implements the
Alignment API but remains experimental and is never selected implicitly.
IDR is an optional ChIP-seq branch for exactly two compatible biological
replicates.

## Requirements

- Linux x86_64 or WSL2; native Windows execution is not supported.
- Java 21.
- Nextflow 25.10.7 (the certified runtime).
- Git.
- Docker for the recommended local container profile, or an appropriate
  site-specific Slurm/container setup.

See [Installation](docs/installation.md) for the tested support matrix.

## Quick start

The first run is a deterministic stub smoke test. It does not perform a
scientific analysis or download biological data.

```bash
git clone https://github.com/GMiguelAlves/HelixForge.git
cd HelixForge
curl -fsSL https://get.nextflow.io | NXF_VER=25.10.7 bash
NEXTFLOW="$PWD/nextflow" bin/helixforge-doctor
./nextflow run . -profile test -stub-run \
  --workflow all \
  --outdir results/quickstart
```

Expected result: the run completes successfully and creates terminal manifests
under `results/quickstart`. On a typical development machine it should finish
within a few minutes.

For a small real, deterministic Integrative execution using generated fixture
data, and for individual workflow commands, follow the
[Quick Start guide](docs/quickstart.md).

## Run a workflow

```bash
# RNA-seq production path
nextflow run . -profile docker \
  --workflow rnaseq \
  --rnaseq_run_mode full \
  --rnaseq_config /path/to/pipeline_config.sh \
  --rnaseq_de_spec /path/to/de_spec.json \
  --outdir results

# ChIP-seq production path
nextflow run . -profile docker \
  --workflow chipseq \
  --chipseq_run_mode full \
  --chipseq_config /path/to/pipeline_config.sh \
  --chipseq_db_spec /path/to/differential_binding.json \
  --outdir results

# Integrate completed assay manifests
nextflow run . -profile local \
  --workflow integrative \
  --rna_manifest /path/to/rnaseq_run_manifest.json \
  --chip_manifest /path/to/chipseq_run_manifest.json \
  --outdir results
```

These examples show the public entry points; real analyses also require the
references, samples and explicit scientific parameters described in
[Workflows](docs/workflows.md). HelixForge never acquires input data inside the
scientific DAG.

## Results and reproducibility

Terminal manifests are the stable integration boundary. Downstream consumers
must use their semantic roles rather than infer meaning from paths. Every run
also produces Nextflow trace, timeline, report and DAG artifacts. See
[Outputs](docs/outputs.md), [Terminal manifests](docs/terminal_manifests.md),
and [Versioning](docs/versioning.md).

HelixForge distinguishes byte-exact artifacts (for example FASTQ and BAM),
semantic artifacts (JSON/TSV where paths or serialization may vary), and
generated presentation artifacts. Scientific policies and validation evidence
are documented in the [Scientific reference](docs/scientific-reference.md).

## Documentation

Start at the [documentation index](docs/index.md):

- [Installation](docs/installation.md)
- [Quick Start](docs/quickstart.md)
- [Workflow guide](docs/workflows.md)
- [Output guide](docs/outputs.md)
- [Public API](docs/public-api.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Developer guide](docs/developer-guide.md)

The same curated user documentation is published in the
[GitHub Wiki](https://github.com/GMiguelAlves/HelixForge/wiki).

## Development

```bash
python3 tests/run_unit_tests.py
nextflow lint .
```

Run `bin/helixforge-doctor` before reporting an environment failure. Contribution
rules and scientific-change expectations are in `CONTRIBUTING.md`.

## Third-party references

HelixForge orchestrates, but does not replace, the scientific software below.
Please cite the relevant original tools and data resources when publishing
results. Version pins and container identities in the module environments and
run manifests are authoritative; these links provide attribution, not mutable
dependency specifications.

### Workflow and execution infrastructure

| Resource | Reference |
|---|---|
| Nextflow | Di Tommaso et al. (2017), [*Nextflow enables reproducible computational workflows*](https://doi.org/10.1038/nbt.3820) |
| Slurm | Yoo, Jette and Grondona (2003), [*SLURM: Simple Linux Utility for Resource Management*](https://doi.org/10.1007/10968987_3) |
| Docker / OCI | [Docker documentation](https://docs.docker.com/) and the [Open Container Initiative](https://opencontainers.org/) |
| Apptainer / Singularity | Kurtzer, Sochat and Bauer (2017), [*Singularity: Scientific containers for mobility of compute*](https://doi.org/10.1371/journal.pone.0177459) |
| Conda / Bioconda | Grüning et al. (2018), [*Bioconda: sustainable and comprehensive software distribution for the life sciences*](https://doi.org/10.1038/s41592-018-0046-7) |
| R / Bioconductor | Gentleman et al. (2004), [*Bioconductor: open software development for computational biology and bioinformatics*](https://doi.org/10.1186/gb-2004-5-10-r80) |

Auxiliary runtime and reporting dependencies—including Python, R, Bash,
Coreutils, gzip, jsonschema, data.table, dplyr, ggplot2, ggrepel, jsonlite,
matrixStats, pheatmap, readr, stringr, tibble and tidyr—are recorded with exact
versions in the corresponding `environment.yml` files. Their package metadata
and `citation()` output should be consulted when a publication depends directly
on one of them.

### Quality control and preprocessing

| Tool | Reference |
|---|---|
| FastQC | Andrews, [FastQC: a quality control tool for high-throughput sequence data](https://www.bioinformatics.babraham.ac.uk/projects/fastqc/) |
| MultiQC | Ewels et al. (2016), [*MultiQC: summarize analysis results for multiple tools and samples in a single report*](https://doi.org/10.1093/bioinformatics/btw354) |
| Trim Galore | Krueger, [Trim Galore project](https://www.bioinformatics.babraham.ac.uk/projects/trim_galore/); adapter trimming is provided by Cutadapt |
| Cutadapt | Martin (2011), [*Cutadapt removes adapter sequences from high-throughput sequencing reads*](https://doi.org/10.14806/ej.17.1.200) |

### RNA-seq

| Tool | Reference |
|---|---|
| STAR | Dobin et al. (2013), [*STAR: ultrafast universal RNA-seq aligner*](https://doi.org/10.1093/bioinformatics/bts635) |
| Salmon | Patro et al. (2017), [*Salmon provides fast and bias-aware quantification of transcript expression*](https://doi.org/10.1038/nmeth.4197) |
| tximport | Soneson, Love and Robinson (2015), [*Differential analyses for RNA-seq: transcript-level estimates improve gene-level inferences*](https://doi.org/10.12688/f1000research.7563.2) |
| DESeq2 | Love, Huber and Anders (2014), [*Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2*](https://doi.org/10.1186/s13059-014-0550-8) |
| rtracklayer | Lawrence, Gentleman and Carey (2009), [*rtracklayer: an R package for interfacing with genome browsers*](https://doi.org/10.1093/bioinformatics/btp328) |
| SummarizedExperiment | [Bioconductor package and citation information](https://bioconductor.org/packages/SummarizedExperiment/) |

### ChIP-seq

| Tool | Reference |
|---|---|
| Bowtie 2 | Langmead and Salzberg (2012), [*Fast gapped-read alignment with Bowtie 2*](https://doi.org/10.1038/nmeth.1923) |
| SAMtools / HTSlib | Li et al. (2009), [*The Sequence Alignment/Map format and SAMtools*](https://doi.org/10.1093/bioinformatics/btp352) |
| BEDTools | Quinlan and Hall (2010), [*BEDTools: a flexible suite of utilities for comparing genomic features*](https://doi.org/10.1093/bioinformatics/btq033) |
| MACS3 | [MACS3 project](https://github.com/macs3-project/MACS); Zhang et al. (2008), [*Model-based analysis of ChIP-Seq (MACS)*](https://doi.org/10.1186/gb-2008-9-9-r137) |
| featureCounts / Subread | Liao, Smyth and Shi (2014), [*featureCounts: an efficient general-purpose program for assigning sequence reads to genomic features*](https://doi.org/10.1093/bioinformatics/btt656) |
| IDR | Li et al. (2011), [*Measuring reproducibility of high-throughput experiments*](https://doi.org/10.1214/11-AOAS466) |
| deepTools | Ramírez et al. (2016), [*deepTools2: a next generation web server for deep-sequencing data analysis*](https://doi.org/10.1093/nar/gkw257) |
| pyBigWig | [pyBigWig project](https://github.com/deeptools/pyBigWig) |

### Benchmark datasets and reference resources

| Resource | Reference and use |
|---|---|
| Polyester synthetic RNA-seq benchmark | Frazee et al. (2015), [*Polyester: simulating RNA-seq datasets with differential transcript expression*](https://doi.org/10.1093/bioinformatics/btv272) |
| GSE52778 / SRP033351 / PRJNA229998 | Himes et al. (2014), [airway smooth-muscle RNA-seq study](https://doi.org/10.1371/journal.pone.0099625); [GEO record](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE52778) |
| GEO | Barrett et al. (2013), [*NCBI GEO: archive for functional genomics data sets—update*](https://doi.org/10.1093/nar/gks1193) |
| European Nucleotide Archive | Harrison et al. (2022), [*The European Nucleotide Archive in 2021*](https://doi.org/10.1093/nar/gkab1051) |
| GENCODE Human Release 49 | [GENCODE release 49](https://www.gencodegenes.org/human/release_49.html); Frankish et al. (2021), [*GENCODE 2021*](https://doi.org/10.1093/nar/gkaa1087) |
| GRCh38 | Schneider et al. (2017), [*Evaluation of GRCh38 and de novo haploid genome assemblies*](https://doi.org/10.1101/gr.213611.116) |

The current ChIP-seq validation artifacts use small project-owned synthetic
fixtures; no third-party biological ChIP-seq dataset is claimed as a completed
benchmark yet. Exact accessions, source checksums and reuse notes for completed
RNA-seq benchmarks are preserved in the
[RNA-seq dataset registry](benchmark/rnaseq/datasets/dataset_registry.md).

## Citation and license

Citation metadata is provided in `CITATION.cff`. HelixForge is licensed under
the [Apache License 2.0](LICENSE).
Third-party tools and container components retain their own licenses; see the
[licensing and third-party software policy](docs/licensing.md).
