# Protocol amendment — broad-domain repeat traversal

## Status

```ini
PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_PRE_EXECUTION
AMENDMENT_BIAS_RISK = LOW
```

Approved on 2026-08-28 before synthetic broad truth generation, read
simulation, HelixForge execution or inspection of any broad peak-calling
result.

## Problem

The frozen requirement that every synthetic broad domain and matched negative
region lie entirely outside repeat intervals is geometrically incompatible
with the frozen reference architecture. Repeats occur every 10 kb, each spans
1 kb, and the frozen 2 kb buffer on both sides leaves uninterrupted eligible
corridors of at most 5 kb. This makes most `MEDIUM_BROAD` domains and every
`LONG_BROAD` domain impossible to place.

## Original definition

Synthetic truth and negative regions were required to remain entirely within
non-repeat, uniquely mappable sequence and at least 2 kb from repeats. Broad
widths were frozen at 2,000–4,999 bp, 5,000–19,999 bp and 20,000–80,000 bp.

## Amended definition

- The reference, 360-domain count, 3 × 3 class balance, exact width ranges,
  signal classes, seeds and minimum inter-domain gap remain unchanged.
- The interior of a synthetic broad domain may traverse repeat intervals.
- Both domain boundaries must lie in non-repeat sequence and remain at least
  2 kb from the nearest repeat. The generator fails rather than silently
  relaxing this boundary rule.
- Matched negative regions follow the same deterministic boundary rule and
  may also traverse repeats.
- Every domain and negative records `repeat_overlap_bp` and
  `repeat_overlap_fraction`.
- Domains are never removed or reclassified because of repeat content.
- MACS3, consensus, matching, topology and acceptance criteria remain
  unchanged.

## Descriptive analysis

The evaluator reports the association of repeat-overlap fraction with
per-domain coverage recall, IoU and boundary error. These measurements are
descriptive and introduce no new release gate.

## Bias assessment

The amendment resolves an impossibility without using scientific outputs and
does not tune a method threshold. Repeat traversal can make some domains more
difficult to recover, so repeat overlap is retained as an explicit covariate
and limitation. The anticipated bias risk is therefore low and auditable.

## Comparability

Synthetic narrow is unchanged. Synthetic broad results are comparable only to
runs using this amendment and the same reference/repeat model. This amendment
must travel with the truth manifest and final benchmark provenance.
