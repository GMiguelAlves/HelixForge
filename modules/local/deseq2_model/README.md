# DESEQ2_MODEL

Fits one model per test variable with the exact legacy filter, factor ordering,
design construction, and default `DESeq()` Wald behavior. Contrasts are not
calculated here, which lets unrelated contrasts reuse the fitted model.
