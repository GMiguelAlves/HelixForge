# FEATURECOUNTS_PEAK

Initial `PEAK_COUNTING_PROVIDER` implementation. It converts a validated BED4
peak universe to SAF, maps BAM columns by final-BAM manifest IDs and writes a
raw integer peak-by-sample matrix. It does not normalize or filter peaks.

V1 rejects mixed layouts, fractional assignment, multiple-overlap assignment
and hidden technical-replicate handling. Scientific options are supplied in the
validated count specification.
