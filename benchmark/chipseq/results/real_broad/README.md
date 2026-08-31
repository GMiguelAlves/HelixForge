# Real Broad benchmark state

This directory stores compact, versioned state and eventual evidence for the
frozen K562 H3K27me3 biological benchmark. Heavy data and work directories are
never committed.

The authoritative progress checkpoint is [`benchmark_state.json`](benchmark_state.json).
Compact final evidence is retained under [`evaluation/`](evaluation/) and
figures under [`figures/`](figures/). RN3 is outside this arm and must not be
reopened here.
