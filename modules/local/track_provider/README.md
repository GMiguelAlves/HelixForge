# TRACK_PROVIDER

Provider abstraction for Track Generation API v1. The first implementation is
`deeptools_bamcoverage_v1`: it emits BigWig from final BAMs and only invokes
`samtools merge` for an explicitly validated aggregate request. No read filters
are applied here.
