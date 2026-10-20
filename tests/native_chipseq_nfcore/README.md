# nf-core consensus and HOMER integration tests

These are reduced implementation checks, not biological benchmarks.

```bash
python3 -m unittest tests.native_chipseq_nfcore.test_contracts -v
docker build -t hf-nfcore-fixture-python:1.0 -f tests/native_chipseq_nfcore/Dockerfile.python tests/native_chipseq_nfcore
NXF_VER=25.10.7 python3 tests/native_chipseq_nfcore/run_checks.py --output /path/to/new-test-directory
NXF_VER=25.10.7 python3 tests/native_chipseq_nfcore/run_checks.py --min-replicates 1 --output /path/to/new-min1-directory
NXF_VER=25.10.7 python3 tests/native_chipseq_nfcore/run_checks.py --stub --output /path/to/another-new-directory
```

The fixture contains connected/partial overlaps, bookended same-library calls,
unique regions and an empty fourth library. Real checks compare the unchanged
upstream tables and HOMER raw output with direct commands; they verify support
exclusions separately from core geometry, gene IDs, zero support, evidence
transport and identical-run cache reuse. Stub checks validate only DAG/output
contracts. Docker, an official Nextflow launcher and the pinned images are
required; a missing runtime is a failed/unavailable test, not a scientific pass.

The minimum-1 check retains all four regions and verifies source library IDs,
support counts/categories and transport into aggregated gene associations.
Unit cases also cover support in all libraries, mixed-provider aggregates,
empty tables and invalid evidence. HOMER comparisons use peak IDs to ignore
row ordering, but require exact annotations and reject missing/duplicate IDs.

Ambiguity checks cover shared/equidistant TSS, opposite strands, chromosome
isolation, duplicate transcripts, missing evidence and checksum rejection.
A separate tiny real-HOMER annotation fixture verifies tied gene flags without
replacing the selected gene or changing the workflow-equivalence reference.
