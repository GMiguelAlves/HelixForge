# Real Broad read-length validation amendment

## Status

```ini
PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_PRE_EXECUTION
SCIENTIFIC_OUTPUT_OBSERVED = NO
DATA_IDENTITY = VALIDATED
PIPELINE_OR_SCIENTIFIC_PARAMETERS_CHANGED = NO
```

## Finding

The ENCODE API and frozen registry describe `ENCFF000BXN` with a read length of
36 bp. The exact released file, however, contains two read-length classes:
11,752,939 reads of 36 bp and 11,077,650 reads of 47 bp. This was discovered
during download validation, before alignment or any scientific result was
produced.

The file is not corrupt or substituted. Its accession, byte size, compressed
MD5, uncompressed-content MD5 and total read count all match the frozen ENCODE
record exactly. `ENCFF000BXP` and `ENCFF000BWK` are uniform at their declared
51 bp and 36 bp lengths, respectively.

## Amendment

The frozen `read_length_bp` field remains the public metadata value and is not
rewritten. FASTQ validation now requires the exact audited length histogram in
addition to the original strict identity, structure and count checks:

| File | Audited length distribution |
| --- | --- |
| `ENCFF000BXP` | 51 bp: 19,297,190 |
| `ENCFF000BXN` | 36 bp: 11,752,939; 47 bp: 11,077,650 |
| `ENCFF000BWK` | 36 bp: 27,579,809 |

This amendment changes only the interpretation of an incomplete descriptive
metadata field. It does not alter the FASTQs, sample selection, preprocessing,
alignment, peak calling, consensus, evaluation criteria or any other frozen
scientific parameter.
