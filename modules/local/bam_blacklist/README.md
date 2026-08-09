# BAM_BLACKLIST

Blacklist input is optional and never inferred from the organism. The module
validates BED coordinates and requires every BED contig to exist in the
validated BAM/reference contract. `fragment` removes every alignment sharing a
QNAME with an overlap and preserves paired-template consistency; `alignment`
reproduces the legacy alignment-level exclusion policy.

