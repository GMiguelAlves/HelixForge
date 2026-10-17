# Tests

From the repository root:

```bash
python3 -m unittest tests.native_chipseq_trimming.test_trimming_contract -v
python3 tests/native_chipseq_trimming/run_functional.py --stub --output /new/stub-directory
```

The same runner without `--stub` exercises a very small real-tool SE/PE fixture,
trimming off/on, direct-tool equivalence, QC reports, BAMs and cache behavior.
It is a functional check, not a scientific/performance benchmark. On a shared
HPC system it must run inside a compute allocation, never on the head node.
