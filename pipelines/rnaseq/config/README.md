# Configuration

Most users should edit only:

```text
config/user_settings.sh
```

Create it from the template:

```bash
cp config/user_settings_template.sh config/user_settings.sh
```

Then edit:

- `PIPELINE_NAME`
- `ORGANISM_NAME`
- `PIPELINE_PROJECTS`
- `SCRATCH_ROOT`
- `CONDA_BASE`
- reference URLs or local reference file paths
- `QUANT_METHOD`: use `salmon` or `star`
- `PIPELINE_EXECUTOR`: use `slurm ` on an HPC server or `local` without Slurm
- `LOCAL_CPUS_PER_TASK`: number of local CPU threads used by tools that honor it

Reference requirements depend on the quantification method:

- `QUANT_METHOD=salmon`: provide transcript FASTA through `TRANSCRIPTS_URL`
  or `REF_TRANSCRIPTS_FA`; the report uses `GFF3_URL`/`GTF_URL` for gene names
  and genomic coordinates when available.
- `QUANT_METHOD=star`: provide genome FASTA plus GTF/GFF3 through
  `GENOME_URL`/`REF_GENOME_FA` and `GTF_URL`/`REF_GTF` or
  `GFF3_URL`/`REF_GFF3`; the pipeline builds/uses `STAR_INDEX_GTF_DIR` and
  imports STAR `ReadsPerGene.out.tab`.

Useful STAR options:

```bash
export QUANT_METHOD="star"
export STAR_GENECOUNT_COLUMN="unstranded"  # or stranded_forward / stranded_reverse
export STAR_QUANT_CONCURRENCY=2
export STAR_READ_FILES_COMMAND="zcat"      # set to "" only for uncompressed FASTQ
```

Do not replace `config/pipeline_config.sh`. It remains the transitional input
contract consumed by native Nextflow adapters; most users edit only
`user_settings.sh` or pass a project-specific configuration.

Run HelixForge from the repository root:

```bash
nextflow run . --workflow rnaseq --rnaseq_config pipelines/rnaseq/config/pipeline_config.sh
```
