# BAM_DUPLICATES

Duplicate handling is an independent scientific policy: `none`, `mark`, or
`remove`. Paired reads are name-sorted, passed through `fixmate -m`, restored to
coordinate order and marked. Single-end input is marked directly in coordinate
order. Removal is performed only after duplicate metrics have been measured.

