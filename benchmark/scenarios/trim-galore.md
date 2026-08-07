# Trim Galore migration benchmark

Use `tests/native_trim_galore/run_comparison.sh` on a controlled host. The
scenario runs the legacy command and native module with the same two-read
synthetic dataset, parameters, CPU count, and pinned container.

The generated `benchmark.tsv` measures wall-clock elapsed time. Nextflow startup
is included in the native value, so this tiny case measures orchestration
overhead rather than production throughput. Production conclusions require
representative FASTQ sizes and repeated runs on the target cluster.
