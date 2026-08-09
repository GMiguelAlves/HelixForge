# IDR_PROVIDER

IDR is not approximated by interval intersection. This v1 provider abstraction
validates exactly two premerged biological narrowPeak inputs, an explicit IDR
threshold, and an explicit rank metric. It emits a structured
`not_implemented` manifest and provider request, with no consolidated peak
artifact.

A future commit may replace the pending runtime with a pinned, validated IDR
tool without changing the subworkflow contract.
