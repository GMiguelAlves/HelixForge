# MultiQC OCI certification

This test executes the reusable `MULTIQC` process with the MultiQC 1.17
BioContainer pinned by OCI digest and two deterministic FastQC result
directories. It validates the
rendered HTML, parsed FastQC table, general-statistics table, recorded version,
status, Nextflow trace, and the immutable OCI repository digest. No mock MultiQC
executable is used.
Result publication is performed by Nextflow rather than by writing from inside
the container to an unmounted host path.

Run on a Docker-capable host with Nextflow 25.10.7 and Java 21:

```bash
NEXTFLOW="$PWD/nextflow" tests/native_multiqc/run_real.sh
```

The certified reference is
`quay.io/biocontainers/multiqc@sha256:fb7d6625fb5adaed43ced8bd051a875038714180bcfcd7c8e467204f72882de9`.
GitHub Actions run `31726522504` executed two FastQC records successfully with
Java 21 and Nextflow 25.10.7. Its downloadable certification artifact includes
the HTML report, parsed tables, trace, recorded tool version, status, and image
digest.
