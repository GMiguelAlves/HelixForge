# Risks and limitations

## Scientific limitations

- The synthetic genome is small and only crudely models repeats and
  mappability, so mapping and peak recovery may be easier than on GRCh38.
- ChIPs produces stochastic biological-like replicates, not true donor or
  culture variation.
- The broad-domain generator tests recovery of declared continuous enrichment;
  it does not model Polycomb nucleation, spreading, accessibility, copy-number
  variation or H3K27me3 boundary biology.
- Negative panels make score-based AUPRC reproducible but do not replace
  genome-wide false-positive accounting.
- ENCODE processed peaks are pipeline-dependent plausibility references, not
  truth.
- The real experiments are legacy data with unequal read lengths and ENCODE
  compliance warnings. Results may reflect platform and experiment age.
- Shared Input reduces cost and laboratory variability but does not test
  provider-specific or experiment-specific control behavior.
- Duplicate retention follows the current HelixForge default. It may inflate
  signal in high-duplication libraries; duplicate statistics must be reported.
- No trimming is performed because no native ChIP trimming stage exists.
- IDR is evaluated only for two narrow biological replicates. Classical IDR is
  not generalized to broad domains.
- Single-condition public experiments do not validate differential binding.

## Implementation risks

- `chipseq_run_mode=full` composes differential binding and is therefore not
  the correct coordinator for these single-condition arms. Mode-specific runs
  may not emit the same terminal manifest as `full`; the benchmark harness must
  produce a complete top-level evidence manifest without changing scientific
  outputs.
- Synthetic paired-end and real single-end data exercise different MACS3 model
  behavior (`BAMPE` versus `BAM`). Results must not be compared as though the
  layouts were equivalent.
- MACS3 broad cutoff is implicit at its documented default because the current
  module does not pass `--broad-cutoff`; tool-version drift would therefore be
  material.
- Container registries or Apptainer may be unavailable from compute nodes.
  OCI is the certified path; unavailable runtimes are classified `BLOCKED`, not
  silently substituted.
- NFS metadata behavior and Nextflow cache persistence may affect `-resume`
  independently of scientific correctness. Cache evidence is reported
  separately.
- The Real Narrow preflight currently uses a small, isolated Conda environment
  solely because Git is absent from the compute nodes. This operational
  hardening reflects accumulated validation lessons and does not imply that
  previous benchmarks were inadequate. It may be replaced in future arms by a
  head-node provenance manifest whose commit, status, and source checksums are
  validated on compute nodes without Git.

## Interpretation risks

- High FRiP alone does not prove accurate peak location or domain boundaries.
- High replicate correlation can coexist with systematic false positives.
- Strong overlap with ENCODE reference outputs can reflect shared software and
  parameter choices rather than biological correctness.
- Narrow and broad metrics are intentionally different; a single pooled score
  would hide failure modes and is prohibited.
- Visual locus inspection is supportive evidence, never a substitute for the
  predeclared quantitative gates.

## Mitigations

Use immutable inputs and checksums, retain independent end-to-end processing,
apply frozen metrics before viewing results, publish limitations with each arm,
and classify arms independently. Any post-freeze scientific parameter change
requires a new protocol version and an explicit explanation; it may not
overwrite this baseline.
