# REFERENCE_BUNDLE

Validates the files needed by RNA-seq providers and creates a SHA-256 manifest.
The module never downloads, edits, decompresses, or indexes a reference. Index
construction remains independently cached in the Alignment and Quantification
APIs.
