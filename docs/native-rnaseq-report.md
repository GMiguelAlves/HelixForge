# Native RNA-seq report migration

## Native processes

- `RNASEQ_REPORT_CONTEXT`: validates API manifests, semantic matrices,
  candidate-gene syntax, parameters and checksums.
- `RNASEQ_GENE_REPORT`: runs the existing scientific R implementation directly
  and adds manifest/provenance artifacts.

The `RNASEQ_REPORT` subworkflow joins those processes. It replaces
`RNASEQ_REPORT_STEP` and `gene_report_job.sh`; no process submits a nested Slurm
job. The module owns its `gene_set_report.R` resource. The initial native copy
is text-identical after LF normalization to the reviewed historical implementation; the legacy copy
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

The clean container and real reduced provider were certified by
[GitHub Actions run 31721249182](https://github.com/GMiguelAlves/HelixForge/actions/runs/31721249182)
on 2026-08-13. The test used four samples, two biological conditions and two
candidate genes. It semantically verified five required tables, eight
gene/sample expression rows, both DEG joins, the rendered HTML, twelve
non-empty PNG figures, the complete manifest and R 4.3.3 session information.

Certified image:

```text
ghcr.io/gmiguelalves/helixforge-rnaseq-report:1.0.0
sha256:ec8818c48c91e2fe501c01ffa27291e92662ddd6d8ab9eb1bc9e6afc99e6f863
```

The default Docker and Apptainer references include that digest. The dedicated
environment pins R 4.3.3, rtracklayer 1.62.0 and every plotting/data package
used by the script.

The Docker image runs as container root so Nextflow work directories mounted
from arbitrary host UIDs remain writable. It requests no privileged mode and
has no host-root capability. `procps` is installed solely for Nextflow task
metrics. Apptainer retains its standard host-user mapping.

The current migration preserves table, figure and HTML names. It does not add
batch correction, enrichment databases or new biological interpretations.
Certification proves the reduced provider contract and runtime. A reviewed
biological benchmark and broad legacy-result comparison remain release-level
validation, as planned; they are not inferred from the synthetic fixture.
