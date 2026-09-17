# Native RNA-seq report migration

> **Historical implementation record.** The current contract is documented in
> the [RNA-seq Report API](rnaseq_report_api.md).

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
Certification proves the reduced provider contract and runtime. The full
synthetic production path also passed on Slurm with 12 non-empty figures. A
reviewed biological benchmark and broad result assessment remain a post-release
validation milestone, as planned; they are not inferred from synthetic data.

## Presentation validation

The revised presentation layer was validated on 2026-09-17 against the
preserved PRJNA597909 result set using the certified R environment on Slurm.
The report completed in 1 minute 56 seconds with a peak resident-memory use of
approximately 1.13 GiB. It represented 65 gene/group entries covering 61
unique requested genes, of which 45 were present in the expression matrix.

The revision reduced the generated figure set from 348 referenced plots to 285
non-empty PNG files by rendering each unique gene only once. The complete
result directory decreased from approximately 78 MB to 38 MB. Automated checks
confirmed that every referenced image resolved, detailed images were deferred
until their section was opened, and no absolute runtime path was exposed in the
HTML or differential-expression tables.

This validation concerns navigation, presentation, portability and resource
use. Candidate-gene selection, expression transformations, differential-
expression thresholds and all exported scientific tables remain unchanged.
