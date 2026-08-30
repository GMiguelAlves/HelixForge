# Protocol amendment — Real Narrow external-reference contigs

## Status

```ini
PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_PRE_EXECUTION
AMENDMENT_BIAS_RISK = LOW
```

Approved on 2026-08-30 after immutable source download and before HelixForge,
the independent scientific path, peak calling, IDR, motif analysis, or result
inspection.

## Problem

The frozen GENCODE release 50 primary-assembly FASTA does not contain six
random or unplaced contigs present in the descriptive ENCODE optimal-IDR peak
file `ENCFF519CXF`. The reference preparation correctly stopped at the frozen
contig-mismatch guard. The GTF and blacklist are compatible with the FASTA.

The ENCODE peaks and signal are external plausibility references, not inputs
to HelixForge and not ground truth. Replacing the primary reference, renaming
contigs, or silently discarding records is prohibited.

## Amended definition

- The GENCODE release, FASTA, GTF, blacklist, effective genome size, FASTQs,
  processing parameters, seeds, metrics, and acceptance criteria remain
  unchanged.
- GTF and blacklist contigs must remain strict subsets of the FASTA contigs;
  any mismatch is fatal.
- External ENCODE comparisons use the explicit intersection of GENCODE FASTA
  contigs and external-reference contigs.
- External records on absent contigs are excluded only from descriptive
  ENCODE overlap, signal, and null-set calculations. They are not renamed.
- The same shared-contig universe is used for the observed overlap and every
  chromosome-preserving null rotation.
- The reference manifest records each excluded contig plus its record count
  and covered bases. The final report must disclose the total exclusion.

## Bias assessment

This amendment resolves an assembly-universe incompatibility without viewing
any HelixForge or independent scientific result and without changing a method
threshold. Because ENCODE is a descriptive reference rather than truth, and
observed and null comparisons use the same contig universe, the anticipated
bias risk is low and auditable.

## Comparability

The HelixForge and independent paths remain directly comparable because both
use the unchanged primary-assembly reference. Comparisons to `ENCFF519CXF`
are comparable only when the shared-contig rule and recorded exclusions are
applied. This amendment must travel with the final benchmark provenance.
