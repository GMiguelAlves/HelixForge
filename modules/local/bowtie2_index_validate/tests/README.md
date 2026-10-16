# Tests

Run `python -m unittest tests.native_bowtie2_prebuilt.test_index_bundle -v`
from the repository root. Unit-test shards are synthetic bytes and exercise
the contract only, not index readability.

`python tests/native_bowtie2_prebuilt/run_functional.py --output <new-directory>`
uses real Bowtie2, samtools and the official Nextflow launcher available on
PATH. It builds once, reuses in an independent run, compares BAM records,
checks resume, and rejects changed reference, version, parameters and shards.
Run this inside a Slurm allocation on HPC, never as processing on the head.
