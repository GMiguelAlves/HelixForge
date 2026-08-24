# HelixForge

HelixForge is a reproducible Nextflow DSL2 framework for RNA-seq, ChIP-seq,
and cross-assay molecular evidence integration. It preserves explicit
scientific contracts, provenance, and deterministic outputs while remaining
ready for future assay providers.

> **Release candidate:** the source is preparing for `1.0.0-rc.1`. No release
> tag has been created; tagging still requires explicit maintainer approval.

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
rules and scientific-change expectations are in `CONTRIBUTING.md` (added as
part of the release-candidate consolidation).

## Citation and license

Citation metadata is provided in `CITATION.cff` as part of the release
candidate. HelixForge is licensed under the [Apache License 2.0](LICENSE).
Third-party tools and container components retain their own licenses; see the
[licensing and third-party software policy](docs/licensing.md).
