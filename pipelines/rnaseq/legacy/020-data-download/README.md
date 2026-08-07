# 020-data-download

Download FASTQs for each project. Files are written to:

```text
${SCRATCH_ROOT}/<PROJECT>/fastq_ftp
```

## Before You Run

In `config/user_settings.sh`, set:

```bash
export PIPELINE_PROJECTS="PRJXXXX PRJYYYY"
export SCRATCH_ROOT="/scratch/my_user/rnaseq"
```

For each project, create:

```text
020-data-download/datasets/<PROJECT>/config.yaml
020-data-download/datasets/<PROJECT>/<link_file>
```

Minimal `config.yaml`:

```yaml
project:
  id: PRJXXXX
  organism: configured_in_config_pipeline_config
  source: ENA
  accession: PRJXXXX

download:
  link_file: ena-file-download-read_run-PRJXXXX-fastq_ftp.sh
  threads: 8

library:
  layout: paired
  compression: gz
```

The link file may be an ENA download script or a plain text list of `ftp://` or
`https://` FASTQ URLs.

Only projects listed in `PIPELINE_PROJECTS` are used by `rnaseq_pipeline.sh`. Any bundled
project folders are examples or legacy inputs, not pipeline defaults.

## Run

Normally `rnaseq_pipeline.sh` submits this step. To run one project manually
from the repository root:

```bash
sbatch --chdir=020-data-download \
  --export=ALL,PROJECT_DIR="$PWD",PIPELINE_CONFIG="$PWD/config/pipeline_config.sh" \
  scripts/020-data-download/download_final.sh PRJXXXX
```

Without Slurm:

```bash
bash scripts/020-data-download/download_final.sh PRJXXXX
```

## Optional FASTQ Renaming

After metadata parsing, preview a rename plan:

```bash
python scripts/020-data-download/generate_rename_manifest.py \
  --metadata 025-parse/030-metadata_final/AllProjects_metadata.csv \
  --project PRJXXXX \
  --output 020-data-download/PRJXXXX_rename_manifest.csv

python scripts/020-data-download/rename_fastqs_from_metadata.py \
  --metadata 025-parse/030-metadata_final/AllProjects_metadata_new.csv \
  --project PRJXXXX \
  --scratch-root "$SCRATCH_ROOT" \
  --manifest 020-data-download/PRJXXXX_rename_manifest.csv
```

Add `--apply` only after validation passes.
