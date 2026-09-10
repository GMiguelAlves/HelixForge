# Integrative benchmark utilities

Only portable scientific utilities are retained here:

- synthetic truth and fixture builders;
- independent evaluators and run comparators;
- manifest re-entry preparation and validation;
- negative-contract executor;
- finalizers and figure renderer;
- GSE133183 metadata/reference adapters, manifest composition and evaluator.

Management-node starters, `sbatch` launchers, one-off recovery drivers, runtime
shims and audit packagers were retired after the baseline freeze. Those files
described one cluster session and are not required to interpret the public
evidence or execute the supported top-level workflow. Their exact historical
versions remain available at the annotated tag
`integrative-benchmark-v1.0.0-rc.1`.

The retained Python utilities are deterministic and parameterized. They do not
contain private cluster paths, raw biological data or Nextflow workdirs.
