# Native RNA-seq report migration

## Native processes

- `RNASEQ_REPORT_CONTEXT`: validates API manifests, semantic matrices,
  candidate-gene syntax, parameters and checksums.
- `RNASEQ_GENE_REPORT`: runs the existing scientific R implementation directly
  and adds manifest/provenance artifacts.

The `RNASEQ_REPORT` subworkflow joins those processes. It replaces
`RNASEQ_REPORT_STEP` and `gene_report_job.sh`; no process submits a nested Slurm
job. The module owns its `gene_set_report.R` resource. The initial native copy
is byte-identical to the reviewed historical implementation; the legacy copy
is retained only so the not-yet-retired legacy pipeline remains executable.

## Validation status

Python contract/finalization tests and a DSL2 stub fixture cover deterministic
orchestration without installing R. On 2026-08-13, the isolated two-process
fixture and the complete top-level RNA-seq stub graph both completed through
`RNASEQ_GENE_REPORT` under Slurm with Nextflow 25.10.7 and Java 21. The
top-level execution used the production Import policy
`full_length + lengthScaledTPM`, a maximum of five queued jobs, and emitted a
valid final report manifest. The temporary scratch tree was removed after
verification.

A real provider run, container build and scientific comparison remain required
before the report image is certified.
The dedicated environment pins R 4.3.3, rtracklayer 1.62.0 and plotting/data
packages used by the script.

The Docker image runs as container root so Nextflow work directories mounted
from arbitrary host UIDs remain writable. It requests no privileged mode and
has no host-root capability. `procps` is installed solely for Nextflow task
metrics. Apptainer retains its standard host-user mapping.

The current migration preserves table, figure and HTML names. It does not add
batch correction, enrichment databases or new biological interpretations.
