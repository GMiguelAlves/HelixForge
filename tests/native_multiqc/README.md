# MultiQC OCI certification

This test executes the reusable `MULTIQC` process with the pinned MultiQC 1.17
BioContainer and two deterministic FastQC result directories. It validates the
rendered HTML, parsed FastQC table, general-statistics table, recorded version,
status, and Nextflow trace. No mock MultiQC executable is used.

Run on a Docker-capable host with Nextflow 25.10.7 and Java 21:

```bash
NEXTFLOW="$PWD/nextflow" tests/native_multiqc/run_real.sh
```

The GitHub Actions certification records the immutable repository digest and
uploads the reduced result bundle as evidence.
