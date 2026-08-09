# PEAK_CALLING_CONTEXT

Validates Peak Calling API v1 before alignment or BAM processing begins. It requires an explicit caller, peak type, numerical effective genome size and significance cutoff, and resolves every treatment/control relationship to one record.

Ambiguous controls, duplicate replicate identities, unsafe output collisions and attempts to override managed MACS3 arguments fail before heavy jobs are submitted.
