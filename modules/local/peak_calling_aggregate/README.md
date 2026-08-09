# PEAK_CALLING_AGGREGATE

Caller-independent output normalization for Peak Calling API v1. It validates exact narrowPeak/broadPeak column counts, half-open non-negative coordinates and numeric score/signal fields, then emits semantic artifacts and compact width, score and signal distributions.

FRiP is intentionally not calculated here because its read-counting definition belongs to a later QC contract.
