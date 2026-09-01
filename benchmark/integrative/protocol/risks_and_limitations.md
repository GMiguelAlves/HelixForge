# Preregistered risks and limitations

## Synthetic arm

- Artificially balanced classes do not represent biological prevalence.
- Fixed effect tiers can make classification easier than real data.
- A truth table necessarily encodes model semantics; circularity is mitigated
  by an independent generator/evaluator, weak effects, discordance, multiple
  peaks, partial evidence and explicit missingness.
- Candidate Score has no concordance penalty. Strong discordant evidence may
  rank highly by design; this is characterized rather than redefined.
- `NO_PEAK`, `MISSING`, `NOT_MEASURED` and `NOT_APPLICABLE` occupy different
  fields/scopes. A flattened missing-state metric would be invalid.
- Context aliases are deliberately limited to the implemented vocabulary;
  fuzzy biological label reconciliation is out of scope.

## Re-entry and contract arms

- Byte identity is inappropriate for HTML and volatile execution metadata.
- A valid contrast present in only one assay is intentionally retained as
  unilateral evidence. Treating it as a mandatory fatal mismatch would test a
  different contract.
- Schema validation and workflow preflight are separate layers; negative tests
  record the expected layer explicitly.

## Real arm

- `GSE133183` has two biological replicates per selected condition/assay.
- Sequencing depth, read length and ChIP quality may differ across libraries.
- GSK343 can cause broad chromatin and transcriptional changes; not every RNA
  response has a direct local peak explanation.
- H3K27me3 broad domains and H3K27ac narrow/active regions have different peak
  geometry and aggregation behavior.
- IgG controls do not remove all antibody- or library-specific biases.
- The study's processed products may use preprocessing choices different from
  HelixForge; raw-data production is therefore preferred for the final arm.
- Reference/annotation identity must be established before execution. A
  mismatch is a stop condition, not an invitation to relabel IDs.
- Literature examples are expectations, not absolute truth. Failure to recover
  one gene is not a false positive/negative classification.
- Cell-line heterogeneity and batch effects may limit concordance.

## Operational risks

- Public accessions or registries may change availability.
- Shared Slurm load may block or distort performance measurements.
- Apptainer/network access may remain unavailable on the university cluster.
- Large raw data, work directories and containers are excluded from Git.

## Mitigations

Freeze checksums before execution, validate accession metadata and reference
compatibility first, keep an independent evaluator, cap concurrent jobs,
separate correctness from descriptive biology/performance, and record every
protocol amendment before looking at affected results.
