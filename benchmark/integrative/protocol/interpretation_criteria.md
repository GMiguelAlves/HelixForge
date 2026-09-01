# Frozen interpretation criteria

Types are `RELEASE_GATE`, `EXPECTED_RANGE`, `SANITY_CHECK` and `DESCRIPTIVE`.
Thresholds cannot be tightened after observing outputs.

| ID | Arm | Metric | Type | Frozen threshold or expectation | Failure meaning |
|---|---|---|---|---|---|
| IS1 | Synthetic | canonical entities preserved | RELEASE_GATE | exactly 1,000; exact truth set | evidence loss/duplication |
| IS2 | Synthetic | full outer gene join | RELEASE_GATE | 100% exact RNA/ChIP master states | incorrect assay-union semantics |
| IS3 | Synthetic | observation missingness | RELEASE_GATE | 100% exact scoped states | missing value converted to evidence/absence |
| IS4 | Synthetic | critical regulatory patterns | RELEASE_GATE | recall, precision and F1 = 1.0 for concordant, discordant, RNA-only and ChIP-only | interpretation defect |
| IS5 | Synthetic | all-pattern accuracy / macro-F1 | RELEASE_GATE | both >= 0.995 | systematic or multiple semantic errors |
| IS6 | Synthetic | harmonization maps | RELEASE_GATE | exact expected entity/contrast/context/mark maps | unsupported or unsafe normalization |
| IS7 | Synthetic | peak aggregation | RELEASE_GATE | counts and complete ID sets exactly equal | peak evidence loss or invented summarization |
| IS8 | Synthetic | Fisher/BH/odds agreement | RELEASE_GATE | all values within abs 1e-10 / rel 1e-8; cells exact | numerical/statistical divergence |
| IS9 | Synthetic | Pearson/Spearman agreement | RELEASE_GATE | coefficients within abs 1e-8; NA semantics exact | correlation divergence |
| IS10 | Synthetic | Candidate Score component agreement | RELEASE_GATE | every component and final score within abs 1e-8; deterministic tie order exact | score implementation divergence |
| IS11 | Synthetic | priority Spearman | EXPECTED_RANGE | >= 0.60 | weak prioritization utility; not core evidence failure |
| IS12 | Synthetic | HIGH-priority top-100 recovery | EXPECTED_RANGE | >= 0.80 | ranking limitation |
| IR1 | Re-entry | semantic table equivalence | RELEASE_GATE | exact rows, columns, entities, states and classes | path-dependent science |
| IR2 | Re-entry | numeric equivalence | RELEASE_GATE | same tolerances as IS8–IS10 | path-dependent numerical result |
| IR3 | Re-entry | deterministic artifact identity | RELEASE_GATE | canonical TSV SHA-256 identical | nondeterministic or altered re-entry |
| IR4 | Re-entry | terminal lineage | RELEASE_GATE | same source manifest/checksum identities; only declared location/runtime fields may differ | broken provenance |
| IC1 | Contracts | reference/genome mismatch | RELEASE_GATE | all frozen fixtures fail at compatibility validation | incompatible biology accepted |
| IC2 | Contracts | assembly/annotation mismatch | RELEASE_GATE | all frozen fixtures fail at compatibility validation | incompatible coordinate/annotation identity accepted |
| IC3 | Contracts | invalid contrast | RELEASE_GATE | malformed or artifact-unknown contrasts fail; valid unmatched assay contrasts remain unilateral | invalid comparison accepted or valid evidence lost |
| IC4 | Contracts | entity collision | RELEASE_GATE | opt-in version-strip collision fails | distinct genes silently merged |
| IC5 | Contracts | manifest/provenance/type validation | RELEASE_GATE | malformed, missing provenance and invalid type fixtures all fail schema validation | invalid contract accepted |
| IC6 | Contracts | supported normalization | SANITY_CHECK | HP1 and histone case normalize; unknown mark/context preserved | undocumented guessing or alias regression |
| IB1 | Biological | contract/reference compatibility | RELEASE_GATE | both assay manifests valid and fully reference-compatible before integration | real arm scientifically invalid |
| IB2 | Biological | technical completion | RELEASE_GATE | complete terminal manifest, report and all required component manifests | incomplete workflow |
| IB3 | Biological | entity/state accounting | SANITY_CHECK | all master genes partition exactly into frozen state categories | accounting defect |
| IB4 | Biological | H3K27me3 depletion direction | EXPECTED_RANGE | loss/decrease predominates among significant H3K27me3 DB evidence | weak drug/assay response or incompatible contrast |
| IB5 | Biological | directional enrichment | EXPECTED_RANGE | concordant activation/repression odds ratio > 1 where tests are evaluable | limited cross-assay biological signal |
| IB6 | Biological | preregistered examples | DESCRIPTIVE | report all expectations without selection | biological plausibility record |
| IB7 | Biological | Candidate Score review | DESCRIPTIVE | top 20 overall + top 10 per concordant direction | prioritization characterization |
| IB8 | Biological | functional analysis | DESCRIPTIVE | database/version/background and BH method recorded | incomplete descriptive provenance |

Core release gates are evaluated independently from ranking quality. Global
classification is `FAIL` if a core release gate fails; unmet expected ranges
may yield `PASS_WITH_LIMITATIONS` after review. Missing descriptive metrics do
not automatically fail the benchmark.
