# HOMER_ANNOTATION_ADAPTER

Normalizes HOMER's output to the Peak Annotation API without assigning genes
again. Peak coordinates come from the validated BED; the original HOMER table,
feature label, nearest promoter ID and TSS distance remain available. Missing
gene IDs/distances stay missing. Every input peak must occur exactly once.

For `nfcore_2_1`, an explicit consensus bundle is required and checked against
the source manifest and artifact SHA-256 values. Each association carries all
library identities, coverage/fractions, core bases and candidate classification.
The original support/core/mapping tables are retained beside the normalized
tables. No enrichment ratio is converted into a p-value or occupancy assertion.

Python normalization runs separately from HOMER, using the existing metadata
runtime. It requires no additional statistical package or reference database.
