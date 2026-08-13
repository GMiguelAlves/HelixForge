# MultiQC OCI certification

This test executes the reusable `MULTIQC` process with the pinned MultiQC 1.17
BioContainer and two deterministic FastQC result directories. It validates the
rendered HTML, parsed FastQC table, general-statistics table, recorded version,
status, Nextflow trace, and the immutable OCI repository digest. No mock MultiQC
executable is used.
Result publication is performed by Nextflow rather than by writing from inside
the container to an unmounted host path.

Run on a Docker-capable host with Nextflow 25.10.7 and Java 21:

```bash
NEXTFLOW="$PWD/nextflow" tests/native_multiqc/run_real.sh
```

The GitHub Actions certification records the immutable repository digest and
uploads the reduced result bundle as evidence.
